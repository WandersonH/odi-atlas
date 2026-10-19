import json, sys, tempfile, unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import build_rede_debate as rd


class TestRedeDebate(unittest.TestCase):
    def test_redes(self):
        d = {"gerado_em_utc": "x", "termos": [
            {"termo": "flavio miliciano", "politica": True, "volume_max": 1000000, "relacionados": ["miliciano", "debate band"],
             "materias": [{"veiculo": "Poder360"}, {"veiculo": "UOL"}, {"veiculo": "Poder360"}]},
            {"termo": "jogo do flamengo", "politica": False, "materias": [{"veiculo": "ge"}]}],
             "curvas": {"relacionados_24h": {"debate": {"em_alta": [{"texto": "quem ganhou o debate"}], "principais": []}}}}
        n, a = rd.canais(d)
        self.assertEqual(a[("t:flavio miliciano", "v:poder360")], 2)       # duas matérias do mesmo veículo no topo
        self.assertNotIn("v:ge", n)                                           # só termos de Política
        n2, a2 = rd.palavras(d)
        self.assertIn(("c:debate", "t:quem ganhou o debate"), a2)
        with tempfile.TemporaryDirectory() as t:
            p = Path(t) / "data/trends/agora"
            p.mkdir(parents=True)
            (p / "debate.json").write_text(json.dumps(d), encoding="utf-8")
            rd.main([t])
            r = json.loads((p / "rede_canais.json").read_text(encoding="utf-8"))
        self.assertEqual(r["veiculos_mais_presentes"][0], ["Poder360", 2])


if __name__ == "__main__":
    unittest.main()
