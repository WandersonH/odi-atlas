"""Fichas de YouTube pela API oficial: duração, janela, médias e engajamento (dados fictícios)."""
import datetime as dt
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import build_youtube_fichas as yf  # noqa: E402


def v(pub, dur, views, likes, coms):
    return {"publicado_em": pub, "duracao": dur, "visualizacoes": views, "curtidas": likes, "comentarios": coms}


class TestFichas(unittest.TestCase):
    def test_segundos(self):
        self.assertEqual(yf.segundos("PT1H2M3S"), 3723)
        self.assertEqual(yf.segundos("PT59S"), 59)
        self.assertEqual(yf.segundos("P0D"), 0)
        self.assertEqual(yf.segundos("P1DT1S"), 86401)
        self.assertIsNone(yf.segundos(""))

    def test_resumo_engajamento_razao_das_somas(self):
        r = yf.resumo([v("", "", "1000", "90", "10"), v("", "", "3000", "100", "100")])
        self.assertEqual(r["videos"], 2)
        self.assertEqual(r["media_visualizacoes"], 2000)
        self.assertEqual(r["engajamento"], 7.5)  # (100 + 200) / 4000

    def test_resumo_contagens_ocultas(self):
        r = yf.resumo([v("", "", "1000", "", "10"), v("", "", "1000", "50", "")])
        self.assertEqual((r["curtidas_ocultas"], r["comentarios_desativados"]), (1, 1))
        self.assertIsNone(r["engajamento"])  # nenhum vídeo com as três contagens
        self.assertEqual(yf.resumo([])["videos"], 0)

    def test_janela_carencia_e_formato(self):
        hoje = dt.date(2026, 10, 15)
        vids = [v("2026-10-14T10:00:00Z", "PT30S", "10", "1", "0"),      # dentro das 48 h: fora
                v("2026-10-12T10:00:00Z", "PT30S", "100", "10", "0"),    # curto, na janela
                v("2026-10-01T10:00:00Z", "PT10M", "300", "20", "10"),   # longo, na janela
                v("2026-10-05T10:00:00Z", "P0D", "0", "0", "0"),         # agendado: fora
                v("2026-09-01T10:00:00Z", "PT10M", "999", "1", "1")]     # antes da janela; conta na campanha
        f = yf.ficha(vids, hoje, 30, 48, 180)
        self.assertEqual(f["janela"]["videos"], 2)
        self.assertEqual(f["curtos"]["videos"], 1)
        self.assertEqual(f["longos"]["media_visualizacoes"], 300)
        self.assertEqual(f["janela"]["engajamento"], 10.0)  # (10 + 30) / 400
        self.assertEqual(f["campanha"]["videos"], 4)


if __name__ == "__main__":
    unittest.main()
