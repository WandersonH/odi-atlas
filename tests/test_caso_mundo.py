"""Caso 019: funções puras (sem rede)."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import caso_mundo as cm  # noqa: E402


class TestMundo(unittest.TestCase):
    def test_continente(self):
        self.assertEqual(cm.continente("us"), "América do Norte, Central e Caribe")
        self.assertEqual(cm.continente("AR"), "América do Sul")
        self.assertEqual(cm.continente("JP"), "Ásia")
        self.assertEqual(cm.continente(None), "⛔ não informado")

    def test_sem_codigo_repetido(self):
        todos = [c for v in cm._CONT.values() for c in v.split()]
        self.assertEqual(len(todos), len(set(todos)))

    def test_pertinencia_e_mencoes(self):
        self.assertTrue(cm.pertinente("Brazil votes: Lula vs Bolsonaro", ""))
        self.assertTrue(cm.pertinente("巴西大选", ""))
        self.assertFalse(cm.pertinente("US midterms recap", "nothing here"))
        self.assertEqual(cm.mencoes("Лула победил", ""), ["Lula"])

    def test_lingua_base(self):
        self.assertEqual(cm.lingua_base("en-US"), "en")
        self.assertIsNone(cm.lingua_base("zxx"))

    def test_identificar(self):
        self.assertEqual(cm.identificar("Lula"), "?")
        self.assertEqual(cm.identificar("Lula ganó las elecciones en Brasil y la oposición no lo acepta"), "es")
