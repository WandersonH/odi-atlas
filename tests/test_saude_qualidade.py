"""Saúde da coleta: camada de qualidade separada da atualização (revisão do segundo par, 01/11/2026)."""
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import build_saude_coleta as bs  # noqa: E402


class TestQualidade(unittest.TestCase):
    def test_busca_no_limite_e_perfis_faltando(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            (root / "m.json").write_text(json.dumps({"status": "ok", "buscas": [{"pedido": 150, "itens": 150}, {"pedido": 150, "itens": 90}]}))
            q = bs.qualidade(root, {"tipo": "manifesto", "arquivo": "m.json"}, {})
            self.assertIn("1 de 2 buscas bateram no limite", q["qualidade"])
            (root / "p.json").write_text(json.dumps({"perfis": [1, 2, 3]}))
            q = bs.qualidade(root, {"tipo": "csv", "esperados_de": {"arquivo": "p.json", "caminho": "perfis"}}, {"perfis": 1, "perfis_atrasados": 0})
            self.assertIn("1 de 3 perfis", q["qualidade"])
            self.assertEqual(q["perfis_esperados"], 3)

    def test_sem_problema(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            (root / "m.json").write_text(json.dumps({"status": "ok", "perfis_total": 3, "perfis_ok": 3}))
            self.assertTrue(bs.qualidade(root, {"tipo": "manifesto", "arquivo": "m.json"}, {})["qualidade"].startswith("sem problema"))


if __name__ == "__main__":
    unittest.main()
