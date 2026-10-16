#!/usr/bin/env python3
"""Rede de contas do TikTok que publicam sobre Lula (vermelho) ou Flávio Bolsonaro (verde), a partir das hashtags.

Mesmas regras e mesmo formato da rede de influenciadores do YouTube (build_rede_influenciadores.gerar): nível 1 = falou
do candidato na legenda; nível 2 = pediu voto. Só contas com 10 mil+ seguidores (data/tiktok/hashtags/videos.csv.gz já
vem filtrado); excluídos os perfis de campanha declarados ao TSE.
Saída: data/tiktok/hashtags/rede.json, rede.gexf, rede_nos.csv, rede_arestas.csv, videos_validos.csv
"""
from __future__ import annotations

import csv
import gzip
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from build_rede_influenciadores import NIVEIS, gerar  # noqa: E402
from collect_influenciadores import avaliar, compilar  # noqa: E402


def main(argv=None) -> int:
    root = Path(argv[0]) if argv else Path(".")
    cfg = json.loads((root / "data/config/influenciadores_youtube.json").read_text(encoding="utf-8"))
    th = json.loads((root / "data/config/tiktok_hashtags.json").read_text(encoding="utf-8"))
    cfg = {**cfg, "min_inscritos": th["min_seguidores_publico"]}
    d = root / "data/tiktok/hashtags"
    src = d / "videos.csv.gz"
    if not src.exists():
        print("⛔ sem coleta por hashtag (data/tiktok/hashtags/videos.csv.gz)")
        return 1
    rows = list(csv.DictReader(gzip.open(src, "rt", encoding="utf-8"), delimiter=";"))
    campanha = {r["perfil"].lower() for r in csv.DictReader(gzip.open(root / "data/tiktok/videos.csv.gz", "rt", encoding="utf-8"), delimiter=";")}
    men, excl = compilar(cfg)
    videos, canais = [], {}
    for r in rows:
        leg = r["legenda"] + " " + " ".join("#" + t for t in r["hashtags"].split("|") if t)
        v = {"video_id": r["video_id"], "channel_id": r["conta"], "canal": r["nome_conta"] or r["conta"], "publicado_em": r["publicado_em"],
             "titulo": leg[:150], "descricao": leg[150:], "categoria": "", "visualizacoes": r["visualizacoes"] or 0,
             "ultima_coleta": r["coletado_em"], "url": r["url"]}
        v.update(avaliar(v, men, excl, {}))
        if r["conta"].lower() in campanha:
            v["excluido"] = "perfil de campanha (declarado ao TSE)"
        videos.append(v)
        canais[r["conta"]] = {"canal": r["nome_conta"] or r["conta"], "handle": "@" + r["conta"], "inscritos": r["seguidores"]}
    metodo = (f"{th['nota']} Hashtags: " + "; ".join(f"{cfg['candidatos'][cid]['nome']}: " + ", ".join("#" + t for t in ts)
                                                  for cid, ts in th["hashtags"].items()) +
              f". Desde {th['desde']}, acumulado a cada coleta. O lado de cada conta vem do que ela escreve (nome, @, hashtag, número), "
              "não da hashtag pela qual o vídeo foi encontrado. " + NIVEIS.replace("canal", "conta"))
    return gerar(videos, canais, cfg, d, metodo, lambda c: f"https://www.tiktok.com/@{c}", lambda v: v["url"])


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
