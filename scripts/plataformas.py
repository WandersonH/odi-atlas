"""Entrada única das análises (corpus/Bardin, CHD de Reinert, rede de coocorrência) para YouTube e TikTok.

Converte o acervo de cada plataforma para o mesmo formato de linha usado pelo YouTube (candidate_id, channel_id,
canal, video_id, publicado_em, titulo, descricao, duracao, visualizacoes, coletado_em, tags) e diz onde gravar
as saídas de cada plataforma. Assim as duas passam pelas MESMAS regras, sem cópia de código.
"""
from __future__ import annotations

import csv
import gzip
from pathlib import Path

INICIO_CAMPANHA = "2026-08-16"

CAMINHOS = {
    "youtube": {"populismo": "data/youtube/populismo.json",
                "corpus": "data/corpus/youtube_candidatos_iramuteq.txt",
                "segmentos": "data/corpus/youtube_candidatos_segmentos.csv",
                "chd": "data/corpus/chd_reinert.json",
                "amostra": "data/codificacao/amostra_populismo_v1.csv",
                "rede": "data/youtube/rede"},
    "tiktok": {"populismo": "data/tiktok/populismo.json",
               "corpus": "data/corpus/tiktok_candidatos_iramuteq.txt",
               "segmentos": "data/corpus/tiktok_candidatos_segmentos.csv",
               "chd": "data/corpus/chd_reinert_tiktok.json",
               "amostra": "data/codificacao/amostra_populismo_tiktok_v1.csv",
               "rede": "data/tiktok/rede"},
}


def args(argv) -> tuple[Path, str]:
    """[raiz] [--plataforma youtube|tiktok] → (raiz, plataforma). Sem argumentos: diretório atual, youtube."""
    argv = list(argv or [])
    plat = "youtube"
    if "--plataforma" in argv:
        i = argv.index("--plataforma")
        plat = argv[i + 1]
        del argv[i:i + 2]
    if plat not in CAMINHOS:
        raise SystemExit(f"plataforma desconhecida: {plat}")
    return (Path(argv[0]) if argv else Path(".")), plat


def videos(root: Path, plat: str) -> list[dict]:
    if plat == "youtube":
        return list(csv.DictReader(gzip.open(root / "data/youtube/videos_latest.csv.gz", "rt", encoding="utf-8"), delimiter=";"))
    out = []
    for r in csv.DictReader(gzip.open(root / "data/tiktok/videos.csv.gz", "rt", encoding="utf-8"), delimiter=";"):
        if r["publicado_em"] < INICIO_CAMPANHA:
            continue
        out.append({"candidate_id": r["candidate_id"], "candidate_name": r["candidate_name"], "channel_id": r["perfil"],
                    "canal": r["perfil"], "video_id": r["video_id"], "publicado_em": r["publicado_em"], "titulo": "",
                    "descricao": r["legenda"], "duracao": f"PT{r['duracao_s']}S" if r.get("duracao_s") else "",
                    "visualizacoes": r["visualizacoes"], "curtidas": r["curtidas"], "comentarios": r["comentarios"],
                    "coletado_em": r["ultima_coleta"], "tags": ""})
    return out


def caminho(root: Path, plat: str, chave: str) -> Path:
    p = root / CAMINHOS[plat][chave]
    p.parent.mkdir(parents=True, exist_ok=True)
    return p
