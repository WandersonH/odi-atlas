import gzip
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import build_banco as bb  # noqa: E402


class TestNomes(unittest.TestCase):
    def test_familia_junta_casos_e_datas(self):
        self.assertEqual(bb.familia("casos/021/itens.csv.gz"), bb.familia("casos/033/itens.csv.gz"))
        self.assertEqual(bb.familia("youtube/videos_2026-11-04.csv.gz"), bb.familia("youtube/videos_2026-11-05.csv.gz"))
        self.assertEqual(bb.familia("casos/014/bruto_x_20261030T013901Z.jsonl.gz"), "casos/<id>/bruto_x_<data>.jsonl.gz")

    def test_nome_tabela_e_caso_e_data(self):
        self.assertEqual(bb.nome_tabela("priv", "casos/<id>/itens.csv.gz"), "priv_casos_itens_csv")
        self.assertEqual(bb.caso_de("casos/009b/x.json"), "009b")
        self.assertEqual(bb.data_no_nome("x/apify_20261030T013901Z.jsonl.gz"), "2026-10-30T01:39:01Z")
        self.assertEqual(bb.data_no_nome("youtube/videos_2026-11-04.csv.gz"), "2026-11-04")


class TestMontar(unittest.TestCase):
    def test_banco_pequeno(self):
        try:
            import duckdb  # noqa: F401
        except ImportError:
            self.skipTest("duckdb não instalado")
        with tempfile.TemporaryDirectory() as t:
            raiz = Path(t) / "data"
            (raiz / "casos/001").mkdir(parents=True)
            (raiz / "casos/002").mkdir(parents=True)
            (raiz / "casos/001/itens.csv").write_text("rede;n\nx;1\nx;2\n", encoding="utf-8")
            (raiz / "casos/002/itens.csv").write_text("rede;n;extra\ntiktok;3;a\n", encoding="utf-8")
            with gzip.open(raiz / "bruto_20261101.jsonl.gz", "wt", encoding="utf-8") as f:
                f.write(json.dumps({"a": 1}) + "\n" + json.dumps({"a": 2}) + "\n")
            (raiz / "resumo.json").write_text(json.dumps({"total": 7}), encoding="utf-8")
            (raiz / "rede.gexf").write_text("<gexf/>", encoding="utf-8")
            import duckdb
            con = duckdb.connect(str(Path(t) / "b.duckdb"))
            cat = []
            bb.carregar(con, "pub", raiz, bb.listar(raiz), cat, lambda s: None)
            self.assertEqual(con.execute("select count(*), count(distinct _caso) from pub_casos_itens_csv").fetchone(), (3, 2))
            self.assertEqual(con.execute("select count(*) from pub_bruto_jsonl").fetchone()[0], 2)
            self.assertEqual(con.execute("select conteudo->>'$.total' from pub_json_documentos").fetchone()[0], "7")
            self.assertEqual(con.execute("select count(*) from _arquivos_fora where _arquivo like '%gexf'").fetchone()[0], 1)
            self.assertFalse(any(c["erros"] for c in cat))


if __name__ == "__main__":
    unittest.main()
