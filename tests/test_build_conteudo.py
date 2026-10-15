"""Testes do caderno 13 (classificação por tema e nuvem de palavras) com dados sintéticos."""
import csv
import gzip
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import build_conteudo as b  # noqa: E402

CFG = {
    "nota": "Teste.",
    "candidatos": {
        "1": {"nome": "Lula", "numero": "13", "adversario": ["flavio", "bolsonaro"]},
        "2": {"nome": "Flávio Bolsonaro", "numero": "22", "adversario": ["lula", "petista*"]},
    },
    "temas": {"economia": ["emprego*", "escala 6x1"], "religiao_valores": ["deus", "igreja*"]},
    "pede_voto": ["vote {n}", "#{n}"],
}


class TestTermos(unittest.TestCase):
    def setUp(self):
        self.temas, self.cands = b.compile_cfg(CFG)

    def test_prefixo_e_palavra_inteira(self):
        c = b.classify("Mais empregos para o povo", self.temas, self.cands["1"])
        self.assertEqual(c["temas"], ["economia"])
        # "deus" não pode casar dentro de outra palavra
        c = b.classify("adeuses e despedidas", self.temas, self.cands["1"])
        self.assertEqual(c["temas"], ["sem_tema"])

    def test_pede_voto_e_adversario(self):
        c = b.classify("Contra os petistas: vote 22!", self.temas, self.cands["2"])
        self.assertTrue(c["pede_voto"])
        self.assertTrue(c["cita_adversario"])
        c = b.classify("vote 13", self.temas, self.cands["2"])
        self.assertFalse(c["pede_voto"])

    def test_link_nao_vira_tema(self):
        r = {"channel_id": "x", "titulo": "Ato", "descricao": "Siga https://deus.com.br/igreja"}
        self.assertEqual(b.classify(b.texto_util(r, {}), self.temas, self.cands["1"])["temas"], ["sem_tema"])

    def test_texto_padrao_repetido_e_removido(self):
        rodape = "Inscreva-se no canal: economia, emprego, família."
        rows = [{"channel_id": "c", "titulo": f"Vídeo {i}", "descricao": f"Assunto {i}. {rodape}"}
                for i in range(b.LIMIAR_REPETICAO)]
        pad = b.texto_padrao(rows)
        self.assertIn(rodape, pad["c"])
        self.assertEqual(b.classify(b.texto_util(rows[0], pad), self.temas, self.cands["1"])["temas"], ["sem_tema"])

    def test_emoji_separa_trechos(self):
        self.assertEqual(b.segmentos("Ato em SP 📱 A TV escuta você"), ["Ato em SP", "A TV escuta você"])


class TestNuvem(unittest.TestCase):
    def test_conta_por_video_e_exclui(self):
        textos = ["Saúde saúde saúde para todos", "A saúde e o SUS", "Saúde pública e SUS forte", "Lula fala de saúde"]
        n = dict(map(tuple, b.nuvem(textos, {"lula"}, minimo=2)))
        self.assertEqual(n["saude"], 4)          # conta 1x por vídeo, sem acento
        self.assertEqual(n["sus"], 2)
        self.assertNotIn("lula", n)              # nome do próprio candidato
        self.assertNotIn("para", n)              # palavra funcional
        self.assertNotIn("todos", n)

    def test_par_absorve_palavra(self):
        textos = ["fim da escala 6x1", "escala 6x1 já", "contra a escala 6x1"]
        n = dict(map(tuple, b.nuvem(textos, set(), minimo=2)))
        self.assertEqual(n.get("escala 6x1"), 3)
        self.assertNotIn("escala", n)

    def test_hashtag_sem_par(self):
        t = b.termos("#ForaPT #Direita juntos", set())
        self.assertIn("#forapt", t)
        self.assertNotIn("#forapt #direita", t)


class TestMain(unittest.TestCase):
    def test_execucao_completa(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            (root / "data/config").mkdir(parents=True)
            (root / "data/youtube").mkdir(parents=True)
            (root / "data/config/temas_youtube.json").write_text(json.dumps(CFG), encoding="utf-8")
            cols = ["candidate_id", "candidate_name", "channel_id", "canal", "video_id", "publicado_em", "titulo",
                    "duracao", "visualizacoes", "curtidas", "comentarios", "coletado_em", "descricao"]
            rows = [["1", "LULA", "c1", "Canal Lula", f"v{i}", f"2026-09-0{i+1}T10:00:00Z",
                     "Emprego e escala 6x1 #13" if i % 2 else "Deus abençoe", "PT1M", "100", "", "", "2026-10-15T00:00:00Z", ""]
                    for i in range(4)]
            rows.append(["3", "OUTRO", "c3", "Outro", "z", "2026-09-01T00:00:00Z", "x", "", "", "", "", "2026-10-15T00:00:00Z", ""])
            with gzip.open(root / "data/youtube/videos_latest.csv.gz", "wt", encoding="utf-8", newline="") as f:
                w = csv.writer(f, delimiter=";"); w.writerow(cols); w.writerows(rows)
            self.assertEqual(b.main([str(root)]), 0)
            out = json.loads((root / "data/youtube/conteudo.json").read_text(encoding="utf-8"))
            lula = out["candidatos"]["1"]
            self.assertEqual(lula["total_videos"], 4)
            self.assertEqual(lula["por_tema"], {"economia": 2, "religiao_valores": 2})
            self.assertEqual(lula["pede_voto"], 2)
            self.assertEqual(lula["videos"][0]["video_id"], "v3")  # mais recente primeiro
            self.assertIn("nuvem", lula)
            self.assertEqual(out["candidatos"]["2"]["total_videos"], 0)


if __name__ == "__main__":
    unittest.main()
