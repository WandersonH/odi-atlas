import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import importar_apify_runs as ia  # noqa: E402


class TestPaginasEFiltro(unittest.TestCase):
    def test_paginas_com_nova_tentativa(self):
        falhas = {"n": 0}

        def chamar(m, path, tok, *a):
            if "offset=500" in path and falhas["n"] == 0:
                falhas["n"] += 1
                raise ConnectionError("IncompleteRead")
            off = int(path.split("offset=")[1])
            return [{"i": off + k} for k in range(500 if off < 1000 else 20)]
        self.assertEqual(len(ia.paginas(chamar, "t", "ds")), 1020)

    def test_filtro_url_separa_os_posts(self):
        def chamar(m, path, tok, *a):
            if path.startswith("/actor-runs"):
                return {"data": {"items": [] if "offset=1000" in path else [
                    {"id": "A", "actId": "x", "startedAt": "2026-10-26T05:06:00Z", "defaultKeyValueStoreId": "kA", "defaultDatasetId": "dA"},
                    {"id": "B", "actId": "x", "startedAt": "2026-10-26T05:40:00Z", "defaultKeyValueStoreId": "kB", "defaultDatasetId": "dB"}]}}
            if path.startswith("/acts/"):
                return {"data": {"username": "datadoping", "name": "comments"}}
            if "records/INPUT" in path:
                return {"post_urls": ["https://www.instagram.com/reel/DeuEvFlRfuH/"]} if "kA" in path else {"post_urls": ["https://www.instagram.com/p/DeujIRxGDYZ/"]}
            return [{"id": 1}]
        with tempfile.TemporaryDirectory() as d:
            man = ia.importar("t", "009", "2026-10-26", "2026-10-26", "datadoping", Path(d) / "p", Path(d) / "pub", chamar, filtro_url="DeuEvFlRfuH")
            self.assertEqual([r["run_id"] for r in man["runs"]], ["A"])
