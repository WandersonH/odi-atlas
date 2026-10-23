import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "scripts"))
import collect_x_posts as xp  # noqa: E402


class TestXConta1(unittest.TestCase):
    def test_lacuna_desde_17_10_teto_do_lote(self):
        pedidos = []

        def fake(pl, cap):
            pedidos.append((pl, cap))
            return {"id": "r", "usageTotalUsd": 0.001}, []
        cwd = os.getcwd()
        with tempfile.TemporaryDirectory() as t:
            (Path(t) / "data/config").mkdir(parents=True)
            (Path(t) / "data/config/x_posts.json").write_text((RAIZ / "data/config/x_posts.json").read_text(encoding="utf-8"), encoding="utf-8")
            (Path(t) / "data/x").mkdir(parents=True)
            (Path(t) / "data/x/manifesto-velho.json").write_text(json.dumps({"custo_usd": 1.9}), encoding="utf-8")  # gasto de outro lote não conta
            os.chdir(t)
            try:
                xp.main(["--conta1"], executar=fake)
                man = json.loads(Path("data/x/manifesto_latest.json").read_text(encoding="utf-8"))
            finally:
                os.chdir(cwd)
        C1 = json.loads((RAIZ / "data/config/x_posts.json").read_text(encoding="utf-8"))["conta1"]
        self.assertEqual((man["lote"], man["conta"], man["gasto_antes_usd"]), (C1["lote"], "APIFY_TOKEN", 0))
        self.assertTrue(pedidos and all(f"since:{C1['desde_lacuna']}" in pl["searchTerms"][0] for pl, _ in pedidos))
        self.assertLessEqual(sum(c for _, c in pedidos), C1["teto_lacuna_usd"] + 0.01 * len(pedidos))


if __name__ == "__main__":
    unittest.main()
