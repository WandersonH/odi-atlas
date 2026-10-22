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


    def test_diario_conta1_respeita_teto_do_dia_e_do_mes(self):
        pedidos = []

        def fake(payload, cap):
            pedidos.append((payload, cap))
            n = payload["resultsLimit"]  # devolve o máximo pedido: pior caso de custo
            return ({"id": "r", "usageTotalUsd": None},
                    [{"postId": f"{payload['startUrls'][0]['url'][-6:]}{i}", "text": "x", "time": "2026-10-21T12:00:00.000Z"} for i in range(n)])
        cfg = json.loads((RAIZ / "data/config/facebook_posts.json").read_text(encoding="utf-8"))
        cwd = os.getcwd()
        with tempfile.TemporaryDirectory() as t:
            (Path(t) / "data/config").mkdir(parents=True)
            (Path(t) / "data/config/facebook_posts.json").write_text(json.dumps(cfg), encoding="utf-8")
            os.chdir(t)
            try:
                fb.main(["--diario"], executar=fake)
                man = json.loads(Path("data/facebook/manifesto_latest.json").read_text(encoding="utf-8"))
            finally:
                os.chdir(cwd)
        D = cfg["diario"]
        self.assertEqual(man["modo"], "diário")
        self.assertEqual(man["conta"], "APIFY_TOKEN")
        self.assertLessEqual(man["custo_usd"], D["teto_dia_usd"])
        self.assertTrue(pedidos[0][0]["startUrls"][0]["url"].endswith(("/lula", "/flaviobolsonaro")))  # principais primeiro
        self.assertEqual(pedidos[0][0]["onlyPostsNewerThan"], man["desde"])
        self.assertTrue(any("teto do dia" in (pg["erro"] or "") for pg in man["paginas"]))  # no pior caso, páginas ficam de fora
    def test_lacuna_desde_fixo_e_teto_proprio(self):
        pedidos = []

        def fake(payload, cap):
            pedidos.append(payload)
            return ({"id": "r"}, [{"postId": f"{len(pedidos)}-{i}", "time": "2026-10-19T12:00:00.000Z"} for i in range(payload["resultsLimit"])])
        cfg = json.loads((RAIZ / "data/config/facebook_posts.json").read_text(encoding="utf-8"))
        cwd = os.getcwd()
        with tempfile.TemporaryDirectory() as t:
            (Path(t) / "data/config").mkdir(parents=True)
            (Path(t) / "data/config/facebook_posts.json").write_text(json.dumps(cfg), encoding="utf-8")
            os.chdir(t)
            try:
                fb.main(["--lacuna"], executar=fake)
                man = json.loads(Path("data/facebook/manifesto_latest.json").read_text(encoding="utf-8"))
                n = len(pedidos)
                fb.main(["--lacuna"], executar=fake)  # 2ª vez: o teto já foi gasto, não roda de novo
                man2 = json.loads(Path("data/facebook/manifesto_latest.json").read_text(encoding="utf-8"))
            finally:
                os.chdir(cwd)
        self.assertEqual((man["modo"], man["desde"]), ("lacuna", cfg["lacuna"]["desde"]))
        self.assertLessEqual(man["custo_usd"], cfg["lacuna"]["teto_usd"])
        self.assertLessEqual(man2["gasto_antes_usd"] + (man2.get("custo_usd") or 0), cfg["lacuna"]["teto_usd"] + 1e-9)
        self.assertGreaterEqual(n, 1)

    def test_retroativo_so_paginas_autorizadas_teto_e_pre_campanha(self):
        pedidos = []

        def fake(payload, cap):
            pedidos.append((payload, cap))
            n = payload["resultsLimit"]
            return ({"id": "r", "usageTotalUsd": round(0.001 + 0.005 * n, 4)},
                    [{"postId": f"{len(pedidos)}-{i}", "time": "2026-07-25T12:00:00.000Z"} for i in range(n)])
        cfg = json.loads((RAIZ / "data/config/facebook_posts.json").read_text(encoding="utf-8"))
        cwd = os.getcwd()
        with tempfile.TemporaryDirectory() as t:
            (Path(t) / "data/config").mkdir(parents=True)
            (Path(t) / "data/config/facebook_posts.json").write_text(json.dumps(cfg), encoding="utf-8")
            os.chdir(t)
            try:
                fb.main(["--retroativo"], executar=fake)
                man = json.loads(Path("data/facebook/manifesto_latest.json").read_text(encoding="utf-8"))
                import csv, gzip
                datas = [r["publicado_em"] for r in csv.DictReader(gzip.open("data/facebook/videos.csv.gz", "rt", encoding="utf-8"), delimiter=";")]
            finally:
                os.chdir(cwd)
        self.assertEqual(man["modo"], "retroativo")
        self.assertEqual([p["startUrls"][0]["url"] for p, _ in pedidos], ["https://www.facebook.com/lula", "https://www.facebook.com/flaviobolsonaro"])
        self.assertEqual(pedidos[0][0]["onlyPostsNewerThan"], "2026-07-20")
        self.assertLessEqual(man["custo_usd"], cfg["retroativo"]["teto_usd"] + 1e-9)
        self.assertTrue(datas and all(d[:10] == "2026-07-25" for d in datas))  # pré-campanha fica no acervo


if __name__ == "__main__":
    unittest.main()
