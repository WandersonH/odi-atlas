import sys, unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import collect_youtube as cy

RAIZ = Path(__file__).resolve().parents[1]


class TestCorrecoes(unittest.TestCase):
    def test_augusto_cury_usa_canal_corrigido_e_mantem_url_do_tse(self):
        t = next(x for x in cy.load_targets(RAIZ) if "CURY" in x["candidate_name"])
        self.assertEqual(t["ref"], ("handle", "@AugustoCury"))
        self.assertTrue(t["url"].upper().startswith("HTTPS://WWW.YOUTUBE.COM/CHANNEL/"))


if __name__ == "__main__":
    unittest.main()
