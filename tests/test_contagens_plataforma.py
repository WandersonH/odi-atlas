import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import contagens_plataforma as cp  # noqa: E402


class TestContagens(unittest.TestCase):
    def test_instagram_le_postscount_por_hashtag(self):
        def executar(a, p, c):
            self.assertLessEqual(c, 0.10)
            return {"id": "r"}, [{"name": "demitaumpetista", "postsCount": 1234}, {"url": "https://www.instagram.com/explore/tags/boicote/", "postsCount": 99}]
        out = cp.instagram(["demitaumpetista", "boicote", "inexistente"], "t", executar)
        self.assertEqual([x["total_posts"] for x in out], [1234, 99, None])
