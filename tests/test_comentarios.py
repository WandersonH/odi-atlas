"""Comentários do YouTube: coleta (mescla, formato da API) e análise agregada. Todos os dados aqui são FICTÍCIOS."""
import csv
import gzip
import json
import os
import random
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "scripts"))
import build_comentarios as bcm  # noqa: E402
import collect_comentarios_youtube as cc  # noqa: E402
import corpus_populismo as cp  # noqa: E402


def item(cid, texto, autor="UCa", respostas=()):
    s = {"authorChannelId": {"value": autor}, "authorDisplayName": "Pessoa", "textOriginal": texto, "likeCount": 2,
         "publishedAt": "2026-10-01T10:00:00Z", "updatedAt": "2026-10-01T10:00:00Z"}
    return {"snippet": {"topLevelComment": {"id": cid, "snippet": s}, "totalReplyCount": len(respostas)},
            "replies": {"comments": [{"id": f"{cid}.r{i}", "snippet": {**s, "textOriginal": t}} for i, t in enumerate(respostas)]}}


class TestColeta(unittest.TestCase):
    def test_linhas_da_conversa(self):
        v = {"video_id": "v1", "candidate_id": "c1", "channel_id": "UCx"}
        ls = cc.linhas_da_conversa(item("a", "oi", respostas=["r1", "r2"]), v, "time", "2026-10-15T00:00:00Z")
        self.assertEqual([l["tipo"] for l in ls], ["comentario", "resposta", "resposta"])
        self.assertEqual(ls[1]["parent_id"], "a")
        self.assertEqual(ls[0]["respostas"], 2)

    def test_mesclar_acumula_ordens(self):
        a = [{"comment_id": "1", "ordem": "relevance", "candidate_id": "c", "video_id": "v", "publicado_em": "x", "curtidas": 1}]
        b = [{"comment_id": "1", "ordem": "time", "candidate_id": "c", "video_id": "v", "publicado_em": "x", "curtidas": 5}]
        m = cc.mesclar(a, b)
        self.assertEqual(len(m), 1)
        self.assertEqual((m[0]["ordem"], m[0]["curtidas"]), ("relevance|time", 5))

    def test_destino_sem_repositorio_privado_e_temporario(self):
        os.environ.pop("ODI_INTERNO_DIR", None)
        self.assertEqual(cc.destino()[1], "efemero")


class TestAnalise(unittest.TestCase):
    def test_repetidos_exige_autores_diferentes(self):
        txt = "texto padrão de campanha copiado muitas vezes"
        rows = [{"comment_id": str(i), "texto": txt, "autor_canal": f"a{i}", "autor_nome": ""} for i in range(3)]
        rows.append({"comment_id": "x", "texto": txt + " outro", "autor_canal": "b", "autor_nome": ""})
        ids, n = bcm.repetidos(rows)
        self.assertEqual((ids, n), ({"0", "1", "2"}, 1))
        um_autor = [{"comment_id": str(i), "texto": txt, "autor_canal": "a", "autor_nome": ""} for i in range(5)]
        self.assertEqual(bcm.repetidos(um_autor)[1], 0)

    def test_concentracao(self):
        rows = [{"autor_canal": "a", "autor_nome": ""}] * 8 + [{"autor_canal": f"b{i}", "autor_nome": ""} for i in range(2)]
        c = bcm.concentracao(rows)
        self.assertEqual((c["autores_unicos"], c["max_comentarios_de_um_autor"]), (3, 8))

    def test_livro_intolerancia_e_exclusoes(self):
        livro = json.loads((RAIZ / "data/config/livro_codigos_intolerancia.json").read_text(encoding="utf-8"))
        regs = cp.compilar(livro)
        self.assertIn("rotulo_pejorativo_politico", cp.precodificar("chora gado", regs))
        self.assertNotIn("rotulo_pejorativo_politico", cp.precodificar("o preço do gado subiu", regs))
        self.assertIn("desinformacao_eleitoral", cp.precodificar("sem voto impresso vai ter fraude", regs))
        self.assertNotIn("desinformacao_eleitoral", cp.precodificar("a fraude do INSS foi investigada", regs))
        self.assertNotIn("ameaca_violencia", cp.precodificar("vamos matar a saudade", regs))

    def test_build_ponta_a_ponta_sem_texto_no_publico(self):
        tmp = Path(tempfile.mkdtemp())
        try:
            for p in ["data/config/temas_youtube.json", "data/config/livro_codigos_populismo.json",
                      "data/config/livro_codigos_intolerancia.json"]:
                (tmp / p).parent.mkdir(parents=True, exist_ok=True)
                shutil.copy(RAIZ / p, tmp / p)
            cfg = json.loads((RAIZ / "data/config/temas_youtube.json").read_text(encoding="utf-8"))
            ids = list(cfg["candidatos"])
            (tmp / "data/youtube").mkdir(parents=True, exist_ok=True)
            (tmp / "data/youtube/conteudo.json").write_text(json.dumps({"candidatos": {i: {"videos": [{"video_id": f"v{i}", "temas": ["saude"]}]} for i in ids}}))
            rnd = random.Random(1)
            palavras = "saude hospital sus medico fila vacina economia emprego salario gado fraude urna povo brasil familia escola".split()
            segredo = "FRASE_PRIVADA_QUE_NAO_PODE_VAZAR"
            rows = []
            for k, cid in enumerate(ids):
                for i in range(400):
                    t = " ".join(rnd.choice(palavras) for _ in range(10)) + (" " + segredo if i == 0 else "")
                    rows.append({"comment_id": f"{k}-{i}", "parent_id": "", "tipo": "comentario", "video_id": f"v{cid}",
                                 "candidate_id": cid, "channel_id": "UCx", "ordem": "relevance", "autor_canal": f"UC{i % 50}",
                                 "autor_nome": "Nome Privado", "texto": t, "curtidas": str(i % 7), "respostas": "0",
                                 "publicado_em": f"2026-10-{1 + i % 9:02d}T10:00:00Z", "atualizado_em": "", "coletado_em": "2026-10-15T00:00:00Z"})
            bruto = tmp / "bruto.csv.gz"
            with gzip.open(bruto, "wt", encoding="utf-8", newline="") as f:
                w = csv.DictWriter(f, cc.CAMPOS, delimiter=";")
                w.writeheader()
                w.writerows(rows)
            cwd = os.getcwd()
            os.chdir(tmp)
            os.environ.pop("ODI_INTERNO_DIR", None)
            try:
                self.assertEqual(bcm.main([str(bruto)]), 0)
            finally:
                os.chdir(cwd)
            os.chdir(tmp)
            os.environ["ODI_INTERNO_DIR"] = str(tmp / "interno")
            try:
                self.assertEqual(bcm.main([str(bruto)]), 0)
            finally:
                os.environ.pop("ODI_INTERNO_DIR", None)
                os.chdir(cwd)
            am = list(csv.DictReader(open(tmp / "interno/codificacao/amostra_comentarios_v1.csv", encoding="utf-8"), delimiter=";"))
            self.assertEqual(len(am), 400)  # 200 por candidato
            self.assertTrue((tmp / "interno/youtube/comentarios/corpus_iramuteq_comentarios.txt").read_text(encoding="utf-8").startswith("**** *cand_"))
            txt = (tmp / "data/youtube/comentarios/analise.json").read_text(encoding="utf-8")
            self.assertNotIn(segredo.lower(), txt.lower())
            self.assertNotIn("Nome Privado", txt)
            self.assertNotIn("UC1", txt)
            a = json.loads(txt)
            c = a["candidatos"][ids[0]]
            self.assertEqual(c["comentarios"], 400)
            self.assertGreater(c["intolerancia_pct"]["rotulo_pejorativo_politico"], 0)
            self.assertIn("saude", c["aderencia_ao_tema_do_video"])
            self.assertTrue(all("texto" not in str(k) for k in c["chd"]))
        finally:
            shutil.rmtree(tmp)


if __name__ == "__main__":
    unittest.main()
