#!/usr/bin/env python3
"""Extrai a identidade visual ODI da página principal para as outras páginas usarem a MESMA folha de estilo.

11/11/2026 (C19.377): a área do pesquisador tinha sido feita com outro desenho (crítica do responsável: "mudou totalmente
a linha de design"). Para isso não se repetir, nenhuma página nova reescreve estilo: todas carregam assets/odi-atlas.css,
que é a cópia literal de todos os blocos <style> de ODI_Atlas_v15_MVP.html, e a marca em assets/odi-marca.jpg (a mesma
imagem embutida na barra lateral). tests/test_css_compartilhado.py falha se a página principal mudar e este script não
for rodado de novo.

Uso: python scripts/build_css_compartilhado.py [--verificar]
"""
from __future__ import annotations

import base64
import re
import sys
from pathlib import Path

ORIGEM = Path("ODI_Atlas_v15_MVP.html")
CSS = Path("assets/odi-atlas.css")
MARCA = Path("assets/odi-marca.jpg")


def extrair() -> tuple[str, bytes]:
    s = ORIGEM.read_text(encoding="utf-8")
    blocos = re.findall(r"<style[^>]*>(.*?)</style>", s, flags=re.S)
    css = ("/* GERADO por scripts/build_css_compartilhado.py a partir de ODI_Atlas_v15_MVP.html — não editar à mão. */\n"
           + "\n".join(b.strip("\n") for b in blocos) + "\n")
    m = re.search(r'<img class="odi-brand-img"[^>]*src="data:image/jpeg;base64,([^"]+)"', s)
    return css, base64.b64decode(m.group(1)) if m else b""


def main() -> int:
    css, marca = extrair()
    if "--verificar" in sys.argv:
        ok = CSS.exists() and CSS.read_text(encoding="utf-8") == css and MARCA.exists() and MARCA.read_bytes() == marca
        print("css compartilhado em dia" if ok else "⛔ assets/odi-atlas.css desatualizado: rode scripts/build_css_compartilhado.py")
        return 0 if ok else 1
    CSS.write_text(css, encoding="utf-8")
    MARCA.write_bytes(marca)
    print(f"{CSS}: {len(css)} caracteres · {MARCA}: {len(marca)} bytes")
    return 0


if __name__ == "__main__":
    sys.exit(main())
