import sys, unicodedata, unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import build_conteudo as bc
import chd_reinert as chd


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
        self.assertNotIn("heart", chd.tokens("Lula [heart] presidente do brasil"))


if __name__ == "__main__":
    unittest.main()
