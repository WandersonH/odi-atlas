"""Debate do 2º turno no YouTube: todos os vídeos publicados sobre o debate e os comentários dos mais vistos.

YouTube Data API v3 (chave YOUTUBE_API_KEY, grátis dentro da cota diária):
  1. search.list — consultas sobre o debate publicadas desde 18/10 12h UTC (manhã do dia do debate), por número de
     visualizações, até 3 páginas de 50 por consulta; mais a busca "debate" nos canais das campanhas (cota: 100 por página);
  2. videos.list — números públicos de cada vídeo (visualizações, curtidas, comentários, duração, dados da live);
  3. commentThreads.list — nos vídeos mais vistos com comentários abertos: até 100 conversas por relevância e 100 pelas
     mais recentes (1 unidade por chamada).
Filtro: título/descrição citam "debate" e Lula, Flávio/Bolsonaro, Band ou "presidencial".

Público: data/debate/youtube_videos.json (metadados públicos dos vídeos e números). Privado (ODI_INTERNO_DIR):
debate/youtube_comentarios.csv.gz (texto e autor dos comentários — pessoas comuns, LGPD).
O chat ao vivo da transmissão NÃO é comentário: a API só lê o chat enquanto a live está no ar (liveChatMessages);
depois que termina, o "replay do chat" não é oferecido pela API. Isso fica registrado como lacuna.
"""
from __future__ import annotations

import csv
import gzip
import json
import os
import re
import sys
import urllib.error
import urllib.parse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from net import get_json, now_utc  # noqa: E402
from collect_comentarios_youtube import linhas_da_conversa  # noqa: E402
import build_conteudo as bc  # noqa: E402

API = "https://www.googleapis.com/youtube/v3"
DESDE = "2026-10-18T12:00:00Z"
CONSULTAS = ["debate Band Lula Flávio Bolsonaro", "debate presidencial Band", "debate Lula Flávio", "debate segundo turno Lula Flávio",
             "debate Lula x Flávio Bolsonaro íntegra", "debate Band melhores momentos"]
PAGINAS = 3
CANAIS_CAMPANHA = {"UCvO2BExvkAbGMsTGnEnI_Ng": "Lula", "UCZBfh4XM2gHxUdY7_Uov3WA": "Lula",
                   "UCl2HptoHv6PjZMQAwTdA--Q": "Flávio Bolsonaro", "UCYJ4looDPmrgIF1FbGDmuUg": "Flávio Bolsonaro"}
CONHECIDOS = ["Gqc1rQtzWUk", "S17iktRbpa0", "HMn0LIrfcws", "Omay_TlhdZM"]  # live da Band Jornalismo e os 3 blocos (BandNews FM)
TOP_COMENTARIOS = 40  # vídeos mais vistos que têm os comentários lidos
CAMPOS = ["comment_id", "parent_id", "tipo", "video_id", "candidate_id", "channel_id", "ordem", "autor_canal", "autor_nome",
          "texto", "curtidas", "respostas", "publicado_em", "atualizado_em", "coletado_em"]
ERROS: list[str] = []


def chamar(rota: str, **q) -> dict:
    try:
        return get_json(f"{API}/{rota}?" + urllib.parse.urlencode(q), timeout=60)
    except urllib.error.HTTPError as e:
        corpo = ""
        try:
            corpo = e.read().decode("utf-8", "replace")
        except Exception:  # noqa: BLE001
            pass
        motivo = next((m for m in ("quotaExceeded", "commentsDisabled", "forbidden", "videoNotFound") if m in corpo), f"HTTP {e.code}")
        raise RuntimeError(motivo) from None
    except Exception as e:  # noqa: BLE001 — a mensagem pode ter a URL com a chave
        raise RuntimeError(type(e).__name__) from None


def dur_s(iso: str | None) -> int | None:
    m = re.fullmatch(r"P(?:(\d+)D)?T?(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?", iso or "")
    if not m:
        return None
    d, h, mi, s = (int(x or 0) for x in m.groups())
    return d * 86400 + h * 3600 + mi * 60 + s


def sobre_o_debate(titulo: str, descricao: str) -> bool:
    t = bc.norm(f"{titulo} {descricao[:400]}")
    return "debate" in t and any(k in t for k in ("lula", "flavio", "bolsonaro", "band", "presidencia"))


def tipo_de(v: dict) -> str:
    if v.get("live_inicio"):
        return "transmissão ao vivo"
    d = v.get("duracao_s") or 0
    if d >= 40 * 60:
        return "íntegra ou longo (40 min ou mais)"
    if d > 180:
        return "corte (3 a 40 min)"
    return "curto (até 3 min)"


def buscar(key: str) -> dict[str, str]:
    """{video_id: consulta que achou}."""
    achados = {v: "indicado" for v in CONHECIDOS}
    pedidos = [({"q": q}, q) for q in CONSULTAS] + [({"q": "debate", "channelId": c}, f"canal {n}") for c, n in CANAIS_CAMPANHA.items()]
    for extra, rotulo in pedidos:
        token = None
        for _ in range(PAGINAS if "channelId" not in extra else 1):
            q = {"part": "snippet", "type": "video", "maxResults": 50, "order": "viewCount", "publishedAfter": DESDE,
                 "regionCode": "BR", "relevanceLanguage": "pt", "key": key, **extra}
            if token:
                q["pageToken"] = token
            try:
                d = chamar("search", **q)
            except RuntimeError as e:
                ERROS.append(f"busca '{rotulo}': {e}")
                break
            for it in d.get("items", []):
                achados.setdefault(it["id"]["videoId"], rotulo)
            token = d.get("nextPageToken")
            if not token:
                break
    return achados


def detalhes(key: str, ids: list[str]) -> list[dict]:
    out = []
    for i in range(0, len(ids), 50):
        try:
            d = chamar("videos", part="snippet,statistics,contentDetails,liveStreamingDetails", id=",".join(ids[i:i + 50]), key=key)
        except RuntimeError as e:
            ERROS.append(f"videos.list: {e}")
            continue
        for it in d.get("items", []):
            sn, st, ld = it["snippet"], it.get("statistics", {}), it.get("liveStreamingDetails") or {}
            n = lambda k: int(st[k]) if str(st.get(k, "")).isdigit() else None  # noqa: E731
            out.append({"id": it["id"], "titulo": sn.get("title"), "canal": sn.get("channelTitle"), "canal_id": sn.get("channelId"),
                        "publicado_em": sn.get("publishedAt"), "duracao_s": dur_s((it.get("contentDetails") or {}).get("duration")),
                        "visualizacoes": n("viewCount"), "curtidas": n("likeCount"), "comentarios": n("commentCount"),
                        "comentarios_abertos": "commentCount" in st, "live_inicio": ld.get("actualStartTime"), "live_fim": ld.get("actualEndTime"),
                        "pico_simultaneo": int(ld["concurrentViewers"]) if str(ld.get("concurrentViewers", "")).isdigit() else None,
                        "chat_ativo": bool(ld.get("activeLiveChatId")), "descricao": (sn.get("description") or "")[:400]})
    return out


def comentarios(key: str, vids: list[dict], agora: str) -> tuple[list[dict], dict]:
    rows, status = [], {}
    for v in vids:
        meta = {"video_id": v["id"], "candidate_id": "", "channel_id": v["canal_id"]}
        lidos = 0
        for ordem in ("relevance", "time"):
            try:
                d = chamar("commentThreads", part="snippet,replies", videoId=v["id"], maxResults=100, order=ordem, textFormat="plainText", key=key)
            except RuntimeError as e:
                status[v["id"]] = str(e)
                break
            novos = [l for it in d.get("items", []) for l in linhas_da_conversa(it, meta, ordem, agora)]
            rows += novos
            lidos += len(novos)
        status.setdefault(v["id"], f"{lidos} lidos")
    por = {}
    for r in rows:  # um registro por comentário
        por[r["comment_id"]] = {**r, "ordem": "|".join(sorted(set((por.get(r["comment_id"]) or {}).get("ordem", "").split("|") + [r["ordem"]]) - {""}))}
    return list(por.values()), status


def main(argv=None) -> int:
    key = os.environ.get("YOUTUBE_API_KEY", "").strip()
    if not key:
        print("⛔ falta YOUTUBE_API_KEY")
        return 1
    agora = now_utc()
    achados = buscar(key)
    vids = [v for v in detalhes(key, list(achados)) if v["id"] in CONHECIDOS or sobre_o_debate(v["titulo"] or "", v["descricao"])]
    for v in vids:
        v["tipo"] = tipo_de(v)
        v["achado_por"] = achados.get(v["id"])
        v["campanha"] = CANAIS_CAMPANHA.get(v["canal_id"])
    vids.sort(key=lambda v: v["visualizacoes"] or 0, reverse=True)
    alvo = [v for v in vids if (v["comentarios"] or 0) > 0][:TOP_COMENTARIOS]
    rows, status = comentarios(key, alvo, agora)
    for v in vids:
        v["comentarios_lidos"] = sum(1 for r in rows if r["video_id"] == v["id"])
        v["leitura_comentarios"] = status.get(v["id"])
        v.pop("descricao", None)
    interno = os.environ.get("ODI_INTERNO_DIR")
    destino = "nenhum (sem ODI_INTERNO_DIR: comentários descartados)"
    if interno and rows:
        p = Path(interno) / "debate/youtube_comentarios.csv.gz"
        p.parent.mkdir(parents=True, exist_ok=True)
        with gzip.open(p, "wt", encoding="utf-8", newline="") as f:
            w = csv.DictWriter(f, fieldnames=CAMPOS, delimiter=";")
            w.writeheader()
            w.writerows(rows)
        destino = "privado: debate/youtube_comentarios.csv.gz"
    out = {"coletado_em_utc": agora, "desde_utc": DESDE, "consultas": CONSULTAS, "canais_campanha": CANAIS_CAMPANHA,
           "videos_com_comentarios_lidos": len(alvo), "comentarios_lidos": len(rows), "comentarios_destino": destino, "erros": ERROS,
           "chat_ao_vivo": "⛔ não coletado: a YouTube Data API só lê o chat enquanto a transmissão está no ar; o replay do chat não é oferecido depois",
           "videos": vids}
    Path("data/debate").mkdir(parents=True, exist_ok=True)
    Path("data/debate/youtube_videos.json").write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"vídeos sobre o debate: {len(vids)} de {len(achados)} achados · visualizações {sum(v['visualizacoes'] or 0 for v in vids):,} · "
          f"comentários lidos {len(rows)} em {len(alvo)} vídeos · erros {ERROS[:3]}")
    return 0 if vids else 1


if __name__ == "__main__":
    raise SystemExit(main())
