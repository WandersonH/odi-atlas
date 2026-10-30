"""Testes da P1 com arquivos sintéticos (fixtures). Não substituem a execução real contra o TSE."""
import csv
import gzip
import io
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import fetch_sources as fs  # noqa: E402

HEADER = ["ANO_ELEICAO", "NR_TURNO", "SG_UF", "CD_MUNICIPIO", "NM_MUNICIPIO", "NR_ZONA",
          "CD_CARGO", "DS_CARGO", "NR_CANDIDATO", "NM_URNA_CANDIDATO", "QT_VOTOS_NOMINAIS"]


def csv_bytes(rows):
    buf = io.StringIO()
    w = csv.writer(buf, delimiter=";", quotechar='"', quoting=csv.QUOTE_ALL, lineterminator="\n")
    w.writerow(HEADER)
    w.writerows(rows)
    return buf.getvalue().encode("latin-1")


SP = ["2022", "1", "SP", "71072", "SÃO PAULO", "1", "1", "PRESIDENTE", "13", "LULA", "100"]
SP2 = ["2022", "1", "SP", "71072", "SÃO PAULO", "1", "1", "PRESIDENTE", "22", "BOLSONARO", "90"]
SP_T2 = ["2022", "2", "SP", "71072", "SÃO PAULO", "1", "1", "PRESIDENTE", "13", "LULA", "120"]
SP_DEP = ["2022", "1", "SP", "71072", "SÃO PAULO", "1", "6", "DEPUTADO FEDERAL", "1310", "FULANO", "5"]
RJ = ["2022", "1", "RJ", "60011", "RIO DE JANEIRO", "4", "1", "PRESIDENTE", "13", "LULA", "80"]


class TestPick(unittest.TestCase):
    def test_exact_match_only(self):
        res = [{"url": "https://x/votacao_partido_munzona_2022.zip"},
               {"url": "https://x/detalhe_votacao_munzona_2022.zip"},
               {"url": "https://x/votacao_candidato_munzona_2022.zip"}]
        self.assertEqual(fs.pick_munzona(res, "2022")["url"], "https://x/votacao_candidato_munzona_2022.zip")

    def test_missing_or_ambiguous_returns_none(self):
        self.assertIsNone(fs.pick_munzona([{"url": "https://x/votacao_partido_munzona_2026.zip"}], "2026"))
        two = [{"url": "https://a/votacao_candidato_munzona_2026.zip"},
               {"url": "https://b/votacao_candidato_munzona_2026.zip"}]
        self.assertIsNone(fs.pick_munzona(two, "2026"))


class TestExtract(unittest.TestCase):
    def build(self, files):
        d = Path(tempfile.mkdtemp())
        zp = d / "votacao_candidato_munzona_2022.zip"
        with zipfile.ZipFile(zp, "w") as z:
            for name, rows in files.items():
                z.writestr(name, csv_bytes(rows))
        return d, zp

    def read(self, gz):
        with gzip.open(gz, "rt", encoding="utf-8") as f:
            return list(csv.reader(f, delimiter=";"))

    def test_filters_cargo_turno_and_keeps_columns(self):
        d, zp = self.build({"votacao_candidato_munzona_2022_SP.csv": [SP, SP2, SP_T2, SP_DEP]})
        st = fs.extract_presidente_1t(zp, d / "out.csv.gz")
        rows = self.read(d / "out.csv.gz")
        self.assertEqual(rows[0], HEADER)
        self.assertEqual(rows[1:], [SP, SP2])
        self.assertEqual(st["rows_written"], 2)
        self.assertEqual(st["files"][0]["rows_read"], 4)

    def test_segundo_turno(self):
        d, zp = self.build({"votacao_candidato_munzona_2022_SP.csv": [SP, SP2, SP_T2, SP_DEP]})
        st = fs.extract_presidente_1t(zp, d / "out2.csv.gz", turno="2")
        self.assertEqual(self.read(d / "out2.csv.gz")[1:], [SP_T2])
        self.assertEqual((st["rows_written"], st["turno"]), (1, "2"))

    def test_dedup_between_br_and_uf_files(self):
        d, zp = self.build({"votacao_candidato_munzona_2022_BR.csv": [SP, SP2, RJ],
                            "votacao_candidato_munzona_2022_SP.csv": [SP, SP2],
                            "votacao_candidato_munzona_2022_RJ.csv": [RJ]})
        st = fs.extract_presidente_1t(zp, d / "out.csv.gz")
        self.assertEqual(st["rows_written"], 3)
        self.assertEqual(st["duplicates_dropped"], 3)
        self.assertEqual(st["rows_by_uf"], {"SP": 2, "RJ": 1})

    def test_latin1_accents_survive(self):
        d, zp = self.build({"a.csv": [SP]})
        fs.extract_presidente_1t(zp, d / "out.csv.gz")
        self.assertEqual(self.read(d / "out.csv.gz")[1][4], "SÃO PAULO")

    def test_missing_columns_fail_loudly(self):
        d = Path(tempfile.mkdtemp())
        zp = d / "x.zip"
        with zipfile.ZipFile(zp, "w") as z:
            z.writestr("a.csv", b'"A";"B"\n"1";"2"\n')
        with self.assertRaises(ValueError):
            fs.extract_presidente_1t(zp, d / "out.csv.gz")


class TestConflict(unittest.TestCase):
    build = TestExtract.build

    def test_same_key_different_votes_is_reported(self):
        changed = SP[:-1] + ["999"]
        d, zp = self.build({"a_BR.csv": [SP], "b_SP.csv": [changed]})
        st = fs.extract_presidente_1t(zp, d / "out.csv.gz")
        self.assertEqual(len(st["duplicate_conflicts"]), 1)


class TestRunOffline(unittest.TestCase):
    """Executa run() inteiro trocando a rede por arquivos locais."""

    def setUp(self):
        self.d = Path(tempfile.mkdtemp())
        src = self.d / "src_votacao_candidato_munzona_2022.zip"
        with zipfile.ZipFile(src, "w") as z:
            z.writestr("votacao_candidato_munzona_2022_SP.csv", csv_bytes([SP, SP2, SP_DEP]))
        self.src = src
        self._orig = (fs.get_json, fs.download)

        def fake_get_json(url):
            if "resultados-2022" in url:
                return {"result": {"metadata_modified": "x", "resources": [
                    {"url": "https://cdn/votacao_candidato_munzona_2022.zip", "name": "Votação"}]}}
            return {"result": {"resources": [{"url": "https://cdn/votacao_partido_munzona_2026.zip"}]}}

        def fake_download(url, dest):
            dest.parent.mkdir(parents=True, exist_ok=True)
            if url.endswith(".zip"):
                dest.write_bytes(self.src.read_bytes())
            else:
                dest.write_text('[{"id": 3550308}]', encoding="utf-8")
            return {"url": url, "file": dest.name, "bytes": dest.stat().st_size, "sha256": "x"}

        fs.get_json, fs.download = fake_get_json, fake_download

    def tearDown(self):
        fs.get_json, fs.download = self._orig

    def test_missing_year_blocks_and_manifest_is_written(self):
        code = fs.main(["--years", "2022", "2026", "--malha", "", "--root", str(self.d)])
        import json
        m = json.loads((self.d / "data" / "manifest" / "latest.json").read_text(encoding="utf-8"))
        self.assertEqual(code, 1)
        self.assertEqual(m["status"], "bloqueado")
        self.assertEqual(m["tse"]["2022"]["status"], "ok")
        self.assertEqual(m["tse"]["2022"]["extract"]["rows_written"], 2)
        self.assertEqual(m["tse"]["2026"]["status"], "recurso_nao_encontrado")
        self.assertEqual(m["ibge"]["municipios_api"]["count"], 1)
        self.assertTrue((self.d / "data" / "tse" / "presidente_1t_2022_munzona.csv.gz").exists())


def make_dbf(fields, rows):
    """Escreve um DBF dBase III mínimo para teste."""
    import struct
    rlen = 1 + sum(sz for _, sz in fields)
    hlen = 32 + 32 * len(fields) + 1
    out = bytearray(struct.pack("<BBBBIHH20x", 3, 126, 1, 1, len(rows), hlen, rlen))
    for name, sz in fields:
        out += name.encode().ljust(11, b"\x00") + b"C" + b"\x00" * 4 + bytes([sz]) + b"\x00" * 15
    out += b"\r"
    for r in rows:
        out += b" " + b"".join(v.encode("utf-8").ljust(sz, b" ")[:sz] for v, (_, sz) in zip(r, fields))
    return bytes(out + b"\x1a")


class TestMalha(unittest.TestCase):
    def test_municipios_from_dbf(self):
        d = Path(tempfile.mkdtemp())
        zp = d / "BR_Municipios_2025.zip"
        dbf = make_dbf([("CD_MUN", 7), ("NM_MUN", 30), ("SIGLA_UF", 2)],
                       [["3550308", "São Paulo", "SP"], ["5300108", "Brasília", "DF"]])
        with zipfile.ZipFile(zp, "w") as z:
            z.writestr("BR_Municipios_2025.dbf", dbf)
            z.writestr("BR_Municipios_2025.cpg", "UTF-8")
        info = fs.municipios_from_malha(zp, d / "m.csv")
        self.assertEqual(info["count"], 2)
        self.assertEqual(info["columns"], ["CD_MUN", "NM_MUN", "SIGLA_UF"])
        self.assertIn("3550308;São Paulo;SP", (d / "m.csv").read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
