#!/usr/bin/env python3
"""Comentários dos vídeos de YouTube das campanhas (Lula e Flávio) — YouTube Data API v3, commentThreads.list.

PRIVACIDADE (LGPD): comentários são de pessoas comuns. O texto, o nome e o canal de quem comentou NUNCA vão para o
repositório público. Destino do arquivo bruto:
  - ODI_INTERNO_DIR definido (checkout do repositório privado odi-atlas-interno) → <dir>/youtube/comentarios/;
  - senão, pasta temporária da execução (RUNNER_TEMP ou /tmp), apagada ao fim do run.
No público fica só o manifesto (contagens, cota, erros) em data/youtube/comentarios/manifesto_latest.json.

Para cada vídeo das campanhas publicado desde 20/07/2026 (pré-campanha) e com comentários: até 100 conversas por ordem de
RELEVÂNCIA (a do YouTube) e até 100 pelas MAIS RECENTES, com as respostas que vêm junto (a API devolve até 5 por
conversa). 1 unidade de cota por chamada; teto em data/config/comentarios_youtube.json.
Chave SOMENTE pela variável de ambiente YOUTUBE_API_KEY; erros não imprimem URL (a URL contém a chave).
"""
from __future__ import annotations

import csv
import datetime as dt
import gzip
import json
import os
import sys
import tempfile
import urllib.error
import urllib.parse
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from net import get_json, now_utc  # noqa: E402

BASE = "https://www.googleapis.com/youtube/v3/commentThreads"
CAMPOS = ["comment_id", "parent_id", "tipo", "video_id", "candidate_id", "channel_id", "ordem", "autor_canal", "autor_nome",
          "texto", "curtidas", "respostas", "publicado_em", "atualizado_em", "coletado_em"]


def destino(plat: str = "youtube") -> tuple[Path, str]:
    d = os.environ.get("ODI_INTERNO_DIR")
    if d:
        return Path(d) / plat / "comentarios", "interno"
    return Path(os.environ.get("RUNNER_TEMP") or tempfile.gettempdir()) / f"odi_comentarios_{plat}", "efemero"


def plataforma(argv) -> tuple[str, list]:
    """--plataforma youtube|kwai (padrão youtube): as análises de comentários valem para as duas, com as mesmas regras."""
    argv = list(argv or [])
    plat = "youtube"
    if "--plataforma" in argv:
        i = argv.index("--plataforma")
        plat = argv[i + 1]
        del argv[i:i + 2]
    if plat not in ("youtube", "kwai", "facebook", "x"):  # x: respostas do X (x/respostas no repositório privado)
        raise SystemExit(f"plataforma desconhecida: {plat}")
    return plat, argv


def linhas_da_conversa(item: dict, video: dict, ordem: str, agora: str) -> list[dict]:
    sn = item["snippet"]
    top = sn["topLevelComment"]
    out = []
    for c, tipo, pai in [(top, "comentario", "")] + [(r, "resposta", top["id"]) for r in (item.get("replies") or {}).get("comments", [])]:
        s = c["snippet"]
        out.append({"comment_id": c["id"], "parent_id": pai, "tipo": tipo, "video_id": video["video_id"],
                    "candidate_id": video["candidate_id"], "channel_id": video["channel_id"], "ordem": ordem,
                    "autor_canal": (s.get("authorChannelId") or {}).get("value", ""), "autor_nome": s.get("authorDisplayName", ""),
                    "texto": (s.get("textOriginal") or s.get("textDisplay") or "").replace("\r", " "),
                    "curtidas": s.get("likeCount", 0), "respostas": sn.get("totalReplyCount", 0) if tipo == "comentario" else "",
                    "publicado_em": s.get("publishedAt", ""), "atualizado_em": s.get("updatedAt", ""), "coletado_em": agora})
    return out


def baixar(key: str, video: dict, ordem: str, agora: str) -> tuple[list[dict], str | None]:
    q = urllib.parse.urlencode({"part": "snippet,replies", "videoId": video["video_id"], "maxResults": 100, "order": ordem,
                                "textFormat": "plainText", "key": key})
    try:
        d = get_json(f"{BASE}?{q}", timeout=60)
    except urllib.error.HTTPError as e:
        corpo = ""
        try:
            corpo = e.read().decode("utf-8", "replace")
        except Exception:  # noqa: BLE001
            pass
        motivo = "commentsDisabled" if "commentsDisabled" in corpo else ("videoNotFound" if e.code == 404 else
                 "quotaExceeded" if "quotaExceeded" in corpo else f"HTTP {e.code}")
        return [], motivo
    except Exception as e:  # noqa: BLE001 — a mensagem pode conter a URL com a chave
        return [], type(e).__name__
    return [l for it in d.get("items", []) for l in linhas_da_conversa(it, video, ordem, agora)], None


def alvos(root: Path, cfg: dict) -> list[dict]:
    temas = json.loads((root / "data/config/temas_youtube.json").read_text(encoding="utf-8"))
    ids = set(temas["candidatos"])
    rows = csv.DictReader(gzip.open(root / "data/youtube/videos_latest.csv.gz", "rt", encoding="utf-8"), delimiter=";")
    vids = [r for r in rows if r["candidate_id"] in ids and r["publicado_em"] >= cfg["desde"]
            and str(r["comentarios"]).isdigit() and int(r["comentarios"]) > 0]
    return sorted(vids, key=lambda r: r["publicado_em"], reverse=True)  # mais novos primeiro (se a cota acabar)


def mesclar(antigos: list[dict], novos: list[dict]) -> list[dict]:
    """Um registro por comment_id; a coleta mais nova atualiza curtidas/texto editado. 'ordem' acumula as origens."""
    por = {r["comment_id"]: r for r in antigos}
    for r in novos:
        a = por.get(r["comment_id"])
        if a:
            ordens = sorted(set(a["ordem"].split("|")) | {r["ordem"]})
            r = {**r, "ordem": "|".join(ordens)}
        por[r["comment_id"]] = r
    return sorted(por.values(), key=lambda r: (r["candidate_id"], r["video_id"], r["publicado_em"], r["comment_id"]))


def main(argv=None) -> int:
    root = Path(argv[0]) if argv else Path(".")
    cfg = json.loads((root / "data/config/comentarios_youtube.json").read_text(encoding="utf-8"))
    key = os.environ.get("YOUTUBE_API_KEY")
    pub = root / "data/youtube/comentarios"
    pub.mkdir(parents=True, exist_ok=True)
    dest, modo = destino()
    man = {"schema_version": 1, "stage": "comentarios-youtube", "run_started_utc": now_utc(), "modo": modo,
           "fonte": "YouTube Data API v3 · commentThreads.list (ordens: relevance e time)", "blocked": [], "erros": {}}
    if not key:
        man["blocked"].append("YOUTUBE_API_KEY ausente")
        (pub / "manifesto_latest.json").write_text(json.dumps(man, ensure_ascii=False, indent=1), encoding="utf-8")
        print("⛔ YOUTUBE_API_KEY ausente")
        return 1
    vids = alvos(root, cfg)
    agora = now_utc()
    tarefas = [(v, o) for v in vids for o in cfg["ordens"]][: cfg["cota_maxima"]]
    novos, erros = [], {}
    with ThreadPoolExecutor(max_workers=cfg.get("paralelo", 6)) as ex:
        for (v, o), (linhas, err) in zip(tarefas, ex.map(lambda t: baixar(key, t[0], t[1], agora), tarefas)):
            novos += linhas
            if err:
                erros[err] = erros.get(err, 0) + 1
    dest.mkdir(parents=True, exist_ok=True)
    acum = dest / "comentarios.csv.gz"
    antigos = list(csv.DictReader(gzip.open(acum, "rt", encoding="utf-8"), delimiter=";")) if acum.exists() else []
    todos = mesclar(antigos, novos)
    with gzip.open(acum, "wt", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, CAMPOS, delimiter=";", lineterminator="\n")
        w.writeheader()
        w.writerows(todos)
    por_cand = {}
    for r in todos:
        c = por_cand.setdefault(r["candidate_id"], {"comentarios": 0, "respostas": 0, "videos": set()})
        c["comentarios" if r["tipo"] == "comentario" else "respostas"] += 1
        c["videos"].add(r["video_id"])
    man.update({"videos_alvo": len(vids), "chamadas": len(tarefas), "cota_usada": len(tarefas),
                "cortado_pela_cota": len(tarefas) < len(vids) * len(cfg["ordens"]),
                "registros_desta_coleta": len(novos), "registros_acumulados": len(todos), "erros": erros,
                "por_candidato": {k: {"comentarios": v["comentarios"], "respostas": v["respostas"], "videos": len(v["videos"])}
                                  for k, v in por_cand.items()},
                "arquivo_bruto": "repositório privado odi-atlas-interno" if modo == "interno" else "temporário (descartado ao fim do run)",
                "status": "ok" if novos else "⛔ nenhum comentário lido"})
    if erros.get("quotaExceeded"):
        man["blocked"].append(f"cota diária da API esgotada em {erros['quotaExceeded']} chamadas")
    (pub / "manifesto_latest.json").write_text(json.dumps(man, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"comentários [{modo}]: {len(vids)} vídeos, {len(tarefas)} chamadas, {len(novos)} registros nesta coleta, "
          f"{len(todos)} acumulados; erros {erros}")
    print(f"BRUTO={acum}")
    return 0 if novos else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
