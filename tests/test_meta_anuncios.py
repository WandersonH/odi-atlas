import json, os, sys, tempfile, unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import collect_meta_anuncios as m

FASES = [{"id": "t1", "rotulo": "1º", "de": "2026-08-16", "ate": "2026-10-04"}]


class TestMeta(unittest.TestCase):
    def test_soma_faixa_aberta(self):
        self.assertEqual(m.soma([(100, 199), (0, 99)]), {"min": 100, "max": 298, "faixas_abertas": 0})
        self.assertEqual(m.soma([(100, 199), (1000000, None)])["max"], None)

    def test_agregar(self):
        ads = [{"page_id": "1", "page_name": "P", "spend": {"lower_bound": "100", "upper_bound": "199"}, "impressions": {"lower_bound": "1000", "upper_bound": "1999"},
                "ad_delivery_start_time": "2026-09-01", "publisher_platforms": ["facebook", "instagram"], "delivery_by_region": [{"region": "São Paulo", "percentage": "0.5"}]},
               {"page_id": "2", "page_name": "Q", "spend": {"lower_bound": "0", "upper_bound": "99"}, "ad_delivery_start_time": "2026-07-25", "publisher_platforms": ["instagram"]}]
        a = m.agregar(ads, FASES)
        self.assertEqual((a["anuncios"], a["paginas"], a["gasto"]["min"], a["gasto"]["max"]), (2, 2, 100, 298))
        self.assertEqual(a["top_paginas"][0]["pagina"], "P")
        self.assertEqual(a["plataformas"], {"instagram": 2, "facebook": 1})
        self.assertEqual(a["fases"][0]["anuncios"], 1)
        self.assertEqual(a["regioes_gasto_min_estimado"][0], {"regiao": "São Paulo", "gasto_min": 50})

    def test_sem_token(self):
        with tempfile.TemporaryDirectory() as t:
            r = Path(t); (r / "data/config").mkdir(parents=True)
            for f in ("meta_anuncios.json", "trends.json"):
                (r / "data/config" / f).write_text((Path(__file__).resolve().parents[1] / "data/config" / f).read_text(encoding="utf-8"), encoding="utf-8")
            os.environ.pop("META_AD_LIBRARY_TOKEN", None)
            self.assertEqual(m.main([str(r)]), 1)
            self.assertTrue(json.loads((r / "data/meta/anuncios.json").read_text(encoding="utf-8"))["status"].startswith("⛔"))


if __name__ == "__main__":
    unittest.main()
