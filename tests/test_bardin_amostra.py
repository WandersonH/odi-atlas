"""Amostra da codificação humana do Bardin: tamanho exato e proporção por estrato, sem corte pela ordem (revisão de 01/11/2026)."""
import sys
import unittest
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import build_bardin_caso as bb  # noqa: E402


def linhas():
    rs = []
    for rede, n in (("facebook", 400), ("instagram", 400), ("tiktok", 500), ("x", 7400)):
        for i in range(n):
            rs.append({"rede": rede, "dia": f"2026-10-{20 + i % 12:02d}", "publicado_em": f"2026-10-{20 + i % 12:02d}T{i % 24:02d}:00:00Z", "item_id": f"{rede}{i}"})
    return rs


class TestAmostraBardin(unittest.TestCase):
    def test_tamanho_exato_e_proporcional(self):
        rs = linhas()
        am = bb.amostra(rs, 200)
        self.assertEqual(len(am), 200)
        c = Counter(r["rede"] for r in am)
        for rede, n in Counter(r["rede"] for r in rs).items():
            # cada estrato rede × dia arredonda até 1 item: a rede pode desviar no máximo o nº de dias (12) da cota exata
            self.assertLessEqual(abs(c[rede] - 200 * n / len(rs)), 12, (rede, c[rede]))

    def test_muitos_estratos_nao_corta_a_ultima_rede(self):
        rs = [{"rede": r, "dia": f"d{d:03d}", "publicado_em": f"{d:03d}", "item_id": f"{r}{d}"} for r in ("a", "z") for d in range(150)]
        c = Counter(r["rede"] for r in bb.amostra(rs, 200))
        self.assertEqual(sum(c.values()), 200)
        # 300 estratos de 1 item para 200 vagas: a escolha é por sorteio, não pela ordem (antes, "z" perdia sempre os 100 cortados)
        self.assertGreaterEqual(min(c["a"], c["z"]), 85)

    def test_corpus_menor_que_n(self):
        self.assertEqual(len(bb.amostra(linhas()[:50], 200)), 50)


if __name__ == "__main__":
    unittest.main()
