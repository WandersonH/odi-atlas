import csv
import gzip
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "scripts"))
import collect_comentarios_tiktok as ci  # noqa: E402


class TestComentariosTikTok(unittest.TestCase):
    def test_carga_cota_teto_e_privacidade(self):
        visto = []

        def fake(ator, pl, cap):
            visto.append((pl, cap))
            itens = []
            for u in pl["postURLs"]:
                for i in range(pl["commentsPerPost"]):
                    itens.append({"cid": f"{u}-{i}", "text": f"comentário {i}", "uniqueId": "fulano", "uid": "9", "createTimeISO": "2026-09-01T00:00:00Z", "videoWebUrl": u})
            return {"id": "r", "status": "SUCCEEDED"}, itens
        base = {"lulaoficial": 1000, "brasilcomlula": 3000, "flaviobolsonaro": 5000, "flaviobolsonaro_velho": 7000}
        posts = lambda perfil, n, desde: [{"video_id": str(base[perfil] + i), "perfil": perfil, "url": f"https://www.tiktok.com/@{perfil}/video/{base[perfil] + i}",
                                           "publicado_em": desde, "comentarios": 100 - i} for i in range(n)]  # noqa: E731
        conteudo = {"candidatos": {"280002542548": {"videos": posts("lulaoficial", 900, "2026-09-01T00:00:00Z") + posts("brasilcomlula", 5, "2026-09-01T00:00:00Z")},
                                   "280002551544": {"videos": posts("flaviobolsonaro", 10, "2026-09-01T00:00:00Z") + posts("flaviobolsonaro_velho", 1, "2026-07-01T00:00:00Z")}}}
        cwd = os.getcwd()
        with tempfile.TemporaryDirectory() as t, tempfile.TemporaryDirectory() as priv:
            (Path(t) / "data/config").mkdir(parents=True)
            (Path(t) / "data/tiktok").mkdir(parents=True)
            (Path(t) / "data/config/tiktok_comentarios.json").write_text((RAIZ / "data/config/tiktok_comentarios.json").read_text(encoding="utf-8"), encoding="utf-8")
            (Path(t) / "data/tiktok/conteudo.json").write_text(json.dumps(conteudo), encoding="utf-8")
            os.chdir(t)
            os.environ["ODI_INTERNO_DIR"] = priv
            try:
                self.assertEqual(ci.main(["--carga"], executar=fake), 0)
                man = json.loads(Path("data/tiktok/comentarios/manifesto_latest.json").read_text(encoding="utf-8"))
                rows = list(csv.DictReader(gzip.open(Path(priv) / "tiktok/comentarios/comentarios.csv.gz", "rt", encoding="utf-8"), delimiter=";"))
                pub = "".join(p.read_text(encoding="utf-8") for p in Path("data/tiktok/comentarios").glob("*.json"))
            finally:
                os.chdir(cwd)
                del os.environ["ODI_INTERNO_DIR"]
        C = json.loads((RAIZ / "data/config/tiktok_comentarios.json").read_text(encoding="utf-8"))
        self.assertLessEqual(man["custo_usd"], C["carga"]["teto_usd"] + 1e-9)
        self.assertTrue(all(cap <= C["carga"]["teto_usd"] for _, cap in visto))
        urls = [u for pl, _ in visto for u in pl["postURLs"]]
        self.assertFalse(any("velho" in u for u in urls))  # só desde 16/08
        por = {}
        for r in rows:
            por[r["candidate_id"]] = por.get(r["candidate_id"], 0) + 1
        self.assertLessEqual(por["280002542548"], C["carga"]["cota_por_candidato"])
        self.assertEqual(por["280002551544"], 10 * C["carga"]["max_por_video"])  # 10 vídeos × 50 (teto por vídeo)
        self.assertNotIn("fulano", pub)

    def test_para_se_a_primeira_execucao_vem_vazia(self):
        visto = []

        def vazio(ator, pl, cap):
            visto.append(pl)
            return {"id": "r", "status": "SUCCEEDED"}, [{"outra": "coisa"}]
        conteudo = {"candidatos": {"280002542548": {"videos": [{"video_id": str(i), "perfil": "lulaoficial", "url": f"https://www.tiktok.com/@lulaoficial/video/{i}",
                                                                 "publicado_em": "2026-09-01T00:00:00Z", "comentarios": 9} for i in range(100)]}}}
        cwd = os.getcwd()
        with tempfile.TemporaryDirectory() as t, tempfile.TemporaryDirectory() as priv:
            (Path(t) / "data/config").mkdir(parents=True)
            (Path(t) / "data/tiktok").mkdir(parents=True)
            (Path(t) / "data/config/tiktok_comentarios.json").write_text((RAIZ / "data/config/tiktok_comentarios.json").read_text(encoding="utf-8"), encoding="utf-8")
            (Path(t) / "data/tiktok/conteudo.json").write_text(json.dumps(conteudo), encoding="utf-8")
            os.chdir(t)
            os.environ["ODI_INTERNO_DIR"] = priv
            try:
                self.assertEqual(ci.main(["--carga"], executar=vazio), 1)
            finally:
                os.chdir(cwd)
                del os.environ["ODI_INTERNO_DIR"]
        self.assertEqual(len(visto), 1)


if __name__ == "__main__":
    unittest.main()
