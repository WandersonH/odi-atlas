import sys, unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import collect_debate_youtube as cy
import build_debate_youtube as by


class TestDebateYoutube(unittest.TestCase):
    def test_filtro_e_tipo(self):
        self.assertTrue(cy.sobre_o_debate("DEBATE COMPLETO: LULA X FLÁVIO BOLSONARO na BAND", ""))
        self.assertFalse(cy.sobre_o_debate("Receita de bolo", "debate"))
        self.assertEqual(cy.dur_s("PT1H2M3S"), 3723)
        self.assertEqual(cy.tipo_de({"live_inicio": "x", "duracao_s": 9}), "transmissão ao vivo")
        self.assertEqual(cy.tipo_de({"duracao_s": 3000}), "íntegra ou longo (40 min ou mais)")
        self.assertEqual(cy.tipo_de({"duracao_s": 600}), "corte (3 a 40 min)")
        self.assertEqual(cy.tipo_de({"duracao_s": 50}), "curto (até 3 min)")

    def test_grupo_e_resumo(self):
        self.assertEqual(by.grupo_de({"canal": "Band Jornalismo"}), "emissoras do debate (Band e parceiras)")
        self.assertEqual(by.grupo_de({"canal": "CNN Brasil"}), "outros veículos de imprensa")
        self.assertEqual(by.grupo_de({"canal": "Lula", "campanha": "Lula"}), "canais das campanhas")
        self.assertEqual(by.grupo_de({"canal": "Ben Mendes TV"}), "outros canais (comentaristas, cortes, perfis)")
        r = by.resumo([{"canal_id": "a", "visualizacoes": 10, "curtidas": 2, "comentarios": None, "duracao_s": 3600},
                       {"canal_id": "a", "visualizacoes": 5, "curtidas": None, "comentarios": 3, "duracao_s": 1800}])
        self.assertEqual(r, {"videos": 2, "canais": 1, "visualizacoes": 15, "curtidas": 2, "comentarios": 3, "horas_de_video": 1.5})


if __name__ == "__main__":
    unittest.main()


class TestConteudo(unittest.TestCase):
    def test_conteudo(self):
        self.assertEqual(by.conteudo_de({"titulo": "PRÉ-DEBATE PRESIDENCIAL | Flávio x Lula"}), "pré-debate")
        self.assertEqual(by.conteudo_de({"titulo": "Canal Livre analisa 1º debate"}), "análise, reação e cobertura")
        self.assertEqual(by.conteudo_de({"titulo": "Lula para Flávio sobre voto de presidiários"}), "o debate e trechos dele")


class TestAcumula(unittest.TestCase):
    """22/10/2026: a busca falhou por cota e a lista caiu de 426 para 69 vídeos; o coletor agora acumula vídeos e comentários."""

    def test_coleta_com_busca_parcial_nao_perde_videos_nem_comentarios(self):
        import csv, gzip, json, os, tempfile
        from unittest import mock

        def vid(i, views, titulo="debate Lula Flávio Band"):
            return {"id": i, "titulo": titulo, "descricao": "", "canal": "c", "canal_id": "x", "visualizacoes": views, "curtidas": 1,
                    "comentarios": 5, "duracao_s": 600, "publicado_em": "2026-10-19T00:00:00Z"}
        with tempfile.TemporaryDirectory() as d, tempfile.TemporaryDirectory() as interno:
            cwd = os.getcwd()
            os.chdir(d)
            try:
                Path("data/debate").mkdir(parents=True)
                velho = {**vid("A", 100), "tipo": "corte (3 a 40 min)", "achado_por": "debate Lula Flávio", "comentarios_lidos": 1}
                velho2 = {**vid("B", 50), "tipo": "corte (3 a 40 min)", "achado_por": "debate Lula Flávio", "comentarios_lidos": 1}
                for v in (velho, velho2):
                    v.pop("descricao")
                Path("data/debate/youtube_videos.json").write_text(json.dumps({"videos": [velho, velho2]}), encoding="utf-8")
                p = Path(interno) / "debate/youtube_comentarios.csv.gz"
                p.parent.mkdir(parents=True)
                with gzip.open(p, "wt", encoding="utf-8", newline="") as f:
                    w = csv.DictWriter(f, fieldnames=cy.CAMPOS, delimiter=";", extrasaction="ignore")
                    w.writeheader()
                    w.writerow({"comment_id": "c1", "video_id": "A"})
                    w.writerow({"comment_id": "c2", "video_id": "B"})
                # busca de hoje só acha C; videos.list devolve A atualizado e não devolve B
                with mock.patch.dict(os.environ, {"YOUTUBE_API_KEY": "k", "ODI_INTERNO_DIR": interno}), \
                        mock.patch.object(cy, "buscar", return_value={"C": "debate Lula Flávio"}), \
                        mock.patch.object(cy, "detalhes", side_effect=lambda k, ids: [vid("A", 300), vid("C", 10)]), \
                        mock.patch.object(cy, "comentarios", return_value=([{"comment_id": "c3", "video_id": "C"}], {"C": "ok"})):
                    self.assertEqual(cy.main(), 0)
                out = json.loads(Path("data/debate/youtube_videos.json").read_text(encoding="utf-8"))
                vs = {v["id"]: v for v in out["videos"]}
                self.assertEqual(set(vs), {"A", "B", "C"})
                self.assertEqual(vs["A"]["visualizacoes"], 300)       # relido: número novo
                self.assertEqual(vs["B"]["visualizacoes"], 50)        # não relido: fica o último número, marcado
                self.assertIn("nao_relido_em", vs["B"])
                self.assertEqual(out["comentarios_lidos"], 3)
                self.assertEqual({v["id"]: v["comentarios_lidos"] for v in out["videos"]}, {"A": 1, "B": 1, "C": 1})
                rows = list(csv.DictReader(gzip.open(p, "rt", encoding="utf-8"), delimiter=";"))
                self.assertEqual({r["comment_id"] for r in rows}, {"c1", "c2", "c3"})
            finally:
                os.chdir(cwd)

    def test_recuperacao_une_versoes_e_ultima_leitura_vence(self):
        import recuperar_debate_youtube as rd
        por = rd.unir_videos([("2026-10-19T00:00:00Z", [{"id": "A", "visualizacoes": 1}, {"id": "B", "visualizacoes": 2}]),
                              ("2026-10-21T00:00:00Z", [{"id": "A", "visualizacoes": 9}])])
        self.assertEqual(por["A"]["visualizacoes"], 9)
        self.assertEqual(por["A"]["numeros_lidos_em"], "2026-10-21T00:00:00Z")
        self.assertEqual(por["B"]["numeros_lidos_em"], "2026-10-19T00:00:00Z")
        self.assertEqual(len(rd.unir_comentarios([[{"comment_id": "1"}], [{"comment_id": "1"}, {"comment_id": "2"}]])), 2)
