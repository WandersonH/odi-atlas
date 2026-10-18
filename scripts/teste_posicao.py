#!/usr/bin/env python3
"""TESTE de posicionamento (favor / contra / neutro) em relação a Lula e a Flávio Bolsonaro, sem treino (zero-shot).

Motivação: revisão de literatura de 18/10/2026 (Alturayeif et al. 2023; Pereira et al. 2025, UstanceBR; Pavan e
Paraboni 2024): sentimento mede o tom, não a posição. Os textos do UstanceBR não são distribuídos (só ids do X), então
este teste usa um modelo aberto de inferência textual multilíngue que roda no próprio Actions — nenhum comentário sai
para serviço externo.

Amostra (semente fixa): N_YT comentários do YouTube e N_X respostas do X, metade em conteúdo de cada candidato,
só textos com 20+ caracteres. Para cada alvo, o modelo julga as hipóteses "o autor apoia <alvo>" e
"o autor é contra <alvo>"; rótulo = a mais provável se passar de LIMIAR, senão "neutro/incerto".

Saída privada (ODI_INTERNO_DIR/posicao/): teste_amostra.csv com texto, previsões e colunas vazias para DOIS
codificadores (kappa). Saída pública: data/pontes/posicao_teste.json — só distribuições, marcadas como NÃO VALIDADAS.
"""
from __future__ import annotations

import csv
import gzip
import json
import os
import random
import sys
import time
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from net import now_utc  # noqa: E402

MODELO = "MoritzLaurer/mDeBERTa-v3-base-xnli-multilingual-nli-2mil7"
L, F = "280002542548", "280002551544"
ALVOS = {"lula": "Lula", "flavio": "Flávio Bolsonaro"}
N_YT, N_X, LIMIAR, SEMENTE = 400, 200, 0.6, 42
HIP = {"favor": "O autor deste comentário apoia {}.", "contra": "O autor deste comentário é contra {}."}


def ler(p: Path) -> list[dict]:
    return list(csv.DictReader(gzip.open(p, "rt", encoding="utf-8"), delimiter=";")) if p.exists() else []


def amostra(rows: list[dict], n: int, rede: str) -> list[dict]:
    rnd = random.Random(SEMENTE)
    out = []
    for cid in (L, F):
        pool = [r for r in rows if r.get("candidate_id") == cid and len((r.get("texto") or "").strip()) >= 20]
        rnd.shuffle(pool)
        out += [{**r, "rede": rede} for r in pool[: n // 2]]
    return out


def rotulo(sf: float, sc: float) -> str:
    return ("favor" if sf >= sc else "contra") if max(sf, sc) >= LIMIAR else "neutro/incerto"


def main(argv=None, classificar=None) -> int:
    root = Path(".")
    interno = os.environ.get("ODI_INTERNO_DIR")
    saida = root / "data/pontes/posicao_teste.json"
    saida.parent.mkdir(parents=True, exist_ok=True)
    if not interno:
        print("⛔ ODI_INTERNO_DIR ausente")
        return 1
    d = Path(interno)
    am = amostra(ler(d / "youtube/comentarios/comentarios.csv.gz"), N_YT, "youtube") + amostra(ler(d / "x/respostas/respostas.csv.gz"), N_X, "x")
    if classificar is None:
        from transformers import pipeline
        clf = pipeline("zero-shot-classification", model=MODELO)

        def classificar(texto: str, alvo: str) -> dict:
            r = clf(texto[:1000], [HIP["favor"].format(alvo), HIP["contra"].format(alvo)], hypothesis_template="{}", multi_label=True)
            sc = dict(zip(r["labels"], r["scores"]))
            return {"favor": sc[HIP["favor"].format(alvo)], "contra": sc[HIP["contra"].format(alvo)]}
    t0, linhas = time.monotonic(), []
    for i, r in enumerate(am):
        lin = {"id_teste": i + 1, "rede": r["rede"], "conteudo_de": "Lula" if r["candidate_id"] == L else "Flávio Bolsonaro",
               "texto": " ".join(r["texto"].split())}
        for k, alvo in ALVOS.items():
            s = classificar(lin["texto"], alvo)
            lin[f"{k}_p_favor"], lin[f"{k}_p_contra"] = round(s["favor"], 3), round(s["contra"], 3)
            lin[f"{k}_modelo"] = rotulo(s["favor"], s["contra"])
            lin[f"{k}_codificador1"] = lin[f"{k}_codificador2"] = ""
        linhas.append(lin)
        if (i + 1) % 100 == 0:
            print(f"  {i + 1}/{len(am)} ({time.monotonic() - t0:.0f} s)", flush=True)
    pd = d / "posicao"
    pd.mkdir(parents=True, exist_ok=True)
    with open(pd / "teste_amostra.csv", "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, list(linhas[0].keys()), delimiter=";", lineterminator="\n")
        w.writeheader()
        w.writerows(linhas)
    dist = {}
    for rede in ("youtube", "x"):
        for onde in ("Lula", "Flávio Bolsonaro"):
            sub = [x for x in linhas if x["rede"] == rede and x["conteudo_de"] == onde]
            dist[f"{rede} · conteúdo de {onde}"] = {"n": len(sub), **{f"sobre {ALVOS[k]}": dict(Counter(x[f"{k}_modelo"] for x in sub)) for k in ALVOS}}
    out = {"schema_version": 1, "gerado_em_utc": now_utc(), "status": "TESTE · NÃO VALIDADO",
           "aviso": "Classificação automática sem treino, ainda sem codificação humana. Não usar como resultado: serve para decidir se vale validar (amostra com duas pessoas, kappa).",
           "modelo": MODELO, "limiar": LIMIAR, "hipoteses": HIP, "semente": SEMENTE, "distribuicao": dist}
    saida.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    for k, v in dist.items():
        print(k, json.dumps(v, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
