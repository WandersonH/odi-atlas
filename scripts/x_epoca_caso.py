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
    # 01/11/2026: a busca única da época bateu no limite e, por vir das mais recentes, cobriu só os 2 ou 3 últimos dias da janela.
    # Complemento por dia ("x_epoca_por_dia": n): n publicações de cada dia da janela, gravadas à parte (x_epoca_<ep>_dias.jsonl.gz);
    # a busca única original é mantida.
    import datetime as _dt
    for ep, e in caso["comparacao"]["episodios"].items():
        n_dia = int(e.get("x_epoca_por_dia") or 0)
        if not n_dia or any(r["episodio"] == f"{ep}_dias" for r in man["runs"]) or executar is None:
            continue
        base = e["x_epoca"].split(" since:")[0]
        lingua = " lang:pt" if "lang:pt" in e["x_epoca"] else ""
        d0, d1 = (_dt.date.fromisoformat(x) for x in e["janela_epoca"])
        dias = [(d0 + _dt.timedelta(days=i)) for i in range((d1 - d0).days + 1)]
        custo_max = round(len(dias) * n_dia * 0.00015 * 1.3, 4)
        if man["gasto_usd"] + custo_max > teto:
            print(f"⛔ X época {ep} por dia: não cabe no teto (gasto {man['gasto_usd']} + até {custo_max} > {teto})")
            continue
        itens_tot, gasto_tot, runs = [], 0.0, []
        for d in dias:
            q = f"{base} since:{d.isoformat()} until:{(d + _dt.timedelta(days=1)).isoformat()}{lingua}"
            try:
                run, itens = executar({"searchTerms": [q], "maxItems": n_dia, "queryType": "Top"}, round(0.00015 * n_dia * 1.3 + 0.02, 4))
            except Exception as ex:  # noqa: BLE001
                print(f"⛔ X época {ep} {d}: {type(ex).__name__}")
                continue
            itens_tot += itens or []
            gasto_tot += float((run or {}).get("usageTotalUsd") or 0) or round(0.00015 * len(itens or []), 4)
            runs.append((run or {}).get("id"))
        with gzip.open(priv / f"x_epoca_{ep}_dias.jsonl.gz", "wt", encoding="utf-8") as f:
            for x in itens_tot:
                f.write(json.dumps(x, ensure_ascii=False) + "\n")
        man["runs"].append({"episodio": f"{ep}_dias", "busca": f"{base} · 1 busca por dia ({len(dias)} dias, {n_dia} por dia, mais relevantes)",
                            "run": runs, "pedidos": n_dia * len(dias), "itens": len(itens_tot), "custo_usd": round(gasto_tot, 4), "em_utc": now_utc()})
        man["gasto_usd"] = round(man["gasto_usd"] + gasto_tot, 4)
        print(f"caso {caso_id} X época {ep} por dia: {len(itens_tot)} itens em {len(dias)} dias · US$ {round(gasto_tot, 4)}")
    man_f.write_text(json.dumps(man, ensure_ascii=False, indent=1), encoding="utf-8")
    pub = Path("data/casos") / caso_id
    pub.mkdir(parents=True, exist_ok=True)
    (pub / "x_epoca.json").write_text(json.dumps({k: v for k, v in man.items()}, ensure_ascii=False, indent=1), encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
