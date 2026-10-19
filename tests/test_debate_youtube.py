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
