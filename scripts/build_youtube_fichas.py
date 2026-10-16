#!/usr/bin/env python3
"""Fichas de YouTube (páginas Panorama, Quem acompanha e Eleitorado e território) pela YouTube Data API v3 — fonte principal de todo indicador de YouTube.

O Modash vira adendo: só a composição estimada da audiência (gênero, idade, país), que a API pública não fornece
(dados demográficos só existem no YouTube Analytics, para o dono do canal).

Perfis: data/config/youtube_fichas.json (id da ficha → @handle).
Para cada canal: channels.list (inscritos, total de vídeos e visualizações) + vídeos dos uploads com estatísticas.

Indicadores, sobre os vídeos publicados na janela (padrão: 30 dias, sem as últimas 48 h, que ainda estão acumulando
visualizações):
  - visualizações, curtidas e comentários médios (e medianas);
  - engajamento = (curtidas + comentários) ÷ visualizações, somados na janela, em %;
  - o mesmo separado por duração: curtos (≤ limite_curto_segundos, padrão 180 s, aproximação de Shorts — a API não
    marca o formato) e longos. Transmissões agendadas (duração 0) ficam de fora.
Também guarda os vídeos desde 16/08/2026 (campanha), para referência.

Chave SOMENTE pela variável de ambiente YOUTUBE_API_KEY. Erros não imprimem URL (a URL contém a chave).
Saída: data/youtube/fichas.json e data/youtube/fichas_historico.csv (uma linha por data, perfil e indicador).
"""
from __future__ import annotations

import csv
import datetime as dt
import json
import os
import re
import statistics
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from collect_youtube import query, videos_do_canal  # noqa: E402
from net import now_utc  # noqa: E402

CAMPANHA = "2026-08-16"
METRICAS = ["inscritos", "visualizacoes_canal", "videos_canal", "videos_janela", "media_visualizacoes", "media_curtidas",
            "media_comentarios", "engajamento", "curtos_media_visualizacoes", "longos_media_visualizacoes"]


def segundos(iso: str) -> int | None:
    m = re.fullmatch(r"P(?:(\d+)D)?T?(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?", iso or "")
    if not m or not iso:
        return None
    d, h, mi, s = (int(x or 0) for x in m.groups())
    return d * 86400 + h * 3600 + mi * 60 + s


def _n(v):
    return int(v) if str(v or "").isdigit() else None


def resumo(videos: list[dict]) -> dict:
    """Médias, medianas e engajamento de um conjunto de vídeos (campos visualizacoes/curtidas/comentarios)."""
    vs = [v for v in videos if _n(v["visualizacoes"]) is not None]
    if not vs:
        return {"videos": 0}
    views = [_n(v["visualizacoes"]) for v in vs]
    likes = [_n(v["curtidas"]) for v in vs if _n(v["curtidas"]) is not None]
    coms = [_n(v["comentarios"]) for v in vs if _n(v["comentarios"]) is not None]
    # engajamento só com vídeos que têm as três contagens públicas
    completos = [v for v in vs if _n(v["curtidas"]) is not None and _n(v["comentarios"]) is not None]
    vw = sum(_n(v["visualizacoes"]) for v in completos)
    eng = (sum(_n(v["curtidas"]) + _n(v["comentarios"]) for v in completos) / vw * 100) if vw else None
    return {"videos": len(vs), "media_visualizacoes": round(statistics.mean(views)),
            "mediana_visualizacoes": round(statistics.median(views)),
            "media_curtidas": round(statistics.mean(likes)) if likes else None,
            "media_comentarios": round(statistics.mean(coms)) if coms else None,
            "engajamento": round(eng, 2) if eng is not None else None,
            "curtidas_ocultas": len(vs) - len(likes), "comentarios_desativados": len(vs) - len(coms)}


def ficha(videos: list[dict], hoje: dt.date, janela_dias: int, carencia_h: int, limite_curto: int) -> dict:
    fim = dt.datetime.combine(hoje, dt.time(), dt.timezone.utc) - dt.timedelta(hours=carencia_h)
    ini = fim - dt.timedelta(days=janela_dias)
    validos = [v for v in videos if (segundos(v["duracao"]) or 0) > 0]
    def data(v):  # noqa: E306
        return dt.datetime.fromisoformat(v["publicado_em"].replace("Z", "+00:00"))
    jan = [v for v in validos if ini <= data(v) < fim]
    curtos = [v for v in jan if segundos(v["duracao"]) <= limite_curto]
    longos = [v for v in jan if segundos(v["duracao"]) > limite_curto]
    camp = [v for v in validos if v["publicado_em"][:10] >= CAMPANHA]
    return {"janela": {"de": ini.strftime("%Y-%m-%dT%H:%MZ"), "ate": fim.strftime("%Y-%m-%dT%H:%MZ"), **resumo(jan)},
            "curtos": resumo(curtos), "longos": resumo(longos), "campanha": resumo(camp)}


def main(argv=None) -> int:
    root = Path(argv[0]) if argv else Path(".")
    cfg = json.loads((root / "data/config/youtube_fichas.json").read_text(encoding="utf-8"))
    key = os.environ.get("YOUTUBE_API_KEY")
    if not key:
        print("⛔ YOUTUBE_API_KEY ausente: fichas do YouTube não atualizadas")
        return 1
    hoje = dt.datetime.now(dt.timezone.utc).date()
    desde = min(CAMPANHA, (hoje - dt.timedelta(days=cfg["janela_dias"] + 3)).isoformat()) + "T00:00:00Z"
    out = {"schema_version": 1, "gerado_em_utc": now_utc(), "data": hoje.isoformat(),
           "fonte": "YouTube Data API v3 · channels.list + playlistItems.list + videos.list",
           "metodo": cfg["nota"], "janela_dias": cfg["janela_dias"], "carencia_horas": cfg["carencia_horas"],
           "limite_curto_segundos": cfg["limite_curto_segundos"], "perfis": {}, "erros": {}, "cota_usada": 0}
    for pid, handle in cfg["perfis"].items():
        try:
            itens = query(key, "handle", handle)
            out["cota_usada"] += 1
            if not itens:
                out["erros"][pid] = f"{handle}: canal não encontrado pela API"
                continue
            c = itens[0]
            st = c.get("statistics", {})
            vids, cota = videos_do_canal(key, c["contentDetails"]["relatedPlaylists"]["uploads"], desde)
            out["cota_usada"] += cota
        except Exception as e:  # noqa: BLE001 — a mensagem pode conter a URL com a chave
            out["erros"][pid] = f"{handle}: {type(e).__name__} {getattr(e, 'code', '')}".strip()
            continue
        f = ficha(vids, hoje, cfg["janela_dias"], cfg["carencia_horas"], cfg["limite_curto_segundos"])
        out["perfis"][pid] = {"handle": handle, "channel_id": c["id"], "titulo": c.get("snippet", {}).get("title"),
                              "url": f"https://www.youtube.com/channel/{c['id']}",
                              "inscritos": None if st.get("hiddenSubscriberCount") else _n(st.get("subscriberCount")),
                              "inscritos_ocultos": bool(st.get("hiddenSubscriberCount")),
                              "videos_canal": _n(st.get("videoCount")), "visualizacoes_canal": _n(st.get("viewCount")), **f}
        j = f["janela"]
        print(f"{pid}: {c.get('snippet', {}).get('title')} · inscritos {out['perfis'][pid]['inscritos']} · "
              f"{j['videos']} vídeos na janela · média {j.get('media_visualizacoes')} visualizações · engaj. {j.get('engajamento')}%")
    for pid, msg in out["erros"].items():
        print(f"⛔ {pid}: {msg}")
    d = root / "data/youtube"
    d.mkdir(parents=True, exist_ok=True)
    (d / "fichas.json").write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    hist = d / "fichas_historico.csv"
    linhas = []
    if hist.exists():
        linhas = [r for r in csv.DictReader(open(hist, encoding="utf-8"), delimiter=";") if r["data"] != out["data"]]
    for pid, p in out["perfis"].items():
        val = {"inscritos": p["inscritos"], "visualizacoes_canal": p["visualizacoes_canal"], "videos_canal": p["videos_canal"],
               "videos_janela": p["janela"]["videos"], "media_visualizacoes": p["janela"].get("media_visualizacoes"),
               "media_curtidas": p["janela"].get("media_curtidas"), "media_comentarios": p["janela"].get("media_comentarios"),
               "engajamento": p["janela"].get("engajamento"),
               "curtos_media_visualizacoes": p["curtos"].get("media_visualizacoes"),
               "longos_media_visualizacoes": p["longos"].get("media_visualizacoes")}
        linhas += [{"data": out["data"], "profile_id": pid, "metric": k, "value": v} for k, v in val.items() if v is not None]
    linhas.sort(key=lambda r: (r["data"], r["profile_id"], METRICAS.index(r["metric"])))
    with open(hist, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, ["data", "profile_id", "metric", "value"], delimiter=";", lineterminator="\n")
        w.writeheader()
        w.writerows(linhas)
    return 0 if out["perfis"] else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
