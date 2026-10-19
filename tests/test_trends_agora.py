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
            ta.main([t], get_batch=lambda h: RESP, get_rss=lambda: RSS, get_curvas=lambda: {"now 1-d": []})
            d = json.loads((Path(t) / "data/trends/agora/debate.json").read_text(encoding="utf-8"))
        x = d["termos"][0]
        self.assertEqual((x["termo"], x["volume_max"], x["politica"], x["trafego_rss"]), ("debate na band", 50000, True, "50000+"))
        self.assertEqual(x["noticias"][0]["veiculo"], "Band")
        self.assertEqual(x["inicio"], "2025-10-18T23:00:00Z" if False else ta.ts([1760828400]))

    def test_fora_da_janela(self):
        ta.now_utc = lambda: "2026-10-21T00:00:00Z"
        self.assertEqual(ta.main(["/nao/existe"]), 0)


if __name__ == "__main__":
    unittest.main()
