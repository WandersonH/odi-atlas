import sys, unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import collect_checagens as cc


class TestChecagens(unittest.TestCase):
    def test_achatar_e_juntar(self):
        claims = [{"text": "Flávio disse que X", "claimant": "Flávio Bolsonaro", "claimDate": "2026-10-18T23:00:00Z",
                   "claimReview": [{"publisher": {"name": "Agência A", "site": "a.com"}, "url": "https://a.com/1",
                                    "title": "É falso que X", "reviewDate": "2026-10-19T02:00:00Z", "textualRating": "Falso", "languageCode": "pt"}]},
                  {"text": "Lula afirmou Y", "claimant": "Lula", "claimDate": "2026-09-01T00:00:00Z",
                   "claimReview": [{"publisher": {"name": "Agência B"}, "url": "https://b.com/2", "reviewDate": "2026-09-02T00:00:00Z", "textualRating": "Enganoso"}]}]
        a = cc.achatar(claims, "Lula")
        b = cc.achatar(claims[:1], "debate Band")
        itens = cc.juntar(a + b)
        self.assertEqual(len(itens), 2)
        primeiro = itens[0]
        self.assertEqual(primeiro["url"], "https://a.com/1")
        self.assertEqual(primeiro["consulta"], ["Lula", "debate Band"])
        self.assertTrue(primeiro["desde_o_debate"])
        self.assertEqual(primeiro["candidatos"], ["Flávio Bolsonaro"])
        self.assertFalse(itens[1]["desde_o_debate"])
        self.assertEqual(itens[1]["candidatos"], ["Lula"])


if __name__ == "__main__":
    unittest.main()
