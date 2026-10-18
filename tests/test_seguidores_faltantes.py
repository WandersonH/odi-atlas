import os, sys, tempfile, unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import collect_seguidores_faltantes as sf

RAIZ = Path(__file__).resolve().parents[1]


class TestSeguidoresFaltantes(unittest.TestCase):
    def test_usuario(self):
        self.assertEqual(sf.usuario("x", "https://x.com/LulaEvangelicos"), "lulaevangelicos")
        self.assertEqual(sf.usuario("tiktok", "HTTPS://WWW.TIKTOK.COM/@BRASILCOMLULA_"), "brasilcomlula_")
        self.assertEqual(sf.usuario("instagram", "https://www.instagram.com/comitepopularoficial"), "comitepopularoficial")

    def test_faltantes_e_fallback(self):
        chamadas = []

        def fake(ator, pl):
            chamadas.append(ator)
            if ator.startswith("clockworks~tiktok-profile"):
                return {"id": "r1"}, [{"noResults": True}]          # 1º ator falha
            return {"id": "r2"}, [{"authorMeta": {"fans": 321}, "followersCount": 321}]
        cwd = os.getcwd()
        with tempfile.TemporaryDirectory() as t:
            (Path(t) / "data/tse").mkdir(parents=True)
            (Path(t) / "data/tse/redes_presidencia_2026.json").write_text((RAIZ / "data/tse/redes_presidencia_2026.json").read_text(encoding="utf-8"), encoding="utf-8")
            (Path(t) / "data/seguidores").mkdir(parents=True)
            (Path(t) / "data/seguidores/tiktok_latest.csv").write_text(
                "candidate_id;candidate_name;platform;url;followers;captured_at;source_url\n"
                "280002542548;LULA;TikTok;https://www.tiktok.com/@pode_espalhar;10;2026-10-18;\n", encoding="utf-8")
            os.chdir(t)
            try:
                al = [a["usuario"] for a in sf.faltantes(Path(".")) if a["plataforma"] == "tiktok"]
                self.assertIn("evangelicoscomlula", al)
                self.assertNotIn("pode_espalhar", al)
                self.assertEqual(sf.main([], executar=fake), 0)
                txt = Path("data/seguidores/complemento_latest.csv").read_text(encoding="utf-8")
            finally:
                os.chdir(cwd)
        self.assertIn("clockworks~tiktok-scraper", chamadas)
        self.assertIn("TikTok;HTTPS://WWW.TIKTOK.COM/@BRASILCOMLULA_;321", txt.upper().replace("TIKTOK;HTTPS", "TikTok;HTTPS"))


if __name__ == "__main__":
    unittest.main()
