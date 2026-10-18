#!/usr/bin/env python3
"""Temas que circulam entre os dois lados: o mesmo tema nos conteúdos de Lula e de Flávio (e nos comentários do
público de cada um, no YouTube), semana a semana, com quem chegou primeiro aos picos e a defasagem.

Método:
- Tema de cada conteúdo: classificação que o Atlas já faz (dicionário data/config/temas_youtube.json), lida de
  data/<rede>/conteudo.json. Redes: YouTube, TikTok, Kwai, Facebook e X, somadas e separadas.
- Série: % dos conteúdos de cada candidato na semana (segunda a domingo) que tratam do tema. Semanas com menos de
  MIN_ITENS_SEMANA conteúdos do candidato ficam sem valor.
- Pico: semana em que a parcela do tema passa da média do candidato + 1 desvio-padrão (e de PISO_PICO pontos).
- Quem chegou primeiro: para cada pico de um lado, o pico mais próximo do outro lado em até JANELA semanas antes
  ou depois. A defasagem é a diferença em semanas. É indício de sequência, não de causa: os dois lados podem
  estar reagindo ao mesmo fato externo.
- Correlação das séries semanais (Pearson) entre os dois candidatos, por tema: quanto o tema sobe e desce junto.
- Comentários (só YouTube, onde há volume): mesma série, com o dicionário aplicado ao texto dos comentários no
  espaço de cada candidato (privado → só a parcela agregada vai para o público).

Saída pública: data/pontes/temas.json.
"""
from __future__ import annotations

import csv
import datetime as dt
import gzip
import json
import os
import statistics
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import build_conteudo as bc  # noqa: E402
from net import now_utc  # noqa: E402

L, F = "280002542548", "280002551544"
NOMES = {L: "Lula", F: "Flávio Bolsonaro"}
REDES = ("youtube", "tiktok", "kwai", "facebook", "x")
DESDE = "2026-07-20"
MIN_ITENS_SEMANA = 5
PISO_PICO = 5.0
JANELA = 2


def semana(iso: str) -> str:
    d = dt.date.fromisoformat(iso[:10])
    return (d - dt.timedelta(days=d.weekday())).isoformat()


def series(itens: list[tuple[str, str, list[str]]], temas: list[str], semanas: list[str]) -> dict:
    """itens: (candidato, data ISO, temas) → {tema: {cand: [pct por semana ou None]}}, e n por semana."""
    n = {c: defaultdict(int) for c in (L, F)}
    k = {c: defaultdict(lambda: defaultdict(int)) for c in (L, F)}
    for c, d, ts in itens:
        if c not in n or d[:10] < DESDE:
            continue
        s = semana(d)
        n[c][s] += 1
        for t in set(ts):
            k[c][t][s] += 1
    out = {t: {NOMES[c]: [round(100 * k[c][t][s] / n[c][s], 1) if n[c][s] >= MIN_ITENS_SEMANA else None for s in semanas]
               for c in (L, F)} for t in temas}
    return out, {NOMES[c]: [n[c][s] for s in semanas] for c in (L, F)}


def picos(v: list) -> list[int]:
    xs = [x for x in v if x is not None]
    if len(xs) < 4:
        return []
    m, sd = statistics.mean(xs), statistics.pstdev(xs)
    return [i for i, x in enumerate(v) if x is not None and x >= max(m + sd, PISO_PICO)]


def pearson(a: list, b: list) -> float | None:
    par = [(x, y) for x, y in zip(a, b) if x is not None and y is not None]
    if len(par) < 5:
        return None
    xs, ys = zip(*par)
    if statistics.pstdev(xs) == 0 or statistics.pstdev(ys) == 0:
        return None
    return round(statistics.correlation(xs, ys), 2)


def sequencia(sl: list, sf: list, semanas: list[str]) -> list[dict]:
    pl, pf = picos(sl), picos(sf)
    out = []
    for i in pl:
        viz = [j for j in pf if abs(j - i) <= JANELA]
        if viz:
            j = min(viz, key=lambda j: abs(j - i))
            out.append({"semana_lula": semanas[i], "semana_flavio": semanas[j], "defasagem_semanas": j - i,
                        "primeiro": "Lula" if j > i else "Flávio Bolsonaro" if j < i else "mesma semana"})
    for j in pf:
        if not any(abs(j - i) <= JANELA for i in pl):
            out.append({"semana_lula": None, "semana_flavio": semanas[j], "defasagem_semanas": None, "primeiro": "só Flávio Bolsonaro"})
    for i in pl:
        if not any(abs(j - i) <= JANELA for j in pf):
            out.append({"semana_lula": semanas[i], "semana_flavio": None, "defasagem_semanas": None, "primeiro": "só Lula"})
    return sorted(out, key=lambda x: x["semana_lula"] or x["semana_flavio"])


def resumo_tema(sl, sf, semanas) -> dict:
    seq = sequencia(sl, sf, semanas)
    pares = [x for x in seq if x["defasagem_semanas"] is not None]
    return {"correlacao": pearson(sl, sf), "picos": seq,
            "picos_em_comum": len(pares), "lula_antes": sum(1 for x in pares if x["primeiro"] == "Lula"),
            "flavio_antes": sum(1 for x in pares if x["primeiro"] == "Flávio Bolsonaro"),
            "mesma_semana": sum(1 for x in pares if x["primeiro"] == "mesma semana"),
            "media_lula": round(statistics.mean([x for x in sl if x is not None]), 1) if any(x is not None for x in sl) else None,
            "media_flavio": round(statistics.mean([x for x in sf if x is not None]), 1) if any(x is not None for x in sf) else None}


def main(argv=None) -> int:
    root = Path(argv[0]) if argv else Path(".")
    cfg = json.loads((root / "data/config/temas_youtube.json").read_text(encoding="utf-8"))
    temas = list(cfg["temas"])
    hoje = dt.date.fromisoformat(now_utc()[:10])
    s0 = dt.date.fromisoformat(semana(DESDE))
    semanas = [(s0 + dt.timedelta(weeks=i)).isoformat() for i in range((hoje - s0).days // 7 + 1)]
    por_rede, todos, cont_redes = {}, [], {}
    for rede in REDES:
        p = root / f"data/{rede}/conteudo.json"
        if not p.exists():
            continue
        d = json.loads(p.read_text(encoding="utf-8"))
        its = [(cid, v.get("publicado_em") or "", [t for t in (v.get("temas") or []) if t != "sem_tema"])
               for cid, c in d["candidatos"].items() for v in (c.get("videos") or []) if v.get("publicado_em")]
        todos += its
        cont_redes[rede] = sum(1 for c, dd, _ in its if dd[:10] >= DESDE)
        s, n = series(its, temas, semanas)
        por_rede[rede] = {"itens_por_semana": n, "temas": {t: {"serie": s[t], **resumo_tema(s[t]["Lula"], s[t]["Flávio Bolsonaro"], semanas)} for t in temas}}
    s, n = series(todos, temas, semanas)
    juntas = {"itens_por_semana": n, "temas": {t: {"serie": s[t], **resumo_tema(s[t]["Lula"], s[t]["Flávio Bolsonaro"], semanas)} for t in temas}}
    # comentários do YouTube no espaço de cada candidato (privado → só parcelas)
    coment = None
    interno = os.environ.get("ODI_INTERNO_DIR")
    pc = Path(interno) / "youtube/comentarios/comentarios.csv.gz" if interno else None
    if pc and pc.exists():
        regs = {t: [bc.term_regex(x) for x in v] for t, v in cfg["temas"].items()}
        its = []
        for r in csv.DictReader(gzip.open(pc, "rt", encoding="utf-8"), delimiter=";"):
            if r.get("candidate_id") in (L, F) and r.get("publicado_em"):
                tx = bc.norm(r.get("texto") or "")
                its.append((r["candidate_id"], r["publicado_em"], [t for t, rs in regs.items() if any(x.search(tx) for x in rs)]))
        s2, n2 = series(its, temas, semanas)
        coment = {"rede": "youtube", "comentarios_por_semana": n2,
                  "temas": {t: {"serie": s2[t], **resumo_tema(s2[t]["Lula"], s2[t]["Flávio Bolsonaro"], semanas)} for t in temas}}
    out = {"schema_version": 1, "gerado_em_utc": now_utc(), "desde": DESDE, "semanas": semanas, "itens_por_rede": cont_redes,
           "metodo": {"tema": "dicionário de temas do Atlas (data/config/temas_youtube.json) aplicado a cada conteúdo",
                      "serie": f"% dos conteúdos do candidato na semana que tratam do tema; semanas com menos de {MIN_ITENS_SEMANA} conteúdos ficam sem valor",
                      "pico": f"semana acima da média do candidato + 1 desvio-padrão (mínimo {PISO_PICO} pontos)",
                      "quem_primeiro": f"pico do outro lado em até {JANELA} semanas; indica sequência, não causa (os dois podem reagir ao mesmo fato)",
                      "correlacao": "Pearson entre as séries semanais dos dois candidatos (semanas com valor nos dois)"},
           "todas_as_redes": juntas, "por_rede": por_rede, "comentarios_youtube": coment}
    saida = root / "data/pontes/temas.json"
    saida.parent.mkdir(parents=True, exist_ok=True)
    saida.write_text(json.dumps(out, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    for t, v in juntas["temas"].items():
        print(f"{t}: corr {v['correlacao']} · picos em comum {v['picos_em_comum']} (Lula antes {v['lula_antes']}, Flávio antes {v['flavio_antes']}, mesma semana {v['mesma_semana']})")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
