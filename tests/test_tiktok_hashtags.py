"""Coleta de vídeos do TikTok por hashtag (resposta fictícia no formato da api/challenge/item_list)."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import collect_tiktok_hashtags as th  # noqa: E402


ITEM = {"id": "123", "desc": "Dia 25 é 22! #vote22", "createTime": 1760000000,
        "author": {"uniqueId": "contaexemplo", "nickname": "Conta Exemplo", "verified": False},
        "authorStats": {"followerCount": 15000}, "stats": {"playCount": 900, "diggCount": 50, "commentCount": 3, "shareCount": 2},
        "challenges": [{"title": "vote22"}, {"title": "FY"}]}


class TestHashtags(unittest.TestCase):
    def test_linha(self):
        r = th.linha(ITEM, "vote22", "280002551544", "2026-10-16T00:00:00Z")
        self.assertEqual((r["conta"], r["seguidores"], r["visualizacoes"], r["hashtags"]), ("contaexemplo", 15000, 900, "fy|vote22"))
        self.assertEqual(r["publicado_em"], "2025-10-09T08:53:20Z")
        self.assertIsNone(th.linha({"id": "1"}, "x", "y", "z"))

    def test_mesclar_acumula_hashtags(self):
        a = th.linha(ITEM, "vote22", "F", "t1")
        b = {**th.linha(ITEM, "flaviobolsonaro", "F", "t2"), "visualizacoes": 1000}
        m = th.mesclar([a], [b])
        self.assertEqual(len(m), 1)
        self.assertEqual((m[0]["hashtag_coletada"], m[0]["visualizacoes"]), ("flaviobolsonaro|vote22", 1000))


if __name__ == "__main__":
    unittest.main()
