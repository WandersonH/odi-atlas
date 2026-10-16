#!/usr/bin/env python3
"""Confere data/reuters/brasil.json contra o texto extraído dos PDFs (repositório privado, ODI_INTERNO_DIR ou argv[1]):
todo número transcrito precisa aparecer no texto das páginas do Brasil indicadas em paginas_pdf; SHA-256 tem de bater
com o registrado no download. Não substitui a conferência visual das páginas (imagens em reuters/img/ no privado)."""
import json, os, re, sys
from pathlib import Path

IGNORAR = {"sha256", "url", "paginas_pdf", "paginas_impressas", "rank", "rsf_total"}


def numeros(x, k=""):
    if isinstance(x, dict):
        for kk, v in x.items():
            if kk not in IGNORAR:
                yield from numeros(v, kk)
    elif isinstance(x, list):
        for v in x:
            yield from numeros(v, k)
    elif isinstance(x, (int, float)) and not isinstance(x, bool):
        yield k, x


def main(argv=None) -> int:
    argv = argv or sys.argv[1:]
    interno = Path(argv[0] if argv else os.environ.get("ODI_INTERNO_DIR", "")) / "reuters"
    d = json.loads(Path("data/reuters/brasil.json").read_text(encoding="utf-8"))
    falhas = 0
    for ano, e in d["edicoes"].items():
        meta = json.loads((interno / f"dnr{ano}.json").read_text(encoding="utf-8"))
        if meta["sha256"] != e["sha256"]:
            print(f"⛔ {ano}: SHA-256 diferente do download"); falhas += 1
        pags = (interno / f"dnr{ano}.txt").read_text(encoding="utf-8").split("\f")
        a, b = e["paginas_pdf"]
        nums = set(re.findall(r"\d+(?:\.\d+)?", " ".join(pags[a - 1:b])))
        faltam = [(k, v) for k, v in numeros(e) if str(abs(v)) not in nums]
        total = sum(1 for _ in numeros(e))
        print(f"{ano}: {total} números conferidos, {len(faltam)} ausentes do texto {faltam[:10]}")
        falhas += len(faltam)
    return 1 if falhas else 0


if __name__ == "__main__":
    sys.exit(main())
