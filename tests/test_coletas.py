"""Testes dos coletores de governo e do Trends, com dados sintéticos (sem rede)."""
import csv
import gzip
import io
import json
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import collect_gov as cg  # noqa: E402
import collect_trends as ct  # noqa: E402


def zcsv(path, files):
    with zipfile.ZipFile(path, "w") as z:
        for name, (header, rows) in files.items():
            buf = io.StringIO()
            w = csv.writer(buf, delimiter=";", quoting=csv.QUOTE_ALL, lineterminator="\n")
            w.writerow(header)
            w.writerows(rows)
            z.writestr(name, buf.getvalue().encode("latin-1"))


CAD_H = ["ANO_ELEICAO", "NR_TURNO", "SG_UF", "CD_CARGO", "DS_CARGO", "SQ_CANDIDATO", "NR_CANDIDATO",
         "NM_CANDIDATO", "NM_URNA_CANDIDATO", "NR_CPF_CANDIDATO", "DS_EMAIL", "DT_NASCIMENTO",
         "NR_TITULO_ELEITORAL_CANDIDATO", "SG_PARTIDO", "DS_SIT_TOT_TURNO"]
PRES = ["2026", "1", "BR", "1", "PRESIDENTE", "280001", "13", "NOME CIVIL A", "LULA", "11122233344",
        "a@b.c", "01/01/1950", "123456789012", "PT", "2º TURNO"]
DEP = ["2026", "1", "SP", "6", "DEPUTADO FEDERAL", "250001", "1234", "NOME CIVIL B", "FULANO", "55566677788",
       "x@y.z", "02/02/1980", "999988887777", "PL", "ELEITO"]
RED_H = ["AA_ELEICAO", "SQ_CANDIDATO", "NR_ORDEM_REDE_SOCIAL", "DS_URL"]


class TestPlataforma(unittest.TestCase):
    def test_dominios(self):
        casos = {"https://www.instagram.com/x/": "instagram", "instagram.com/x": "instagram",
                 "https://x.com/abc": "x", "https://twitter.com/abc": "x", "https://m.facebook.com/p": "facebook",
                 "https://youtu.be/v": "youtube", "https://www.kwai.com/@a": "kwai", "https://t.me/canal": "telegram",
                 "https://www.threads.net/@a": "threads", "https://meusite.com.br": "site_ou_outro",
                 "https://notinstagram.com": "site_ou_outro", "": "invalida"}
        for url, esperado in casos.items():
            self.assertEqual(cg.plataforma(url), esperado, url)


class TestCandidatos(unittest.TestCase):
    def setUp(self):
        self.d = Path(tempfile.mkdtemp())
        self.cad = self.d / "consulta_cand_2026.zip"
        zcsv(self.cad, {"consulta_cand_2026_BRASIL.csv": (CAD_H, [PRES, DEP]),
                        "consulta_cand_2026_SP.csv": (CAD_H, [DEP])})

    def test_dados_pessoais_nunca_gravados(self):
        st, _ = cg.build_candidatos(self.cad, self.d / "c.csv.gz")
        txt = gzip.open(self.d / "c.csv.gz", "rt", encoding="utf-8").read()
        for proibido in ("11122233344", "55566677788", "a@b.c", "01/01/1950", "123456789012", "NOME CIVIL"):
            self.assertNotIn(proibido, txt)
        for col in ("NR_CPF_CANDIDATO", "DS_EMAIL", "DT_NASCIMENTO", "NR_TITULO_ELEITORAL_CANDIDATO", "NM_CANDIDATO"):
            self.assertIn(col, st["columns_dropped"])

    def test_dedup_e_indice(self):
        st, idx = cg.build_candidatos(self.cad, self.d / "c.csv.gz")
        self.assertEqual((st["rows_written"], st["duplicates_dropped"]), (2, 1))
        self.assertEqual(idx["280001"]["NM_URNA_CANDIDATO"], "LULA")

    def test_redes_join(self):
        _, idx = cg.build_candidatos(self.cad, self.d / "c.csv.gz")
        red = self.d / "rede_social_candidato_2026.zip"
        rows = [["2026", "280001", "1", "https://www.instagram.com/lula/"],
                ["2026", "280001", "2", "https://x.com/lula"],
                ["2026", "999999", "1", "https://site.com"]]
        zcsv(red, {"rede_BR.csv": (RED_H, rows), "rede_BRASIL.csv": (RED_H, rows[:1])})
        st = cg.build_redes(red, idx, self.d / "r.csv.gz")
        self.assertEqual((st["rows_written"], st["duplicates_dropped"], st["sem_cadastro"]), (3, 1, 1))
        self.assertEqual({p["plataforma"] for p in st["presidencia"]}, {"instagram", "x"})


class TestSidra(unittest.TestCase):
    def test_filtra_pnad_continua_internet(self):
        cat = [{"nome": "Pesquisa Nacional por Amostra de Domicílios Contínua anual",
                "agregados": [{"id": "1", "nome": "Domicílios em que havia utilização da Internet"},
                              {"id": "2", "nome": "Rendimento médio"}]},
               {"nome": "Censo Demográfico", "agregados": [{"id": "3", "nome": "Acesso à Internet"}]}]
        self.assertEqual([t["id"] for t in cg.tabelas_internet(cat)], ["1"])


class TestTrends(unittest.TestCase):
    def test_prefixo_e_csv(self):
        raw = ')]}\',\n{"default":{"timelineData":[{"time":"1760486400","formattedTime":"15 de out.","value":[80,100],"isPartial":true}]}}'
        data = ct._strip(raw)
        p = Path(tempfile.mkdtemp()) / "s.csv"
        self.assertEqual(ct.write_timeline(data, ["A", "B"], p), 1)
        linhas = p.read_text(encoding="utf-8").splitlines()
        self.assertEqual(linhas[0], "timestamp_utc;rotulo;A;B;parcial")
        self.assertTrue(linhas[1].endswith(";80;100;1"))

    def test_resolver_topico_e_bloqueio(self):
        class T:
            def autocomplete(self, termo):
                return [{"mid": "/m/02yy8", "title": "Lula", "type": "Presidente do Brasil"},
                        {"mid": "/m/0lula", "title": "Lula", "type": "Molusco"}]
        r = ct.resolver(T(), {"rotulo": "Lula", "busca": "Lula", "tipo_contem": "presidente"})
        self.assertEqual((r["consulta"], r["modo"]), ("/m/02yy8", "topico"))
        self.assertEqual(ct.resolver(T(), "Lula")["modo"], "palavra")
        with self.assertRaises(ValueError):
            ct.resolver(T(), {"rotulo": "X", "busca": "X", "tipo_contem": "Governador"})

    def test_config_respeita_limite_de_5_termos(self):
        cfg = json.loads((Path(__file__).resolve().parents[1] / "data/config/trends.json").read_text(encoding="utf-8"))
        self.assertTrue(all(1 <= len(g["termos"]) <= 5 for g in cfg["grupos"]))


class TestGzip(unittest.TestCase):
    def test_read_body_descompacta(self):
        import gzip as gz
        sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
        import net

        class R:
            headers = {}
            def read(self):
                return gz.compress(b'{"ok": 1}')
        self.assertEqual(json.loads(net.read_body(R())), {"ok": 1})


if __name__ == "__main__":
    unittest.main()
