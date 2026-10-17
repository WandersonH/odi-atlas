import sys, unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import build_criativos_meta as b


class TestCriativos(unittest.TestCase):
    def test_previa_e_texto(self):
        self.assertEqual(b.previa({"images": [], "videos": [{"video_preview_image_url": "v.jpg"}]}), "v.jpg")
        self.assertEqual(b.previa({"cards": [{"resized_image_url": "c.jpg"}]}), "c.jpg")
        self.assertIsNone(b.previa({}))
        self.assertEqual(b.texto({"body": {"text": "{{product.brand}}"}, "cards": [{"body": "Vote  13"}]}), "Vote 13")
        self.assertEqual(b.piso_impressoes({"impressions_with_index": {"impressions_text": ">1M"}}), 1000000)


if __name__ == "__main__":
    unittest.main()
