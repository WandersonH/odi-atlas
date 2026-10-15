#!/usr/bin/env python3
"""Caderno 14 — consolida a coleta mais recente do Google Trends num arquivo para a página.

Entrada: data/trends/AAAA-MM-DD/HHMMSS/ (collect_trends.py; usa a pasta mais recente com status ok)
Saída:   data/trends/caderno.json  (séries e mapa por UF de cada grupo × período, com o tópico usado)
Os valores do Trends são 0–100 relativos DENTRO de cada consulta: não são volume e não se comparam entre consultas.
"""
from __future__ import annotations

import csv
import json
import sys
from pathlib import Path


def ultima_execucao(base: Path) -> Path | None:
    pastas = sorted((p for p in base.glob("????-??-??/??????") if (p / "manifesto.json").exists()), reverse=True)
    for p in pastas:
        if json.loads((p / "manifesto.json").read_text(encoding="utf-8")).get("status") == "ok":
            return p
    return None


def ler(p: Path) -> list[dict]:
    return list(csv.DictReader(open(p, encoding="utf-8"), delimiter=";")) if p.exists() else []


def main(argv=None) -> int:
    root = Path(argv[0]) if argv else Path(".")
    base = root / "data/trends"
    pasta = ultima_execucao(base)
    if not pasta:
        print("⛔ nenhuma coleta do Trends com status ok")
        return 1
    m = json.loads((pasta / "manifesto.json").read_text(encoding="utf-8"))
    out = {"schema_version": 1, "coleta_utc": m["run_started_utc"], "pasta": str(pasta.relative_to(root)),
           "aviso": m.get("aviso_metodologico", ""), "nota": m["config"].get("nota", ""),
           "nota_relacionados": (m["config"].get("relacionados") or {}).get("nota", ""), "consultas": []}
    for c in m["consultas"]:
        if c.get("status") != "ok":
            continue
        stem = f"{c['grupo']}__{c['periodo'].replace(' ', '_')}"
        serie = ler(pasta / f"{stem}__serie.csv")
        uf = ler(pasta / f"{stem}__uf.csv")
        rel = ler(pasta / f"{stem}__relacionados.csv")
        termos = c["termos"]
        out["consultas"].append({
            "grupo": c["grupo"], "periodo": c["periodo"], "termos": termos,
            "itens": [{"rotulo": i["rotulo"], "modo": i["modo"], "tipo": i.get("topico_tipo", ""), "consulta": i["consulta"]} for i in c["itens"]],
            "serie": [{"t": r["timestamp_utc"], "parcial": r.get("parcial") in ("1", "True", "true"),
                       "v": [int(r[t]) if r.get(t, "").strip() != "" else None for t in termos]} for r in serie],
            "uf": [{"uf": r["geo_code"].replace("BR-", ""), "nome": r["geo_nome"],
                    "v": [int(r[t]) if r.get(t, "").strip() != "" else None for t in termos]} for r in uf],
            "relacionados": [{"termo": r["termo"], "tipo": r["tipo"], "lista": r["lista"], "pos": int(r["posicao"]),
                              "texto": r["texto"], "tipo_assunto": r["tipo_assunto"], "valor": r["valor"],
                              "rotulo": r["valor_formatado"]} for r in rel],
            "arquivos": {"serie": f"{out['pasta']}/{stem}__serie.csv", "uf": f"{out['pasta']}/{stem}__uf.csv",
                         **({"relacionados": f"{out['pasta']}/{stem}__relacionados.csv"} if rel else {})}})
    (base / "caderno.json").write_text(json.dumps(out, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(f"trends: {len(out['consultas'])} consultas da coleta {out['coleta_utc']} ({out['pasta']})")
    return 0 if out["consultas"] else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
