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


    def test_historico_horario_acumula_cada_leitura(self):
        import csv, json, tempfile
        from pathlib import Path
        import collect_whatsapp as cw
        orig_b, orig_n = cw.baixar, cw.now_utc
        cw.baixar = lambda url, idioma: '<meta property="og:title" content="Canal X"><meta name="d" content="1,2 mil seguidores">'
        try:
            with tempfile.TemporaryDirectory() as t:
                (Path(t) / "data/config").mkdir(parents=True)
                (Path(t) / "data/config/whatsapp_canais.json").write_text(json.dumps({"canais": [{"id": "A1", "nome": "X", "lado": "Lula"}]}), encoding="utf-8")
                for hora in ("2026-10-21T22:05:00Z", "2026-10-21T23:05:00Z"):
                    cw.now_utc = lambda h=hora: h
                    self.assertEqual(cw.main([t]), 0)
                ler = lambda n: list(csv.DictReader(open(Path(t) / "data/whatsapp" / n, encoding="utf-8"), delimiter=";"))
                self.assertEqual(len(ler("seguidores_horario.csv")), 2)
                self.assertEqual(len(ler("seguidores.csv")), 1)   # a planilha diária guarda a última leitura do dia
                self.assertEqual(ler("seguidores.csv")[0]["coletado_em_utc"], "2026-10-21T23:05:00Z")
        finally:
            cw.baixar, cw.now_utc = orig_b, orig_n

if __name__ == "__main__":
    unittest.main()
