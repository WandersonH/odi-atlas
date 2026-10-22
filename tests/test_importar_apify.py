import json
import sys
import tempfile
import unittest
import urllib.error
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import importar_apify_runs as ia  # noqa: E402


def fake(method, path, token, body=None, timeout=0):
    assert method == "GET"  # só leitura
    if path.startswith("/actor-runs"):
        return {"data": {"items": [
            {"id": "r3", "actId": "a2", "startedAt": "2026-09-25T10:00:00Z"},
            {"id": "r2", "actId": "a1", "startedAt": "2026-09-24T12:04:01Z", "defaultKeyValueStoreId": "k2", "defaultDatasetId": "d2", "meta": {"origin": "WEB"}},
            {"id": "r1", "actId": "a1", "startedAt": "2026-09-23T21:59:21Z", "defaultKeyValueStoreId": "k1", "defaultDatasetId": "d1", "meta": {"origin": "API"}},
            {"id": "r0", "actId": "a1", "startedAt": "2026-09-20T00:00:00Z"}]}}
    if path.startswith("/acts/"):
        return {"data": {"username": "xquik", "name": "x-engagement"}}
    if path == "/key-value-stores/k1/records/INPUT":
        return {"tweet": "2060119225176404134"}
    if path.startswith("/key-value-stores/"):
        raise urllib.error.HTTPError(path, 404, "not found", {}, None)
    if path.startswith("/datasets/d1/"):
        return [{"id": "1"}, {"id": "2"}]
    raise urllib.error.HTTPError(path, 404, "not found", {}, None)


class TestImportarApify(unittest.TestCase):
    def test_janela_leitura_e_retencao(self):
        with tempfile.TemporaryDirectory() as t:
            man = ia.importar("x", "006", "2026-09-23", "2026-09-24", "xquik", Path(t) / "priv", Path(t) / "pub", chamar=fake)
            pub = (Path(t) / "pub/importacao_apify.json").read_text(encoding="utf-8")
            bruto = json.loads((Path(t) / "priv/r1.json").read_text(encoding="utf-8"))
        self.assertEqual([r["run_id"] for r in man["runs"]], ["r1", "r2"])
        self.assertEqual(man["itens_total"], 2)
        self.assertTrue(man["runs"][1]["dataset"].startswith("⛔"))   # apagado: registrado, não estimado
        self.assertNotIn("2060119225176404134", pub)                  # entrada só no privado
        self.assertEqual(bruto["input"], {"tweet": "2060119225176404134"})


if __name__ == "__main__":
    unittest.main()
