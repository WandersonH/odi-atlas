"""Testes do coletor do YouTube (sem rede)."""
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import collect_youtube as cy  # noqa: E402


class TestParse(unittest.TestCase):
    def test_formatos(self):
        self.assertEqual(cy.parse_channel("https://www.youtube.com/@LULAOFICIAL"), ("handle", "@LULAOFICIAL"))
        self.assertEqual(cy.parse_channel("https://youtube.com/channel/UCabcdefghijklmnopqrstuv"), ("id", "UCabcdefghijklmnopqrstuv"))
        self.assertEqual(cy.parse_channel("https://www.youtube.com/user/fulano"), ("username", "fulano"))
        self.assertIsNone(cy.parse_channel("https://www.youtube.com/c/fulano"))
        self.assertIsNone(cy.parse_channel("https://www.youtube.com/watch?v=abc"))
        self.assertIsNone(cy.parse_channel("https://instagram.com/x"))

    def test_sem_chave_bloqueia(self):
        old = os.environ.pop("YOUTUBE_API_KEY", None)
        try:
            r = Path(tempfile.mkdtemp())
            self.assertEqual(cy.main([str(r)]), 1)
        finally:
            if old is not None:
                os.environ["YOUTUBE_API_KEY"] = old


if __name__ == "__main__":
    unittest.main()
