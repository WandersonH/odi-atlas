import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import collect_processual as cp  # noqa: E402


class TestProcessual(unittest.TestCase):
    def test_agrega_temas_e_candidatos(self):
        proc = [{"NR_PROCESSO": "1", "SG_UF_TRIBUNAL": "SP", "NR_INSTANCIA": "2", "DS_CLASSE": "REPRESENTAÇÃO", "DS_ASSUNTO_PRINCIPAL": "Propaganda Política - Propaganda Eleitoral - Internet",
                 "DT_AUTUACAO": "10/09/2026", "DT_BAIXA": "", "QT_DECISOES": "2", "DS_URL_PROCESSO": "https://consulta/1"},
                {"NR_PROCESSO": "2", "SG_UF_TRIBUNAL": "DF", "NR_INSTANCIA": "3", "DS_CLASSE": "REPRESENTAÇÃO", "DS_ASSUNTO_PRINCIPAL": "Pesquisa Eleitoral",
                 "DT_AUTUACAO": "01/10/2026", "DT_BAIXA": "05/10/2026", "QT_DECISOES": "0", "DS_URL_PROCESSO": "https://consulta/2"}]
        ass = [{"NR_PROCESSO": "1", "DS_ASSUNTO": "Divulgação de Fato Sabidamente Inverídico"}]
        par = [{"NR_PROCESSO": "2", "SQ_CANDIDATO": "999", "DS_POLO": "PASSIVO", "NM_PARTE": "FULANO", "ST_CANDIDATO": "S"},
               {"NR_PROCESSO": "1", "SQ_CANDIDATO": "", "DS_POLO": "ATIVO", "NM_PARTE": "PESSOA COMUM", "ST_CANDIDATO": "N"}]
        out = cp.agregar({"processo": proc, "assuntos": ass, "decisoes": [{"DS_TIPO_DECISAO": "Decisão", "DT_DECISAO": "11/09/2026"}], "partes": par, "recursos": []},
                         {"999": {"nome": "CANDIDATO X", "cargo": "Presidente", "numero": "99"}})
        self.assertEqual(out["totais"]["processos"], 2)
        self.assertEqual(out["temas"]["desinformação ou fato inverídico"]["processos"], 1)
        self.assertEqual(out["temas"]["internet e redes sociais"]["processos"], 1)
        self.assertEqual(out["temas"]["pesquisa eleitoral"]["por_tribunal"], [("TSE", 1)])
        c = out["candidatos_presidencia"][0]
        self.assertEqual((c["nome"], c["processos"], c["lista"][0]["polo"]), ("CANDIDATO X", 1, ["PASSIVO"]))
        self.assertNotIn("PESSOA COMUM", str(out))
        self.assertEqual(out["por_mes_autuacao"], [("2026-09", 1), ("2026-10", 1)])

    def test_lista_de_ia_e_tema_por_chapa(self):
        proc = [{"NR_PROCESSO": "7", "SG_UF_TRIBUNAL": "BR", "NR_INSTANCIA": "3", "DS_CLASSE": "REPRESENTAÇÃO",
                 "DS_ASSUNTO_PRINCIPAL": "Propaganda Política - Propaganda Eleitoral - Deep Fake", "DT_AUTUACAO": "15/10/2026", "DT_BAIXA": "",
                 "QT_DECISOES": "1", "DS_URL_PROCESSO": "https://consulta/7"}]
        par = [{"NR_PROCESSO": "7", "SQ_CANDIDATO": "13", "DS_POLO": "Pólo ativo", "NM_PARTE": "LULA"},
               {"NR_PROCESSO": "7", "SQ_CANDIDATO": "", "DS_POLO": "Pólo passivo", "NM_PARTE": "PERFIL COMUM"}]
        out = cp.agregar({"processo": proc, "assuntos": [], "decisoes": [], "partes": par, "recursos": []},
                         {"13": {"nome": "LULA", "cargo": "Presidente", "numero": "13"}})
        ia = out["temas"]["inteligência artificial ou conteúdo sintético"]
        self.assertEqual(len(ia["lista"]), 1)
        self.assertEqual(ia["lista"][0]["chapas"], ["LULA (presidente, 13) · polo ativo"])
        self.assertEqual(out["tema_por_chapa"]["inteligência artificial ou conteúdo sintético"][0]["polo"], "ativo")
        self.assertNotIn("PERFIL COMUM", str(out))


if __name__ == "__main__":
    unittest.main()
