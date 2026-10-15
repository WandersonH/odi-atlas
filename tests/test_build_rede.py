"""Testes da rede de coocorrência (caderno 13) com dados sintéticos."""
import csv
import gzip
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
try:
    import build_rede as br  # noqa: E402
except ImportError:  # networkx ausente
    br = None


@unittest.skipIf(br is None, "networkx não instalado")
class TestRede(unittest.TestCase):
    IDS = ("A", "B")

    def videos(self):
        return ([("A", {"saude", "sus", "hospital"})] * 4 + [("A", {"saude", "sus"})] * 2 +
                [("B", {"#direita", "#vote22", "vencer"})] * 5 + [("B", {"saude", "vencer"})] * 3 + [("A", {"raro"})])

    def test_nos_arestas_e_lado(self):
        g = br.montar(self.videos(), self.IDS, min_videos=3, min_peso=3)
        self.assertNotIn("raro", g)                       # abaixo do mínimo de vídeos
        self.assertEqual(g["saude"]["sus"]["weight"], 6)  # 6 vídeos com os dois
        self.assertEqual(g["saude"]["vencer"]["weight"], 3)
        self.assertEqual(g.nodes["saude"]["lado"], round(6 / 9, 3))
        self.assertEqual(g.nodes["#vote22"]["lado"], 0.0)

    def test_deterministico_e_comunidades(self):
        r1, r2 = br.montar(self.videos(), self.IDS, 3, min_peso=3), br.montar(self.videos(), self.IDS, 3, min_peso=3)
        i1, i2 = br.analisar(r1), br.analisar(r2)
        self.assertEqual({n: (d["x"], d["y"], d["comunidade"]) for n, d in r1.nodes(data=True)},
                         {n: (d["x"], d["y"], d["comunidade"]) for n, d in r2.nodes(data=True)})
        self.assertNotEqual(r1.nodes["#direita"]["comunidade"], r1.nodes["sus"]["comunidade"])
        self.assertEqual(i1["modularidade"], i2["modularidade"])

    def test_execucao_completa_e_planilhas_conferem(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            (root / "data/config").mkdir(parents=True)
            (root / "data/youtube").mkdir(parents=True)
            cfg = {"nota": "", "temas": {}, "pede_voto": [],
                   "candidatos": {"1": {"nome": "Lula", "numero": "13", "adversario": []},
                                  "2": {"nome": "Flávio Bolsonaro", "numero": "22", "adversario": []}}}
            (root / "data/config/temas_youtube.json").write_text(json.dumps(cfg), encoding="utf-8")
            cols = ["candidate_id", "candidate_name", "channel_id", "canal", "video_id", "publicado_em", "titulo",
                    "duracao", "visualizacoes", "curtidas", "comentarios", "coletado_em", "descricao", "tags"]
            rows = [["1", "L", "c1", "Canal L", f"a{i}", "2026-09-01T00:00:00Z", f"Saúde e SUS para o povo {i}",
                     "", "", "", "", "2026-10-15T00:00:00Z", "", ""] for i in range(10)]
            rows += [["2", "F", "c2", "Canal F", f"b{i}", "2026-09-01T00:00:00Z", f"Vencer com o povo #Direita {i}",
                      "", "", "", "", "2026-10-15T00:00:00Z", "", ""] for i in range(10)]
            with gzip.open(root / "data/youtube/videos_latest.csv.gz", "wt", encoding="utf-8", newline="") as f:
                w = csv.writer(f, delimiter=";"); w.writerow(cols); w.writerows(rows)
            self.assertEqual(br.main([str(root)]), 0)
            yt = root / "data/youtube"
            for nome in ("rede.json", "rede.gexf", "rede_nos.csv", "rede_arestas.csv", "rede_videos_termos.csv"):
                self.assertTrue((yt / nome).exists(), nome)
            matriz = [set(r["termos_na_rede"].split("|")) for r in csv.DictReader(open(yt / "rede_videos_termos.csv", encoding="utf-8"))]
            arestas = list(csv.DictReader(open(yt / "rede_arestas.csv", encoding="utf-8")))
            self.assertTrue(arestas)
            for e in arestas:  # o peso de toda aresta se refaz a partir da matriz vídeo × termos
                self.assertEqual(int(e["Weight"]), sum(1 for s in matriz if e["Source"] in s and e["Target"] in s))
            nos = {r["Id"]: r for r in csv.DictReader(open(yt / "rede_nos.csv", encoding="utf-8"))}
            self.assertEqual((nos["povo"]["videos_lula"], nos["povo"]["videos_flavio"]), ("10", "10"))
            self.assertNotIn("lula", nos)  # nome do próprio candidato fica fora


if __name__ == "__main__":
    unittest.main()
