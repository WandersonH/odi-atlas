import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import build_caso_instagram as bi  # noqa: E402


class TestCasoInstagram(unittest.TestCase):
    def test_unifica_dois_atores_e_protege_autor(self):
        a = {"comment_id": "10", "text": "isso é montagem, fake", "created_at_utc": 1791100000, "comment_like_count": 5,
             "user": {"id": "u1", "username": "fulana", "full_name": "Fulana de Tal", "is_verified": False}}
        b = {"id": "10", "text": "isso é montagem, fake", "timestamp": "2026-10-05T12:00:00.000Z", "likesCount": 9,
             "owner": {"id": "u1", "username": "fulana"}}
        c = {"id": "11", "text": "Que vergonha", "timestamp": "2026-10-05T13:00:00.000Z", "likesCount": 1, "ownerUsername": "beltrano"}
        reel = {"shortCode": "X1", "videoPlayCount": 100, "commentsCount": 50, "ownerUsername": "dono", "likesCount": 7}
        with tempfile.TemporaryDirectory() as t:
            fs = []
            for i, it in enumerate([[a, reel], [b, c], []]):
                p = Path(t) / f"r{i}.json"
                p.write_text(json.dumps({"run_id": f"r{i}", "inicio_utc": "2026-10-07T01:30:00Z", "items": it}), encoding="utf-8")
                fs.append(p)
            coms, rl, st = bi.unificar(fs, "X1")
        self.assertEqual((st["itens_brutos"], st["comentarios_unicos"], st["runs_sem_itens"]), (4, 2, 1))
        self.assertEqual(coms["10"]["curtidas"], 9)
        self.assertEqual(coms["10"]["runs"], {"r0", "r1"})
        ag = bi.agregar(coms, rl, st, bi.CASOS["007"])
        self.assertEqual(ag["unificacao"]["duplicados_removidos"], 1)
        self.assertEqual(ag["reel"]["reproducoes"], 100)
        txt = json.dumps(ag, ensure_ascii=False)
        for nome in ("fulana", "beltrano", "dono"):
            self.assertNotIn(nome, txt)
        self.assertEqual(ag["categorias_pct"]["aponta montagem, IA ou fake"], 50.0)


if __name__ == "__main__":
    unittest.main()


class TestAutorPublico(unittest.TestCase):
    def test_nome_e_video_so_com_10_mil_seguidores_lidos(self):
        import build_caso_instagram as b
        grande = b.autor_publico({"usuario": "u", "nome": "N", "seguidores": 10000, "lido_em_utc": "x"}, "SC")
        self.assertEqual(grande["autor"], "@u (N)")
        self.assertEqual(grande["embed"], "https://www.instagram.com/p/SC/embed")
        pequeno = b.autor_publico({"usuario": "u", "nome": "N", "seguidores": 9999}, "SC")
        self.assertNotIn("u", pequeno["autor"].split())
        self.assertNotIn("embed", pequeno)
        self.assertTrue(b.autor_publico(None, "SC")["autor"].startswith("⛔"))
