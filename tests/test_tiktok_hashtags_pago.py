import datetime as dt
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import collect_tiktok_hashtags as th  # noqa: E402

PG = {"ator": "apidojo~tiktok-scraper", "segredo": "APIFY_TOKEN", "teto_mensal_usd": 20.0, "usd_por_item": 0.0004,
      "usd_por_busca": 0.006, "itens_por_hashtag": 100, "dateRange": "THIS_WEEK"}


class TestPago(unittest.TestCase):
    def test_teto_do_dia(self):
        self.assertEqual(th.dia_mes(dt.date(2026, 11, 2)), 29)
        teto, n = th.plano_pago(PG, 14, 0.0, dt.date(2026, 11, 2))
        self.assertAlmostEqual(teto, round(20 / 29, 4))
        self.assertEqual(n, 100)
        teto, n = th.plano_pago(PG, 14, 19.99, dt.date(2026, 11, 30))
        self.assertLess(n, 5)  # mês esgotado: não roda

    def test_coleta_com_executor_falso(self):
        cfg = {"pago": PG, "hashtags": {"a": ["lula"], "b": ["flavio"]}}
        pedidos = []

        def exe(ator, pl, cap):
            pedidos.append(pl)
            return {"id": "r1", "usageTotalUsd": 0.01}, [{"id": "7", "channel": {"username": "fulano", "followers": 20000},
                                                           "uploadedAt": 1793000000, "title": "texto #Lula", "views": 10, "postPage": "https://t/7"}]
        with tempfile.TemporaryDirectory() as t:
            rows, res, info = th.coletar_pago(cfg, "2026-11-02T12:00:00Z", "x", Path(t) / "g.csv", executar=exe)
        self.assertEqual(pedidos[0]["sortType"], "DATE_POSTED")
        self.assertEqual(pedidos[0]["dateRange"], "THIS_WEEK")
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0]["conta"], "fulano")
        self.assertEqual(rows[0]["hashtags"], "lula")
        self.assertEqual(info["status"], "ok")


if __name__ == "__main__":
    unittest.main()
