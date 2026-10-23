import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import collect_busca_ia as b  # noqa: E402


class TestBuscaIA(unittest.TestCase):
    def test_teto_do_lote_e_agregados(self):
        chamadas = []

        def executar(ator, pl, cap):
            chamadas.append((ator, pl, cap))
            if "tiktok" in ator:
                itens = [{"id": f"{pl['keywords'][0]}-{i}", "title": "Lula IA eleição", "views": 1000 * i, "channel": {"username": "grande", "followers": 50000}} for i in range(3)]
            else:
                itens = [{"shortCode": f"{pl['hashtags'][0]}{i}", "caption": "Flávio IA", "likesCount": i, "ownerUsername": "pessoa"} for i in range(2)]
            return {"id": "r", "status": "SUCCEEDED", "usageTotalUsd": 0.5}, itens
        C = b.cfg()
        with tempfile.TemporaryDirectory() as d:
            priv, pub = Path(d) / "priv", Path(d) / "pub"
            man = b.coletar(C, priv, pub, executar)
            self.assertLessEqual(man["gasto_antes_usd"] + man["custo_usd"], C["teto_usd"] + 1e-9)
            self.assertTrue(all(c <= C["teto_usd"] for _, _, c in chamadas))
            n1 = len(chamadas)
            b.coletar(C, priv, pub, executar)  # 2ª vez: buscas já feitas não repetem
            self.assertEqual(len(chamadas), n1)  # o teto do lote já foi gasto: nada roda de novo
            self.assertTrue(any("⛔ não executada" in (e.get("status") or "") for e in man["execucoes"]))
            itens = b.itens_privados(C, priv)
            out = b.agregar(itens, C)
        self.assertGreater(out["redes"]["TikTok"]["posts"], 0)
        self.assertEqual(out["redes"]["Instagram"]["mais_vistos"], [])  # sem seguidores conhecidos: ninguém nomeado
        self.assertTrue(all((p["seguidores"] or 0) >= 10000 for p in out["redes"]["TikTok"]["mais_vistos"]))
        self.assertNotIn("pessoa", json.dumps(out))


if __name__ == "__main__":
    unittest.main()
