"""Testes do coletor e do processamento do TikTok, sem rede (dados sintéticos)."""
import csv
import gzip
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import collect_tiktok as ct  # noqa: E402
import build_tiktok as bt  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]


class TestColetor(unittest.TestCase):
    def test_handle(self):
        self.assertEqual(ct.handle("HTTPS://WWW.TIKTOK.COM/@LULAOFICIAL?_R=1&_T=ZS-98H1GREGK7H"), "lulaoficial")
        self.assertEqual(ct.handle("HTTP://WWW.TIKTOK.COM/ALFREDOGASPAR"), "alfredogaspar")
        self.assertEqual(ct.handle("https://www.tiktok.com/@comitedeluta?lang=en"), "comitedeluta")
        self.assertIsNone(ct.handle("https://www.instagram.com/lula"))

    def test_data_pelo_id(self):
        # 7697006006529821958 >> 32 = 1792107… (outubro de 2026)
        self.assertTrue(ct.data_do_id("7697006006529821958").startswith("2026-10"))
        self.assertIsNone(ct.data_do_id("abc"))

    def test_alvos_das_chapas_13_e_22(self):
        a = ct.alvos(ROOT)
        perfis = {x["perfil"]: x["candidate_name"] for x in a}
        self.assertEqual(perfis.get("lulaoficial"), "Lula")
        self.assertEqual(perfis.get("flaviobolsonaro"), "Flávio Bolsonaro")
        self.assertEqual(perfis.get("alckmingeraldo"), "Lula")  # vice entra na chapa do titular
        self.assertNotIn("augustocuryoficial", perfis)
        self.assertEqual(len(perfis), len(a))  # sem duplicatas

    def test_linha_e_mescla_preserva_bloqueados(self):
        alvo = {"candidate_id": "1", "candidate_name": "L", "perfil": "p", "declarado_por": "L"}
        r = ct.linha(alvo, {"id": "7697006006529821958", "description": "Fim  da escala 6x1", "view_count": 386,
                            "like_count": 33, "comment_count": 18}, "2026-10-15T00:00:00Z")
        self.assertEqual((r["visualizacoes"], r["legenda"], r["compartilhamentos"]), (386, "Fim da escala 6x1", ""))
        antigo = {"q|1": {"perfil": "q", "video_id": "1", "primeira_coleta": "2026-10-01T00:00:00Z"},
                  "p|7697006006529821958": {"primeira_coleta": "2026-10-10T00:00:00Z"}}
        m = ct.mesclar(antigo, [r])
        self.assertIn("q|1", m)  # perfil que não veio hoje continua no acervo
        self.assertEqual(m["p|7697006006529821958"]["primeira_coleta"], "2026-10-10T00:00:00Z")
        self.assertEqual(m["p|7697006006529821958"]["visualizacoes"], 386)


class TestProcessamento(unittest.TestCase):
    def test_conteudo(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            (root / "data/config").mkdir(parents=True)
            (root / "data/tiktok").mkdir(parents=True)
            (root / "data/config/temas_youtube.json").write_text(
                (ROOT / "data/config/temas_youtube.json").read_text(encoding="utf-8"), encoding="utf-8")
            rows = []
            for i in range(4):
                rows.append({"candidate_id": "280002542548", "candidate_name": "Lula", "perfil": "lulaoficial",
                             "declarado_por": "LULA", "video_id": str(7697006006529821958 + i), "url": "u",
                             "publicado_em": "2026-10-1%dT00:00:00Z" % i,
                             "legenda": "Fim da escala 6x1 para o trabalhador #lula13 #emprego" if i % 2 else "Vote 13 #lula13",
                             "duracao_s": "30", "visualizacoes": "100", "curtidas": "10", "comentarios": "5",
                             "compartilhamentos": "5", "primeira_coleta": "", "ultima_coleta": ""})
            with gzip.open(root / "data/tiktok/videos.csv.gz", "wt", encoding="utf-8", newline="") as f:
                w = csv.DictWriter(f, fieldnames=ct.COLS, delimiter=";"); w.writeheader(); w.writerows(rows)
            self.assertEqual(bt.main([d]), 0)
            out = json.loads((root / "data/tiktok/conteudo.json").read_text(encoding="utf-8"))
            lula = out["candidatos"]["280002542548"]
            self.assertEqual(lula["total_videos"], 4)
            self.assertEqual(lula["por_tema"].get("economia"), 2)
            self.assertEqual(lula["pede_voto"], 2)
            self.assertEqual(lula["taxa_interacao_mediana"], 0.2)
            tags = dict(map(tuple, lula["hashtags"]))
            self.assertEqual(tags.get("lula13"), 4)   # hashtag de campanha conta
            self.assertNotIn("lulaoficial", tags)     # nome do próprio perfil não conta
            self.assertEqual(out["candidatos"]["280002551544"]["total_videos"], 0)


class TestPlataformas(unittest.TestCase):
    def test_args_e_caminhos(self):
        import plataformas as pl
        self.assertEqual(pl.args([]), (Path("."), "youtube"))
        self.assertEqual(pl.args(["/x", "--plataforma", "tiktok"]), (Path("/x"), "tiktok"))
        with self.assertRaises(SystemExit):
            pl.args(["--plataforma", "orkut"])
        self.assertEqual(pl.args(["--plataforma", "kwai"])[1], "kwai")
        self.assertEqual(len({pl.CAMINHOS[p]["chd"] for p in ("youtube", "tiktok", "kwai")}), 3)

    def test_tiktok_no_formato_do_youtube(self):
        import plataformas as pl
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / "data/tiktok").mkdir(parents=True)
            rows = [{**{k: "" for k in ct.COLS}, "candidate_id": "1", "perfil": "p", "video_id": "9", "legenda": "x #y",
                     "publicado_em": pub, "duracao_s": "30", "ultima_coleta": "z"} for pub in ("2026-07-01T00:00:00Z", "2026-09-01T00:00:00Z")]
            with gzip.open(Path(d) / "data/tiktok/videos.csv.gz", "wt", encoding="utf-8", newline="") as f:
                w = csv.DictWriter(f, fieldnames=ct.COLS, delimiter=";"); w.writeheader(); w.writerows(rows)
            v = pl.videos(Path(d), "tiktok")
            self.assertEqual(len(v), 1)  # antes do início da pré-campanha (20/07) fica fora
            self.assertEqual((v[0]["channel_id"], v[0]["descricao"], v[0]["duracao"]), ("p", "x #y", "PT30S"))


if __name__ == "__main__":
    unittest.main()


class TestMencoes(unittest.TestCase):
    def test_mencoes_e_rede(self):
        try:
            import build_rede_mencoes_tiktok as bm
        except ImportError:
            self.skipTest("networkx ausente")
        self.assertEqual(bm.mencoes("Com @FernandoHaddadOficial e @lulaoficial. email a@b.com"), {"fernandohaddadoficial", "lulaoficial"})
        base = {k: "" for k in ct.COLS}
        rows = [{**base, "candidate_id": "280002542548", "candidate_name": "Lula", "perfil": "alck", "video_id": str(i),
                 "publicado_em": "2026-09-01T00:00:00Z", "legenda": "com @lulaoficial @simonetebet", "url": "u"} for i in range(3)]
        rows += [{**base, "candidate_id": "280002551544", "candidate_name": "Flávio", "perfil": "fb", "video_id": "9",
                  "publicado_em": "2026-09-01T00:00:00Z", "legenda": "com @nikolas e @fb", "url": "u"},
                 {**base, "candidate_id": "280002542548", "candidate_name": "Lula", "perfil": "vazio", "video_id": "8",
                  "publicado_em": "2026-09-01T00:00:00Z", "legenda": "sem marcação", "url": "u"},
                 {**base, "candidate_id": "280002542548", "candidate_name": "Lula", "perfil": "alck", "video_id": "7",
                  "publicado_em": "2026-07-01T00:00:00Z", "legenda": "@antes", "url": "u"}]
        g = bm.montar(rows)
        self.assertEqual(g["alck"]["lulaoficial"]["weight"], 3)
        self.assertNotIn("antes", g)            # antes de 16/08 fica fora
        self.assertFalse(g.has_edge("fb", "fb"))  # automenção não conta
        self.assertEqual(g.nodes["nikolas"]["frac_lula"], 0.0)
        bm.posicionar(g)
        self.assertNotIn("vazio", g)            # perfil sem marcação sai do desenho
        self.assertLess(g.nodes["lulaoficial"]["x"], g.nodes["nikolas"]["x"])  # Lula à esquerda, Flávio à direita
