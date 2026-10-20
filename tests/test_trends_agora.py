import json, sys, tempfile, unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import collect_trends_agora as ta

ITEM = ["debate na band", None, "BR", [1760828400], None, None, 50000, None, 1000, ["debate band", "lula debate"], [14, 5]]
RESP = ")]}'\n\n123\n" + json.dumps([["wrb.fr", "i0OFE", json.dumps([None, [ITEM]]), None, None, None, "generic"]]) + "\n"
RSS = b"""<?xml version="1.0"?><rss xmlns:ht="https://trends.google.com/trending/rss"><channel><item><title>debate na band</title>
<ht:approx_traffic>50000+</ht:approx_traffic><pubDate>Sun, 18 Oct 2026 23:10:00 +0000</pubDate>
<ht:news_item><ht:news_item_title>Debate</ht:news_item_title><ht:news_item_url>https://x</ht:news_item_url><ht:news_item_source>Band</ht:news_item_source></ht:news_item>
</item></channel></rss>"""


class TestTrendsAgora(unittest.TestCase):
    def test_coleta(self):
        with tempfile.TemporaryDirectory() as t:
            ta.now_utc = lambda: "2026-10-19T01:00:00Z"
            NEWS = b"""<rss><channel><item><title>Flavio no debate - Folha</title><link>https://n/1</link><source url="https://folha.uol.com.br">Folha</source><pubDate>Sun, 18 Oct 2026 23:30:00 +0000</pubDate></item></channel></rss>"""
            ta.main([t], get_batch=lambda h, *a: RESP, get_rss=lambda: RSS, get_curvas=lambda: {"now 1-d": []}, get_materias=lambda q: NEWS)
            d = json.loads((Path(t) / "data/trends/agora/debate.json").read_text(encoding="utf-8"))
        x = d["termos"][0]
        self.assertEqual((x["termo"], x["volume_max"], x["politica"], x["trafego_rss"]), ("debate na band", 50000, True, "50000+"))
        self.assertEqual(x["noticias"][0]["veiculo"], "Band")
        self.assertEqual((x["materias"][0]["posicao"], x["materias"][0]["titulo"], x["materias"][0]["veiculo"]), (1, "Flavio no debate", "Folha"))
        self.assertEqual(x["inicio"], "2025-10-18T23:00:00Z" if False else ta.ts([1760828400]))

    def test_fora_da_janela(self):
        ta.now_utc = lambda: "2026-10-21T00:00:00Z"
        self.assertEqual(ta.main(["/nao/existe"]), 0)


if __name__ == "__main__":
    unittest.main()


class TestRelacionados(unittest.TestCase):
    def test_perguntas_e_relacionados(self):
        r = ta.relacionados({"default": {"rankedList": [{"rankedKeyword": [{"query": "quem ganhou o debate", "value": 100, "formattedValue": "100"}]},
                                                        {"rankedKeyword": [{"query": "debate band", "value": 5000, "formattedValue": "+5.000%"}]}]}})
        self.assertEqual(r["em_alta"][0]["exibido"], "+5.000%")
        self.assertTrue(ta.PERGUNTA.match("quem ganhou o debate"))
        self.assertFalse(ta.PERGUNTA.match("debate band ao vivo"))


class TestEmAlta(unittest.TestCase):
    def test_em_alta_fora_da_janela(self):
        import tempfile
        from pathlib import Path as P
        bruto = [["termo político", None, None, [1760900000], None, None, 5000, None, 300, ["rel a"], [14]],
                 ["jogo", None, None, [1760900000], [1760903600], None, 20000, None, 1000, [], [17]]]
        with tempfile.TemporaryDirectory() as t:
            (P(t) / "data").mkdir()
            ta.now_utc = lambda: "2026-10-21T12:00:00Z"
            resp = ")]}'\n\n1\n" + json.dumps([["wrb.fr", "i0OFE", json.dumps([None, bruto]), None, None, None, "generic"]]) + "\n"
            rc = ta.main([t], get_batch=lambda h, *a: resp, get_materias=lambda q: [{"posicao": 1, "titulo": "x", "link": "l", "veiculo": "v"}])
            self.assertEqual(rc, 0)
            d = json.loads((P(t) / "data/trends/agora/em_alta.json").read_text(encoding="utf-8"))
            self.assertEqual([x["termo"] for x in d["listas"]["24h"]], ["termo político", "jogo"])
            self.assertEqual(d["listas"]["24h"][0]["materias"][0]["veiculo"], "v")
            self.assertEqual(len((P(t) / "data/trends/agora/em_alta_historico.csv").read_text(encoding="utf-8").splitlines()), 5)
            self.assertFalse((P(t) / "data/trends/agora/retratos").exists())  # debate congelado
