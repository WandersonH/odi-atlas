import os, sys, tempfile, unittest, shutil
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import collect_whatsapp_canais as wc

RAIZ = Path(__file__).resolve().parents[1]


class TestWhatsAppCanais(unittest.TestCase):
    def test_numero(self):
        self.assertEqual(wc.numero("Canal • 1,2 mi seguidores"), 1_200_000)
        self.assertEqual(wc.numero("Channel • 1.2M followers"), 1_200_000)
        self.assertEqual(wc.numero("35.401 seguidores"), 35401)
        self.assertEqual(wc.numero("12K followers"), 12000)
        self.assertEqual(wc.numero("459 mil seguidores"), 459000)
        self.assertIsNone(wc.numero("sem contagem"))

    def test_canais_reais_e_main(self):
        cs = wc.canais(RAIZ)
        self.assertTrue(any(c["canal"] == "0029VaDH1GU7DAWpJTrCXH39" for c in cs))
        self.assertTrue(any(c["canal"] is None for c in cs))  # link de grupo não é canal
        pag = '<meta property="og:title" content="Lula"><meta property="og:description" content="Canal do WhatsApp &#xb7; 1,5 mi seguidores">'
        cwd = os.getcwd()
        with tempfile.TemporaryDirectory() as t:
            (Path(t) / "data/tse").mkdir(parents=True)
            shutil.copy(RAIZ / "data/tse/redes_sociais_candidatos_2026.csv.gz", Path(t) / "data/tse/")
            os.chdir(t)
            try:
                self.assertEqual(wc.main([], baixar=lambda u: (200, pag)), 0)
                txt = Path("data/seguidores/whatsapp_latest.csv").read_text(encoding="utf-8")
            finally:
                os.chdir(cwd)
        self.assertIn("WhatsApp;https://whatsapp.com/channel/0029VaDH1GU7DAWpJTrCXH39;1500000", txt)


if __name__ == "__main__":
    unittest.main()
