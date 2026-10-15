"""Testes do coletor do YouTube (sem rede)."""
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import collect_youtube as cy  # noqa: E402


class TestParse(unittest.TestCase):
    def test_formatos(self):
        self.assertEqual(cy.parse_channel("https://www.youtube.com/@LULAOFICIAL"), ("handle", "@LULAOFICIAL"))
        self.assertEqual(cy.parse_channel("https://youtube.com/channel/UCabcdefghijklmnopqrstuv"), ("id", "UCabcdefghijklmnopqrstuv"))
        self.assertEqual(cy.parse_channel("https://www.youtube.com/user/fulano"), ("username", "fulano"))
        self.assertIsNone(cy.parse_channel("https://www.youtube.com/c/fulano"))
        self.assertIsNone(cy.parse_channel("https://www.youtube.com/watch?v=abc"))
        self.assertIsNone(cy.parse_channel("https://instagram.com/x"))

    def test_sem_chave_bloqueia(self):
        old = os.environ.pop("YOUTUBE_API_KEY", None)
        try:
            r = Path(tempfile.mkdtemp())
            self.assertEqual(cy.main([str(r)]), 1)
        finally:
            if old is not None:
                os.environ["YOUTUBE_API_KEY"] = old


if __name__ == "__main__":
    unittest.main()


class TestVideos(unittest.TestCase):
    def test_pagina_ate_a_data_e_busca_estatisticas(self):
        chamadas = []

        def fake(url, timeout=60):
            chamadas.append(url)
            if "/playlistItems" in url and "pageToken" not in url:
                return {"items": [{"contentDetails": {"videoId": "v2", "videoPublishedAt": "2026-10-10T00:00:00Z"}},
                                  {"contentDetails": {"videoId": "v1", "videoPublishedAt": "2026-09-01T00:00:00Z"}}],
                        "nextPageToken": "P2"}
            if "/playlistItems" in url:
                return {"items": [{"contentDetails": {"videoId": "v0", "videoPublishedAt": "2026-08-01T00:00:00Z"}}],
                        "nextPageToken": "P3"}
            return {"items": [{"id": "v2", "snippet": {"publishedAt": "2026-10-10T00:00:00Z", "title": "A"},
                               "statistics": {"viewCount": "10", "likeCount": "2", "commentCount": "1"},
                               "contentDetails": {"duration": "PT1M"}},
                              {"id": "v1", "snippet": {"publishedAt": "2026-09-01T00:00:00Z", "title": "B"},
                               "statistics": {"viewCount": "5"}, "contentDetails": {"duration": "PT2M"}}]}
        orig = cy.get_json
        cy.get_json = fake
        try:
            vids, cota = cy.videos_do_canal("k", "UU123", "2026-08-16")
        finally:
            cy.get_json = orig
        self.assertEqual([v["video_id"] for v in vids], ["v2", "v1"])
        self.assertEqual(cota, 3)  # 2 páginas da playlist (parou ao passar da data) + 1 videos.list
        self.assertFalse(any("P3" in c for c in chamadas))
