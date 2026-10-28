import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import bolhas_apoio as b  # noqa: E402


class TestClassificar(unittest.TestCase):
    def test_lados(self):
        self.assertEqual(b.classificar("Meu voto é Lula, sem dúvida")[0], "lula")
        self.assertEqual(b.classificar("Vou de 22 no domingo!")[0], "flavio")
        self.assertEqual(b.classificar("Declaro meu voto no segundo turno para Flávio Bolsonaro")[0], "flavio")
        self.assertEqual(b.classificar("Tô com Lula #Lula13")[0], "lula")
        self.assertEqual(b.classificar("vou anular meu voto")[0], "nulo")

    def test_negacao_e_ambiguidade(self):
        self.assertIsNone(b.classificar("Eu nunca vou votar no Lula")[0])
        self.assertIsNone(b.classificar("Jamais voto no Flávio")[0])
        self.assertEqual(b.classificar("Ontem eu disse meu voto é Lula; hoje digo: vou de 22")[0], "ambiguo")
        self.assertIsNone(b.classificar("Ciro e Lula no segundo turno de 2002")[0])
        self.assertIsNone(b.classificar("Lula e Flávio disputam o segundo turno")[0])

    def test_auxiliares(self):
        self.assertEqual(b.faixa(150000), "100 mil–500 mil")
        self.assertEqual(b.faixa(12_000_000), "10 mi+")
        self.assertIsNone(b.faixa(99999))
        self.assertEqual(b.semana("2026-10-26T01:00:00Z"), "2026-10-19")  # 25/10 22h em Brasília, semana de 19/10
        self.assertEqual(b.handle("https://www.instagram.com/fulano_x/?hl=pt", "instagram"), "fulano_x")
        self.assertEqual(b.handle("HTTPS://X.COM/@Fulano", "x"), "fulano")
        self.assertIsNone(b.handle("https://www.instagram.com/p/abc/", "instagram"))
        self.assertIsNone(b.handle("https://www.instagram.com/channel/AbC", "instagram"))

    def test_sinal_mdb_por_uf(self):
        cfg = {"partidos": {"MDB": {"posicao": "por_uf", "nota": "", "fontes": [], "lula_ufs": ["BA"], "demais_ufs": "flavio"}}}
        self.assertEqual(b.sinal("MDB", "BA", cfg)[0], "lula")
        self.assertEqual(b.sinal("MDB", "SP", cfg)[0], "flavio")
        self.assertEqual(b.sinal("XYZ", "SP", cfg)[0], "sem_fonte")


if __name__ == "__main__":
    unittest.main()
