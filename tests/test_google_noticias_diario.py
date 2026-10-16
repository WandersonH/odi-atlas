import datetime as dt, json, os, sys, tempfile, unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import collect_google_noticias_diario as g


def it(t, iso):
    return {"titulo": t, "link": "l", "veiculo": "V", "dominio": "v.com", "data_publicacao": iso, "trecho": ""}


class TestDiario(unittest.TestCase):
    def test_do_dia_horario_de_brasilia(self):
        itens = [it("a", "2026-10-16T02:00:00Z"),  # 15/10 23h em Brasília
                 it("b", "2026-10-15T12:00:00Z"), it("c", "2026-10-14T12:00:00Z")]
        r = g.do_dia(itens, "2026-10-15", 5)
        self.assertEqual([x["titulo"] for x in r], ["a", "b"])
        self.assertEqual(r[1]["posicao"], 2)

    def test_main_nao_refaz_dia_fechado(self):
        chamadas = []
        def fake(q, dia):
            chamadas.append((q, dia.isoformat()))
            return [it(f"{q} {dia}", f"{dia.isoformat()}T15:00:00Z")]
        cwd = os.getcwd()
        with tempfile.TemporaryDirectory() as t:
            (Path(t) / "data/config").mkdir(parents=True); (Path(t) / "data/trends").mkdir(parents=True)
            (Path(t) / "data/config/google_busca.json").write_text((Path(cwd) / "data/config/google_busca.json").read_text(encoding="utf-8"), encoding="utf-8")
            os.chdir(t)
            try:
                g.main(["--desde", "2026-10-10"], buscar_fn=fake, hoje=dt.date(2026, 10, 13))
                n1 = len(chamadas)
                g.main(["--desde", "2026-10-10"], buscar_fn=fake, hoje=dt.date(2026, 10, 13))
                d = json.loads(Path("data/trends/google_noticias_diario.json").read_text(encoding="utf-8"))
                import csv, gzip
                u = list(csv.DictReader(gzip.open("data/trends/noticias/universo.csv.gz", "rt", encoding="utf-8"), delimiter=";"))
            finally:
                os.chdir(cwd)
        self.assertEqual(n1, 8)                 # 4 dias × 2 candidatos
        self.assertEqual(len(chamadas) - n1, 4)  # depois, só ontem e hoje
        self.assertEqual(len(u), 8)  # 1 item por dia e candidato, sem duplicar nas recoletas
        self.assertEqual(d["dias"]["2026-10-10"]["universo"], {"280002542548": 1, "280002551544": 1})
        self.assertTrue(d["dias"]["2026-10-10"]["fechado"]); self.assertFalse(d["dias"]["2026-10-13"]["fechado"])


if __name__ == "__main__":
    unittest.main()
