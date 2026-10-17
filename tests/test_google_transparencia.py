import json, sys, tempfile, unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import collect_google_transparencia as g

RAIZ = Path(__file__).resolve().parents[1]


class TestTransparencia(unittest.TestCase):
    def test_parse(self):
        d = {"1": [{"1": "AR1", "2": "CR1", "4": 2, "6": {"1": "1773798838", "2": 0}, "7": {"1": "1774376329"}, "12": "PT", "14": "pt.org.br"}]}
        c = g.parse_criativos(d, "x")[0]
        self.assertEqual((c["formato"], c["primeira_exibicao"], c["ultima_exibicao"]), ("imagem", "2026-03-18", "2026-03-24"))
        self.assertIn("/advertiser/AR1/creative/CR1", c["url"])

    def test_aceitar_sem_homonimos(self):
        aceitos = ["partido dos trabalhadores", "luiz inacio lula da silva"]
        self.assertTrue(g.aceitar({"nome": "PARTIDO DOS TRABALHADORES - PT", "pais": "BR"}, aceitos))
        self.assertFalse(g.aceitar({"nome": "MONICA ROCHA LULA", "pais": "BR"}, aceitos))
        self.assertFalse(g.aceitar({"nome": "Partido dos Trabalhadores", "pais": "US"}, aceitos))

    def test_main(self):
        def fake(cfg):
            return ({"AR1": {"advertiser_id": "AR1", "nome": "PT", "encontrado_por": "x"}},
                    [{"creative_id": "CR1", "advertiser_id": "AR1", "anunciante": "PT", "dominio": "", "formato": "vídeo",
                      "primeira_exibicao": "2026-09-01", "ultima_exibicao": "2026-09-03", "origem": "x", "url": "u"},
                     {"creative_id": "CR2", "advertiser_id": "AR1", "anunciante": "PT", "dominio": "", "formato": "imagem",
                      "primeira_exibicao": "2026-03-01", "ultima_exibicao": "2026-03-05", "origem": "x", "url": "u"}], [])
        with tempfile.TemporaryDirectory() as t:
            r = Path(t); (r / "data/config").mkdir(parents=True)
            (r / "data/config/google_transparencia.json").write_text((RAIZ / "data/config/google_transparencia.json").read_text(encoding="utf-8"), encoding="utf-8")
            self.assertEqual(g.main([str(r)], coletar_fn=fake), 0)
            o = json.loads((r / "data/google_ads/transparencia.json").read_text(encoding="utf-8"))
            a = o["anunciantes"][0]
            self.assertEqual((a["anuncios"], a["exibidos_na_campanha"], o["status"]), (2, 1, "ok"))
            self.assertEqual([c["creative_id"] for c in o["anuncios_exibidos_na_campanha"]], ["CR1"])


if __name__ == "__main__":
    unittest.main()
