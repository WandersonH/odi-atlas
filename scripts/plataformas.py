"""Entrada única das análises (corpus/Bardin, CHD de Reinert, rede de coocorrência) para YouTube, TikTok e Kwai.

Converte o acervo de cada plataforma para o mesmo formato de linha usado pelo YouTube (candidate_id, channel_id,
canal, video_id, publicado_em, titulo, descricao, duracao, visualizacoes, coletado_em, tags) e diz onde gravar
as saídas de cada plataforma. Assim as duas passam pelas MESMAS regras, sem cópia de código.
"""
from __future__ import annotations

import csv
import gzip
from pathlib import Path

INICIO_CAMPANHA = "2026-07-20"  # análises desde a pré-campanha (fases: pré, 1º turno, 2º turno)

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
    "kwai": {"populismo": "data/kwai/populismo.json",
             "corpus": "data/corpus/kwai_candidatos_iramuteq.txt",
             "segmentos": "data/corpus/kwai_candidatos_segmentos.csv",
             "chd": "data/corpus/chd_reinert_kwai.json",
             "amostra": "data/codificacao/amostra_populismo_kwai_v1.csv",
             "rede": "data/kwai/rede"},
}
CAMINHOS["facebook"] = {"populismo": "data/facebook/populismo.json",
                         "corpus": "data/corpus/facebook_candidatos_iramuteq.txt",
                         "segmentos": "data/corpus/facebook_candidatos_segmentos.csv",
                         "chd": "data/corpus/chd_reinert_facebook.json",
                         "amostra": "data/codificacao/amostra_populismo_facebook_v1.csv",
                         "rede": "data/facebook/rede"}
CAMINHOS["x"] = {k: v.replace("facebook", "x") for k, v in CAMINHOS["facebook"].items()}
# Kwai: acervo histórico completo (pedido de 17/10/2026), sem corte de data; TikTok: desde o início da campanha
INICIO_POR_PLATAFORMA = {"tiktok": INICIO_CAMPANHA, "kwai": "", "facebook": INICIO_CAMPANHA, "x": INICIO_CAMPANHA}


def args(argv) -> tuple[Path, str]:
    """[raiz] [--plataforma youtube|tiktok|kwai] → (raiz, plataforma). Sem argumentos: diretório atual, youtube."""
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
    inicio = INICIO_POR_PLATAFORMA[plat]
    for r in csv.DictReader(gzip.open(root / f"data/{plat}/videos.csv.gz", "rt", encoding="utf-8"), delimiter=";"):
        if r["publicado_em"] < inicio:
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
