#!/usr/bin/env python3
"""Caderno 13 — vídeos do YouTube de Lula e Flávio Bolsonaro classificados por tema (dicionário aberto).

Entrada: data/youtube/videos_latest.csv.gz (coleta diária) + data/config/temas_youtube.json
Saída:   data/youtube/conteudo.json

Para cada vídeo, sobre título + descrição normalizados:
  - temas: todos os temas do dicionário com pelo menos um termo encontrado ("sem_tema" se nenhum);
  - cita_adversario: algum termo do adversário aparece;
  - pede_voto: alguma expressão de pedido de voto com o próprio número (ou referência ao 2º turno).
Inspirado nos níveis do Flaviômetro (0 não cita / 1 cita / 2 pede voto), mas com regras publicadas.
"""
from __future__ import annotations

import csv
import datetime as dt
import gzip
import json
import re
import sys
import unicodedata
from collections import Counter
from pathlib import Path


def norm(s: str) -> str:
    s = unicodedata.normalize("NFKD", s or "").lower()
    s = "".join(c for c in s if not unicodedata.combining(c))
    return " " + re.sub(r"[^a-z0-9#]+", " ", s).strip() + " "


def term_regex(term: str) -> re.Pattern:
    t = norm(term).strip()
    body = re.escape(t.rstrip("*")).replace(r"\ ", " ")
    return re.compile(r"(?<![a-z0-9])" + body + (r"[a-z0-9]*" if t.endswith("*") else r"(?![a-z0-9])"))


def compile_cfg(cfg: dict):
    temas = {k: [term_regex(t) for t in v] for k, v in cfg["temas"].items()}
    cands = {}
    for cid, c in cfg["candidatos"].items():
        cands[cid] = {"adv": [term_regex(t) for t in c["adversario"]],
                      "voto": [term_regex(t.replace("{n}", c["numero"])) for t in cfg["pede_voto"]], **c}
    return temas, cands


def classify(text: str, temas, cand) -> dict:
    t = norm(text)
    found = [k for k, regs in temas.items() if any(r.search(t) for r in regs)]
    return {"temas": found or ["sem_tema"],
            "cita_adversario": any(r.search(t) for r in cand["adv"]),
            "pede_voto": any(r.search(t) for r in cand["voto"])}


def main(argv=None) -> int:
    root = Path(argv[0]) if argv else Path(".")
    cfg = json.loads((root / "data/config/temas_youtube.json").read_text(encoding="utf-8"))
    temas, cands = compile_cfg(cfg)
    src = root / "data/youtube/videos_latest.csv.gz"
    rows = list(csv.DictReader(gzip.open(src, "rt", encoding="utf-8"), delimiter=";"))
    coletado = max((r["coletado_em"] for r in rows), default=None)
    out = {"schema_version": 1, "gerado_em_utc": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
           "coletado_em_utc": coletado, "fonte": "YouTube Data API v3 (canais declarados ao TSE)",
           "metodo": cfg["nota"], "temas": list(cfg["temas"]) + ["sem_tema"], "candidatos": {}}
    for cid, cand in cands.items():
        vids = []
        for r in rows:
            if r["candidate_id"] != cid:
                continue
            c = classify(r["titulo"] + " " + r.get("descricao", ""), temas, cand)
            vids.append({"video_id": r["video_id"], "canal": r["canal"], "titulo": r["titulo"],
                         "publicado_em": r["publicado_em"], "duracao": r["duracao"],
                         "visualizacoes": int(r["visualizacoes"]) if r["visualizacoes"] else None,
                         "curtidas": int(r["curtidas"]) if r["curtidas"] else None,
                         "comentarios": int(r["comentarios"]) if r["comentarios"] else None, **c})
        vids.sort(key=lambda v: v["publicado_em"] or "", reverse=True)
        por_tema = Counter(t for v in vids for t in v["temas"])
        views_tema = Counter()
        for v in vids:
            for t in v["temas"]:
                views_tema[t] += v["visualizacoes"] or 0
        out["candidatos"][cid] = {"nome": cand["nome"], "numero": cand["numero"], "total_videos": len(vids),
                                  "canais": sorted({v["canal"] for v in vids}),
                                  "por_tema": dict(por_tema.most_common()), "visualizacoes_por_tema": dict(views_tema.most_common()),
                                  "cita_adversario": sum(v["cita_adversario"] for v in vids),
                                  "pede_voto": sum(v["pede_voto"] for v in vids),
                                  "videos": vids[:120]}
        print(cand["nome"], len(vids), "vídeos | temas:", dict(por_tema.most_common(6)),
              "| cita adversário:", out["candidatos"][cid]["cita_adversario"], "| pede voto:", out["candidatos"][cid]["pede_voto"])
    (root / "data/youtube/conteudo.json").write_text(json.dumps(out, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
