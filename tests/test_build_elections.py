"""Testes da geração do elections.json (P2/P3) com dados sintéticos."""
import csv
import gzip
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import build_elections as be  # noqa: E402

H = ["CD_CARGO", "NR_TURNO", "SG_UF", "CD_MUNICIPIO", "NM_MUNICIPIO", "NR_ZONA", "NR_CANDIDATO",
     "NM_URNA_CANDIDATO", "QT_VOTOS_NOMINAIS_VALIDOS"]


def fixture(rows_by_year, malha, exc=()):
    root = Path(tempfile.mkdtemp())
    (root / "data/tse").mkdir(parents=True); (root / "data/ibge").mkdir(); (root / "data/config").mkdir()
    for y, rows in rows_by_year.items():
        with gzip.open(root / f"data/tse/presidente_1t_{y}_munzona.csv.gz", "wt", encoding="utf-8", newline="") as f:
            w = csv.writer(f, delimiter=";"); w.writerow(H); w.writerows(rows)
    with open(root / "data/ibge/municipios_malha_2025.csv", "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f, delimiter=";"); w.writerow(["CD_MUN", "NM_MUN", "SIGLA_UF"]); w.writerows(malha)
    with open(root / "data/config/tse_ibge_excecoes.csv", "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f, delimiter=";"); w.writerow(["uf", "cd_municipio_tse", "cd_mun_ibge", "nome_tse", "nome_ibge", "motivo"]); w.writerows(exc)
    return root


MALHA = [["3550308", "São Paulo", "SP"], ["3165206", "São Tomé das Letras", "MG"], ["4300001", 'Área Operacional "Lagoa Mirim"', "RS"]]
ROWS = [["1", "1", "SP", "71072", "SÃO PAULO", "1", "13", "LULA", "60"],
        ["1", "1", "SP", "71072", "SÃO PAULO", "2", "13", "LULA", "40"],
        ["1", "1", "SP", "71072", "SÃO PAULO", "1", "22", "X", "50"],
        ["1", "1", "MG", "53031", "SÃO THOMÉ DAS LETRAS", "1", "22", "X", "7"],
        ["1", "1", "ZZ", "99999", "LISBOA", "1", "13", "LULA", "5"]]
EXC = [["MG", "53031", "3165206", "SÃO THOMÉ DAS LETRAS", "São Tomé das Letras", "grafia"]]


class TestBuild(unittest.TestCase):
    def test_norm_igual_ao_caderno(self):
        self.assertEqual(be.norm("Espigão D'Oeste"), "ESPIGAO D OESTE")
        self.assertEqual(be.norm("São Luiz do Paraitinga"), "SAO LUIZ DO PARAITINGA")

    def test_agrega_zonas_exclui_exterior_usa_excecao(self):
        root = fixture({"2022": ROWS, "2026": ROWS}, MALHA, EXC)
        self.assertEqual(be.main([str(root)]), 0)
        e = json.loads((root / "data/elections.json").read_text(encoding="utf-8"))
        sp = e["years"]["2026"]["SP|SAO PAULO"]
        self.assertEqual((sp["ibge"], sp["validos_nominais"], sp["candidatos"]), ("3550308", 150, {"13": 100, "22": 50}))
        self.assertEqual(e["years"]["2026"]["MG|SAO TOME DAS LETRAS"]["ibge"], "3165206")
        d = e["diagnostics"]["sources"]["2026"]
        self.assertEqual((d["validos_exterior"], d["municipios"]), (5, 2))

    def test_sem_correspondencia_bloqueia(self):
        root = fixture({"2022": ROWS, "2026": ROWS}, MALHA)  # sem a exceção de São Thomé
        self.assertEqual(be.main([str(root)]), 1)
        e = json.loads((root / "data/elections.json").read_text(encoding="utf-8"))
        self.assertEqual(e["status"], "bloqueado")

    def test_lagoas_nao_removem_municipios_reais(self):
        malha = MALHA + [["4300034", "Aceguá", "RS"]]
        rows = ROWS + [["1", "1", "RS", "85600", "ACEGUÁ", "1", "13", "LULA", "3"]]
        root = fixture({"2022": rows, "2026": rows}, malha, EXC)
        self.assertEqual(be.main([str(root)]), 0)


if __name__ == "__main__":
    unittest.main()
