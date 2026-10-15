"""Testes da rede de influenciadores (coleta e montagem) sem rede, com dados sintéticos."""
import csv
import gzip
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import collect_influenciadores as ci  # noqa: E402

try:
    import build_rede_influenciadores as bri  # noqa: E402
except ImportError:
    bri = None

ROOT = Path(__file__).resolve().parents[1]
CFG = json.loads((ROOT / "data/config/influenciadores_youtube.json").read_text(encoding="utf-8"))
L, F = "280002542548", "280002551544"


def v(titulo, desc="", cat="25"):
    return {"titulo": titulo, "descricao": desc, "categoria": cat}


class TestAvaliar(unittest.TestCase):
    def setUp(self):
        self.men, self.excl = ci.compilar(CFG)

    def ev(self, x):
        return ci.avaliar(x, self.men, self.excl, CFG["excluir_categorias"])

    def test_cita_cada_um(self):
        r = self.ev(v("Debate: Lula x Flávio Bolsonaro"))
        self.assertEqual((r[f"cita_{L}"], r[f"cita_{F}"], r["excluido"]), (1, 1, ""))
        r = self.ev(v("Senador Flávio fala em Manaus"))
        self.assertEqual((r[f"cita_{L}"], r[f"cita_{F}"]), (0, 1))

    def test_niveis_iguais_para_os_dois(self):
        casos = {"Vote 22 no domingo": (0, 2), "Dia 25 é Flávio!": (0, 2), "Vote 13": (2, 0), "Dia 25 é Lula": (2, 0),
                 "@flaviobolsonaro em Manaus": (0, 1), "#Lula13 #Lula": (1, 0), "Olê olá Lula 13": (1, 0), "Lula comenta inflação": (1, 0),
                 "Flávio 22 e Lula 13 no debate": (1, 1), "Eu voto no Flávio Bolsonaro": (0, 2), "Votar Lula para garantir": (2, 0), "#FlavioBolsonaro critica o governo": (0, 1)}
        for titulo, (nl, nf) in casos.items():
            r = self.ev(v(titulo))
            self.assertEqual((r[f"nivel_{L}"], r[f"nivel_{F}"]), (nl, nf), titulo)
        self.assertIn("vote 22", self.ev(v("Domingo: vote 22"))[f"gatilho_{F}"])

    def test_flavio_sozinho_nao_basta(self):
        # "Flávio" sozinho é ambíguo (ex.: Flávio Dino)
        r = self.ev(v("Flávio Dino decide no STF"))
        self.assertEqual(r["excluido"], "sem menção no título/descrição")

    def test_molusco_fora(self):
        self.assertEqual(self.ev(v("Lula à dorê crocante", cat="26"))["excluido"], "categoria 26")
        self.assertEqual(self.ev(v("Receita de lula recheada"))["excluido"], "termo de exclusão")

    def test_cota_respeita_teto(self):
        c = ci.Cota(250)
        self.assertTrue(c.gastar(100)); self.assertTrue(c.gastar(100)); self.assertFalse(c.gastar(100))
        self.assertEqual(c.usada, 200)

    def test_sem_chave_bloqueia(self):
        import os
        old = os.environ.pop("YOUTUBE_API_KEY", None)
        try:
            with tempfile.TemporaryDirectory() as d:
                (Path(d) / "data/config").mkdir(parents=True)
                (Path(d) / "data/config/influenciadores_youtube.json").write_text(json.dumps(CFG), encoding="utf-8")
                self.assertEqual(ci.main([d]), 1)
                m = json.loads((Path(d) / "data/youtube/influenciadores/manifesto_latest.json").read_text(encoding="utf-8"))
                self.assertEqual(m["status"], "bloqueado")
        finally:
            if old is not None:
                os.environ["YOUTUBE_API_KEY"] = old


@unittest.skipIf(bri is None, "networkx não instalado")
class TestRede(unittest.TestCase):
    def test_rede_bipartida_e_corte_por_inscritos(self):
        vids = []
        for i in range(3):
            vids.append({"video_id": f"a{i}", "channel_id": "UCa", "visualizacoes": "100", "excluido": "", f"cita_{L}": "1", f"cita_{F}": "0", f"nivel_{L}": "2" if i == 0 else "1"})
        vids.append({"video_id": "b0", "channel_id": "UCb", "visualizacoes": "50", "excluido": "", f"cita_{L}": "1", f"cita_{F}": "1"})
        vids.append({"video_id": "c0", "channel_id": "UCc", "visualizacoes": "9", "excluido": "", f"cita_{L}": "0", f"cita_{F}": "1"})
        vids.append({"video_id": "x0", "channel_id": "UCa", "visualizacoes": "999", "excluido": "categoria 26", f"cita_{L}": "1", f"cita_{F}": "0"})
        canais = {"UCa": {"canal": "A", "inscritos": "50000"}, "UCb": {"canal": "B", "inscritos": "20000"},
                  "UCc": {"canal": "C", "inscritos": "500"}}
        g = bri.montar(vids, canais, CFG)
        self.assertNotIn("UCc", g)                       # abaixo de min_inscritos
        self.assertEqual(g["UCa"]["cand:" + L]["weight"], 3)  # vídeo excluído não conta
        self.assertNotIn("cand:" + F, g["UCa"])
        self.assertEqual(g["UCa"]["cand:" + L]["pede_voto"], 1)
        self.assertEqual(g["UCa"]["cand:" + L]["nivel"], 2)
        self.assertEqual(g["UCb"]["cand:" + L]["nivel"], 1)
        self.assertEqual(g.nodes["UCb"]["frac_lula"], 0.5)
        self.assertEqual(g.nodes["UCa"]["cor"], CFG["candidatos"][L]["cor"])


if __name__ == "__main__":
    unittest.main()
