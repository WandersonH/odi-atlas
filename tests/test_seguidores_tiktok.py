import os, sys, tempfile, unittest, json
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import collect_seguidores_tiktok as st

RAIZ = Path(__file__).resolve().parents[1]


class TestSeguidoresTikTok(unittest.TestCase):
    def test_alvos_e_csv(self):
        al = st.alvos(RAIZ)
        self.assertIn("evangelicoscomlula", [a["usuario"] for a in al])
        self.assertEqual(len({a["usuario"] for a in al}), len(al))

        def fake(payload, cap):
            return {"id": "r"}, [{"authorMeta": {"fans": 1234}}]
        cwd = os.getcwd()
        with tempfile.TemporaryDirectory() as t:
            (Path(t) / "data/tse").mkdir(parents=True)
            (Path(t) / "data/tse/redes_presidencia_2026.json").write_text((RAIZ / "data/tse/redes_presidencia_2026.json").read_text(encoding="utf-8"), encoding="utf-8")
            os.chdir(t)
            try:
                self.assertEqual(st.main([], executar=fake), 0)
                txt = Path("data/seguidores/tiktok_latest.csv").read_text(encoding="utf-8")
            finally:
                os.chdir(cwd)
        self.assertIn("TikTok;https://www.tiktok.com/@evangelicoscomlula;1234", txt)


if __name__ == "__main__":
    unittest.main()
