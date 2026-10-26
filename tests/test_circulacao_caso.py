import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import circulacao_caso as cc  # noqa: E402

CFG = {"009": {"teto_usd": 0.2, "ate": "2099-01-01", "posts": [
    {"rotulo": "reel", "url": "https://www.instagram.com/reel/AAA/", "ator": "reel", "pasta": "009"},
    {"rotulo": "carrossel", "url": "https://www.instagram.com/p/BBB/?img_index=8", "ator": "post", "pasta": "009b"}]}}


class TestCirculacao(unittest.TestCase):
    def _amb(self, d):
        root, interno = Path(d) / "pub", Path(d) / "int"
        (root / "data/config").mkdir(parents=True)
        (root / "data/config/circulacao_caso.json").write_text(json.dumps(CFG), encoding="utf-8")
        (interno / "casos/009/apify").mkdir(parents=True)
        (interno / "casos/009/apify/r0.json").write_text(json.dumps({"run_id": "r0", "fim_utc": "2026-10-26T05:06:02.031Z", "items": [
            {"shortCode": "AAA", "likesCount": 10, "videoPlayCount": 100, "commentsCount": 3, "sharesCount": 7, "ownerUsername": "grande", "type": "Video"}]}), encoding="utf-8")
        (interno / "casos/009/perfil_instagram.json").write_text(json.dumps({"seguidores": 26000000}), encoding="utf-8")
        (interno / "casos/009b").mkdir(parents=True)
        (interno / "casos/009b/perfil_instagram.json").write_text(json.dumps({"seguidores": 500}), encoding="utf-8")
        return root, interno

    def test_ponto_zero_leitura_diaria_e_privacidade(self):
        chamadas = []

        def executar(tok, ator, pl, cap):
            chamadas.append(ator)
            cod = "AAA" if "reel" in ator else "BBB"
            return {"id": f"x{len(chamadas)}", "usageTotalUsd": 0.005}, [{"shortCode": cod, "likesCount": 20, "commentsCount": 4, "ownerUsername": "pequeno" if cod == "BBB" else "grande"}]
        with tempfile.TemporaryDirectory() as d:
            root, interno = self._amb(d)
            with mock.patch.dict(os.environ, {"ODI_INTERNO_DIR": str(interno), "APIFY_TOKEN": ""}):
                cc.main(["--caso", "009"], executar=executar, root=root)
                cc.main(["--caso", "009"], executar=executar, root=root)  # mesmo dia: não lê de novo
            pub = json.loads((root / "data/casos/009/circulacao.json").read_text(encoding="utf-8"))
            self.assertEqual(chamadas, ["apify~instagram-reel-scraper", "apify~instagram-scraper"])
            reel, car = pub["posts"]
            self.assertEqual([x["origem"] for x in reel["serie"]], ["coleta do caso", "leitura diária"])
            self.assertEqual(reel["autor"], "grande")
            self.assertIsNone(car["autor"])  # menos de 10 mil seguidores
            self.assertEqual(car["codigo"], "BBB")
            self.assertNotIn("custo", json.dumps(pub))
            self.assertTrue(all(x["compartilhamentos"] is None for x in car["serie"]))
            est = json.loads((interno / "casos/009/circulacao_estado.json").read_text(encoding="utf-8"))
            self.assertLessEqual(est["gasto_usd"], CFG["009"]["teto_usd"])

    def test_teto_impede_leitura(self):
        with tempfile.TemporaryDirectory() as d:
            root, interno = self._amb(d)
            (interno / "casos/009/circulacao_estado.json").write_text(json.dumps({"gasto_usd": 0.15, "leituras": {}, "erros": []}), encoding="utf-8")
            chamadas = []
            with mock.patch.dict(os.environ, {"ODI_INTERNO_DIR": str(interno)}):
                cc.main(["--caso", "009"], executar=lambda *a: chamadas.append(a) or ({}, []), root=root)
            self.assertEqual(chamadas, [])
