"""Testes do livro de códigos (pré-codificação), corpus IRaMuTeQ, CHD de Reinert e kappa — dados sintéticos."""
import sys
import unittest
from pathlib import Path

import json

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import corpus_populismo as cp  # noqa: E402
import concordancia as cc  # noqa: E402

try:
    import numpy as np
    import chd_reinert as cr  # noqa: E402
except ImportError:
    cr = None

LIVRO = json.loads((Path(__file__).resolve().parents[1] / "data/config/livro_codigos_populismo.json").read_text(encoding="utf-8"))


class TestPrecodificacao(unittest.TestCase):
    def setUp(self):
        self.regs = cp.compilar(LIVRO)

    def test_simetrica_esquerda_e_direita(self):
        self.assertIn("inimigo_contraposicao", cp.precodificar("Os bilionários não pagam imposto", self.regs))
        self.assertIn("inimigo_contraposicao", cp.precodificar("Chega de comunistas no poder", self.regs))

    def test_exclusoes(self):
        self.assertNotIn("inimigo_contraposicao", cp.precodificar("Vamos fortalecer o Sistema Único de Saúde", self.regs))
        self.assertNotIn("ataque_imprensa", cp.precodificar("Presidente fala com a imprensa", self.regs))
        self.assertIn("ataque_imprensa", cp.precodificar("Isso a Globo não mostra", self.regs))
        self.assertNotIn("anticiencia", cp.precodificar("Quem defende o SUS investe em vacinas", self.regs))

    def test_trecho_registrado(self):
        r = cp.precodificar("Fora Moraes, ditadura do STF", self.regs)
        self.assertIn("moraes", r["instituicoes_conflito"])


class TestCorpus(unittest.TestCase):
    def test_limpeza_iramuteq(self):
        t = cp.limpar_iramuteq('Vote 22 *agora* "já" 100% #Flavio @tv https://x.com/a 🇧🇷')
        for ch in '*"%#@':
            self.assertNotIn(ch, t)
        self.assertNotIn("https", t)

    def test_segmentos_e_variaveis(self):
        segs = cp.segmentos(" ".join(["palavra"] * 95) + ". fim.")
        self.assertTrue(all(len(s.split()) <= 40 for s in segs))
        self.assertEqual(cp.var("Flávio Bolsonaro"), "flaviobolsonaro")
        self.assertEqual(cp.formato("PT45S"), "short")
        self.assertEqual(cp.formato("PT1H2M"), "longo")
        self.assertEqual(cp.semana("2026-07-20T10:00:00Z"), 1)  # semana 1 = início da pré-campanha
        self.assertEqual(cp.semana("2026-07-27T10:00:00Z"), 2)

    def test_amostra_estratificada_estavel(self):
        vids = [{"cid": c, "publicado_em": f"2026-{m:02d}-01", "video_id": f"{c}{m}{i}"}
                for c in "AB" for m in (8, 9, 10) for i in range(20 if c == "A" else 10)]
        a1, a2 = cp.amostra_estratificada(vids, 30), cp.amostra_estratificada(vids, 30)
        self.assertEqual(len(a1), 30)
        self.assertEqual([v["video_id"] for v in a1], [v["video_id"] for v in a2])
        self.assertIn(sum(v["cid"] == "A" for v in a1), (19, 20, 21))  # proporcional: 2/3 de A (±1 do arredondamento por estrato)


@unittest.skipIf(cr is None, "numpy não instalado")
class TestCHD(unittest.TestCase):
    def test_separa_dois_vocabularios(self):
        a = ["escala trabalho descanso familia jornada"] * 30
        b = ["seguranca crime policia faccao territorio"] * 30
        X, voc = cr.matriz(a + b, min_freq=3)
        rot, arv = cr.chd(X, k=2, min_classe=10)
        self.assertEqual(len(set(rot[:30])), 1)
        self.assertEqual(len(set(rot[30:])), 1)
        self.assertNotEqual(rot[0], rot[30])
        self.assertEqual(arv[0]["filhos"], [1, 2])

    def test_chi2_sinal(self):
        ch = cr.chi2_assoc(np.array([10.0, 0.0]), np.array([10.0, 10.0]), 10, 20)
        self.assertGreater(ch[0], 3.84)
        self.assertLess(ch[1], 0)


class TestKappa(unittest.TestCase):
    def test_kappa_valores_conhecidos(self):
        self.assertEqual(cc.kappa(["1", "0", "1", "0"], ["1", "0", "1", "0"]), 1.0)
        # exemplo clássico: po=0.7, pe=0.5 → κ=0.4
        a = ["1"] * 5 + ["0"] * 5
        b = ["1"] * 3 + ["0"] * 2 + ["1"] * 1 + ["0"] * 4
        self.assertAlmostEqual(cc.kappa(a, b), 0.4, places=3)

    def test_precisao_cobertura(self):
        A = {"v1": {"inimigo": "1"}, "v2": {"inimigo": "0"}, "v3": {"inimigo": "1"}, "v4": {"inimigo": "UC"}}
        B = {"v1": {"inimigo": "1"}, "v2": {"inimigo": "0"}, "v3": {"inimigo": "1"}, "v4": {"inimigo": "1"}}
        pre = {"v1": {"inimigo": "1"}, "v2": {"inimigo": "1"}, "v3": {"inimigo": "0"}, "v4": {"inimigo": "1"}}
        r = cc.avaliar(A, B, pre, ["inimigo"])["categorias"]["inimigo"]
        self.assertEqual(r["pre_codificacao"]["consenso"], 3)
        self.assertEqual((r["pre_codificacao"]["precisao"], r["pre_codificacao"]["cobertura"]), (0.5, 0.5))


if __name__ == "__main__":
    unittest.main()
