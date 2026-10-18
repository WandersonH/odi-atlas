import sys, unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import build_pontes as bp
import build_temas_circulam as tc

L, F = bp.L, bp.F
FASES = [{"id": "turno1", "rotulo": "1º", "de": "2026-08-16", "ate": "2026-10-04"}]


def c(cid, aut, vid, cand, dia="2026-09-01", pai="", texto="economia e emprego"):
    return {"comment_id": cid, "autor_canal": aut, "video_id": vid, "candidate_id": cand, "publicado_em": dia + "T10:00:00Z", "parent_id": pai, "texto": texto}


class TestPontes(unittest.TestCase):
    def test_publicos_e_pontes(self):
        rows = [c("1", "AUTOR_A", "v1", L), c("2", "AUTOR_A", "v1", L), c("3", "AUTOR_A", "v2", F),   # a: público de Lula (2/3) e conta-ponte
                c("4", "AUTOR_B", "v2", F), c("5", "AUTOR_B", "v2", F),                          # b: público de Flávio
                c("6", "z", "v1", L)]                                                # z: 1 comentário, sem público
        casa = bp.publicos(rows)
        self.assertEqual((casa["AUTOR_A"], casa["AUTOR_B"], casa["z"]), (L, F, None))
        rows.append(c("7", "AUTOR_B", "v1", L, pai="1"))  # b (Flávio) responde a a (Lula) → resposta entre públicos
        itens = {"v1": {"candidate_id": L, "data": "2026-09-01", "titulo": "t", "url": "", "temas": ["economia"]},
                 "v2": {"candidate_id": F, "data": "2026-09-01", "titulo": "u", "url": "", "temas": []}}
        temas = bp.bc.compile_cfg({"temas": {"economia": ["economia"]}, "candidatos": {}, "pede_voto": []})
        bp.MIN_AUTORES_ITEM = 1
        r = bp.analisar(rows, {"7": "NEG"}, itens, FASES, temas)
        self.assertEqual(r["contas_ponte"]["autores"], 2)          # a e b comentaram nos dois lados
        self.assertEqual(r["respostas_entre_publicos"]["entre_publicos_diferentes"], 1)
        self.assertEqual(r["respostas_entre_publicos"]["tom"]["negativo"], 100.0)
        self.assertIn("economia", r["respostas_entre_publicos"]["temas"])
        top_l = r["conteudos_que_furam_bolha"]["Lula"]["top"][0]
        self.assertEqual((top_l["id"], top_l["publico_adversario"]), ("v1", 1))
        self.assertNotIn("AUTOR_", str(r))  # nenhum id de autor na saída
        bp.MIN_AUTORES_ITEM = 30


class TestTemasCirculam(unittest.TestCase):
    def test_sequencia_e_correlacao(self):
        sem = [f"s{i}" for i in range(8)]
        lula = [2, 2, 2, 30, 2, 2, 2, 2]
        flav = [2, 2, 2, 2, 30, 2, 2, 2]   # pico uma semana depois
        seq = tc.sequencia(lula, flav, sem)
        self.assertEqual(seq[0]["primeiro"], "Lula")
        self.assertEqual(seq[0]["defasagem_semanas"], 1)
        self.assertEqual(tc.pearson([1, 2, 3, 4, 5], [2, 4, 6, 8, 10]), 1.0)
        self.assertIsNone(tc.pearson([1, None, 3], [1, 2, 3]))

    def test_series_min_itens(self):
        its = [(L, "2026-07-20T00:00:00Z", ["economia"])] * 3
        s, n = tc.series(its, ["economia"], ["2026-07-20"])
        self.assertIsNone(s["economia"]["Lula"][0])   # menos de 5 conteúdos na semana
        self.assertEqual(n["Lula"][0], 3)


if __name__ == "__main__":
    unittest.main()
