import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import collect_imprensa_ia as ci  # noqa: E402

RAIZ = Path(__file__).resolve().parents[1]


class TestImprensaIA(unittest.TestCase):
    def test_filtro_e_acumulo(self):
        cfg = json.loads((RAIZ / "data/config/imprensa_ia.json").read_text(encoding="utf-8"))
        self.assertTrue(ci.relevante("Vídeos feitos com IA inundam a eleição", cfg))
        self.assertTrue(ci.relevante("A.I. Election Videos Are Flooding Brazil", cfg))
        self.assertFalse(ci.relevante("IA vai mudar o mercado de trabalho", cfg))      # sem eleição
        self.assertFalse(ci.relevante("Lula visita a Bahia", cfg))                      # sem IA
        rodada = [[{"titulo": "Deepfake de Lula circula na eleição", "link": "u1", "veiculo": "A", "data_publicacao": "2026-10-20T10:00:00Z"},
                   {"titulo": "Receita de bolo", "link": "u2"}],
                  [{"titulo": "TSE e a inteligência artificial na eleição", "link": "u3", "veiculo": "B", "data_publicacao": "2026-10-21T10:00:00Z"}]]
        cwd = os.getcwd()
        with tempfile.TemporaryDirectory() as t:
            (Path(t) / "data/config").mkdir(parents=True)
            (Path(t) / "data/config/imprensa_ia.json").write_text(json.dumps(cfg), encoding="utf-8")
            os.chdir(t)
            try:
                for itens in rodada:
                    ci.main([], ler=lambda url, it=itens: it)
                d = json.loads(Path("data/ia/imprensa.json").read_text(encoding="utf-8"))
            finally:
                os.chdir(cwd)
        self.assertEqual([x["link"] for x in d["itens"]], ["u3", "u1"])      # acumula, mais novo primeiro, filtro aplicado
        self.assertEqual(len(d["itens"][1]["consultas"]), len(cfg["consultas"]))


if __name__ == "__main__":
    unittest.main()
