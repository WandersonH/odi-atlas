import csv
import gzip
import json
import os
import sys
import tempfile
import unittest
import urllib.parse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import collect_comentarios_youtube_completo as C  # noqa: E402


def conversa(i, n_resp):
    sn = lambda t: {"authorDisplayName": "a", "authorChannelId": {"value": "c"}, "textOriginal": t, "likeCount": 0, "publishedAt": "2026-10-01T00:00:00Z"}
    return {"snippet": {"topLevelComment": {"id": f"t{i}", "snippet": sn("oi")}, "totalReplyCount": n_resp},
            "replies": {"comments": [{"id": f"t{i}.r{j}", "snippet": sn("r")} for j in range(min(5, n_resp))]}}


class TestCompleto(unittest.TestCase):
    def test_pagina_ate_o_fim_e_busca_respostas_extras(self):
        d = Path(tempfile.mkdtemp())
        cwd = os.getcwd()
        try:
            os.chdir(d)
            Path("data/config").mkdir(parents=True)
            Path("data/youtube").mkdir(parents=True)
            Path("data/config/comentarios_youtube.json").write_text(json.dumps({"desde": "2026-08-16", "paralelo": 1, "completo": {"cota_dia": 50}}))
            Path("data/config/temas_youtube.json").write_text(json.dumps({"candidatos": {"1": {}}}))
            with gzip.open("data/youtube/videos_latest.csv.gz", "wt", encoding="utf-8") as f:
                w = csv.DictWriter(f, ["candidate_id", "video_id", "channel_id", "publicado_em", "comentarios"], delimiter=";")
                w.writeheader()
                w.writerow({"candidate_id": "1", "video_id": "v1", "channel_id": "ch", "publicado_em": "2026-09-01", "comentarios": "300"})
            os.environ["ODI_INTERNO_DIR"] = str(d / "int")

            def api(url):
                q = dict(urllib.parse.parse_qsl(urllib.parse.urlparse(url).query))
                if "commentThreads" in url:
                    if q.get("pageToken") == "p2":
                        return {"items": [conversa(2, 7)]}, None
                    return {"items": [conversa(1, 0)], "nextPageToken": "p2"}, None
                return {"items": [{"id": f"t2.r{j}", "snippet": {"textOriginal": "r", "publishedAt": "x"}} for j in range(7)]}, None
            rc = C.main([], chamar_api=api)
            self.assertEqual(rc, 0)
            rows = list(csv.DictReader(gzip.open(d / "int/youtube/comentarios/comentarios.csv.gz", "rt", encoding="utf-8"), delimiter=";"))
            self.assertEqual(sum(1 for r in rows if r["tipo"] == "comentario"), 2)
            self.assertEqual(sum(1 for r in rows if r["parent_id"] == "t2"), 7)
            est = json.loads((d / "int/youtube/comentarios/estado_completo.json").read_text())
            self.assertTrue(est["threads"]["v1"]["fim"])
            m = json.loads(Path("data/youtube/comentarios/manifesto_completo.json").read_text())
            self.assertEqual((m["chamadas"], m["videos_lidos_ate_o_fim"]), (3, 1))
        finally:
            os.environ.pop("ODI_INTERNO_DIR", None)
            os.chdir(cwd)


if __name__ == "__main__":
    unittest.main()


class TestRetirados(unittest.TestCase):
    def test_some_da_foto_com_canal_lido(self):
        import build_retirados_youtube as R
        base = {"candidate_id": "1", "candidate_name": "LULA", "canal": "c", "titulo": "t", "visualizacoes": "1"}
        F = {"2026-10-20": {"a": {**base, "channel_id": "C1", "publicado_em": "2026-09-01"}, "b": {**base, "channel_id": "C2", "publicado_em": "2026-09-01"},
                            "old": {**base, "channel_id": "C1", "publicado_em": "2026-06-01"}},
             "2026-10-23": {"x": {**base, "channel_id": "C1", "publicado_em": "2026-10-22"}}}
        c = R.candidatos_a_retirado(F)
        self.assertEqual(list(c), ["a"])  # b: canal C2 não lido na última foto; old: antes de 20/07
        self.assertEqual(c["a"]["visto_pela_ultima_vez"], "2026-10-20")
