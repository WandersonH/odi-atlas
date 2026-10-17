import json, sys, tempfile, unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import build_variacao_seguidores as b


class TestVariacao(unittest.TestCase):
    def test_chave(self):
        self.assertEqual(b.chave_url("HTTPS://WWW.INSTAGRAM.COM/LulaOficial/"), "instagram.com|/lulaoficial")
        self.assertEqual(b.chave_url("instagram.com/lulaoficial"), "instagram.com|/lulaoficial")

    def test_main(self):
        with tempfile.TemporaryDirectory() as t:
            p = Path(t) / "data/seguidores"; p.mkdir(parents=True)
            cab = "candidate_id;candidate_name;platform;url;followers;captured_at;source_url\n"
            (p / "coleta_2026-10-15.csv").write_text(cab + "1;A;Instagram;https://instagram.com/a;1000;2026-10-15;\n1;A;Instagram;https://instagram.com/b;0;;\n", encoding="utf-8")
            (p / "coleta_2026-10-17.csv").write_text(cab + "1;A;Instagram;https://www.instagram.com/A/;1010;2026-10-17;\n1;A;Instagram;https://instagram.com/b;5;;\n", encoding="utf-8")
            (p / "latest.csv").write_text(cab, encoding="utf-8")  # ignorado
            self.assertEqual(b.main([t]), 0)
            v = json.loads((p / "variacao.json").read_text(encoding="utf-8"))["itens"]
            x = v["1|instagram.com|/a"]
            self.assertEqual((x["diferenca"], x["variacao_pct"], x["data_anterior"]), (10, 1.0, "2026-10-15"))
            self.assertIsNone(v["1|instagram.com|/b"]["variacao_pct"])


if __name__ == "__main__":
    unittest.main()
