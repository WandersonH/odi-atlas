import csv
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import build_saude_coleta as B  # noqa: E402
import collect_seguidores_tiktok as T  # noqa: E402


class TestSaude(unittest.TestCase):
    def rodar(self, arquivos: dict, series: list, agora: str):
        d = tempfile.mkdtemp()
        cwd = os.getcwd()
        try:
            os.chdir(d)
            Path("data/config").mkdir(parents=True)
            Path("data/config/saude_coleta.json").write_text(json.dumps({"nota": "t", "series": series}), encoding="utf-8")
            for k, v in arquivos.items():
                Path(k).parent.mkdir(parents=True, exist_ok=True)
                Path(k).write_text(v if isinstance(v, str) else json.dumps(v), encoding="utf-8")
            rc = B.main(["--agora", agora, "--falhar"])
            return rc, json.loads(Path("data/saude_coleta.json").read_text(encoding="utf-8"))
        finally:
            os.chdir(cwd)

    def test_tentativa_falha_nao_conta_como_dado(self):
        rc, S = self.rodar({"data/k/manifesto_latest.json": {"run_started_utc": "2026-10-23T10:00:00Z", "status": "⛔ Apify: HTTPError 401"},
                            "data/k/manifesto-2026-10-x.json": {"run_started_utc": "2026-10-18T16:00:00Z", "status": "ok"}},
                           [{"nome": "K", "pagina": "K", "tipo": "manifesto", "arquivo": "data/k/manifesto_latest.json", "max_horas": 36}],
                           "2026-10-23T16:00:00Z")
        x = S["series"][0]
        self.assertEqual(x["ultimo_dado"], "2026-10-18T16:00:00Z")
        self.assertEqual(x["situacao"], "⛔ atrasada")
        self.assertEqual(rc, 1)

    def test_csv_em_dia(self):
        txt = "url;followers;captured_at\na;1;2026-10-23\nb;2;2026-10-18\n"
        rc, S = self.rodar({"data/s/t_latest.csv": txt},
                           [{"nome": "T", "pagina": "Q", "tipo": "csv", "arquivo": "data/s/t_latest.csv", "coluna": "captured_at", "max_horas": 36}],
                           "2026-10-23T16:00:00Z")
        x = S["series"][0]
        self.assertEqual(x["situacao"], "em dia")
        self.assertEqual((x["perfis_lidos_no_ultimo_dia"], x["perfis_no_arquivo"]), (1, 2))
        self.assertEqual(rc, 0)


class TestTikTokPagina(unittest.TestCase):
    def test_le_seguidores_do_bloco(self):
        d = {"__DEFAULT_SCOPE__": {"webapp.user-detail": {"userInfo": {"stats": {"followerCount": 6200000}}}}}
        html = f'<html><script id="__UNIVERSAL_DATA_FOR_REHYDRATION__" type="application/json">{json.dumps(d)}</script></html>'
        self.assertEqual(T.da_pagina(html), 6200000)
        self.assertIsNone(T.da_pagina("<html>captcha</html>"))

    def test_gratis_preserva_numero_antigo_com_data_antiga(self):
        d = Path(tempfile.mkdtemp())
        seg = d / "data/seguidores"
        seg.mkdir(parents=True)
        (seg / "tiktok_latest.csv").write_text("candidate_id;candidate_name;platform;url;followers;captured_at;source_url\n"
                                                "1;X;TikTok;U2;50;2026-10-18;s\n", encoding="utf-8")
        al = [{"usuario": "a", "url_tse": "U1", "candidate_id": "1", "declarado_por": "X"},
              {"usuario": "b", "url_tse": "U2", "candidate_id": "1", "declarado_por": "X"}]
        import time as _t
        s0 = _t.sleep
        _t.sleep = lambda *_: None
        try:
            rc = T.gratis(d, al, "2026-10-23T16:00:00Z", seg, lambda u: (100, None) if u == "a" else (None, "bloqueado"))
        finally:
            _t.sleep = s0
        self.assertEqual(rc, 0)
        rows = {r["url"]: r for r in csv.DictReader(open(seg / "tiktok_latest.csv", encoding="utf-8"), delimiter=";")}
        self.assertEqual((rows["U1"]["followers"], rows["U1"]["captured_at"]), ("100", "2026-10-23"))
        self.assertEqual((rows["U2"]["followers"], rows["U2"]["captured_at"]), ("50", "2026-10-18"))


if __name__ == "__main__":
    unittest.main()
