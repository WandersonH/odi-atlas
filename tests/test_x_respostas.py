import json, os, sys, tempfile, unittest, csv, gzip
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import collect_x_respostas as xr

RAIZ = Path(__file__).resolve().parents[1]


class TestXRespostas(unittest.TestCase):
    def test_linha(self):
        r = xr.linha({"id": "9", "inReplyToId": "5", "conversationId": "5", "text": "oi  tudo", "createdAt": "Wed Oct 15 12:00:00 +0000 2026",
                      "author": {"id": "77", "userName": "fulano"}, "likeCount": 3}, {"candidate_id": "1", "handle": "H"}, "t")
        self.assertEqual((r["video_id"], r["autor_canal"], r["texto"], r["publicado_em"]), ("5", "77", "oi tudo", "2026-10-15T12:00:00Z"))

    def test_main_amostra_igual_e_teto(self):
        pedidos = []

        def fake(pl, cap):
            pedidos.append(pl)
            termo = pl["searchTerms"][0]
            return {"id": "r"}, [{"id": f"{termo}-{i}", "inReplyToId": "1", "text": "x", "createdAt": "2026-07-20T10:00:00.000Z",
                                  "author": {"id": str(i)}} for i in range(min(3, pl["maxItems"]))]
        cwd = os.getcwd()
        with tempfile.TemporaryDirectory() as t:
            (Path(t) / "data/config").mkdir(parents=True)
            cfg = json.loads((RAIZ / "data/config/x_respostas.json").read_text(encoding="utf-8"))
            cfg.update(desde="2026-07-20", teto_total_usd=0.05)
            (Path(t) / "data/config/x_respostas.json").write_text(json.dumps(cfg), encoding="utf-8")
            os.environ["ODI_INTERNO_DIR"] = str(Path(t) / "interno")
            os.chdir(t)
            try:
                self.assertEqual(xr.main([], executar=fake), 0)
                man = json.loads(Path("data/x/respostas/manifesto_latest.json").read_text(encoding="utf-8"))
                n = sum(1 for _ in csv.DictReader(gzip.open(Path(t) / "interno/x/respostas/respostas.csv.gz", "rt"), delimiter=";"))
            finally:
                os.chdir(cwd)
                del os.environ["ODI_INTERNO_DIR"]
        self.assertLessEqual(man["custo_usd"], 0.05)
        lula = sum(1 for p in pedidos if "LulaOficial" in p["searchTerms"][0])
        flav = sum(1 for p in pedidos if "FlavioBolsonaro" in p["searchTerms"][0])
        self.assertEqual(lula, flav)
        self.assertGreater(n, 0)
        self.assertIn("filter:replies", pedidos[0]["searchTerms"][0])


if __name__ == "__main__":
    unittest.main()
