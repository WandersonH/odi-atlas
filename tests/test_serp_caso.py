"""SERP do caso: leitura de um retorno simulado do Apify (sem rede)."""
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "scripts"))
import serp_caso as sc  # noqa: E402


class TestSerp(unittest.TestCase):
    def test_grava_ranking(self):
        item = {"searchQuery": {"term": "Valéria Diniz", "resultsTotal": 12300},
                "organicResults": [{"position": 1, "title": "T", "url": "https://www.metropoles.com/x", "description": "d"}],
                "topStories": [{"title": "N", "url": "https://g1.globo.com/y", "source": "g1"}], "relatedQueries": [{"title": "r"}]}
        with tempfile.TemporaryDirectory() as t:
            (Path(t) / "data/config").mkdir(parents=True)
            (Path(t) / "data/config/casos.json").write_text(json.dumps({"casos": [{"id": "020", "buscas_google_serp": ["Valéria Diniz"],
                                                                                  "teto_usd": {"google_serp": 0.3}}]}), encoding="utf-8")
            cwd = os.getcwd()
            os.chdir(t)
            try:
                rc = sc.main(["--caso", "020"], executar=lambda pl, cap: ({"status": "SUCCEEDED", "usageTotalUsd": 0.002}, [item]))
                d = json.loads(Path("data/casos/020/serp.json").read_text(encoding="utf-8"))
            finally:
                os.chdir(cwd)
        self.assertEqual(rc, 0)
        c = d["leituras"][0]["consultas"][0]
        self.assertEqual((c["consulta"], c["total_informado"], c["resultados"][0]["dominio"]), ("Valéria Diniz", 12300, "metropoles.com"))


if __name__ == "__main__":
    unittest.main()
