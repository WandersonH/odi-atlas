import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import coletar_caso_perfis_instagram as cp  # noqa: E402


class TestPerfisInstagram(unittest.TestCase):
    def test_posts_do_periodo_e_comentarios_no_teto(self):
        ch = []

        def executar(ator, pl, cap):
            ch.append((ator, pl, cap))
            if "instagram-scraper" in ator:
                return {"id": "p", "usageTotalUsd": 0.02}, [
                    {"url": "https://www.instagram.com/p/A/", "timestamp": "2026-10-25T10:00:00Z", "ownerUsername": "x"},
                    {"url": "https://www.instagram.com/p/B/", "timestamp": "2026-10-20T10:00:00Z", "ownerUsername": "x"}]
            return {"id": "c", "usageTotalUsd": pl["max_comments"] * cp.PRECO_COMENTARIO}, [{"id": "1", "text": "oi"}]
        with tempfile.TemporaryDirectory() as d:
            man = cp.coletar("010", ["x"], "2026-10-24", 2.5, Path(d) / "ig", executar)
            self.assertEqual([p["url"] for p in man["posts"]], ["https://www.instagram.com/p/A/"])
            self.assertEqual(ch[1][1]["code_or_id_or_url"], ["https://www.instagram.com/p/A/"])
            self.assertLessEqual(ch[0][2] + 0, 2.5)
            self.assertLessEqual(ch[1][2], 2.5 - 0.02)
            self.assertTrue(man["dentro_do_teto"])
            self.assertTrue((Path(d) / "ig/manifesto.json").exists())

    def test_rodar_le_em_paginas(self):
        chamadas = []

        def chamar(m, path, tok, *a):
            chamadas.append(path)
            if m == "POST":
                return {"data": {"id": "r", "status": "RUNNING"}}
            if path.startswith("/actor-runs"):
                return {"data": {"id": "r", "status": "SUCCEEDED", "defaultDatasetId": "ds"}}
            off = int(path.split("offset=")[1])
            return [{"i": off + k} for k in range(500 if off == 0 else 3)]
        run, itens = cp.rodar("t", "a~b", {}, 0.1, chamar, espera=lambda s: None)
        self.assertEqual(len(itens), 503)
        self.assertEqual(run["status"], "SUCCEEDED")
