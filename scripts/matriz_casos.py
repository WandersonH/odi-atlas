#!/usr/bin/env python3
"""Matriz caso × análise do padrão completo, lida dos arquivos publicados (não da configuração).

Pedido do responsável (01/11/2026, 21h28): começar a padronização pelos casos sem o padrão completo. O padrão completo, como
definido na auditoria de 01/11: (R) publicações coletadas por termo/hashtag nas redes · (B) Bardin com livro de códigos ·
(H) classes (CHD de Reinert) · (T) Google Trends por estado · (K) busca de checagens.
Cada célula diz de onde veio: arquivo e campo. Uso: python scripts/matriz_casos.py  →  data/casos/matriz.json
"""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def ler(p: Path):
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        return None


def main() -> int:
    cfg = json.loads((ROOT / "data/config/casos.json").read_text(encoding="utf-8"))["casos"]
    linhas = []
    for c in cfg:
        cid = c["id"]
        d = ROOT / "data/casos" / cid
        caso, busca, bardin, mundo = ler(d / "caso.json"), ler(d / "busca.json"), ler(d / "bardin.json"), ler(d / "mundo.json")
        redes = {k: v.get("publicacoes", 0) for k, v in ((caso or {}).get("redes") or {}).items() if isinstance(v, dict)}
        R = {"ok": sum(redes.values()) > 0, "fonte": "caso.json → redes", "detalhe": {k: n for k, n in redes.items() if n}}
        for extra in ("x.json", "instagram.json"):
            j = ler(d / extra)
            if j and not R["ok"]:
                R = {"ok": True, "fonte": f"{extra} (posts indicados, sem busca por termo)", "detalhe": {}}
        B = {"ok": bool(bardin) or bool((mundo or {}).get("analises", {}).get("bardin")),
             "fonte": "bardin.json" if bardin else ("mundo.json → analises.bardin" if mundo else None),
             "livro": (ROOT / f"data/config/livro_codigos_caso{cid}.json").exists()}
        fontes_h = []
        if busca and busca.get("classes"):
            fontes_h.append("busca.json → classes (comentários do YouTube)")
        if bardin and bardin.get("chd_palavras"):
            fontes_h.append("bardin.json → chd_palavras (publicações)")
        for extra in ("instagram.json", "x.json"):
            if (ler(d / extra) or {}).get("classes"):
                fontes_h.append(f"{extra} → classes")
        if mundo and (mundo.get("analises") or {}).get("classes"):
            fontes_h.append("mundo.json → analises.classes")
        H = {"ok": bool(fontes_h), "fonte": fontes_h, "sobre_publicacoes": any("publicações" in f for f in fontes_h)}
        tr = (busca or {}).get("trends") or {}
        uf = [k for k, g in tr.items() if isinstance(g, dict) and ("uf_12m" in g or any(x.startswith("paises_") for x in g))]
        T = {"ok": bool(uf), "fonte": f"busca.json → trends.{uf[0]}" if uf else None, "trends_sem_estado": bool(tr) and not uf}
        K = {"ok": busca is not None and "checagens" in busca, "achadas": (len(busca["checagens"]) if busca and isinstance(busca.get("checagens"), list) else None)}
        falta = [n for n, x in (("redes", R), ("Bardin", B), ("CHD", H), ("Trends por estado", T), ("checagens", K)) if not x["ok"]]
        linhas.append({"caso": cid, "titulo": c.get("titulo"), "R": R, "B": B, "H": H, "T": T, "K": K, "falta": falta,
                       "completo": not falta, "pasta_existe": d.exists()})
    out = {"gerado_em_utc": __import__("datetime").datetime.now(__import__("datetime").timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
           "criterio": __doc__.split("Cada célula")[0].strip(), "casos": linhas,
           "completos": [x["caso"] for x in linhas if x["completo"]], "incompletos": [x["caso"] for x in linhas if not x["completo"]]}
    (ROOT / "data/casos/matriz.json").write_text(json.dumps(out, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    for x in linhas:
        print(x["caso"], "✓" if x["completo"] else "falta: " + ", ".join(x["falta"]),
              "| H:", "posts" if x["H"]["sobre_publicacoes"] else ("coment." if x["H"]["ok"] else "—"),
              "| livro:", "s" if x["B"]["livro"] else "n", "| R:", x["R"]["detalhe"] or x["R"]["fonte"] if x["R"]["ok"] else "—")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
