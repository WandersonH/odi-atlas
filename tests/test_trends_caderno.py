"""Testes do consolidador do caderno 14 (Google Trends) com coleta sintética."""
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import build_trends_caderno as bt  # noqa: E402


def coleta(base: Path, dia: str, hora: str, status: str, valor: int):
    d = base / "data/trends" / dia / hora
    d.mkdir(parents=True)
    m = {"run_started_utc": f"{dia}T00:00:00Z", "status": status, "aviso_metodologico": "relativo", "config": {"nota": "n"},
         "consultas": [{"grupo": "g", "periodo": "now 7-d", "termos": ["Flávio Bolsonaro", "Lula"], "status": "ok",
                        "itens": [{"rotulo": "Flávio Bolsonaro", "modo": "topico", "consulta": "/g/x", "topico_tipo": "Candidato"},
                                  {"rotulo": "Lula", "modo": "topico", "consulta": "/m/y", "topico_tipo": "Presidente"}]}]}
    (d / "manifesto.json").write_text(json.dumps(m), encoding="utf-8")
    (d / "g__now_7-d__serie.csv").write_text(
        f"timestamp_utc;rotulo;Flávio Bolsonaro;Lula;parcial\n2026-10-14T00:00:00Z;x;{valor};50;0\n2026-10-14T01:00:00Z;x;;60;1\n", encoding="utf-8")
    (d / "g__now_7-d__uf.csv").write_text("geo_code;geo_nome;Flávio Bolsonaro;Lula\nBR-SP;São Paulo;40;60\n", encoding="utf-8")


class TestPeriodoEleitoral(unittest.TestCase):
    def test_janela(self):
        sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
        import collect_trends as ct
        cfg = {"periodo_eleitoral": {"inicio": "2026-07-20", "fim": "2026-10-25"}}
        self.assertEqual(ct.resolver_periodo("eleitoral", cfg, "2026-10-15"), "2026-07-20 2026-10-15")
        self.assertEqual(ct.resolver_periodo("eleitoral", cfg, "2026-11-30"), "2026-07-20 2026-10-25")
        self.assertEqual(ct.resolver_periodo("today 3-m", cfg), "today 3-m")


class TestRelacionados(unittest.TestCase):
    def test_csv_longo(self):
        import collect_trends as ct
        dados = {"default": {"rankedList": [
            {"rankedKeyword": [{"query": "lula hoje", "value": 100, "formattedValue": "100"}]},
            {"rankedKeyword": [{"topic": {"title": "Banco Master", "type": "Banco"}, "value": 5000, "formattedValue": "Aumento repentino"}]}]}}
        with tempfile.TemporaryDirectory() as t:
            p = Path(t) / "r.csv"
            self.assertEqual(ct.write_related([("Lula", "consultas", dados)], p), 2)
            linhas = p.read_text(encoding="utf-8").splitlines()
            self.assertIn("Lula;consultas;principais;1;lula hoje;;100;100", linhas)
            self.assertIn("Lula;consultas;em_alta;1;Banco Master;Banco;5000;Aumento repentino", linhas)


class TestTrendsCaderno(unittest.TestCase):
    def test_usa_a_mais_recente_com_status_ok(self):
        with tempfile.TemporaryDirectory() as t:
            root = Path(t)
            coleta(root, "2026-10-14", "080000", "ok", 11)
            coleta(root, "2026-10-15", "080000", "ok", 22)
            coleta(root, "2026-10-15", "090000", "bloqueado", 99)  # mais nova, mas bloqueada
            self.assertEqual(bt.main([t]), 0)
            d = json.loads((root / "data/trends/caderno.json").read_text(encoding="utf-8"))
            c = d["consultas"][0]
            self.assertEqual(d["pasta"], "data/trends/2026-10-15/080000")
            self.assertEqual(c["serie"][0]["v"], [22, 50])
            self.assertEqual(c["serie"][1], {"t": "2026-10-14T01:00:00Z", "parcial": True, "v": [None, 60]})  # vazio vira null, não zero
            self.assertEqual(c["uf"], [{"uf": "SP", "nome": "São Paulo", "v": [40, 60]}])
            self.assertEqual(c["itens"][1]["tipo"], "Presidente")

    def test_sem_coleta_bloqueia(self):
        with tempfile.TemporaryDirectory() as t:
            (Path(t) / "data/trends").mkdir(parents=True)
            self.assertEqual(bt.main([t]), 1)


if __name__ == "__main__":
    unittest.main()
