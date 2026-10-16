import csv, gzip, json, random, sys, tempfile, unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
try:
    import build_noticias_texto as b
except ImportError as e:  # workflows sem networkx/numpy
    raise unittest.SkipTest(f"dependência ausente: {e}")

RAIZ = Path(__file__).resolve().parents[1]


class TestNoticias(unittest.TestCase):
    def test_unicos(self):
        rows = [{"candidate_id": "A", "dia": "2026-09-02", "posicao": "1", "titulo": "Lula viaja!", "veiculo": "X"},
                {"candidate_id": "A", "dia": "2026-09-01", "posicao": "3", "titulo": "Lula viaja", "veiculo": "Y"},
                {"candidate_id": "B", "dia": "2026-09-01", "posicao": "1", "titulo": "Lula viaja", "veiculo": "Y"}]
        u = b.unicos(rows)
        self.assertEqual(len(u), 2)
        a = [x for x in u if x["candidate_id"] == "A"][0]
        self.assertEqual((a["dia"], a["repeticoes"]), ("2026-09-01", 2))

    def test_main_sintetico(self):
        rnd = random.Random(1)
        temas = [["economia", "inflacao", "juros", "mercado", "gasolina", "imposto"], ["pesquisa", "datafolha", "quaest", "votos", "empate", "turno"],
                 ["seguranca", "policia", "faccao", "crime", "prisao", "violencia"]]
        with tempfile.TemporaryDirectory() as t:
            r = Path(t); (r / "data/config").mkdir(parents=True); (r / "data/trends/noticias").mkdir(parents=True)
            for f in ("google_busca.json", "trends.json"):
                (r / "data/config" / f).write_text((RAIZ / "data/config" / f).read_text(encoding="utf-8"), encoding="utf-8")
            with gzip.open(r / "data/trends/noticias/universo.csv.gz", "wt", encoding="utf-8", newline="") as f:
                w = csv.DictWriter(f, ["dia", "candidate_id", "posicao", "titulo", "veiculo", "dominio", "link", "data_publicacao", "coletado_em"], delimiter=";")
                w.writeheader()
                for i in range(900):
                    cid = "280002542548" if i % 2 else "280002551544"
                    tema = temas[i % 3]
                    w.writerow({"dia": f"2026-09-{1 + i % 28:02d}", "candidate_id": cid, "posicao": i % 50 + 1,
                                "titulo": f"Lula e Flávio Bolsonaro {' '.join(rnd.sample(tema, 4))} caso {i}", "veiculo": f"V{i % 7}",
                                "dominio": "v.com", "link": f"https://x/{i}", "data_publicacao": "", "coletado_em": ""})
            self.assertEqual(b.main([str(r)]), 0)
            o = json.loads((r / "data/trends/noticias/texto.json").read_text(encoding="utf-8"))
            c = o["candidatos"]["280002542548"]
            self.assertEqual(c["titulos_unicos"], 450)
            palavras = {p for p, _ in c["nuvem"]}
            self.assertNotIn("lula", palavras); self.assertNotIn("bolsonaro", palavras)
            self.assertTrue(c["chd"].get("classes"))
            corpus = (r / "data/trends/noticias/corpus_iramuteq.txt").read_text(encoding="utf-8").splitlines()
            self.assertEqual(len(corpus), 1800)
            self.assertTrue(corpus[0].startswith("**** *cand_"))
            self.assertIn("*fase_turno1", corpus[0])
            self.assertTrue((r / "data/trends/noticias/rede_termos.gexf").exists())


if __name__ == "__main__":
    unittest.main()
