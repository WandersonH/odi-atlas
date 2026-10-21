import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import collect_tse_denuncias_pesquisas as tp  # noqa: E402


def den(**k):
    base = {"DT_GERACAO": "20/10/2026", "HH_GERACAO": "16:00:06", "DS_ELEICAO": "Eleição Geral Federal 2026", "SG_UF": "SP",
            "NM_MUNICIPIO": "SÃO PAULO", "DS_CARGO": "DEPUTADO FEDERAL", "TP_IRREGULARIDADE": "Vias públicas",
            "DS_ORIGEM_DENUNCIA": "IOS", "ST_PETICIONAMENTO": "BAIXADA DO SISTEMA", "NR_PROCESSO_PJE": "#NULO"}
    base.update(k)
    return base


class TestDenuncias(unittest.TestCase):
    def test_resumo(self):
        rows = [den(), den(DS_ELEICAO="Eleição Geral Federal 2026 - 2° Turno", DS_CARGO="PRESIDENTE", TP_IRREGULARIDADE="Propaganda na Internet",
                        ST_PETICIONAMENTO="PETICIONADA NO PJE"),
                den(TP_IRREGULARIDADE="Envio de mensagens", SG_UF="BA"), den(TP_IRREGULARIDADE="#NULO")]
        d = tp.resumo_denuncias(rows)
        self.assertEqual(d["total"], 4)
        self.assertEqual(d["gerado_pelo_tse"], "2026-10-20")
        self.assertEqual(dict(d["por_turno"]), {"1º turno": 3, "2º turno": 1})
        self.assertEqual(d["presidente"]["total"], 1)
        self.assertEqual(d["digitais"]["total"], 2)
        self.assertEqual(d["peticionadas_pje"], 1)
        self.assertIn(["não informado", 1], d["por_tipo"])

    def test_historico_um_por_arquivo(self):
        rows = [den()]
        with tempfile.TemporaryDirectory() as t:
            arq = Path(t) / "h.csv"
            d = {**tp.resumo_denuncias(rows), "coletado_em_utc": "2026-10-21T00:00:00Z"}
            tp.historico(arq, d)
            tp.historico(arq, d)  # mesma geração do TSE: substitui, não duplica
            d2 = {**tp.resumo_denuncias([den(DT_GERACAO="21/10/2026")] * 3), "coletado_em_utc": "2026-10-22T00:00:00Z"}
            h = tp.historico(arq, d2)
        self.assertEqual([x["gerado_pelo_tse"] for x in h], ["2026-10-20", "2026-10-21"])
        self.assertEqual(h[-1]["total"], 3)


class TestPesquisas(unittest.TestCase):
    def test_resumo_e_privacidade(self):
        pesq = [{"DT_GERACAO": "20/10/2026", "NR_PROTOCOLO_REGISTRO": "BR1", "SG_UE": "BR", "DS_CARGO": "Presidente", "NM_EMPRESA": "X LTDA",
                 "NM_EMPRESA_FANTASIA": "#NULO#", "DT_REGISTRO": "2026-10-10 10:00:00", "DT_INICIO_PESQUISA": "2026-10-12 00:00:00",
                 "DT_FIM_PESQUISA": "2026-10-14 00:00:00", "DT_DIVULGACAO": "2026-10-16 00:00:00", "QT_ENTREVISTADO": "2000",
                 "VR_PESQUISA": "150000,00", "ST_PESQUISA_PROPRIA": "N", "NM_ESTATISTICO_RESP": "FULANO",
                 "DS_PLANO_AMOSTRAL": "Universo: eleitorado brasileiro com 16 anos ou mais."},
                {"DT_GERACAO": "20/10/2026", "NR_PROTOCOLO_REGISTRO": "BR2", "SG_UE": "BR", "DS_CARGO": "Presidente, Governador",
                 "NM_EMPRESA": "Y", "QT_ENTREVISTADO": "800", "DT_INICIO_PESQUISA": "2026-09-01 00:00:00",
                 "DS_PLANO_AMOSTRAL": "Universo: Eleitores do estado de São Paulo. Fonte: IBGE, população brasileira."},
                {"DT_GERACAO": "20/10/2026", "NR_PROTOCOLO_REGISTRO": "BA1", "SG_UE": "BA", "DS_CARGO": "Governador"}]
        contr = [{"NR_PROTOCOLO_REGISTRO": "BR1", "NR_CPF_CNPJ_CONTRATANTE": "12345678901", "NM_CONTRATANTE": "MARIA DA SILVA",
                  "DS_ORIGEM_RECURSO": "Recursos Próprios"},
                 {"NR_PROTOCOLO_REGISTRO": "BR1", "NR_CPF_CNPJ_CONTRATANTE": "12345678000199", "NM_CONTRATANTE": "JORNAL Z LTDA", "DS_ORIGEM_RECURSO": "#NULO#"}]
        pag = [{"NR_PROTOCOLO_REGISTRO": "BR1", "NR_CPF_CNPJ_PAGANTE": "12345678000199", "NM_PAGANTE": "JORNAL Z LTDA", "DS_ORIGEM_RECURSO": "#NULO#"}]
        p = tp.resumo_pesquisas(pesq, contr, pag)
        self.assertEqual((p["registradas_total"], p["com_presidente"]), (3, 2))
        self.assertEqual(dict(p["abrangencia_presidente"]), {"nacional": 1, "estadual": 1})
        self.assertEqual(p["estaduais_por_uf"], [("SP", 1)])
        self.assertEqual(p["nacionais"]["total"], 1)
        x = next(i for i in p["lista_presidente"] if i["protocolo"] == "BR1")
        self.assertEqual(x["empresa"], "X LTDA")
        self.assertTrue(x["segundo_turno"])
        self.assertEqual(x["valor"], 150000.0)
        self.assertEqual(x["contratantes"], ["JORNAL Z LTDA", "pessoa física (nome omitido)"])
        txt = str(p)
        self.assertNotIn("MARIA", txt)
        self.assertNotIn("FULANO", txt)  # estatístico responsável não vai para o público
        self.assertEqual(tp.pessoa("12345678000199", "FULANO DE TAL 99263319634"), "empresa individual (nome omitido)")
        self.assertEqual(p["nacionais"]["origem_recurso"], [("Recursos Próprios", 1)])


    def test_abrangencia(self):
        ab = tp.abrangencia
        self.assertEqual(ab("Universo: Eleitorado brasileiro", ""), ("nacional", None))
        self.assertEqual(ab("Eleitores do estado do Ceará", "Fonte: IBGE, população brasileira"), ("estadual", "CE"))
        self.assertEqual(ab("", "A área de abrangência da coleta é : ESPIRITO SANTO A relação das localidades"), ("estadual", "ES"))
        self.assertEqual(ab("cobertura geográfica no estado do RN", ""), ("estadual", "RN"))
        self.assertEqual(ab("Eleitores do município de Cuiabá", ""), ("municipal", None))
        self.assertEqual(ab("A área de abrangência da coleta é : NOVA FLORESTA - PB", ""), ("municipal", None))
        self.assertEqual(ab("amostra representativa do eleitorado desta UF", ""), ("estadual", None))
        self.assertEqual(ab("Representativo do eleitorado da área em estudo", "EM ANEXO."), ("não identificada", None))
        self.assertEqual(ab("Estado de Minas Gerais, Estado da Bahia e Estado de São Paulo", "abrangência nacional"), ("nacional", None))


if __name__ == "__main__":
    unittest.main()
