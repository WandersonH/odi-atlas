import gzip
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import build_caso_perfis_exterior as b  # noqa: E402


class TestCaso010(unittest.TestCase):
    def test_categorias(self):
        self.assertIn(b.UNIAO, b.categorias("Salve o Brasil, presidente!"))
        self.assertIn("cita a eleição", b.categorias("A eleição foi fraudada, as urnas"))
        self.assertNotIn(b.UNIAO, b.categorias("God bless America @brasil https://x.com/br/1"))
        self.assertIn("cita Lula, Bolsonaro ou Flávio", b.categorias("Lula ladrão"))

    def test_portugues(self):
        self.assertTrue(b.em_portugues("Obrigado presidente, você é muito importante pra nós"))
        self.assertTrue(b.em_portugues("🇧🇷🇧🇷"))
        self.assertFalse(b.em_portugues("Gracias presidente, usted es muy importante y el pueblo"))
        self.assertFalse(b.em_portugues("Thank you Mr President"))

    def test_resumo(self):
        with tempfile.TemporaryDirectory() as d:
            pasta = Path(d) / "casos/010"
            (pasta / "instagram").mkdir(parents=True)
            with gzip.open(pasta / "bruto_x_1.jsonl.gz", "wt", encoding="utf-8") as f:
                for i, (t, txt) in enumerate([("resp. @realDonaldTrump", "Salve o Brasil"), ("resp. @realDonaldTrump", "Deus abençoe"),
                                              ("posts dos perfis", "Great day")]):
                    f.write(json.dumps({"id": str(i), "_termo": t, "fullText": txt, "createdAt": "2026-10-25T10:00:00Z",
                                        "author": {"userName": "u%d" % i, "followers": 20000}}) + "\n")
            (pasta / "instagram/c.json").write_text(json.dumps({"ator": "datadoping/x", "items": [
                {"comment_id": "1", "text": "Fraude na eleição do Brasil, você viu?", "input_url": "https://www.instagram.com/p/A/"},
                {"comment_id": "2", "text": "Thank you sir", "input_url": "https://www.instagram.com/p/A/"}]}), encoding="utf-8")
            (pasta / "instagram/p.json").write_text(json.dumps({"ator": "apify/instagram-scraper", "items": [
                {"url": "https://www.instagram.com/p/A/", "ownerUsername": "realdonaldtrump", "likesCount": 5}]}), encoding="utf-8")
            cwd = os.getcwd()
            os.chdir(d)
            try:
                with mock.patch.dict(os.environ, {"ODI_INTERNO_DIR": d}):
                    b.main(["--caso", "010"])
                r = json.loads((Path(d) / "data/casos/010/resumo.json").read_text(encoding="utf-8"))
            finally:
                os.chdir(cwd)
            self.assertEqual(r["x"]["total"]["n"], 2)
            self.assertEqual(r["x"]["total"]["categorias"][b.UNIAO]["pct"], 50.0)
            self.assertEqual(len(r["x"]["posts_dos_perfis"]), 1)
            self.assertEqual(r["instagram"]["em_portugues"], 1)
            self.assertEqual(r["instagram"]["por_post"][0]["comentarios_lidos"], 2)
            self.assertNotIn("Deus abençoe", json.dumps(r, ensure_ascii=False))
