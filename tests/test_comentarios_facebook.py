import csv, gzip, json, os, sys, tempfile, unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import collect_comentarios_facebook as cf

RAIZ = Path(__file__).resolve().parents[1]


class TestComentariosFacebook(unittest.TestCase):
    def test_teste(self):
        def fake(payload, cap):
            return ({"id": "r", "status": "SUCCEEDED", "chargedEventCounts": {}},
                    [{"commentId": "c1", "text": "  boa  ", "profileName": "Fulana", "profileId": "9", "likesCount": "3", "date": "2026-09-02T10:00:00.000Z",
                      "inputUrl": "https://www.facebook.com/lula/posts/p1/"}])
        cwd = os.getcwd()
        with tempfile.TemporaryDirectory() as t, tempfile.TemporaryDirectory() as priv:
            (Path(t) / "data/config").mkdir(parents=True)
            (Path(t) / "data/facebook").mkdir(parents=True)
            (Path(t) / "data/config/facebook_comentarios.json").write_text((RAIZ / "data/config/facebook_comentarios.json").read_text(encoding="utf-8"), encoding="utf-8")
            with gzip.open(Path(t) / "data/facebook/videos.csv.gz", "wt", encoding="utf-8") as f:
                w = csv.DictWriter(f, ["candidate_id", "perfil", "video_id", "url", "publicado_em", "comentarios"], delimiter=";")
                w.writeheader()
                w.writerow({"candidate_id": "280002542548", "perfil": "lula", "video_id": "p1", "url": "https://www.facebook.com/lula/posts/p1",
                            "publicado_em": "2026-09-01T00:00:00Z", "comentarios": "40"})
            os.chdir(t)
            os.environ["ODI_INTERNO_DIR"] = priv
            try:
                self.assertEqual(cf.main(["--teste"], executar=fake), 0)
                rows = list(csv.DictReader(gzip.open(Path(priv) / "facebook/comentarios/comentarios.csv.gz", "rt", encoding="utf-8"), delimiter=";"))
                pub = "".join(p.read_text(encoding="utf-8") for p in Path("data/facebook/comentarios").glob("*.json"))
            finally:
                os.chdir(cwd)
                del os.environ["ODI_INTERNO_DIR"]
        self.assertEqual((rows[0]["comment_id"], rows[0]["texto"], rows[0]["video_id"], rows[0]["autor_nome"]), ("c1", "boa", "p1", "Fulana"))
        self.assertNotIn("Fulana", pub)


if __name__ == "__main__":
    unittest.main()
