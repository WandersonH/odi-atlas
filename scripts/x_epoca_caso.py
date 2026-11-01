#!/usr/bin/env python3
"""Busca do X numa janela passada ("época"), lida UMA vez por episódio, para casos de conteúdo antigo recirculado.

Generaliza a leitura da época do caso 018 (caso_antigo_atual.py) para outros casos (01/11/2026: caso 023, greve dos
caminhoneiros): casos.json → "comparacao" → episódios com "x_epoca" (busca com since/until). Teto: "teto_epoca_x_usd" do caso.
Privado: ODI_INTERNO_DIR/casos/<caso>/x_epoca_<ep>.jsonl.gz e x_epoca_manifesto.json. Uso: python scripts/x_epoca_caso.py --caso 023
"""
from __future__ import annotations

import gzip
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from net import now_utc  # noqa: E402


def main(argv=None, executar=None) -> int:
    argv = sys.argv[1:] if argv is None else list(argv)
    caso_id = argv[argv.index("--caso") + 1]
    caso = next(c for c in json.loads(Path("data/config/casos.json").read_text(encoding="utf-8"))["casos"] if c["id"] == caso_id)
    interno = os.environ.get("ODI_INTERNO_DIR")
    if not interno:
        print("⛔ ODI_INTERNO_DIR ausente")
        return 1
    priv = Path(interno) / "casos" / caso_id
    priv.mkdir(parents=True, exist_ok=True)
    eps = {k: v["x_epoca"] for k, v in caso["comparacao"]["episodios"].items() if v.get("x_epoca")}
    teto = float(caso.get("teto_epoca_x_usd", 0))
    man_f = priv / "x_epoca_manifesto.json"
    man = json.loads(man_f.read_text(encoding="utf-8")) if man_f.exists() else {"runs": [], "gasto_usd": 0.0}
    if executar is None:
        from collect_meta_apify import run_actor
        tok = os.environ.get(caso.get("segredo", "APIFY_TOKEN"), "").strip()
        executar = (lambda pl, cap: run_actor(tok, "xquik~x-tweet-scraper", pl, cap)) if tok else None  # noqa: E731
    faltam = [ep for ep in eps if not any(r["episodio"] == ep for r in man["runs"])]
    for ep in faltam:
        sobra = round(teto - man["gasto_usd"], 4)
        n = min(int(caso.get("maximo_epoca", 1500)), int(sobra * 0.9 / 0.00015 / max(1, len(faltam)))) if sobra > 0.02 else 0
        if executar is None or n < 20:
            print(f"⛔ X época {ep}: sem token ou sem teto (sobra US$ {sobra})")
            continue
        try:
            run, itens = executar({"searchTerms": [eps[ep]], "maxItems": n, "queryType": "Latest"}, round(0.00015 * n * 1.3 + 0.02, 4))
        except Exception as e:  # noqa: BLE001
            print(f"⛔ X época {ep}: {type(e).__name__}")
            continue
        gasto = float((run or {}).get("usageTotalUsd") or 0) or round(0.00015 * len(itens or []), 4)
        with gzip.open(priv / f"x_epoca_{ep}.jsonl.gz", "wt", encoding="utf-8") as f:
            for x in itens or []:
                f.write(json.dumps(x, ensure_ascii=False) + "\n")
        man["runs"].append({"episodio": ep, "busca": eps[ep], "run": (run or {}).get("id"), "pedidos": n, "itens": len(itens or []),
                            "no_limite": len(itens or []) >= n, "custo_usd": gasto, "em_utc": now_utc()})
        man["gasto_usd"] = round(man["gasto_usd"] + gasto, 4)
        print(f"caso {caso_id} X época {ep}: {len(itens or [])} de {n} pedidos · US$ {gasto}")
    man_f.write_text(json.dumps(man, ensure_ascii=False, indent=1), encoding="utf-8")
    pub = Path("data/casos") / caso_id
    pub.mkdir(parents=True, exist_ok=True)
    (pub / "x_epoca.json").write_text(json.dumps({k: v for k, v in man.items()}, ensure_ascii=False, indent=1), encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
