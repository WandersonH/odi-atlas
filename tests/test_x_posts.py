import csv, gzip, json, os, sys, tempfile, unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import collect_x_posts as cx

RAIZ = Path(__file__).resolve().parents[1]


class TestX(unittest.TestCase):
    def test_teste(self):
        pedidos = []

        def fake(payload, cap):
            pedidos.append((payload, cap))
            return ({"id": "r", "status": "SUCCEEDED", "chargedEventCounts": {}},
                    [{"type": "tweet", "id": "1", "url": "https://x.com/LulaOficial/status/1", "text": "Vote  13", "createdAt": "Wed Sep 02 12:00:00 +0000 2026",
                      "likeCount": 10, "replyCount": 2, "retweetCount": 3, "quoteCount": 1, "viewCount": 1000, "author": {"userName": "LulaOficial", "followers": 9000000}},
                     {"type": "tweet", "id": "2", "text": "repost de outro", "createdAt": "Wed Sep 02 12:00:00 +0000 2026", "author": {"userName": "outro", "followers": 5}},
                     {"type": "tweet", "id": "3", "text": "antigo", "createdAt": "Mon Jul 06 12:00:00 +0000 2026", "author": {"userName": "LulaOficial", "followers": 9000000}}])
        cfg = json.loads((RAIZ / "data/config/x_posts.json").read_text(encoding="utf-8"))
        cwd = os.getcwd()
        with tempfile.TemporaryDirectory() as t:
            (Path(t) / "data/config").mkdir(parents=True)
            (Path(t) / "data/config/x_posts.json").write_text(json.dumps(cfg), encoding="utf-8")
            os.chdir(t)
            try:
                self.assertEqual(cx.main(["--teste"], executar=fake), 0)
                rows = list(csv.DictReader(gzip.open("data/x/videos.csv.gz", "rt", encoding="utf-8"), delimiter=";"))
                seg = Path("data/seguidores/x_latest.csv").read_text(encoding="utf-8")
            finally:
                os.chdir(cwd)
        self.assertEqual(pedidos[0][0], {"twitterHandles": ["LulaOficial"], "start": "2026-07-20", "maxItems": 20, "sort": "Latest"})
        self.assertEqual([r["video_id"] for r in rows], ["1"])  # repost de outro perfil e post antigo ficam fora
        self.assertEqual((rows[0]["legenda"], rows[0]["publicado_em"], rows[0]["compartilhamentos"]), ("Vote 13", "2026-09-02T12:00:00Z", "4"))
        self.assertIn("X / Twitter;HTTPS://X.COM/LULAOFICIAL;9000000", seg)  # URL declarada ao TSE, para casar com o card


if __name__ == "__main__":
    unittest.main()
