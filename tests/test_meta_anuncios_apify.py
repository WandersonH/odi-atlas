import json, os, sys, tempfile, unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import collect_meta_anuncios_apify as m

RAIZ = Path(__file__).resolve().parents[1]


class TestMetaApify(unittest.TestCase):
    def test_faixa(self):
        self.assertEqual(m.faixa_de({"lower_bound": "100", "upper_bound": "199"}), {"lower_bound": "100", "upper_bound": "199"})
        self.assertEqual(m.faixa_de("R$ 1.000 - R$ 1.499"), {"lower_bound": "1000", "upper_bound": "1499"})
        self.assertEqual(m.faixa_de("<R$100"), {"lower_bound": "0", "upper_bound": "100"})
        self.assertEqual(m.faixa_de(">1M")["upper_bound"], "")
        self.assertIsNone(m.faixa_de(""))
        self.assertEqual(m.faixa_de("R$20K - R$25K"), {"lower_bound": "20000", "upper_bound": "25000"})
        self.assertEqual(m.faixa_de("R$1.5K - R$2K"), {"lower_bound": "1500", "upper_bound": "2000"})
        self.assertEqual(m.faixa_de(">1M"), {"lower_bound": "1000000", "upper_bound": ""})
        self.assertEqual(m.faixa_de("700K - 800K"), {"lower_bound": "700000", "upper_bound": "800000"})

    def test_main_teto_e_atribuicao(self):
        def fake(payload, cap):
            cfg = json.loads((RAIZ / "data/config/meta_anuncios_apify.json").read_text(encoding="utf-8"))
            self.assertEqual(cap, round(cfg["teto_teste_usd"] / len(cfg["consultas"]), 4))  # teto dividido entre as consultas
            self.assertIn("ad_type=political_and_issue_ads", payload["adLibraryUrls"][0])
            return ({"id": "r1", "status": "SUCCEEDED", "usageTotalUsd": 0.0, "chargedEventCounts": {"apify-default-dataset-item": 800},
                     "pricingInfo": {"pricingPerEvent": {"actorChargeEvents": {"apify-default-dataset-item": {"eventTieredPricingUsd": {"FREE": {"tieredEventPriceUsd": 0.00015}}}}}}},
                    [{"ad_archive_id": "1", "page_name": "P", "page_id": "9", "start_date": 1789000000, "spend": "R$ 100 - R$ 199", "impressions_with_index": {"impressions_text": "1K - 5K"},
                      "publisher_platform": ["FACEBOOK"], "adLibraryUrl": payload["adLibraryUrls"][0]},
                     {"page_name": "Q", "snapshot": {"body": {"text": "Flávio Bolsonaro"}}, "start_date": 1789000000}])
        cwd = os.getcwd()
        with tempfile.TemporaryDirectory() as t:
            (Path(t) / "data/config").mkdir(parents=True)
            for f in ("meta_anuncios_apify.json", "trends.json"):
                (Path(t) / "data/config" / f).write_text((RAIZ / "data/config" / f).read_text(encoding="utf-8"), encoding="utf-8")
            os.chdir(t)
            try:
                self.assertEqual(m.main(["--teste"], executar=fake), 0)
                o = json.loads(Path("data/meta/anuncios.json").read_text(encoding="utf-8"))
            finally:
                os.chdir(cwd)
        self.assertEqual((o["consultas"]["lula"]["anuncios"], o["consultas"]["flavio"]["anuncios"]), (1, 1))  # sem id não entra
        self.assertEqual(o["consultas"]["lula"]["gasto"]["min"], 100)
        self.assertEqual(o["consultas"]["lula"]["impressoes"]["min"], 1000)
        self.assertEqual(o["custo_usd"], 0.24)  # 2 execuções × 800 × 0,00015


if __name__ == "__main__":
    unittest.main()
