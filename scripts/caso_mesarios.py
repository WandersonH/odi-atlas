"""Caso 022: quantas publicações citam mesários e quantas são de quem se declara mesário (só contagens).

Pedido do responsável (02/11/2026, 15h57) sobre os dados de mesários do TSE. Não cruza a lista de mesários convocados com
contas (identificaria pessoas comuns); lê só o texto das publicações já coletadas do caso. Autodeclaração = padrão
"sou/fui/trabalhei como mesário" etc.; cada uma é conferida à mão e o número final vem com a conferência.
Uso: ODI_INTERNO_DIR=... python scripts/caso_mesarios.py --caso 022
"""
import csv
import gzip
import json
import os
import re
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CITA = re.compile(r"mes[aá]ri[oa]s?\b", re.I)
AUTO = re.compile(r"\b(sou|fui|era|estava|trabalhei|trabalho|servi|atuei|atuo)\s+(como\s+|de\s+|o\s+|a\s+)?(1[ºo°]?\s+|primeir[oa]\s+|segund[oa]\s+)?mes[aá]ri[oa]"
                  r"|\beu,?\s+mes[aá]ri[oa]", re.I)


def contar(rows: list[dict]) -> dict:
    rows = list({(r["rede"], r["item_id"]): r for r in rows}.values())
    cita = [r for r in rows if CITA.search(r.get("texto") or "")]
    auto = [r for r in cita if AUTO.search(r.get("texto") or "")]
    return {"lidas": len(rows), "citam_mesario": len(cita), "pct_citam": round(100 * len(cita) / len(rows), 2) if rows else None,
            "autodeclaradas_pelo_padrao": len(auto), "autodeclaradas_por_rede": dict(Counter(r["rede"] for r in auto)),
            "citam_por_rede": dict(Counter(r["rede"] for r in cita))}


def main(argv):
    caso = argv[argv.index("--caso") + 1] if "--caso" in argv else "022"
    p = Path(os.environ["ODI_INTERNO_DIR"]) / "casos" / caso / "itens.csv.gz"
    res = contar(list(csv.DictReader(gzip.open(p, "rt", encoding="utf-8"), delimiter=";")))
    out = {"caso": caso, "universo": "⛔ desconhecido (as plataformas não informam o total de publicações por termo)",
           "amostra": "publicações coletadas do caso (mesma coleta do dossiê); repetidas contam uma vez", **res,
           "nota": "Só contagens. Não há cruzamento com a lista de mesários do TSE. A autodeclaração é por padrão de texto e precisa de conferência à mão."}
    (ROOT / "data/casos" / caso / "mesarios.json").write_text(json.dumps(out, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(out)


if __name__ == "__main__":
    main(sys.argv[1:])
