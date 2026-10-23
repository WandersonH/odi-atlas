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
import collect_comentarios_instagram as ci  # noqa: E402


class TestComentariosInstagram(unittest.TestCase):
    def test_carga_cota_teto_e_privacidade(self):
        visto = []

        def fake(ator, pl, cap):
            visto.append((pl, cap))
            itens = []
            for u in pl["code_or_id_or_url"]:
                itens.append({"comment_id": "cap" + u, "content_type": "caption", "text": "legenda do dono", "input_url": u})
                for i in range(pl["max_comments"]):
                    itens.append({"comment_id": f"{u}-{i}", "text": f"comentário {i}", "username": "fulano", "user_id": "9", "created_at_utc": "2026-09-01T00:00:00Z", "input_url": u})
            return {"id": "r", "status": "SUCCEEDED"}, itens
        posts = lambda perfil, n, desde: [{"video_id": f"{perfil}{i}", "perfil": perfil, "url": f"https://www.instagram.com/p/{perfil}{i}/",
                                           "publicado_em": desde, "comentarios": 100 - i} for i in range(n)]  # noqa: E731
        conteudo = {"candidatos": {"280002542548": {"videos": posts("lulaoficial", 900, "2026-09-01T00:00:00Z") + posts("brasilcomlula", 5, "2026-09-01T00:00:00Z")},
                                   "280002551544": {"videos": posts("flaviobolsonaro", 10, "2026-09-01T00:00:00Z") + posts("flaviobolsonaro_velho", 1, "2026-07-01T00:00:00Z")}}}
        cwd = os.getcwd()
        with tempfile.TemporaryDirectory() as t, tempfile.TemporaryDirectory() as priv:
            (Path(t) / "data/config").mkdir(parents=True)
            (Path(t) / "data/instagram").mkdir(parents=True)
            (Path(t) / "data/config/instagram_comentarios.json").write_text((RAIZ / "data/config/instagram_comentarios.json").read_text(encoding="utf-8"), encoding="utf-8")
            (Path(t) / "data/instagram/conteudo.json").write_text(json.dumps(conteudo), encoding="utf-8")
            os.chdir(t)
            os.environ["ODI_INTERNO_DIR"] = priv
            try:
                self.assertEqual(ci.main(["--carga"], executar=fake), 0)
                man = json.loads(Path("data/instagram/comentarios/manifesto_latest.json").read_text(encoding="utf-8"))
                rows = list(csv.DictReader(gzip.open(Path(priv) / "instagram/comentarios/comentarios.csv.gz", "rt", encoding="utf-8"), delimiter=";"))
                pub = "".join(p.read_text(encoding="utf-8") for p in Path("data/instagram/comentarios").glob("*.json"))
            finally:
                os.chdir(cwd)
                del os.environ["ODI_INTERNO_DIR"]
        C = json.loads((RAIZ / "data/config/instagram_comentarios.json").read_text(encoding="utf-8"))
        self.assertLessEqual(man["custo_usd"], C["carga"]["teto_usd"] + 1e-9)
        self.assertTrue(all(cap <= C["carga"]["teto_usd"] for _, cap in visto))
        urls = [u for pl, _ in visto for u in pl["code_or_id_or_url"]]
        self.assertFalse(any("brasilcomlula" in u or "velho" in u for u in urls))  # só perfis principais, desde 16/08
        por = {}
        for r in rows:
            por[r["candidate_id"]] = por.get(r["candidate_id"], 0) + 1
        self.assertLessEqual(por["280002542548"], C["carga"]["cota_por_candidato"])
        self.assertEqual(por["280002551544"], 10 * C["carga"]["max_por_post"])  # 10 posts × 50 (teto por post)
        self.assertFalse(any(r["texto"] == "legenda do dono" for r in rows))  # legenda do post não é comentário
        self.assertNotIn("fulano", pub)


if __name__ == "__main__":
    unittest.main()
