import sys, unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import teste_posicao as tp


class TestPosicao(unittest.TestCase):
    def test_rotulo(self):
        self.assertEqual(tp.rotulo(0.9, 0.2), "favor")
        self.assertEqual(tp.rotulo(0.1, 0.7), "contra")
        self.assertEqual(tp.rotulo(0.4, 0.5), "neutro/incerto")

    def test_amostra_equilibrada(self):
        rows = [{"candidate_id": c, "texto": "x" * 30} for c in (tp.L, tp.F) for _ in range(50)]
        a = tp.amostra(rows, 20, "youtube")
        self.assertEqual(sum(1 for r in a if r["candidate_id"] == tp.L), 10)


if __name__ == "__main__":
    unittest.main()
