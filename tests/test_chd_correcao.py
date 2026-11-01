"""CHD de Reinert (correção de 01/11/2026): o corte não é empurrado até o tamanho mínimo; grupos pequenos não viram classe."""
import random
import sys
import unittest
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import chd_reinert as cr  # noqa: E402


def corpus():
    rnd = random.Random(7)
    temas = [["urna", "voto", "fraude", "eleicao", "apuracao", "tse"],
             ["preco", "gasolina", "mercado", "inflacao", "salario", "comida"],
             ["escola", "professor", "aluno", "aula", "educacao", "creche"]]
    segs = [" ".join(rnd.sample(t, 4)) for t in temas for _ in range(80)]
    segs += ["zebra girafa elefante"] * 4  # 4 segmentos repetidos com vocabulário exclusivo (como cópias de spam)
    return segs


class TestChdCorrecao(unittest.TestCase):
    def setUp(self):
        self.X, self.voc = cr.matriz(corpus())

    def test_tres_temas_sem_classe_no_piso(self):
        rot, arvore = cr.chd(self.X, k=6, min_classe=24)
        tamanhos = sorted(int((rot == k).sum()) for k in set(rot.tolist()) if k > 0)
        self.assertGreaterEqual(len(tamanhos), 3)
        self.assertFalse(tamanhos.count(24) > 1, f"classes no tamanho mínimo: {tamanhos}")

    def test_grupo_pequeno_nao_vira_classe(self):
        rot, arvore = cr.chd(self.X, k=6, min_classe=24)
        self.assertTrue(all(r == -1 for r in rot[-4:]), "os 4 segmentos isolados deveriam ficar não classificados")
        self.assertTrue(any(n.get("eliminado") for n in arvore))

    def test_aproveitamento(self):
        rot, _ = cr.chd(self.X, k=6, min_classe=24)
        a = cr.aproveitamento(rot, len(rot))
        self.assertEqual(a["minimo_pct"], 75.0)
        self.assertTrue(a["atinge_minimo"])
        self.assertLessEqual(a["pct_classificados"], 100 * 240 / 244 + 0.1)


if __name__ == "__main__":
    unittest.main()
