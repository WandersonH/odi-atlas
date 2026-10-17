import csv, gzip, json, os, sys, tempfile, unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import collect_kwai_apify as k

RAIZ = Path(__file__).resolve().parents[1]


class TestKwai(unittest.TestCase):
    def test_main(self):
        def fake(payload, cap):
            self.assertEqual(payload["profileHandles"], ["Lulaoficial", "podeespalhar", "FlavioBolsonaro"])
            return ({"id": "r", "status": "SUCCEEDED", "chargedEventCounts": {}},
                    [{"recordType": "profile", "handle": "podeespalhar", "url": "https://www.kwai.com/@podeespalhar", "followers": 1000, "displayName": "PE"},
                     {"recordType": "video", "videoId": "v1", "url": "https://www.kwai.com/@podeespalhar/video/v1", "caption": "Vote 13 &eacute;", "uploadTime": 1789000000,
                      "viewCount": 100, "likeCount": 10, "commentCount": 1, "shareCount": 2},
                     {"type": "video", "videoId": "v2", "authorHandle": "outro", "caption": "x", "viewCount": 1}])
        cwd = os.getcwd()
        with tempfile.TemporaryDirectory() as t:
            (Path(t) / "data/config").mkdir(parents=True)
            (Path(t) / "data/config/kwai.json").write_text((RAIZ / "data/config/kwai.json").read_text(encoding="utf-8"), encoding="utf-8")
            os.chdir(t)
            try:
                self.assertEqual(k.main(["--teste"], executar=fake), 0)
                seg = Path("data/seguidores/kwai_latest.csv").read_text(encoding="utf-8")
                rows = list(csv.DictReader(gzip.open("data/kwai/videos.csv.gz", "rt", encoding="utf-8"), delimiter=";"))
                perf = list(csv.DictReader(open("data/kwai/perfis.csv", encoding="utf-8"), delimiter=";"))
                man = json.loads(Path("data/kwai/manifesto_latest.json").read_text(encoding="utf-8"))
            finally:
                os.chdir(cwd)
        self.assertEqual([r["video_id"] for r in rows], ["v1"])  # perfil não monitorado fica fora
        self.assertEqual((rows[0]["perfil"], rows[0]["visualizacoes"], rows[0]["publicado_em"][:10], rows[0]["legenda"]), ("podeespalhar", "100", "2026-09-10", "Vote 13 é"))
        self.assertEqual(perf[0]["seguidores"], "1000")
        self.assertEqual(man["videos_novos"], 1)
        self.assertIn("Kwai;https://www.kwai.com/u/@podeespalhar/Cu4CfgOx;1000", seg)  # URL declarada ao TSE, para casar com o card


if __name__ == "__main__":
    unittest.main()
