import sys
import unittest
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import collect_tse_auditoria_urna as au  # noqa: E402


class TestAuditoria(unittest.TestCase):
    def test_mais_recente_e_hora(self):
        res = [{"url": "https://x/bweb_2t_AC_261020260742.zip"}, {"url": "https://x/bweb_2t_AC_251020262300.zip"},
               {"url": "https://x/bweb_1t_AC_051020261403.zip"}]
        self.assertTrue(au.mais_recente(res, "bweb", "AC").endswith("261020260742.zip"))
        self.assertIsNone(au.mais_recente(res, "bweb", "SP"))
        self.assertAlmostEqual(au.hora("25/10/2026 17:30:05"), 17.5)
        self.assertIsNone(au.hora(""))

    def test_agregar(self):
        s = lambda comp, sb, l, f, fe: {"aptos": 100, "comp": comp, "sem_bio": sb, "fecha": fe, "votos": Counter({"13": l, "22": f})}  # noqa: E731
        a = au.agregar([s(80, 8, 40, 40, 16.9), s(20, 2, 15, 5, 17.6)])
        self.assertEqual(a["sem_biometria"], 10)
        self.assertEqual(a["pct_sem_biometria_do_comparecimento"], 10.0)
        self.assertEqual(a["pct_lula_validos"], 55.0)
        self.assertEqual(a["encerramento_das_secoes"], {"antes das 17h": 1, "17h30–17h59": 1})
        self.assertEqual(au.pearson([1, 2, 3], [2, 4, 6]), 1.0)


if __name__ == "__main__":
    unittest.main()
