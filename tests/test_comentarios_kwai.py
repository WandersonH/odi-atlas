import csv, gzip, json, os, sys, tempfile, unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import collect_comentarios_kwai as k

RAIZ = Path(__file__).resolve().parents[1]


class TestComentariosKwai(unittest.TestCase):
    def test_teste_e_carga(self):
        visto = []

        def fake(payload, cap):
            visto.append((payload, cap))
            return ({"id": "r", "status": "SUCCEEDED", "chargedEventCounts": {}},
                    [{"id": "v1", "comments": [{"id": "c1", "text": "  bom  vídeo ", "likeCount": 3, "createTime": 1789000000,
                                                "author": {"id": "u1", "name": "Fulano"}}]},
                     {"id": "c2", "authorId": 7, "authorName": "Beltrana", "content": "outro  formato", "timestamp": 1789000000000,
                      "likedCount": 1, "replyToCommentId": None, "replyCount": 0, "videoId": "v1"},
                     {"id": "x9", "author": {"username": "Lulaoficial"}, "createTime": "2026-10-01T00:00:00Z"}])
        cwd = os.getcwd()
        with tempfile.TemporaryDirectory() as t, tempfile.TemporaryDirectory() as priv:
            (Path(t) / "data/config").mkdir(parents=True)
            (Path(t) / "data/kwai").mkdir(parents=True)
            (Path(t) / "data/config/kwai_comentarios.json").write_text((RAIZ / "data/config/kwai_comentarios.json").read_text(encoding="utf-8"), encoding="utf-8")
            with gzip.open(Path(t) / "data/kwai/videos.csv.gz", "wt", encoding="utf-8") as f:
                w = csv.DictWriter(f, ["candidate_id", "perfil", "video_id", "url", "publicado_em", "comentarios"], delimiter=";")
                w.writeheader()
                w.writerow({"candidate_id": "280002551544", "perfil": "FlavioBolsonaro", "video_id": "v1",
                            "url": "https://www.kwai.com/@FlavioBolsonaro/video/v1", "publicado_em": "2026-09-01T00:00:00Z", "comentarios": "500"})
                w.writerow({"candidate_id": "280002551544", "perfil": "FlavioBolsonaro", "video_id": "v0",
                            "url": "u0", "publicado_em": "2026-01-01T00:00:00Z", "comentarios": "9"})
            os.chdir(t)
            os.environ["ODI_INTERNO_DIR"] = priv
            try:
                self.assertEqual(k.main(["--teste"], executar=fake), 0)
                man = json.loads(Path("data/kwai/comentarios/manifesto_latest.json").read_text(encoding="utf-8"))
                rows = list(csv.DictReader(gzip.open(Path(priv) / "kwai/comentarios/comentarios.csv.gz", "rt", encoding="utf-8"), delimiter=";"))
                pub = "".join(p.read_text(encoding="utf-8") for p in Path("data/kwai/comentarios").glob("*.json"))
                self.assertEqual(k.main([], executar=fake), 0)  # carga: v1 já lido → nada pendente
                man2 = json.loads(Path("data/kwai/comentarios/manifesto_latest.json").read_text(encoding="utf-8"))
            finally:
                os.chdir(cwd)
                del os.environ["ODI_INTERNO_DIR"]
        cfg = json.loads((RAIZ / "data/config/kwai_comentarios.json").read_text(encoding="utf-8"))
        payload, cap = visto[0]
        self.assertEqual(payload["urls"][0], "https://www.kwai.com/video/v1")  # vídeo de janeiro fica fora; formato /video/ID
        self.assertEqual(len(payload["urls"]), 1 + len(cfg["teste"]["perfis"]))
        self.assertEqual(cap, cfg["teto_teste_usd"])
        self.assertEqual((rows[0]["comment_id"], rows[0]["texto"], rows[0]["autor_nome"], rows[0]["publicado_em"][:10]), ("c1", "bom vídeo", "Fulano", "2026-09-10"))
        self.assertEqual((rows[1]["comment_id"], rows[1]["texto"], rows[1]["autor_nome"], rows[1]["tipo"]), ("c2", "outro formato", "Beltrana", "comentario"))
        self.assertNotIn("Fulano", pub)
        self.assertNotIn("Beltrana", pub)  # nome e texto só no privado
        self.assertNotIn("bom vídeo", pub)
        self.assertGreater(man["custo_usd"], 0)  # estimativa pela tabela quando a Apify não informa
        self.assertEqual(man["itens_fora_da_lista"][0]["autor"], "Lulaoficial")
        self.assertEqual(len(visto), 1)
        self.assertEqual(man2["status"], "ok · nada pendente")


if __name__ == "__main__":
    unittest.main()
