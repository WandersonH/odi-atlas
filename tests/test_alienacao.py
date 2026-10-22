import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import collect_alienacao as ca  # noqa: E402


def s(apt, abst, br, nu, local="1010", mun="BELO"):
    return {"nm_mun": mun, "local": local, "aptos": apt, "comparecimento": apt - abst, "abstencoes": abst, "brancos": br, "nulos": nu}


class TestAlienacao(unittest.TestCase):
    def test_agrega_municipio_local_e_secao(self):
        sec = {("MG", "41238", "1", "10"): s(400, 80, 10, 10), ("MG", "41238", "1", "11"): s(100, 20, 5, 5),
               ("MG", "41238", "2", "5"): s(300, 30, 3, 3, local="2020"), ("ZZ", "29539", "1", "1"): s(50, 40, 0, 0, mun="EXTERIOR")}
        loc = {("MG", "41238", "1", "10"): {"local": "1010", "nome": "ESCOLA A", "bairro": "CENTRO", "coord": (-19.9, -43.9)},
               ("MG", "41238", "1", "11"): {"local": "1010", "nome": "ESCOLA A", "bairro": "CENTRO", "coord": (-19.9, -43.9)},
               ("MG", "41238", "2", "5"): {"local": "2020", "nome": "ESCOLA B", "bairro": "X", "coord": None}}
        resumo, locs = ca.agregar(sec, loc, {"41238": "3106200"})
        m = resumo["municipios"]["3106200"]
        self.assertEqual((m["aptos"], m["alienacao"], m["secoes"]), (800, 166, 3))
        self.assertAlmostEqual(m["pct_alienacao"], 20.75)
        self.assertEqual(resumo["brasil"]["aptos"], 850)                 # exterior entra no total do país
        self.assertNotIn("ZZ", locs)                                     # e fica fora do mapa
        a = next(x for x in locs["MG"] if x["local"] == "1010")
        self.assertEqual((a["aptos"], len(a["secoes"]), a["lat"]), (500, 2, -19.9))
        self.assertEqual(resumo["diagnostico"]["secoes_sem_coordenada"], 1)
        self.assertEqual(resumo["diagnostico"]["secoes_sem_local"], 1)   # a do exterior não tem local na tabela

    def test_cargo_presidente(self):
        self.assertTrue(ca.eh_presidente({"CD_CARGO": "1"}))
        self.assertTrue(ca.eh_presidente({"DS_CARGO": "Presidente"}))
        self.assertFalse(ca.eh_presidente({"CD_CARGO": "3", "DS_CARGO": "Governador"}))


if __name__ == "__main__":
    unittest.main()
