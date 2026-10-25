import csv, gzip, json, os, sys, tempfile, unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import build_sentimento_comentarios as b

FASES = [{"id": "t1", "rotulo": "1º", "de": "2026-08-16", "ate": "2026-10-04"}, {"id": "t2", "rotulo": "2º", "de": "2026-10-05", "ate": "2026-10-25"}]


class TestSentimento(unittest.TestCase):
    def test_distrib(self):
        d = b.distrib(["POS", "NEG", "NEG", "NEU"])
        self.assertEqual((d["n"], d["positivo"], d["negativo"], d["saldo"]), (4, 25.0, 50.0, -25.0))
        self.assertEqual(b.distrib([]), {"n": 0})

    @unittest.skipUnless(__import__('importlib').util.find_spec('emoji'), 'emoji não instalado')
    def test_preparar(self):
        t = b.preparar("@fulano vejaaaaaa https://x.com/a 👍")
        self.assertIn("@usuario", t); self.assertIn("url", t); self.assertIn("vejaaa ", t); self.assertNotIn("👍", t)

    def test_agregar_minimo_por_video(self):
        rows = [{"comment_id": str(i), "candidate_id": "A", "video_id": "v1" if i < 3 else "v2",
                 "publicado_em": "2026-10-06T10:00:00Z" if i % 2 else "2026-09-01T10:00:00Z"} for i in range(5)]
        rot = {"0": "POS", "1": "NEG", "2": "POS", "3": "NEU"}  # "4" ainda não classificado
        a = b.agregar(rows, rot, FASES, 3, {"A": "Cand A"})["A"]
        self.assertEqual((a["coletados"], a["n"], a["cobertura_pct"]), (5, 4, 80.0))
        self.assertEqual(a["videos"]["v1"]["n"], 3); self.assertNotIn("insuficiente", a["videos"]["v1"])
        self.assertTrue(a["videos"]["v2"]["insuficiente"])
        f = {x["id"]: x for x in a["fases"]}
        self.assertEqual((f["t1"]["n"], f["t2"]["n"]), (2, 2))

    def test_main_com_cache_e_sem_texto_publico(self):
        with tempfile.TemporaryDirectory() as t:
            root, interno = Path(t) / "r", Path(t) / "i"
            (root / "data/config").mkdir(parents=True)
            for f in ("sentimento_comentarios.json", "trends.json"):
                (root / "data/config" / f).write_text((Path(__file__).resolve().parents[1] / "data/config" / f).read_text(encoding="utf-8"), encoding="utf-8")
            d = interno / "youtube/comentarios"; d.mkdir(parents=True)
            with gzip.open(d / "comentarios.csv.gz", "wt", encoding="utf-8", newline="") as f:
                w = csv.DictWriter(f, ["comment_id", "candidate_id", "video_id", "publicado_em", "texto"], delimiter=";"); w.writeheader()
                for i in range(40):
                    w.writerow({"comment_id": f"c{i}", "candidate_id": "A", "video_id": "v", "publicado_em": "2026-10-10T00:00:00Z", "texto": f"texto secreto {i}"})
            chamadas = []
            fake = lambda ts: chamadas.append(len(ts)) or [{"rotulo": "POS", "p_pos": .9, "p_neg": .05, "p_neu": .05} for _ in ts]
            os.environ["ODI_INTERNO_DIR"] = str(interno)
            try:
                self.assertEqual(b.main([str(root)], classificar=fake), 0)
                self.assertEqual(b.main([str(root)], classificar=fake), 0)  # segundo run: tudo em cache
            finally:
                del os.environ["ODI_INTERNO_DIR"]
            self.assertEqual(chamadas, [40])
            pub = (root / "data/youtube/comentarios/sentimento.json").read_text(encoding="utf-8")
            self.assertNotIn("secreto", pub); self.assertNotIn("c1", pub)
            o = json.loads(pub)
            self.assertEqual((o["status"], o["candidatos"]["A"]["positivo"], o["candidatos"]["A"]["videos"]["v"]["n"]), ("ok", 100.0, 40))

    def test_partes_em_paralelo_e_juncao(self):
        with tempfile.TemporaryDirectory() as t:
            root, interno = Path(t) / "r", Path(t) / "i"
            (root / "data/config").mkdir(parents=True)
            for f in ("sentimento_comentarios.json", "trends.json"):
                (root / "data/config" / f).write_text((Path(__file__).resolve().parents[1] / "data/config" / f).read_text(encoding="utf-8"), encoding="utf-8")
            d = interno / "youtube/comentarios"; d.mkdir(parents=True)
            with gzip.open(d / "comentarios.csv.gz", "wt", encoding="utf-8", newline="") as f:
                w = csv.DictWriter(f, ["comment_id", "candidate_id", "video_id", "publicado_em", "texto"], delimiter=";"); w.writeheader()
                for i in range(30):
                    w.writerow({"comment_id": f"c{i}", "candidate_id": "A", "video_id": "v", "publicado_em": "2026-08-01T00:00:00Z", "texto": f"t {i}"})
            chamadas = []
            fake = lambda ts: chamadas.append(len(ts)) or [{"rotulo": "NEG", "p_pos": .1, "p_neg": .8, "p_neu": .1} for _ in ts]
            os.environ["ODI_INTERNO_DIR"] = str(interno)
            try:
                self.assertEqual(b.main([str(root), "--parte", "0/2"], classificar=fake), 0)
                self.assertEqual(b.main([str(root), "--parte", "1/2"], classificar=fake), 0)
                self.assertEqual(b.main([str(root)], classificar=fake), 0)  # junta: nada a classificar
            finally:
                del os.environ["ODI_INTERNO_DIR"]
            self.assertEqual(sum(chamadas), 30)
            self.assertEqual(len(chamadas), 2)
            o = json.loads((root / "data/youtube/comentarios/sentimento.json").read_text(encoding="utf-8"))
            self.assertEqual((o["status"], o["classificados_total"]), ("ok", 30))


if __name__ == "__main__":
    unittest.main()
