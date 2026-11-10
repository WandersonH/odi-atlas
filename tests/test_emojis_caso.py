"""C19.373: emojis.json de cada caso traz só contagens (nenhum texto), com universo e amostra."""
import glob
import json
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))


class TestEmojisCaso(unittest.TestCase):
    def test_estrutura_sem_texto(self):
        arqs = glob.glob("data/casos/*/emojis.json")
        self.assertTrue(arqs)
        for f in arqs:
            d = json.load(open(f, encoding="utf-8"))
            self.assertEqual(set(d), {"schema_version", "caso", "gerado_em_utc", "fontes", "total", "posicao", "emojis", "palavras", "metodo", "aviso"}, f)
            for x in d["fontes"]:
                self.assertIn("universo", x)
                self.assertIn("lidos", x)
            for e in d["emojis"]:
                self.assertNotIn("texto", e)
                self.assertLessEqual(e["textos"], d["total"]["lidos"])

    def test_variantes_unidas(self):
        import emoji  # noqa: F401
        from emojis_caso import norm
        self.assertEqual(norm("❤️"), norm("❤"))
        self.assertEqual(norm("👏🏽"), "👏")


if __name__ == "__main__":
    unittest.main()
