"""Testes do coletor Apify (sem rede e sem gastar crédito)."""
import csv
import gzip
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import collect_meta_apify as cm  # noqa: E402


def root_with_targets():
    r = Path(tempfile.mkdtemp())
    (r / "data/tse").mkdir(parents=True); (r / "data/config").mkdir(); (r / "data/seguidores").mkdir()
    cfg = json.loads((Path(__file__).resolve().parents[1] / "data/config/seguidores_meta.json").read_text(encoding="utf-8"))
    (r / "data/config/seguidores_meta.json").write_text(json.dumps(cfg), encoding="utf-8")
    with gzip.open(r / "data/tse/redes_sociais_candidatos_2026.csv.gz", "wt", encoding="utf-8", newline="") as f:
        w = csv.writer(f, delimiter=";")
        w.writerow(["SQ_CANDIDATO", "DS_URL", "DS_CARGO", "NM_URNA_CANDIDATO", "PLATAFORMA"])
        w.writerow(["280002542548", "HTTPS://WWW.INSTAGRAM.COM/LULAOFICIAL/", "PRESIDENTE", "LULA", "instagram"])
        w.writerow(["280002542548", "https://facebook.com/LULA", "PRESIDENTE", "LULA", "facebook"])
        w.writerow(["250001", "https://instagram.com/deputado", "DEPUTADO FEDERAL", "X", "instagram"])
    return r, cfg


class TestChaves(unittest.TestCase):
    def test_ig_username(self):
        self.assertEqual(cm.ig_username("HTTPS://WWW.INSTAGRAM.COM/LULAOFICIAL/"), "lulaoficial")
        self.assertEqual(cm.ig_username("instagram.com/@flavio.bolsonaro?igsh=abc"), "flavio.bolsonaro")
        self.assertIsNone(cm.ig_username("https://www.instagram.com/p/ABC123/"))
        self.assertIsNone(cm.ig_username("https://www.instagram.com/"))

    def test_fb_url(self):
        self.assertEqual(cm.fb_url("https://m.facebook.com/LULA/"), "https://www.facebook.com/LULA")
        self.assertEqual(cm.fb_url("https://facebook.com/profile.php?id=123"), "https://www.facebook.com/profile.php?id=123")
        self.assertIsNone(cm.fb_url("https://www.facebook.com/"))
        self.assertIsNone(cm.fb_url("https://x.com/abc"))

    def test_alvos_filtram_cargo(self):
        r, cfg = root_with_targets()
        t = cm.load_targets(r, cfg)
        self.assertEqual([(x["platform"], x["key"]) for x in t],
                         [("instagram", "lulaoficial"), ("facebook", "https://www.facebook.com/LULA")])


class TestBloqueios(unittest.TestCase):
    def setUp(self):
        self.old = os.environ.pop("APIFY_TOKEN", None)

    def tearDown(self):
        if self.old is not None:
            os.environ["APIFY_TOKEN"] = self.old

    def test_sem_token_bloqueia_sem_chamar_api(self):
        r, _ = root_with_targets()
        self.assertEqual(cm.main([str(r)]), 1)
        m = json.loads((r / "data/seguidores/manifesto_latest.json").read_text(encoding="utf-8"))
        self.assertIn("APIFY_TOKEN ausente", m["blocked"][0])

    def test_teto_mensal_bloqueia_antes_de_gastar(self):
        r, cfg = root_with_targets()
        import datetime as dt
        mes = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m")
        (r / f"data/seguidores/manifesto-{mes}-x.json").write_text(json.dumps({"custo_total_usd": cfg["teto_mensal_usd"]}))
        os.environ["APIFY_TOKEN"] = "teste-nao-usado"
        chamou = []
        orig = cm.api
        cm.api = lambda *a, **k: chamou.append(a) or {}
        try:
            self.assertEqual(cm.main([str(r)]), 1)
        finally:
            cm.api = orig
            os.environ.pop("APIFY_TOKEN", None)
        self.assertEqual(chamou, [])
        m = json.loads((r / "data/seguidores/manifesto_latest.json").read_text(encoding="utf-8"))
        self.assertIn("teto mensal", m["blocked"][0])


if __name__ == "__main__":
    unittest.main()
