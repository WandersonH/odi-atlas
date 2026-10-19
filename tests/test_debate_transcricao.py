import json, os, shutil, sys, tempfile, unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import build_debate_transcricao as bd
import collect_debate_video as cv

RAIZ = Path(__file__).resolve().parents[1]


class TestDebate(unittest.TestCase):
    def test_vtt(self):
        vtt = "WEBVTT\n\n00:00:01.000 --> 00:00:03.000\nboa noite\n\n00:00:03.000 --> 00:00:05.000\nboa noite\nvamos começar\n"
        s = cv.vtt_segmentos(vtt)
        self.assertEqual([x["texto"] for x in s], ["boa noite", "vamos começar"])
        self.assertEqual(cv.dur_s("PT6H12M26S"), 22346)

    def test_oradores(self):
        segs = [{"ini": 0, "fim": 2, "texto": "boa noite a todos"},
                {"ini": 2, "fim": 4, "texto": "candidato Lula, o senhor tem um minuto para a resposta"},
                {"ini": 4, "fim": 9, "texto": "o povo brasileiro quer emprego e salário"},
                {"ini": 9, "fim": 11, "texto": "réplica, candidato Flávio, trinta segundos"},
                {"ini": 11, "fim": 15, "texto": "segurança pública e combate ao crime"}]
        self.assertEqual(bd.orador_por_deixas(segs, {}), ["mediacao", "mediacao", "lula", "mediacao", "flavio"])

    def test_main(self):
        frases = {"lula": "o povo trabalhador precisa de emprego salário mínimo e comida na mesa do brasileiro",
                  "flavio": "segurança pública polícia combate ao crime e família cristã contra a corrupção do governo"}
        segs, t = [], 0.0
        for i in range(40):
            for o, c in (("Lula", "candidato Lula, o senhor tem um minuto"), ("Flávio", "candidato Flávio, sua resposta")):
                segs.append({"ini": t, "fim": t + 2, "texto": c}); t += 2
                k = "lula" if o == "Lula" else "flavio"
                for _ in range(2):
                    segs.append({"ini": t, "fim": t + 5, "texto": frases[k]}); t += 5
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / "interno/debate").mkdir(parents=True)
            (Path(d) / "interno/debate/transcricao.json").write_text(json.dumps({"video": {"id": "x"}, "fonte": "teste", "segmentos": segs}), encoding="utf-8")
            (Path(d) / "data/config").mkdir(parents=True)
            shutil.copy(RAIZ / "data/config/temas_youtube.json", Path(d) / "data/config/")
            os.environ["ODI_INTERNO_DIR"] = str(Path(d) / "interno")
            try:
                self.assertEqual(bd.main([d]), 0)
                a = json.loads((Path(d) / "data/debate/analise.json").read_text(encoding="utf-8"))
                corpus = (Path(d) / "interno/debate/corpus_iramuteq.txt").read_text(encoding="utf-8")
            finally:
                os.environ.pop("ODI_INTERNO_DIR")
        self.assertEqual(a["tempo_de_fala_min"]["Lula"], a["tempo_de_fala_min"]["Flávio Bolsonaro"])
        self.assertIn("**** *orador_lula *bloco_1", corpus)
        self.assertGreater(a["temas"]["por_tema"]["seguranca"]["Flávio Bolsonaro"]["segmentos"], a["temas"]["por_tema"]["seguranca"]["Lula"]["segmentos"])
        self.assertTrue(all(len(e["trecho"].split()) <= 26 for t in a["temas"]["por_tema"].values() for o in t.values() for e in o["exemplos"]))


if __name__ == "__main__":
    unittest.main()
