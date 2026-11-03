import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import build_correlacoes as bc  # noqa: E402


class TestCorrelacoes(unittest.TestCase):
    def test_pearson_e_postos(self):
        self.assertEqual(bc.pearson([1, 2, 3, 4], [2, 4, 6, 8]), 1.0)
        self.assertEqual(bc.pearson([1, 2, 3, 4], [8, 6, 4, 2]), -1.0)
        self.assertIsNone(bc.pearson([1, 1, 1], [1, 2, 3]))
        self.assertEqual(bc.postos([10, 20, 20, 5]), [2, 3.5, 3.5, 1])

    def test_dentro_da_uf_tira_efeito_regional(self):
        # duas UFs com níveis diferentes e relação negativa dentro de cada uma
        linhas = [{"uf": "A", "x": x, "y": 10 - x} for x in (1, 2, 3)] + [{"uf": "B", "x": x, "y": 30 - x} for x in (11, 12, 13)]
        c = bc.correlacoes(linhas, "x", "y")
        self.assertGreater(c["pearson"], 0.9)
        self.assertEqual(c["dentro_uf"], -1.0)
        self.assertEqual(c["n"], 6)


if __name__ == "__main__":
    unittest.main()
