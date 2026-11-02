"""Lematização com o dicionário do IRaMuTeQ e risadas normalizadas (01/11/2026)."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import chd_reinert as chd  # noqa: E402


class TestLematizacao(unittest.TestCase):
    def test_lemas_e_formas_ativas(self):
        t = chd.tokens("Os petistas votaram e estão votando nas eleições")
        self.assertEqual(t.count("votar"), 2)
        self.assertIn("petista", t)
        self.assertIn("eleicao", t)
        self.assertNotIn("estao", t)  # auxiliar (ver_sup) não é forma ativa

    def test_risadas_viram_uma_forma(self):
        self.assertEqual(chd.tokens("kkkkkkk kkk hahaha rsrsrs"), ["risada"] * 4)

    def test_mencao_hashtag_link_fora(self):
        self.assertEqual(chd.tokens("@fulano #lula https://x.com/a"), [])

    def test_dicionario_presente(self):
        self.assertGreater(chd.lematizacao().get("formas_no_dicionario", 0), 100000)


if __name__ == "__main__":
    unittest.main()
