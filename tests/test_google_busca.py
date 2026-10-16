"""Google Programmable Search: leitura do item (resposta fictícia no formato da API)."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import collect_google_busca as gb  # noqa: E402


class TestGoogleBusca(unittest.TestCase):
    def test_resultado_com_data(self):
        it = {"title": "Título", "link": "https://exemplo.com.br/a", "displayLink": "exemplo.com.br", "snippet": "linha 1\nlinha 2",
              "pagemap": {"metatags": [{"article:published_time": "2026-10-15T10:00:00-03:00"}]}}
        r = gb.resultado(it, 1)
        self.assertEqual((r["posicao"], r["dominio"], r["trecho"], r["data_publicacao"]), (1, "exemplo.com.br", "linha 1 linha 2", "2026-10-15T10:00:00-03:00"))

    def test_resultado_sem_data(self):
        self.assertEqual(gb.data_pub({"title": "x"}), "")



class TestRSS(unittest.TestCase):
    def test_parse_rss(self):
        import collect_google_busca as g
        xml = b"""<?xml version="1.0"?><rss><channel><item><title>Lula faz X - Folha de S.Paulo</title><link>https://news.google.com/a</link>
<pubDate>Thu, 15 Oct 2026 22:10:00 GMT</pubDate><source url="https://www.folha.uol.com.br">Folha de S.Paulo</source></item></channel></rss>"""
        r = g.parse_rss(xml)[0]
        self.assertEqual((r["titulo"], r["dominio"], r["veiculo"], r["data_publicacao"]),
                         ("Lula faz X", "folha.uol.com.br", "Folha de S.Paulo", "2026-10-15T22:10:00Z"))


if __name__ == "__main__":
    unittest.main()
