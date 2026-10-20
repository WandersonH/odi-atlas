import json, sys, tempfile, unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import collect_rotulo_ia as cr
import build_rotulo_ia as br


class TestRotuloIA(unittest.TestCase):
    def test_campos(self):
        it = {"id": "1", "desc": "x", "aigcLabelType": 1, "AIGCDescription": "", "stats": {"playCount": 3}, "music": {"isAiGenerated": False}}
        c = cr.campos_ia(it)
        self.assertEqual(c, {"aigcLabelType": 1, "AIGCDescription": "", "music.isAiGenerated": False})
        self.assertTrue(cr.tem_rotulo(c))
        self.assertFalse(cr.tem_rotulo({"AIGCDescription": "", "x.isAiGenerated": False}))
        self.assertFalse(cr.tem_rotulo({"ShowAIGC": True, "aigcLabelType": 0, "AIGCDescription": ""}))
        self.assertTrue(cr.tem_rotulo({"ShowAIGC": True, "moderationAigcLabelType": 1}))

    def test_agregados(self):
        y = {"videos": [{"id": "a", "origem": "canal da candidatura", "candidato": "Lula", "canal": "c", "titulo": "t", "publicado_em": "2026-10-01",
                         "campo_presente": True, "sintetico_declarado": True},
                        {"id": "b", "origem": "canal da candidatura", "candidato": "Lula", "canal": "c", "titulo": "t", "publicado_em": "2026-10-02",
                         "campo_presente": False, "sintetico_declarado": None},
                        {"id": "c", "origem": "vídeo sobre o debate", "candidato": None, "canal": "d", "titulo": "t", "publicado_em": "2026-10-19",
                         "campo_presente": True, "sintetico_declarado": False}]}
        r = br.youtube(y)
        self.assertEqual(r["por_candidato"]["Lula"], {"videos": 2, "campo_presente": 1, "declarados": 1, "pct": 50.0})
        self.assertEqual(r["debate"], {"videos": 1, "declarados": 0})
        self.assertEqual([v["id"] for v in r["lista"]], ["a"])
        with tempfile.TemporaryDirectory() as t:
            p = Path(t) / "data/checagens"
            p.mkdir(parents=True)
            (p / "checagens.json").write_text(json.dumps({"itens": [
                {"afirmacao": "Vídeo de Flávio foi gerado por IA", "titulo": "", "candidatos": ["Flávio Bolsonaro"], "agencia": "A", "data_checagem": "2026-10-16"},
                {"afirmacao": "Lula disse que ia votar", "titulo": "", "candidatos": ["Lula"], "agencia": "B", "data_checagem": "2026-10-10"}]}), encoding="utf-8")
            k = br.checagens(Path(t))
        self.assertEqual((k["sobre_ia"], k["total_base"], k["citam_candidato"]), (1, 2, {"Lula": 0, "Flávio Bolsonaro": 1}))


if __name__ == "__main__":
    unittest.main()


class TestCasoBusca(unittest.TestCase):
    def test_config_e_youtube(self):
        import collect_caso_busca as cb
        import build_caso_busca as bb
        cb.configurar("005")
        self.assertTrue(cb.RX_TITULO.search("Caso ANA CLARA: menina morta"))
        cb.configurar("002")
        self.assertTrue(cb.RX_TITULO.search("Onde mora o ladrão?") and cb.RX_ATRIBUTO.search("onde mora"))
        y = bb.youtube({"videos": [{"id": "a", "canal_id": "c1", "publicado_em": "2022-11-03", "visualizacoes": 100, "curtidas": 5, "comentarios": 2, "inscritos": 50000, "titulo": "t", "canal": "C"},
                                   {"id": "b", "canal_id": "c2", "publicado_em": "2026-10-09", "visualizacoes": 10, "curtidas": None, "comentarios": 1, "inscritos": 300, "titulo": "t", "canal": "P"}]})
        self.assertEqual((y["videos"], y["visualizacoes"], y["videos_de_canais_pequenos"]), (2, 110, 1))
        self.assertEqual([v["id"] for v in y["mais_vistos"]], ["a"])
        self.assertEqual(y["por_ano"]["2022"]["visualizacoes"], 100)
        self.assertTrue(cb.CATEGORIAS["relato de teste"].search("testei aqui e deu o lula"))


class TestRedesCaso(unittest.TestCase):
    def test_privacidade(self):
        import redes_caso as rc
        n, a, d = rc.circulacao([{"canal_id": "c1", "canal": "Canal Grande", "inscritos": 50000, "visualizacoes": 10, "consulta": "q"},
                                 {"canal_id": "c2", "canal": "Fulano", "inscritos": 20, "visualizacoes": 5, "consulta": "q"}],
                                [{"veiculo": "G1", "consulta": "q"}],
                                [{"conta": "pessoa", "seguidores": "15", "verificada": "0", "termo": "#x", "visualizacoes": "3"}])
        rotulos = {v["rotulo"] for v in n.values()}
        self.assertIn("Canal Grande", rotulos)
        self.assertNotIn("Fulano", rotulos)
        self.assertNotIn("@pessoa", rotulos)
        rows = [{"comment_id": "1", "parent_id": "", "tipo": "comentario", "autor_canal": "X", "autor_nome": "Maria"},
                {"comment_id": "2", "parent_id": "1", "tipo": "resposta", "autor_canal": "Y", "autor_nome": "João"}]
        n, a, r = rc.respostas(rows)
        self.assertEqual(set(n), {"A0001", "A0002"})
        self.assertEqual(r["respostas_entre_autores"], 1)
