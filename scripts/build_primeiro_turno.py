#!/usr/bin/env python3
"""Resumo por chapa do 1º turno: perfis declarados, seguidores, publicações e repercussão por rede e por fase.

Fontes (todas já no repositório):
- publicações das chapas 13 e 22: data/<rede>/videos.csv.gz (YouTube: data/youtube/videos_latest.csv.gz, já com todas as chapas);
- demais chapas: data/primeiro_turno/<rede>/videos.csv.gz (collect_primeiro_turno.py);
- seguidores: data/seguidores/*latest.csv (último número de cada endereço; perfis do vice somam na chapa);
- votos do 1º turno: data/elections.json (soma dos municípios).
Cobertura desigual é explícita: cada célula traz o número de perfis lidos e se a coleta bateu no limite de posts por perfil.

Saída: data/primeiro_turno/resumo.json.
"""
from __future__ import annotations

import csv
import gzip
import json
import statistics
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from net import now_utc  # noqa: E402

REDES = ("youtube", "tiktok", "instagram", "facebook", "x", "kwai")
ROTULO = {"youtube": "YouTube", "tiktok": "TikTok", "instagram": "Instagram", "facebook": "Facebook", "x": "X", "kwai": "Kwai"}
PLAT_SEG = {"YouTube": "youtube", "TikTok": "tiktok", "Instagram": "instagram", "Facebook": "facebook", "X / Twitter": "x", "Kwai": "kwai"}
DESDE = "2026-07-20"


def num(v):
    try:
        return int(float(v))
    except (TypeError, ValueError):
        return None


def fases(root: Path) -> list[dict]:
    return json.loads((root / "data/config/trends.json").read_text(encoding="utf-8"))["fases"]


def ler(p: Path) -> list[dict]:
    if not p.exists():
        return []
    return list(csv.DictReader(gzip.open(p, "rt", encoding="utf-8"), delimiter=";"))


def main(argv=None) -> int:
    root = Path(argv[0]) if argv else Path(".")
    tse = [r for r in csv.DictReader(gzip.open(root / "data/tse/redes_sociais_candidatos_2026.csv.gz", "rt", encoding="utf-8"), delimiter=";")
           if r.get("DS_CARGO", "").upper() in ("PRESIDENTE", "VICE-PRESIDENTE")]
    el = json.loads((root / "data/elections.json").read_text(encoding="utf-8"))
    urna = el["candidates"]["2026"]
    votos = {}
    for m in el["years"]["2026"].values():
        for nr, v in (m.get("candidatos") or {}).items():
            votos[nr] = votos.get(nr, 0) + int(v or 0)
    nr_de_sq = {r["SQ_CANDIDATO"]: r["NR_CANDIDATO"] for r in tse}
    pessoas = {}
    for r in tse:
        if r["NR_CANDIDATO"] in urna:
            pessoas.setdefault(r["NR_CANDIDATO"], {})[r["SQ_CANDIDATO"]] = (r["NM_URNA_CANDIDATO"].title(), r["DS_CARGO"].title())
    fs = [f for f in fases(root) if f["de"] <= "2026-10-04"]  # 1º turno: pré-campanha e campanha
    chapas = {nr: {"numero": nr, "nome": urna[nr].title(), "votos_1t": votos.get(nr),
                   "pessoas": [{"nome": n, "cargo": c} for n, c in sorted(pessoas.get(nr, {}).values(), key=lambda x: x[1] != "Presidente")],
                   "redes": {}} for nr in urna}
    # seguidores: último número de cada endereço
    seg = {}
    for p in sorted((root / "data/seguidores").glob("*latest.csv")):
        if p.name.startswith(("whatsapp", "socialblade")):
            continue
        for r in csv.DictReader(open(p, encoding="utf-8"), delimiter=";"):
            rede = PLAT_SEG.get(r.get("platform", ""))
            nr = nr_de_sq.get(r.get("candidate_id", ""))
            n = num(r.get("followers"))
            if not rede or nr not in chapas or n is None or n <= 0:
                continue
            k = (rede, (r.get("source_url") or r.get("url") or "").lower().rstrip("/"))
            if k not in seg or r.get("captured_at", "") >= seg[k][2]:
                seg[k] = (nr, n, r.get("captured_at", ""))
    for (rede, _), (nr, n, d) in seg.items():
        c = chapas[nr]["redes"].setdefault(rede, {})
        c["seguidores"] = c.get("seguidores", 0) + n
        c["seguidores_perfis"] = c.get("seguidores_perfis", 0) + 1
        c["seguidores_data"] = max(c.get("seguidores_data", ""), d)
    # publicações
    head = {"280002542548": "13", "280002551544": "22"}
    manif = {}
    for rede in REDES:
        if rede == "youtube":
            rows = ler(root / "data/youtube/videos_latest.csv.gz")
            for r in rows:
                r["_nr"] = nr_de_sq.get(r["candidate_id"])
        else:
            rows = [{**r, "_nr": head.get(r["candidate_id"])} for r in ler(root / f"data/{rede}/videos.csv.gz")]
            rows += [{**r, "_nr": nr_de_sq.get(r["candidate_id"])} for r in ler(root / f"data/primeiro_turno/{rede}/videos.csv.gz")]
            mp = root / f"data/primeiro_turno/{rede}/manifesto_latest.json"
            if mp.exists():
                manif[rede] = json.loads(mp.read_text(encoding="utf-8"))
        vistos = set()
        for r in rows:
            nr, d = r.get("_nr"), (r.get("publicado_em") or "")[:10]
            if nr not in chapas or not d or d < DESDE:
                continue
            k = (nr, r.get("video_id"))
            if k in vistos:
                continue
            vistos.add(k)
            c = chapas[nr]["redes"].setdefault(rede, {})
            c.setdefault("_rows", []).append(r)
    for nr, ch in chapas.items():
        for rede, c in ch["redes"].items():
            rows = c.pop("_rows", [])
            if not rows:
                continue
            perfis = sorted({r.get("perfil") or r.get("canal") or "" for r in rows} - {""})
            c["perfis_com_posts"] = len(perfis)
            c["por_fase"] = {}
            for f in fases(root):
                fr = [r for r in rows if f["de"] <= r["publicado_em"][:10] <= f["ate"]]
                vis = [num(r.get("visualizacoes")) for r in fr]
                inter = [sum(num(r.get(k)) or 0 for k in ("curtidas", "comentarios", "compartilhamentos")) for r in fr]
                c["por_fase"][f["id"]] = {"posts": len(fr), "visualizacoes": sum(v for v in vis if v) if any(vis) else None,
                                          "visualizacoes_informadas": sum(1 for v in vis if v is not None),
                                          "interacoes": sum(inter), "interacao_mediana": statistics.median(inter) if inter else None}
            c["posts"] = sum(v["posts"] for v in c["por_fase"].values())
            c["ultimo_post"] = max(r["publicado_em"][:10] for r in rows)
            m = manif.get(rede)
            if m and nr not in ("13", "22"):
                lim = [p for p in m.get("perfis", []) if p.get("no_limite") and p["perfil"] in perfis]
                c["perfis_no_limite"] = [p["perfil"] for p in lim]
    cob = {rede: {"status": m.get("status"), "coletado_em": m.get("run_started_utc"), "modo": m.get("modo"),
                  "posts_pedidos_por_perfil": m.get("posts_pedidos_por_perfil"), "perfis_declarados": m.get("perfis_declarados"),
                  "perfis_com_erro": [p["perfil"] for p in m.get("perfis", []) if p.get("erro") or (p.get("status") not in (None, "ok"))]}
           for rede, m in manif.items()}
    out = {"schema_version": 1, "gerado_em_utc": now_utc(), "desde": DESDE, "fases": fases(root), "rotulos": ROTULO,
           "cobertura_demais_chapas": cob,
           "nota": "Chapas 13 e 22 pelos coletores próprios (mais perfis e mais tempo de coleta); demais chapas pela coleta de 18/10 com limite de posts por perfil. YouTube pela API oficial para todas. Seguidores: último número de cada endereço declarado ao TSE; perfis do vice somam na chapa.",
           "chapas": sorted(chapas.values(), key=lambda c: -(c["votos_1t"] or 0))}
    saida = root / "data/primeiro_turno/resumo.json"
    saida.parent.mkdir(parents=True, exist_ok=True)
    saida.write_text(json.dumps(out, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    for c in out["chapas"]:
        print(f"{c['numero']} {c['nome']}: " + " · ".join(f"{ROTULO[r]} {v.get('posts', 0)} posts" for r, v in c["redes"].items()))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
