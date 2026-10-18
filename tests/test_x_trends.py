import json, os, sys, tempfile, unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import collect_x_trends as xt

PAG = """<table class="table"><tr><td class="main"><a class="string" href="/brazil/trend/%23ForaLula/">#ForaLula</a><div class="desc"><span>87.1K tweets</span></div></td></tr>
<tr><td class="main"><a href="/brazil/trend/Flamengo/">Flamengo</a><div class="desc"><span>12K tweets</span></div></td></tr>
<tr><td class="main"><a href="/brazil/trend/Bom%20dia/">Bom dia</a></td></tr></table><table><tr><td><a href="/brazil/trend/Velho/">Velho</a></td></tr></table>"""


class TestTrends(unittest.TestCase):
    def test_parse_e_resumo(self):
        it = xt.parse(PAG)
        self.assertEqual([(i["posicao"], i["assunto"], i["volume"]) for i in it], [(1, "#ForaLula", 87100), (2, "Flamengo", 12000), (3, "Bom dia", None)])
        with tempfile.TemporaryDirectory() as d:
            self.assertEqual(xt.main([d], pagina=PAG), 0)
            res = json.loads((Path(d) / "data/x/trends/latest.json").read_text(encoding="utf-8"))
        self.assertEqual(res["citam_candidatos"][0]["assunto"], "#ForaLula")
        self.assertEqual(res["citam_candidatos"][0]["cita"], ["Lula"])


if __name__ == "__main__":
    unittest.main()
