"""Leitura do número de seguidores de canais de WhatsApp (HTML fictício)."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import collect_whatsapp as wa  # noqa: E402


class TestWhatsapp(unittest.TestCase):
    def test_numero(self):
        self.assertEqual(wa.numero("12,3", "mil"), 12300)
        self.assertEqual(wa.numero("1,2", "mi"), 1_200_000)
        self.assertEqual(wa.numero("12.3", "K"), 12300)
        self.assertEqual(wa.numero("1.234", None), 1234)
        self.assertEqual(wa.numero("987", None), 987)

    def test_extrair_texto_visivel(self):
        h = ('<html><head><meta property="og:title" content="Canal Exemplo"><script>var x="99 seguidores"</script></head>'
             '<body><h3>Canal Exemplo</h3><span>Canal</span> · <span>45,6 mil seguidores</span></body></html>')
        r = wa.extrair(h)
        self.assertEqual((r["nome"], r["seguidores"], r["texto_original"]), ("Canal Exemplo", 45600, "45,6 mil seguidores"))

    def test_extrair_meta_em_ingles(self):
        h = '<html><head><title>WhatsApp Channel: Exemplo</title><meta name="description" content="Channel • 2.1M followers"></head><body></body></html>'
        r = wa.extrair(h)
        self.assertEqual((r["nome"], r["seguidores"]), ("Exemplo", 2_100_000))

    def test_sem_numero(self):
        self.assertNotIn("seguidores", wa.extrair("<html><body>nada</body></html>"))


if __name__ == "__main__":
    unittest.main()
