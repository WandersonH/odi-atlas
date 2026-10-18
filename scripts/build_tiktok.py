#!/usr/bin/env python3
"""Caderno 02 — TikTok de Lula e Flávio Bolsonaro por tema, com as MESMAS regras do caderno 02 (YouTube).

Entrada: data/tiktok/videos.csv.gz (collect_tiktok.py), data/tiktok/manifesto_latest.json, data/config/temas_youtube.json
Saída:   data/tiktok/conteudo.json

Reaproveita de build_conteudo.py: dicionário de temas, remoção de trechos repetidos em 10+ vídeos do mesmo perfil,
nuvem de palavras, mapa de hashtags (sem pacote fixo: TikTok não tem campo de tags separado) e marcas
"cita o adversário" / "pede voto". Taxa de interação = (curtidas + comentários + compartilhamentos) ÷ visualizações
(métrica de interação por visualização, como nos relatórios Sensika/BFMI; não mede apoio).
"""
from __future__ import annotations

import csv
import datetime as dt
import gzip
import json
import re
import statistics
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import build_conteudo as bc  # noqa: E402


def num(v) -> int | None:
    return int(v) if str(v or "").strip().lstrip("-").isdigit() else None


def taxa(r: dict) -> float | None:
    v = num(r["visualizacoes"])
    if not v:
        return None
    return sum(num(r[k]) or 0 for k in ("curtidas", "comentarios", "compartilhamentos")) / v


def por_fase(vids: list[dict], fases: list[dict]) -> dict:
    """Vídeos, visualizações e interação mediana por fase (pré-campanha, 1º turno, 2º turno — data/config/trends.json)."""
    out = {}
    for f in fases:
        vs = [v for v in vids if f["de"] <= (v["publicado_em"] or "")[:10] <= f["ate"]]
        tx = [v["taxa_interacao"] for v in vs if v["taxa_interacao"] is not None]
        out[f["id"]] = {"rotulo": f["rotulo"], "de": f["de"], "ate": f["ate"], "videos": len(vs),
                        "visualizacoes": sum(v["visualizacoes"] or 0 for v in vs),
                        "taxa_interacao_mediana": round(statistics.median(tx), 4) if tx else None}
    return out


def main(argv=None) -> int:
    argv = list(argv or [])
    plat = "kwai" if "--kwai" in argv else "facebook" if "--facebook" in argv else "tiktok"  # Kwai e Facebook: mesmo formato de acervo e mesmas regras
    argv = [a for a in argv if a not in ("--kwai", "--facebook")]
    root = Path(argv[0]) if argv else Path(".")
    desde = "" if plat == "kwai" else "2026-07-20"  # TikTok e Facebook: desde a pré-campanha  # Kwai: acervo histórico completo, com a data de cada post
    cfg = json.loads((root / "data/config/temas_youtube.json").read_text(encoding="utf-8"))
    temas, cands = bc.compile_cfg(cfg)
    src = root / f"data/{plat}/videos.csv.gz"
    if not src.exists():
        print(f"⛔ sem acervo ({src})")
        return 1
    rows = list(csv.DictReader(gzip.open(src, "rt", encoding="utf-8"), delimiter=";"))
    man_p = root / f"data/{plat}/manifesto_latest.json"
    man = json.loads(man_p.read_text(encoding="utf-8")) if man_p.exists() else {}
    # adapta ao formato do YouTube: perfil = canal, legenda = descrição
    pseudo = [{"channel_id": r["perfil"], "titulo": "", "descricao": r["legenda"]} for r in rows]
    # última leitura bem-sucedida de cada perfil (a tentativa mais recente pode ter sido bloqueada)
    acervo_perfil = {}
    for r in rows:
        a = acervo_perfil.setdefault(r["perfil"], {"videos_desde_16_08": 0, "ultima_leitura_ok": ""})
        a["videos_desde_16_08"] += int(r["publicado_em"] >= "2026-08-16")
        a["ultima_leitura_ok"] = max(a["ultima_leitura_ok"], r["ultima_coleta"] or "")
    padrao = bc.texto_padrao(pseudo)
    out = {"schema_version": 1, "gerado_em_utc": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
           "coletado_em_utc": man.get("run_started_utc"), "status_coleta": man.get("status"),
           "ferramenta": man.get("ferramenta"), "perfis_coleta": [{**p, **acervo_perfil.get(p["perfil"], {"videos_desde_16_08": 0, "ultima_leitura_ok": ""})}
                             for p in (man.get("perfis") or man.get("paginas") or [])],
           "fonte": ("Kwai público via Apify (perfis declarados ao TSE pelas chapas 13 e 22)" if plat == "kwai"
                     else "Facebook público via Apify (páginas declaradas ao TSE pelas chapas 13 e 22)" if plat == "facebook"
                     else "TikTok público via yt-dlp (perfis declarados ao TSE pelas chapas 13 e 22)"),
           "metodo": cfg["nota"] + f" Mesmas regras do caderno 02 (YouTube): links removidos e trechos repetidos em {bc.LIMIAR_REPETICAO}+ vídeos do mesmo perfil descartados. Taxa de interação = (curtidas + comentários + compartilhamentos) ÷ visualizações.",
           "temas": list(cfg["temas"]) + ["sem_tema"], "desde": desde or None, "candidatos": {}}
    tj = root / "data/config/trends.json"
    fases = json.loads(tj.read_text(encoding="utf-8")).get("fases", []) if tj.exists() else []
    out["fases"] = fases
    for cid, cand in cands.items():
        meus = [(r, p) for r, p in zip(rows, pseudo) if r["candidate_id"] == cid and r["publicado_em"] >= desde]
        nome = bc.norm(cand["nome"]).split()
        excluir = set(nome) | {"".join(nome)} | {r["perfil"].replace("_", "").replace(".", "") for r, _ in meus}
        vids, textos, tags = [], [], []
        for r, p in meus:
            txt = bc.texto_util(p, padrao)
            textos.append(txt)
            tg = {bc._tag_key(t) for t in bc.HASHTAG.findall(r["legenda"])} - excluir
            tags.append(tg)
            c = bc.classify(txt, temas, cand)
            vids.append({"video_id": r["video_id"], "perfil": r["perfil"], "url": r["url"], "legenda": r["legenda"][:400],
                         "publicado_em": r["publicado_em"], "visualizacoes": num(r["visualizacoes"]),
                         "curtidas": num(r["curtidas"]), "comentarios": num(r["comentarios"]),
                         "compartilhamentos": num(r["compartilhamentos"]),
                         "taxa_interacao": round(taxa(r), 4) if taxa(r) is not None else None,
                         "hashtags": sorted(tg), **c})
        vids.sort(key=lambda v: v["publicado_em"], reverse=True)
        por_tema = Counter(t for v in vids for t in v["temas"])
        views_tema = Counter()
        for v in vids:
            for t in v["temas"]:
                views_tema[t] += v["visualizacoes"] or 0
        taxas = [v["taxa_interacao"] for v in vids if v["taxa_interacao"] is not None]
        tot = {k: sum(v[k] or 0 for v in vids) for k in ("visualizacoes", "curtidas", "comentarios", "compartilhamentos")}
        out["candidatos"][cid] = {
            "nome": cand["nome"], "numero": cand["numero"], "total_videos": len(vids),
            "perfis": dict(Counter(v["perfil"] for v in vids).most_common()),
            "totais": tot, "taxa_interacao_mediana": round(statistics.median(taxas), 4) if taxas else None,
            "por_tema": dict(por_tema.most_common()), "visualizacoes_por_tema": dict(views_tema.most_common()),
            "cita_adversario": sum(v["cita_adversario"] for v in vids), "pede_voto": sum(v["pede_voto"] for v in vids),
            "nuvem": bc.nuvem(textos, excluir),
            "hashtags": [[t, n] for t, n in Counter(t for s in tags for t in s).most_common(40) if n >= 2],
            "por_mes": dict(sorted(Counter(v["publicado_em"][:7] for v in vids if v["publicado_em"]).items())),
            "desde_16_08": sum(1 for v in vids if v["publicado_em"] >= "2026-08-16"),
            "por_fase": por_fase(vids, fases),
            "videos": vids}
        c = out["candidatos"][cid]
        print(f"{cand['nome']}: {len(vids)} vídeos de {len(c['perfis'])} perfis | {tot['visualizacoes']:,} visualizações | "
              f"interação mediana {c['taxa_interacao_mediana']} | temas {dict(por_tema.most_common(5))} | "
              f"cita adversário {c['cita_adversario']} | pede voto {c['pede_voto']}")
    (root / f"data/{plat}/conteudo.json").write_text(json.dumps(out, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
