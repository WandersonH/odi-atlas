import csv
import gzip
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import intolerancia_publico as ip  # noqa: E402


class TestIntoleranciaPublico(unittest.TestCase):
    def test_arquivos_sem_texto_e_contagem_reproduz(self):
        with tempfile.TemporaryDirectory() as t:
            priv, pub = Path(t) / "priv", Path(t) / "pub"
            (priv / "intolerancia").mkdir(parents=True)
            pub.mkdir()
            with gzip.open(priv / "itens.csv.gz", "wt", encoding="utf-8", newline="") as fh:
                w = csv.writer(fh, delimiter=";")
                w.writerow(["rede", "item_id", "texto", "publicado_em"])
                w.writerow(["x", "111", "texto secreto número um", "2026-10-30T10:00:00Z"])
                w.writerow(["x", "222", "texto secreto número dois", "2026-10-31T10:00:00Z"])
            with gzip.open(priv / "intolerancia" / "escores.csv.gz", "wt", encoding="utf-8", newline="") as fh:
                w = csv.writer(fh, delimiter=";")
                w.writerow(["id", "ofensividade_hatebr:False", "ofensividade_hatebr:True", "rede"])
                w.writerow(["111", "0.1", "0.9", "x"])
                w.writerow(["222", "0.8", "0.2", "x"])
            (pub / "intolerancia.json").write_text(json.dumps({"modelos": {"ofensividade_hatebr": {
                "modelo": "m", "total": {"lidos": 2, "sinalizados": 1, "pct": 50.0},
                "por_rede": {"x": {"lidos": 2, "sinalizados_algum_rotulo": 1, "pct_algum": 50.0, "por_rotulo": {"True": {"n": 1, "pct": 50.0}}}}}}}))
            r = ip.publicar("999", priv, pub)
            self.assertEqual(r["linhas"], 2)
            corpo = (pub / "intolerancia_escores.csv").read_text(encoding="utf-8")
            self.assertNotIn("secreto", corpo)
            self.assertNotIn("111", corpo)
            linhas = list(csv.DictReader(corpo.splitlines(), delimiter=";"))
            col = [c for c in linhas[0] if c.startswith("ofensividade_hatebr:marcado")][0]
            self.assertEqual(sum(x[col] == "s" for x in linhas), 1)
            self.assertEqual(linhas[0]["dia"], "2026-10-30")
            self.assertIn("arquivos", json.loads((pub / "intolerancia.json").read_text()))


if __name__ == "__main__":
    unittest.main()
