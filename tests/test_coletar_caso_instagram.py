import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import coletar_caso_instagram as cc  # noqa: E402


class TestColetarCaso(unittest.TestCase):
    def _exec(self, chamadas, custo_por_ator):
        def executar(ator, pl, cap):
            chamadas.append((ator, pl, cap))
            itens = {"apify~instagram-reel-scraper": [{"shortCode": "X", "ownerUsername": "autor", "videoPlayCount": 1, "commentsCount": 9}],
                     "apify~instagram-profile-scraper": [{"username": "autor", "followersCount": 12000}]}.get(ator, [{"id": str(i), "text": "t"} for i in range(3)])
            return {"id": f"r{len(chamadas)}", "status": "SUCCEEDED", "usageTotalUsd": min(cap, custo_por_ator(ator, pl))}, itens
        return executar

    def test_cada_execucao_cabe_no_que_sobra_do_teto(self):
        ch = []
        with tempfile.TemporaryDirectory() as d:
            man = cc.coletar("008", "https://www.instagram.com/reel/X/", 3.0, 2000, Path(d) / "casos/008/apify",
                             self._exec(ch, lambda a, pl: 0.01 if "reel" in a else (pl.get("max_comments", 0) * cc.PRECO_COMENTARIO) or 0.0))
            self.assertLessEqual(man["gasto_usd"], 3.0)
            caps = [c for _, _, c in ch]
            self.assertEqual(caps[0], 0.10)
            self.assertLessEqual(ch[1][1]["max_comments"] * cc.PRECO_COMENTARIO, caps[1])
            self.assertLessEqual(sum(caps[:1]) * 0 + man["runs"][0]["custo_usd"] + caps[1] + caps[2], 3.0 + 1e-9)
            perfil = json.loads((Path(d) / "casos/008/perfil_instagram.json").read_text(encoding="utf-8"))
            self.assertEqual(perfil["seguidores"], 12000)
            self.assertEqual(len(list((Path(d) / "casos/008/apify").glob("r*.json"))), 2)  # o perfil vai só para perfil_instagram.json
            self.assertEqual(len(man["runs"]), 3)

    def test_teto_pequeno_reduz_comentarios(self):
        ch = []
        with tempfile.TemporaryDirectory() as d:
            cc.coletar("008", "https://www.instagram.com/reel/X/", 0.5, 2000, Path(d) / "a", self._exec(ch, lambda a, pl: 0.01))
            self.assertEqual(ch[1][1]["max_comments"], int((0.5 - 0.01 - cc.RESERVA_PERFIL) / cc.PRECO_COMENTARIO))

    def test_nova_tentativa_reaproveita_e_conta_no_teto(self):
        ch = []
        with tempfile.TemporaryDirectory() as d:
            priv = Path(d) / "a"
            priv.mkdir()
            (priv / "r0.json").write_text(json.dumps({"ator": "apify/instagram-reel-scraper · X", "custo_usd": 0, "status": "SUCCEEDED",
                                                      "items": [{"ownerUsername": "autor", "videoPlayCount": 1}]}), encoding="utf-8")
            cc.coletar("008", "u", 1.0, 2000, priv, self._exec(ch, lambda a, pl: 0.01))
            self.assertNotIn("apify~instagram-reel-scraper", [c[0] for c in ch])
            self.assertEqual(ch[0][1]["max_comments"], int((1.0 - 0.01 - cc.RESERVA_PERFIL) / cc.PRECO_COMENTARIO))

    def test_erro_da_api_fica_registrado(self):
        def executar(ator, pl, cap):
            if "datadoping" in ator:
                raise RuntimeError("entrada inválida")
            return {"id": "r", "status": "SUCCEEDED", "usageTotalUsd": 0.01}, [{"ownerUsername": "autor", "videoPlayCount": 1, "followersCount": 5}]
        with tempfile.TemporaryDirectory() as d:
            man = cc.coletar("008", "u", 3.0, 2000, Path(d) / "a", executar)
            self.assertTrue(any("entrada inválida" in e for e in man["erros"]))

    def test_sem_teto_nao_roda(self):
        self.assertEqual(cc.main(["--caso", "008", "--url", "https://www.instagram.com/reel/X/"], executar=lambda *a: None), 1)


if __name__ == "__main__":
    unittest.main()


class TestTranscricao(unittest.TestCase):
    def test_transcricao_liga_o_campo_e_aumenta_o_teto_da_etapa(self):
        ch = []

        def executar(ator, pl, cap):
            ch.append((ator, pl, cap))
            return {"id": f"r{len(ch)}", "status": "SUCCEEDED", "usageTotalUsd": 0.01}, [{"ownerUsername": "autor", "videoPlayCount": 1}]
        with tempfile.TemporaryDirectory() as d:
            cc.coletar("009", "u", 3.5, 2000, Path(d) / "a", executar, transcricao=True)
            self.assertTrue(ch[0][1]["includeTranscript"])
            self.assertEqual(ch[0][2], cc.CAP_TRANSCRICAO)
        ch.clear()
        with tempfile.TemporaryDirectory() as d:
            cc.coletar("009", "u", 3.5, 2000, Path(d) / "a", executar)
            self.assertFalse(ch[0][1]["includeTranscript"])
            self.assertEqual(ch[0][2], cc.MIN_CAP)
