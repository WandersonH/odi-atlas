import random
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import intolerancia as it  # noqa: E402


class TestIntolerancia(unittest.TestCase):
    def test_rotulo_positivo(self):
        for r in ("LABEL_1", "Offensive", "Sexism", "Racism", "Ideology"):
            self.assertTrue(it.positivo(r), r)
        for r in ("LABEL_0", "Non-Offensive", "non-hateful", "não ofensivo", "Neutral"):
            self.assertFalse(it.positivo(r), r)

    def test_amostra_estratificada_tamanho_exato(self):
        rows = [{"rede": "x", "id": str(i)} for i in range(90)] + [{"rede": "instagram", "id": f"i{i}"} for i in range(10)]
        s = it.amostra(rows, 20, random.Random(1))
        self.assertEqual(len(s), 20)
        self.assertEqual(sum(1 for r in s if r["rede"] == "x"), 18)
        self.assertEqual(it.amostra(rows[:5], 20, random.Random(1)).__len__(), 5)


if __name__ == "__main__":
    unittest.main()
