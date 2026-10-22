import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import build_caso_x as bx  # noqa: E402

POST = "99"


def run(rid, itens):
    return {"run_id": rid, "items": itens}


class TestCasoX(unittest.TestCase):
    def test_unifica_e_remove_duplicados(self):
        orig = {"id": POST, "text": "original", "createdAt": "Thu May 28 22:01:13 +0000 2026", "replyCount": 10, "author": {"userName": "SecRubio", "followers": 5_000_000}}
        r1 = {"id": "1", "text": "Finalmente!", "type": "reply", "resultType": "replies", "inReplyToId": POST, "likeCount": 3,
              "createdAt": "Thu May 28 23:00:00 +0000 2026", "author": {"id": "u1", "userName": "pessoa", "followers": 50}, "lang": "pt"}
        r1b = dict(r1, likeCount=7, resultType="completeReplies")          # mesmo post em outra execução, métrica maior
        q = {"id": "2", "text": "soberania!", "type": "tweet", "resultType": "quotes", "isQuoteStatus": True, "lang": "pt",
             "createdAt": "Fri May 29 10:00:00 +0000 2026", "author": {"id": "u2", "userName": "famoso", "followers": 20000}}
        rt = {"id": "u9", "username": "rep", "followers": 10, "resultType": "retweeters"}
        with tempfile.TemporaryDirectory() as t:
            fs = []
            for i, it in enumerate([[orig, r1, rt], [r1b, q, dict(rt)]]):
                p = Path(t) / f"r{i}.json"
                p.write_text(json.dumps(run(f"r{i}", it)), encoding="utf-8")
                fs.append(p)
            posts, rts, st = bx.unificar(fs, POST)
        self.assertEqual((st["itens_brutos"], st["posts_unicos"], st["repostadores_unicos"]), (6, 3, 1))
        self.assertEqual(posts["1"]["curtidas"], 7)
        self.assertEqual(posts["1"]["runs"], {"r0", "r1"})
        self.assertEqual((posts["1"]["tipo"], posts["2"]["tipo"], posts[POST]["tipo"]), ("resposta", "citação", "original"))
        self.assertEqual(posts["1"]["criado_em_utc"], "2026-05-28T23:00:00Z")
        ag = bx.agregar(posts, rts, st, {**bx.CASOS["006"], "post": POST, "autor": "SecRubio"})
        self.assertEqual(ag["unificacao"]["duplicados_removidos"], 2)
        txt = json.dumps(ag, ensure_ascii=False)
        self.assertNotIn("pessoa", txt)                                   # perfil pequeno não aparece
        self.assertIn("@famoso", txt)
        self.assertEqual(ag["categorias_pct_pt"]["apoia a designação"], 50.0)


if __name__ == "__main__":
    unittest.main()
