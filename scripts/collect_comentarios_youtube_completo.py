#!/usr/bin/env python3
"""Leitura COMPLETA dos comentários do YouTube das campanhas, em etapas diárias dentro da cota gratuita da API.

Pedido do responsável (23/10/2026, 18h00): "por que não lemos tudo, já que o YouTube nos dá maior liberdade para extrair?".
A coleta diária (collect_comentarios_youtube.py) lê só dois recortes por vídeo: 100 conversas por relevância e 100 mais
recentes, com até 5 respostas cada. Este coletor percorre TODAS as páginas de cada vídeo e depois TODAS as respostas das
conversas com mais de 5, guardando onde parou (estado no repositório privado). Assim, a leitura completa avança um pouco
a cada dia sem esgotar a cota usada pelas outras coletas.

- Fase 1: commentThreads.list (order=time, 100 por página) até o fim de cada vídeo, do mais novo para o mais antigo.
- Fase 2: comments.list (parentId, 100 por página) para conversas com mais respostas do que as já lidas.
- 1 unidade de cota por chamada; teto diário em data/config/comentarios_youtube.json → completo.cota_dia.
- Para no primeiro quotaExceeded. Mesmas regras de privacidade: texto e autor só no repositório privado.
Saída pública: data/youtube/comentarios/manifesto_completo.json (progresso e contagens, sem texto).
"""
from __future__ import annotations

import csv
import gzip
import json
import os
import sys
import threading
import urllib.error
import urllib.parse
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from collect_comentarios_youtube import CAMPOS, alvos, destino, linhas_da_conversa, mesclar  # noqa: E402
from net import get_json, now_utc  # noqa: E402

API = "https://www.googleapis.com/youtube/v3/"


class Cota:
    def __init__(self, teto: int):
        self.teto, self.usada, self.esgotou, self.lock = teto, 0, False, threading.Lock()

    def pegar(self) -> bool:
        with self.lock:
            if self.esgotou or self.usada >= self.teto:
                return False
            self.usada += 1
            return True


def chamar(url: str) -> tuple[dict | None, str | None]:
    try:
        return get_json(url, timeout=60), None
    except urllib.error.HTTPError as e:
        corpo = ""
        try:
            corpo = e.read().decode("utf-8", "replace")
        except Exception:  # noqa: BLE001
            pass
        return None, ("quotaExceeded" if "quotaExceeded" in corpo else "commentsDisabled" if "commentsDisabled" in corpo
                      else "videoNotFound" if e.code == 404 else f"HTTP {e.code}")
    except Exception as e:  # noqa: BLE001 — a mensagem pode conter a URL com a chave
        return None, type(e).__name__


def linha_resposta(c: dict, pai: dict, agora: str) -> dict:
    s = c["snippet"]
    return {"comment_id": c["id"], "parent_id": pai["comment_id"], "tipo": "resposta", "video_id": pai["video_id"],
            "candidate_id": pai["candidate_id"], "channel_id": pai["channel_id"], "ordem": "completo",
            "autor_canal": (s.get("authorChannelId") or {}).get("value", ""), "autor_nome": s.get("authorDisplayName", ""),
            "texto": (s.get("textOriginal") or s.get("textDisplay") or "").replace("\r", " "), "curtidas": s.get("likeCount", 0),
            "respostas": "", "publicado_em": s.get("publishedAt", ""), "atualizado_em": s.get("updatedAt", ""), "coletado_em": agora}


def main(argv=None, chamar_api=None) -> int:
    root = Path(".")
    cfg = json.loads((root / "data/config/comentarios_youtube.json").read_text(encoding="utf-8"))
    teto = int(cfg.get("completo", {}).get("cota_dia", 3500))
    key = os.environ.get("YOUTUBE_API_KEY", "")
    pub = root / "data/youtube/comentarios"
    pub.mkdir(parents=True, exist_ok=True)
    dest, modo = destino()
    agora = now_utc()
    man = {"stage": "comentarios-youtube-completo", "run_started_utc": agora, "cota_dia": teto, "erros": {}}

    def fim(status: str, code: int) -> int:
        man["status"] = status
        (pub / "manifesto_completo.json").write_text(json.dumps(man, ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"comentários YouTube (completo): {status}")
        return code

    if modo != "interno":
        return fim("⛔ sem repositório privado: a leitura completa precisa guardar o estado e o texto no privado", 1)
    if not (key or chamar_api):
        return fim("⛔ YOUTUBE_API_KEY ausente", 1)
    chamar_api = chamar_api or chamar
    dest.mkdir(parents=True, exist_ok=True)
    arq_estado = dest / "estado_completo.json"
    est = json.loads(arq_estado.read_text(encoding="utf-8")) if arq_estado.exists() else {"threads": {}, "respostas": {}}
    acum = dest / "comentarios.csv.gz"
    antigos = list(csv.DictReader(gzip.open(acum, "rt", encoding="utf-8"), delimiter=";")) if acum.exists() else []
    vids = alvos(root, cfg)
    cota = Cota(teto)
    novos, lock = [], threading.Lock()

    def erro(e: str):
        with lock:
            man["erros"][e] = man["erros"].get(e, 0) + 1
        if e == "quotaExceeded":
            cota.esgotou = True

    def um_video(v: dict):
        st = est["threads"].setdefault(v["video_id"], {"token": None, "fim": False, "paginas": 0})
        while not st["fim"] and cota.pegar():
            q = {"part": "snippet,replies", "videoId": v["video_id"], "maxResults": 100, "order": "time", "textFormat": "plainText", "key": key}
            if st["token"]:
                q["pageToken"] = st["token"]
            d, e = chamar_api(API + "commentThreads?" + urllib.parse.urlencode(q))
            if e:
                erro(e)
                if e in ("commentsDisabled", "videoNotFound"):
                    st["fim"] = True
                return
            ls = [l for it in d.get("items", []) for l in linhas_da_conversa(it, v, "completo", agora)]
            with lock:
                novos.extend(ls)
            st["paginas"] += 1
            st["token"] = d.get("nextPageToken")
            st["fim"] = not st["token"]

    pend = [v for v in vids if not est["threads"].get(v["video_id"], {}).get("fim")]
    with ThreadPoolExecutor(max_workers=cfg.get("paralelo", 6)) as ex:
        list(ex.map(um_video, pend))
    fase1_ok = all(est["threads"].get(v["video_id"], {}).get("fim") for v in vids)

    if fase1_ok and not cota.esgotou:  # fase 2: respostas além das 5 que vêm com a conversa
        todos_ate_agora = mesclar(antigos, novos)
        lidas = {}
        for r in todos_ate_agora:
            if r["tipo"] == "resposta":
                lidas[r["parent_id"]] = lidas.get(r["parent_id"], 0) + 1
        pais = [r for r in todos_ate_agora if r["tipo"] == "comentario" and str(r.get("respostas") or "0").isdigit()
                and int(r["respostas"]) > lidas.get(r["comment_id"], 0) and not est["respostas"].get(r["comment_id"], {}).get("fim")]
        pais.sort(key=lambda r: -int(r["respostas"]))

        def um_pai(p: dict):
            st = est["respostas"].setdefault(p["comment_id"], {"token": None, "fim": False})
            while not st["fim"] and cota.pegar():
                q = {"part": "snippet", "parentId": p["comment_id"], "maxResults": 100, "textFormat": "plainText", "key": key}
                if st["token"]:
                    q["pageToken"] = st["token"]
                d, e = chamar_api(API + "comments?" + urllib.parse.urlencode(q))
                if e:
                    erro(e)
                    if e == "videoNotFound":
                        st["fim"] = True
                    return
                with lock:
                    novos.extend(linha_resposta(c, p, agora) for c in d.get("items", []))
                st["token"] = d.get("nextPageToken")
                st["fim"] = not st["token"]
        with ThreadPoolExecutor(max_workers=cfg.get("paralelo", 6)) as ex:
            list(ex.map(um_pai, pais))
        man["conversas_com_respostas_pendentes"] = sum(1 for p in pais if not est["respostas"].get(p["comment_id"], {}).get("fim"))

    todos = mesclar(antigos, novos)
    with gzip.open(acum, "wt", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, CAMPOS, delimiter=";", lineterminator="\n")
        w.writeheader()
        w.writerows(todos)
    arq_estado.write_text(json.dumps(est, ensure_ascii=False), encoding="utf-8")
    informados = sum(int(v["comentarios"]) for v in vids)
    feitos = sum(1 for v in vids if est["threads"].get(v["video_id"], {}).get("fim"))
    man.update(chamadas=cota.usada, cota_esgotada=cota.esgotou, registros_novos=len({r["comment_id"] for r in novos} - {r["comment_id"] for r in antigos}),
               registros_acumulados=len(todos), comentarios_informados_pelo_youtube=informados,
               videos_total=len(vids), videos_lidos_ate_o_fim=feitos, fase=("respostas" if fase1_ok else "conversas"),
               parcela_lida_pct=round(100 * len(todos) / informados, 1) if informados else None)
    print(f"{cota.usada} chamadas · {man['registros_novos']} novos · acervo {len(todos)} de {informados} informados "
          f"({man['parcela_lida_pct']}%) · vídeos completos {feitos}/{len(vids)} · erros {man['erros']}")
    return fim("ok" if cota.usada else "⛔ nenhuma chamada feita", 0 if cota.usada else 1)


if __name__ == "__main__":
    sys.exit(main())
