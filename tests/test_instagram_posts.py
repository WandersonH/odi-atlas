import json, os, sys, tempfile, unittest, shutil, csv, gzip
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import collect_instagram_posts as ig

RAIZ = Path(__file__).resolve().parents[1]


class TestInstagramPosts(unittest.TestCase):
    def test_perfis(self):
        ps = ig.perfis(RAIZ, {"comitepopularoficial"})
        nomes = [p["perfil"] for p in ps]
        self.assertEqual(nomes[:2], ["lulaoficial", "flaviobolsonaro"])     # principais primeiro, Lula antes
        self.assertNotIn("comitepopularoficial", nomes)
        self.assertNotIn("fernandohaddadoficial", nomes)                     # candidato a governador não entra
        self.assertEqual(next(p for p in ps if p["perfil"] == "geraldoalckmin_")["candidato"], "Lula")  # vice na chapa do titular

    def test_entrada_por_ator(self):
        self.assertEqual(ig.entrada("esdrasdw~instagram-content-scraper", "lulaoficial", 5, "2026-07-20")["onlyPostsNewerThan"], "2026-07-20")
        self.assertIn("startUrls", ig.entrada("apidojo~instagram-scraper", "lulaoficial", 5, "2026-07-20"))

    def test_main(self):
        itens = [{"shortCode": "ABC", "caption": "Educação  é futuro", "timestamp": "2026-08-01T10:00:00.000Z", "likesCount": 10,
                  "commentsCount": 2, "videoPlayCount": 100, "type": "Video", "displayUrl": "https://x/img.jpg"},
                 {"shortCode": "OLD", "caption": "antigo", "timestamp": "2026-01-01T10:00:00.000Z", "likesCount": -1},
                 {"demo": True, "shortCode": "D"}]
        cwd = os.getcwd()
        with tempfile.TemporaryDirectory() as t:
            (Path(t) / "data/tse").mkdir(parents=True)
            (Path(t) / "data/config").mkdir(parents=True)
            shutil.copy(RAIZ / "data/tse/redes_sociais_candidatos_2026.csv.gz", Path(t) / "data/tse/")
            shutil.copy(RAIZ / "data/config/instagram_posts.json", Path(t) / "data/config/")
            os.chdir(t)
            try:
                self.assertEqual(ig.main(["--teste"], executar=lambda pl, cap: ({"id": "r"}, itens)), 0)
                rows = list(csv.DictReader(gzip.open("data/instagram/videos.csv.gz", "rt", encoding="utf-8"), delimiter=";"))
                man = json.loads(Path("data/instagram/manifesto_latest.json").read_text(encoding="utf-8"))
            finally:
                os.chdir(cwd)
        self.assertEqual(len(rows), 1)                                   # fora do período e demonstração descartados
        r = rows[0]
        self.assertEqual((r["video_id"], r["legenda"], r["visualizacoes"], r["tipo"], r["candidate_id"]), ("ABC", "Educação é futuro", "100", "vídeo", "280002542548"))
        self.assertLessEqual(man["custo_usd"], 0.05)

    def test_conta1_diario_e_lacuna_com_teto_estrito(self):
        import datetime as dt
        hoje = dt.date.today().isoformat()
        caps = []

        def fake(pl, cap):
            caps.append((pl.get("resultsType"), cap, len(pl["directUrls"])))
            if pl.get("resultsType") == "reels":
                return {"id": "r2", "usageTotalUsd": 0.01}, [{"shortCode": "N1", "videoPlayCount": 500}]
            return {"id": "r1", "usageTotalUsd": 0.02}, [
                {"shortCode": "N1", "ownerUsername": "lulaoficial", "caption": "hoje", "timestamp": hoje + "T10:00:00.000Z", "likesCount": 5},
                {"shortCode": "X9", "ownerUsername": "desconhecido", "timestamp": hoje + "T10:00:00.000Z"}]
        cwd = os.getcwd()
        with tempfile.TemporaryDirectory() as t:
            (Path(t) / "data/tse").mkdir(parents=True)
            (Path(t) / "data/config").mkdir(parents=True)
            shutil.copy(RAIZ / "data/tse/redes_sociais_candidatos_2026.csv.gz", Path(t) / "data/tse/")
            shutil.copy(RAIZ / "data/config/instagram_posts.json", Path(t) / "data/config/")
            os.chdir(t)
            try:
                self.assertEqual(ig.main(["--diario"], executar=fake), 0)
                man = json.loads(Path("data/instagram/manifesto_latest.json").read_text(encoding="utf-8"))
                rows = list(csv.DictReader(gzip.open("data/instagram/videos.csv.gz", "rt", encoding="utf-8"), delimiter=";"))
                ig.main(["--lacuna"], executar=fake)
                lac = json.loads(Path("data/instagram/manifesto_latest.json").read_text(encoding="utf-8"))
            finally:
                os.chdir(cwd)
        cfg = json.loads((RAIZ / "data/config/instagram_posts.json").read_text(encoding="utf-8"))
        self.assertEqual((man["modo"], man["conta"]), ("diário", "APIFY_TOKEN"))
        self.assertLessEqual(caps[0][1], 0.10)
        self.assertLessEqual(0.02 + caps[1][1], cfg["diario"]["teto_dia_usd"] + 1e-9)   # custo real da 1ª + teto da 2ª cabem no teto do dia
        self.assertGreater(caps[0][2], 1)                                                     # uma execução para todos os perfis
        self.assertEqual([r["video_id"] for r in rows], ["N1"])                               # perfil fora da lista é descartado
        self.assertEqual(rows[0]["visualizacoes"], "500")
        self.assertLessEqual(man["custo_usd"], cfg["diario"]["teto_dia_usd"])
        self.assertEqual((lac["modo"], lac["desde"]), ("lacuna", cfg["lacuna"]["desde"]))
        self.assertLessEqual(0.02 + caps[3][1], cfg["lacuna"]["teto_usd"] + 1e-9)
        self.assertLessEqual(lac["custo_usd"], cfg["lacuna"]["teto_usd"])


if __name__ == "__main__":
    unittest.main()
