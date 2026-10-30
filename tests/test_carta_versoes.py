import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import carta_versoes as c  # noqa: E402


class TestCartaVersoes(unittest.TestCase):
    def test_diferencas(self):
        d = c.diferencas("como o verdadeiro presidente do Brasil. Eu sou o presidente eleito e",
                         "como o líder do Brasil. Eu sou o líder e")
        self.assertEqual([(x["antes"], x["depois"]) for x in d], [("verdadeiro presidente", "líder"), ("presidente eleito", "líder")])
        self.assertEqual(c.diferencas("igual", "igual"), [])

    def test_token(self):
        t = c.token("2115538982012682337")
        self.assertTrue(t and "." not in t and "0" not in t)


if __name__ == "__main__":
    unittest.main()
