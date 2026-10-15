#!/usr/bin/env python3
"""Concordância entre codificadores (kappa de Cohen) e qualidade da pré-codificação — livro de códigos de populismo.

Entrada (preenchidas por pessoas, a partir de data/codificacao/amostra_populismo_v1.csv):
  data/codificacao/codificador_A_v1.csv  e  data/codificacao/codificador_B_v1.csv   (separador ;)
  data/codificacao/amostra_populismo_v1_precodificacao.csv                          (gerada automaticamente)
Saída: data/codificacao/concordancia_v1.json

Para cada categoria: concordância percentual e kappa de Cohen entre A e B (valores 0, 1, UC);
depois, nos vídeos em que A e B concordam (consenso, sem UC), precisão e cobertura da pré-codificação.
Sem as duas planilhas, o status é "aguardando codificação humana" (bloqueio, não sucesso).
"""
from __future__ import annotations

import csv
import json
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import plataformas as pl  # noqa: E402

VALIDOS = {"0", "1", "UC"}


def kappa(a: list[str], b: list[str]) -> float | None:
    n = len(a)
    if n == 0:
        return None
    po = sum(x == y for x, y in zip(a, b)) / n
    ca, cb = Counter(a), Counter(b)
    pe = sum(ca[k] * cb[k] for k in set(ca) | set(cb)) / n ** 2
    return None if pe == 1 else round((po - pe) / (1 - pe), 3)


def ler(p: Path) -> dict[str, dict]:
    with open(p, encoding="utf-8-sig") as f:
        return {r["video_id"]: r for r in csv.DictReader(f, delimiter=";")}


def normaliza(v: str) -> str:
    v = (v or "").strip().upper()
    return {"SIM": "1", "NAO": "0", "NÃO": "0", "S": "1", "N": "0"}.get(v, v)


def avaliar(A: dict, B: dict, pre: dict, cats: list[str]) -> dict:
    ids = sorted(set(A) & set(B))
    out = {"videos_comuns": len(ids), "categorias": {}}
    for c in cats:
        pares = [(normaliza(A[i].get(c, "")), normaliza(B[i].get(c, ""))) for i in ids]
        pares = [(x, y) for x, y in pares if x in VALIDOS and y in VALIDOS]
        xa, xb = [p[0] for p in pares], [p[1] for p in pares]
        res = {"pares_validos": len(pares),
               "concordancia_pct": round(100 * sum(x == y for x, y in pares) / len(pares), 1) if pares else None,
               "kappa": kappa(xa, xb), "uc_A": xa.count("UC"), "uc_B": xb.count("UC")}
        cons = [i for i in ids if normaliza(A[i].get(c, "")) == normaliza(B[i].get(c, "")) in {"0", "1"}]
        if cons and c in next(iter(pre.values()), {}):
            vp = sum(1 for i in cons if normaliza(A[i][c]) == "1" and str(pre.get(i, {}).get(c)) == "1")
            fp = sum(1 for i in cons if normaliza(A[i][c]) == "0" and str(pre.get(i, {}).get(c)) == "1")
            fn = sum(1 for i in cons if normaliza(A[i][c]) == "1" and str(pre.get(i, {}).get(c)) != "1")
            res["pre_codificacao"] = {"consenso": len(cons), "verdadeiros_positivos": vp, "falsos_positivos": fp,
                                      "falsos_negativos": fn,
                                      "precisao": round(vp / (vp + fp), 3) if vp + fp else None,
                                      "cobertura": round(vp / (vp + fn), 3) if vp + fn else None}
        out["categorias"][c] = res
    return out


def main(argv=None) -> int:
    root, plat = pl.args(argv)
    d = root / "data/codificacao"
    suf = "" if plat == "youtube" else "_" + plat
    livro = json.loads((root / "data/config/livro_codigos_populismo.json").read_text(encoding="utf-8"))
    cats = list(livro["categorias"])
    pa, pb = d / f"codificador_A{suf}_v1.csv", d / f"codificador_B{suf}_v1.csv"
    if not (pa.exists() and pb.exists()):
        out = {"status": "aguardando codificação humana",
               "faltam": [p.name for p in (pa, pb) if not p.exists()],
               "instrucao": f"Duas pessoas copiam amostra_populismo{suf}_v1.csv, preenchem as colunas de categoria com 0, 1 ou UC "
                            "(e instituicoes_direcao com A, D ou UC) sem ver a pré-codificação nem a outra planilha, e salvam como "
                            f"codificador_A{suf}_v1.csv e codificador_B{suf}_v1.csv nesta pasta."}
    else:
        out = {"status": "ok", **avaliar(ler(pa), ler(pb), ler(d / f"amostra_populismo{suf}_v1_precodificacao.csv"), cats)}
    out["plataforma"] = plat
    (d / f"concordancia{suf}_v1.json").write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({k: out[k] for k in out if k != "categorias"}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
