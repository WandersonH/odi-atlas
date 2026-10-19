import sys, unicodedata, unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import build_conteudo as bc
try:
    import chd_reinert as chd
except ImportError:  # workflows de coleta sem numpy (ex.: Seguidores Meta): não derrubar a coleta
    chd = None


class TestNormalizacao(unittest.TestCase):
    def test_nfd_nao_parte_palavra(self):
        t = unicodedata.normalize("NFD", "a família do Flávio")
        ts = bc.termos(t, set())
        self.assertIn("familia", ts)
        self.assertIn("flavio", ts)
        self.assertNotIn("fami", ts)
        self.assertNotIn("vio", ts)

    def test_emoji_do_kwai(self):
        self.assertNotIn("heart", bc.termos("Lula [heart][heart_eyes] presidente", set()))
        if chd is None:
            self.skipTest("sem numpy neste workflow")
        self.assertNotIn("heart", chd.tokens("Lula [heart] presidente do brasil"))


class TestRodape(unittest.TestCase):
    def test_rodape_legal_sai(self):
        r = {"channel_id": "c", "titulo": "", "descricao": "Educação pública de qualidade. - Propaganda eleitoral - Coligação Brasil: PSB/PDT/Federação Fé Brasil (PT/PCdoB/PV). CNPJ: 68.475.818/0001-02."}
        t = bc.texto_util(r, {})
        self.assertIn("Educação pública", t)
        self.assertNotIn("CNPJ", t)
        self.assertNotIn("Coligação", t)


if __name__ == "__main__":
    unittest.main()
