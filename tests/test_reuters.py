import json, unittest
from pathlib import Path

D = json.loads((Path(__file__).resolve().parents[1] / "data/reuters/brasil.json").read_text(encoding="utf-8"))


class TestReuters(unittest.TestCase):
    def test_estrutura(self):
        self.assertEqual(set(D["edicoes"]), {"2022", "2026"})
        for ano, e in D["edicoes"].items():
            self.assertEqual(len(e["sha256"]), 64)
            self.assertTrue(e["url"].startswith("https://reutersinstitute.politics.ox.ac.uk/"))
            self.assertEqual(len(e["paginas_pdf"]), 2)
            for k, v in e.items():
                if k.endswith("_pct") and isinstance(v, (int, float)):
                    self.assertTrue(0 <= v <= 100, (ano, k, v))
            for x in e["confianca_marcas"]:
                self.assertTrue(0 <= x["confia_pct"] + x["nao_confia_pct"] <= 100, x)
            self.assertEqual([r["rank"] for r in e["redes_para_noticias"]], list(range(1, 7)))

    def test_valores_chave(self):
        a, z = D["edicoes"]["2022"], D["edicoes"]["2026"]
        self.assertEqual((a["confianca_geral_pct"], z["confianca_geral_pct"]), (48, 36))
        self.assertEqual(z["redes_para_noticias"][0]["rede"], "Instagram")


if __name__ == "__main__":
    unittest.main()
