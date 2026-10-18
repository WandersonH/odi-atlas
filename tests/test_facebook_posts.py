import csv, gzip, json, os, sys, tempfile, unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import collect_facebook_posts as fb

RAIZ = Path(__file__).resolve().parents[1]


class TestFacebook(unittest.TestCase):
    def test_teste_e_carga(self):
        pedidos = []

        def fake(payload, cap):
            pedidos.append((payload, cap))
            return ({"id": "r", "status": "SUCCEEDED", "chargedEventCounts": {}},
                    [{"postId": "p1", "url": "https://www.facebook.com/lula/posts/p1", "text": "Vote 13  pelo Brasil", "time": "2026-09-01T12:00:00.000Z",
                      "likes": 100, "comments": 10, "shares": 5},
                     {"postId": "p0", "text": "antigo", "time": "2026-07-01T00:00:00.000Z", "likes": 1}])
        cfg = json.loads((RAIZ / "data/config/facebook_posts.json").read_text(encoding="utf-8"))
        cwd = os.getcwd()
        with tempfile.TemporaryDirectory() as t:
            (Path(t) / "data/config").mkdir(parents=True)
            (Path(t) / "data/config/facebook_posts.json").write_text(json.dumps(cfg), encoding="utf-8")
            os.chdir(t)
            try:
                self.assertEqual(fb.main(["--teste"], executar=fake), 0)
                rows = list(csv.DictReader(gzip.open("data/facebook/videos.csv.gz", "rt", encoding="utf-8"), delimiter=";"))
                man = json.loads(Path("data/facebook/manifesto_latest.json").read_text(encoding="utf-8"))
                self.assertEqual(fb.main([], executar=fake), 0)
                man2 = json.loads(Path("data/facebook/manifesto_latest.json").read_text(encoding="utf-8"))
            finally:
                os.chdir(cwd)
        self.assertEqual(pedidos[0][0], {"startUrls": [{"url": "https://www.facebook.com/lula"}], "resultsLimit": 10, "onlyPostsNewerThan": "2026-08-16"})
        self.assertLessEqual(pedidos[0][1], cfg["teto_teste_usd"])
        self.assertEqual([r["video_id"] for r in rows], ["p1"])  # post de julho fica fora
        self.assertEqual((rows[0]["legenda"], rows[0]["curtidas"], rows[0]["perfil"]), ("Vote 13 pelo Brasil", "100", "lula"))
        self.assertGreater(man["custo_usd"], 0)
        self.assertEqual(len(pedidos), 1 + len(cfg["paginas"]))  # carga: uma execução por página
        self.assertLessEqual(man2["gasto_antes_usd"] + man2["custo_usd"], cfg["teto_total_usd"])


if __name__ == "__main__":
    unittest.main()
