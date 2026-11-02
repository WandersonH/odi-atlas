import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import build_atores_caso as ba  # noqa: E402

CAND = {"nome": "Fulano", "numero": "2222", "partido": "PX", "cargo": "Deputado Federal", "uf": "SP", "situacao": "ELEITO", "posicao_partido_2t": "lula"}


class TestAtores(unittest.TestCase):
    def test_cruzamento_partido_e_privacidade(self):
        perf = {("x", "fulano"): CAND, ("instagram", "fulano.of"): CAND}
        it = lambda i, rede, conta, seg, cur: {"rede": rede, "item_id": str(i), "conta": conta, "nome_conta": "N", "seguidores": seg,  # noqa: E731
                                               "publicado_em": "2026-10-30T10:00:00Z", "texto": "t", "visualizacoes": "10", "curtidas": cur,
                                               "comentarios": "0", "compartilhamentos": "0", "termo": "a", "url": f"u{i}"}
        itens = [it(1, "x", "Fulano", "", "5"), it(2, "instagram", "fulano.of", "", "7"), it(3, "x", "pessoa_comum", "300", "99"),
                 it(4, "x", "grande", "50000", "3"), it(1, "x", "Fulano", "", "5")]
        out, linhas = ba.analisar("999", itens, perf, {"candidaturas_com_perfil": 1})
        self.assertEqual(out["amostra"]["publicacoes_lidas"], 4)  # repetida conta uma vez
        self.assertEqual(out["resumo"]["candidaturas_no_caso"], 1)  # mesma pessoa em duas redes
        self.assertEqual(out["partidos"][0]["candidaturas"], 1)
        self.assertEqual(out["partidos"][0]["publicacoes"], 2)
        contas = {a["conta"] for a in out["atores"]}
        self.assertNotIn("pessoa_comum", contas)  # menos de 10 mil e não candidata: só nas contagens
        self.assertIn("grande", contas)
        self.assertNotIn("pessoa_comum", str(linhas))


if __name__ == "__main__":
    unittest.main()
