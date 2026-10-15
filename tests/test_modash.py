"""Leitor de relatórios Modash. O texto abaixo é FICTÍCIO (perfil @exemplo), só reproduz a diagramação do pdftotext -layout."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import extrair_modash as em  # noqa: E402

TXT = """                                                     powered by


Perfil Exemplo
@exemplo
Business account • Cidade, Brazil
Followers                         Avg. likes                     Engagement rate
2.5M 1.00%                        10.2k 2.00%                    0.50%
Popular posts

Followers

Followers                                                         2.5M
Fake followers                    20.00%

Audience breakdown
Real people                                                       50.00%
Suspicious accounts               10.00%

Audience reachability
<500 accounts                     30.00%
500-1k accounts                   20.00%
1k-1.5k accounts                  10.00%
>1.5k accounts                    40.00%

Followers growth

Content

Average likes                                                      10.2k
Fake likers                       5.00%

All content
Engagement rate                   0.50% below average for creators this size
Estimated impressions                                              1.2M
Average likes                                                      10.2k
Average comments                                       900

Reels
Engagement rate                   0.40%
Average reel plays                                                 300k
Average likes                                                      9k
Average comments                                       800
Average shares                                         100

Collaborations
Paid engagement                                       50.00%

Engagement rate distribution

Audience data by followers

Gender
Female                            60.00%
Male                              40.00%

Age
13-17                             1.00%
18-24                             19.00%
25-34                             40.00%
35-44                             25.00%
45-64                             15.00%

Countries
Brazil                            97.50%

Audience data by likers

Popular hashtags                                Popular mentions
#tema                             50.00%        @aliado                     25.00%
#outro                            10.00%

Gender split
Gender                            Likers                     Followers
Female                            600 / 55.00%               1,500,000 / 60.00%
Male                              490 / 45.00%               1,000,000 / 40.00%

Age split
Age                               Likers                     Followers
13-17                             -                          25,000 / 1.00%
18-24                             100 / 10.00%               475,000 / 19.00%
"""


class TestModash(unittest.TestCase):
    def test_numero(self):
        self.assertEqual(em.numero("5.9M"), 5_900_000)
        self.assertEqual(em.numero("925.5k"), 925_500)
        self.assertEqual(em.numero("132"), 132)
        self.assertEqual(em.numero("18.40%"), 18.4)
        self.assertIsNone(em.numero("abc"))

    def test_nomes(self):
        self.assertEqual(em.data_do_arquivo("report-lulaoficial-Oct-15-2026-2.pdf"), "2026-10-15")
        self.assertEqual(em.nome_original("396b57cc-report-flaviobolsonaro-Oct-15-2026.pdf"), "report-flaviobolsonaro-Oct-15-2026.pdf")
        self.assertEqual(em.nome_original("report-x-Oct-1-2026.pdf"), "report-x-Oct-1-2026.pdf")

    def test_parse(self):
        p = em.parse(TXT)
        self.assertEqual(p["platform"], "Instagram")
        self.assertEqual((p["name"], p["handle"]), ("Perfil Exemplo", "@exemplo"))
        self.assertEqual(p["followers"], 2_500_000)
        self.assertEqual((p["engagement"], p["avg_likes"], p["avg_comments"], p["impressions"]), (0.5, 10_200, 900, 1_200_000))
        self.assertEqual(p["engagement_comparison"], "below average for creators this size")
        self.assertEqual((p["fake_followers"], p["fake_likers"]), (20.0, 5.0))
        self.assertEqual(p["reachability"], [30.0, 20.0, 10.0, 40.0])
        self.assertEqual(p["audience_breakdown"], {"Real people": 50.0, "Suspicious accounts": 10.0})
        self.assertEqual(p["reels"], {"engagement": 0.4, "views": 300_000, "likes": 9_000, "comments": 800, "shares": 100})
        self.assertEqual(p["ages"]["25–34"], 40.0)
        self.assertEqual((p["female"], p["brazil"]), (60.0, 97.5))
        self.assertEqual(p["hashtags"], [["#tema", 50.0], ["#outro", 10.0]])
        self.assertEqual(p["mentions"], [["@aliado", 25.0]])
        self.assertEqual(p["likers"]["female"], 55.0)
        self.assertEqual(p["likers"]["ages"][:2], [None, 10.0])
        self.assertEqual(p["tabelas"]["genero"][0]["followers"], {"n": 1_500_000, "pct": 60.0})

    def test_historico_e_comparacao(self):
        dic = {"followers": ["Seguidores", "contas", ""], "engagement": ["Engajamento", "%", ""], "female": ["F", "%", ""]}
        p = em.parse(TXT)
        h1 = em.historico(p, "ig_x", "2026-10-10", "a.pdf", dic)
        self.assertEqual({r["metric"] for r in h1}, {"followers", "engagement", "female"})
        h2 = [dict(r, value=2_600_000 if r["metric"] == "followers" else r["value"]) for r in h1]
        c = em.comparar(h2, h1)
        self.assertEqual((c["indicadores_comparados"], c["iguais"]), (3, 2))
        self.assertEqual(c["mudaram"], [{"metric": "followers", "antes": 2_500_000, "depois": 2_600_000}])

    def test_plataforma(self):
        self.assertEqual(em.plataforma("Videos\nShorts\nAverage likes"), "YouTube")
        self.assertEqual(em.plataforma("Average saves 96"), "TikTok")


if __name__ == "__main__":
    unittest.main()
