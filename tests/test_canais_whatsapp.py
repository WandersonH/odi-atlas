import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import canais_whatsapp as cw  # noqa: E402


class TestNumero(unittest.TestCase):
    def test_formatos(self):
        self.assertEqual(cw.numero("Channel · 161K followers"), 161000)
        self.assertEqual(cw.numero("1,2 mi seguidores"), 1200000)
        self.assertEqual(cw.numero("44.926 seguidores"), 44926)
        self.assertEqual(cw.numero("10 740 000 abonnés"), 10740000)
        self.assertEqual(cw.numero("10.7M followers"), 10700000)
        self.assertEqual(cw.numero("45 mil seguidores"), 45000)

    def test_sem_numero_nao_inventa(self):
        self.assertIsNone(cw.numero("Siga o canal no WhatsApp"))
        self.assertIsNone(cw.numero(""))


if __name__ == "__main__":
    unittest.main()
