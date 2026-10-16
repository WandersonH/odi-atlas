#!/usr/bin/env python3
"""Comentários dos vídeos de TikTok das campanhas (Lula e Flávio) — endpoint público da web do TikTok, gratuito.

Usa https://www.tiktok.com/api/comment/list/ (o mesmo que a página do vídeo chama ao abrir os comentários, sem login).
Não é API oficial: pode bloquear ou mudar sem aviso. Por vídeo, até `por_video` comentários (páginas de 50, por
relevância, a ordem que o TikTok mostra), com a 1ª resposta que o TikTok devolve junto quando houver.

PRIVACIDADE (LGPD): o texto, o nome e o id de quem comentou vão SÓ para o repositório privado (ODI_INTERNO_DIR) ou para
uma pasta temporária apagada no fim do run. No público fica o manifesto (contagens, erros).
Saída: <privado>/tiktok/comentarios/comentarios.csv.gz (mesmas colunas da coleta do YouTube) e
       data/tiktok/comentarios/manifesto_latest.json

Uso: python scripts/collect_comentarios_tiktok.py [--teste N]   (--teste: só N vídeos, imprime o diagnóstico, não grava)
"""
from __future__ import annotations

import csv
import datetime as dt
import gzip
import json
import os
import sys
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from collect_comentarios_youtube import CAMPOS, mesclar  # noqa: E402
from net import now_utc  # noqa: E402

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
API = "https://www.tiktok.com/api/comment/list/"


def destino() -> tuple[Path, str]:
    d = os.environ.get("ODI_INTERNO_DIR")
    if d:
        return Path(d) / "tiktok/comentarios", "interno"
    return Path(os.environ.get("RUNNER_TEMP") or tempfile.gettempdir()) / "odi_comentarios_tiktok", "efemero"


def iso(ts) -> str:
    try:
        return dt.datetime.fromtimestamp(int(ts), dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    except (TypeError, ValueError):
        return ""


def linhas(c: dict, video: dict, agora: str, pai: str = "") -> list[dict]:
    u = c.get("user") or {}
    r = {"comment_id": str(c.get("cid", "")), "parent_id": pai, "tipo": "resposta" if pai else "comentario",
         "video_id": video["video_id"], "candidate_id": video["candidate_id"], "channel_id": video["perfil"],
         "ordem": "relevancia", "autor_canal": str(u.get("uid") or u.get("sec_uid") or u.get("unique_id") or ""),
         "autor_nome": u.get("nickname") or u.get("unique_id") or "", "texto": (c.get("text") or "").replace("\r", " "),
         "curtidas": c.get("digg_count", 0), "respostas": "" if pai else c.get("reply_comment_total", 0),
         "publicado_em": iso(c.get("create_time")), "atualizado_em": "", "coletado_em": agora}
    out = [r]
    for rc in (c.get("reply_comment") or []) if not pai else []:
        out += linhas(rc, video, agora, pai=r["comment_id"])
    return out


def pagina(video: dict, cursor: int, n: int = 50) -> dict:
    q = urllib.parse.urlencode({"aid": 1988, "app_language": "pt-BR", "app_name": "tiktok_web", "aweme_id": video["video_id"],
                                "count": n, "cursor": cursor, "current_region": "BR", "device_platform": "web_pc"})
    req = urllib.request.Request(f"{API}?{q}", headers={"User-Agent": UA, "Accept": "application/json, text/plain, */*",
                                                       "Accept-Language": "pt-BR,pt;q=0.9", "Referer": video["url"]})
    with urllib.request.urlopen(req, timeout=30) as resp:
        corpo = resp.read().decode("utf-8", "replace")
    return json.loads(corpo) if corpo.strip() else {"_vazio": True}


def baixar(video: dict, por_video: int, agora: str, pausa: float) -> tuple[list[dict], str | None, dict]:
    out, cursor, diag = [], 0, {}
    while len([r for r in out if r["tipo"] == "comentario"]) < por_video:
        try:
            d = pagina(video, cursor)
        except urllib.error.HTTPError as e:
            return out, f"HTTP {e.code}", diag
        except Exception as e:  # noqa: BLE001
            return out, type(e).__name__, diag
        if d.get("_vazio"):
            return out, "resposta vazia", diag
        diag = {"status_code": d.get("status_code"), "chaves": sorted(d)[:12], "total": d.get("total"), "has_more": d.get("has_more")}
        cs = d.get("comments") or []
        if d.get("status_code") not in (0, None) and not cs:
            return out, f"status_code {d.get('status_code')} {d.get('status_msg', '')}".strip(), diag
        for c in cs:
            out += linhas(c, video, agora)
        if not d.get("has_more") or not cs:
            break
        cursor = d.get("cursor", cursor + len(cs))
        time.sleep(pausa)
    return out, None, diag


def alvos(root: Path, cfg: dict) -> list[dict]:
    rows = csv.DictReader(gzip.open(root / "data/tiktok/videos.csv.gz", "rt", encoding="utf-8"), delimiter=";")
    vs = [r for r in rows if r["publicado_em"] >= cfg["desde"] and str(r["comentarios"]).isdigit() and int(r["comentarios"]) > 0]
    return sorted(vs, key=lambda r: r["publicado_em"], reverse=True)[: cfg["max_videos"]]


def main(argv=None) -> int:
    argv = argv or []
    root = Path(".")
    cfg = json.loads((root / "data/config/comentarios_tiktok.json").read_text(encoding="utf-8"))
    teste = int(argv[argv.index("--teste") + 1]) if "--teste" in argv else 0
    vids = alvos(root, cfg)
    if teste:  # um vídeo de cada candidato e os mais recentes
        por = {}
        for v in vids:
            por.setdefault(v["candidate_id"], v)
        vids = (list(por.values()) + [v for v in vids if v not in por.values()])[:teste]
    agora = now_utc()
    novos, erros, falhas_seguidas, lidos, diags = [], {}, 0, 0, []
    for v in vids:
        ls, err, dg = baixar(v, cfg["por_video"], agora, cfg["pausa_s"])
        novos += ls
        diags.append({"video": v["video_id"], "perfil": v["perfil"], "comentarios_no_tiktok": v["comentarios"], "lidos": len(ls), "erro": err, **dg})
        if err:
            erros[err] = erros.get(err, 0) + 1
            falhas_seguidas = falhas_seguidas + 1 if not ls else 0
        else:
            falhas_seguidas, lidos = 0, lidos + 1
        if falhas_seguidas >= cfg["parar_apos_falhas"]:
            erros["interrompido"] = f"{falhas_seguidas} vídeos seguidos sem comentários lidos"
            break
        time.sleep(cfg["pausa_s"])
    if teste:
        for d in diags:
            print(json.dumps(d, ensure_ascii=False))
        amostra = [{k: r[k] for k in ("tipo", "publicado_em", "curtidas", "respostas")} | {"tamanho_texto": len(r["texto"])} for r in novos[:5]]
        print("amostra (sem texto):", json.dumps(amostra, ensure_ascii=False))
        print(f"TESTE: {len(vids)} vídeos, {len(novos)} registros, erros {erros}")
        return 0 if novos else 1
    pub = root / "data/tiktok/comentarios"
    pub.mkdir(parents=True, exist_ok=True)
    dest, modo = destino()
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
    man = {"schema_version": 1, "stage": "comentarios-tiktok", "run_started_utc": agora, "modo": modo,
           "fonte": "endpoint público da web do TikTok (api/comment/list), sem login; não é API oficial",
           "videos_alvo": len(vids), "videos_lidos": lidos, "registros_desta_coleta": len(novos), "registros_acumulados": len(todos),
           "erros": erros, "por_candidato": {k: {"comentarios": v["comentarios"], "respostas": v["respostas"], "videos": len(v["videos"])}
                                             for k, v in por_cand.items()},
           "arquivo_bruto": "repositório privado odi-atlas-interno" if modo == "interno" else "temporário (descartado ao fim do run)",
           "status": "ok" if novos else "⛔ nenhum comentário lido"}
    (pub / "manifesto_latest.json").write_text(json.dumps(man, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"comentários TikTok [{modo}]: {len(vids)} vídeos, {lidos} lidos, {len(novos)} registros nesta coleta, {len(todos)} acumulados; erros {erros}")
    return 0 if novos else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
