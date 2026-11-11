"""C19.377: as páginas novas usam a MESMA folha de estilo do Atlas (identidade visual, regra 5)."""
import os
import re
import sys
import unittest
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
import build_css_compartilhado as b  # noqa: E402


class TestCssCompartilhado(unittest.TestCase):
    def test_css_em_dia_com_a_pagina_principal(self):
        css, marca = b.extrair()
        self.assertEqual(Path("assets/odi-atlas.css").read_text(encoding="utf-8"), css, "rode scripts/build_css_compartilhado.py")
        self.assertEqual(Path("assets/odi-marca.jpg").read_bytes(), marca)
        self.assertGreater(len(marca), 1000)

    def test_area_usa_a_folha_e_a_estrutura_do_atlas(self):
        h = Path("area-pesquisador.html").read_text(encoding="utf-8")
        self.assertIn('<link rel="stylesheet" href="./assets/odi-atlas.css">', h)
        for classe in ("layout", "side", "brand-head", "navbutton", "paper-ribbon", "cs-idx", "cs-ficha", "subtabs", "odi-map-hero"):
            self.assertRegex(h, r'class="[^"]*\b' + re.escape(classe) + r'\b', classe)
        # o estilo próprio da página não redefine as peças do Atlas
        proprio = re.search(r"<style>(.*?)</style>", h, flags=re.S).group(1)
        for seletor in (".side", ".card", ".navbutton", ".cs-ficha", "body", ":root", ".intro h1", ".eyebrow"):
            self.assertNotRegex(proprio, r"(^|[}\n])\s*" + re.escape(seletor) + r"\{", seletor)


if __name__ == "__main__":
    unittest.main()
