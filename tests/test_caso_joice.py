import csv
import gzip
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import caso_joice as cj  # noqa: E402
from collect_comentarios_youtube import CAMPOS  # noqa: E402


def gravar(arq, linhas):
    arq.parent.mkdir(parents=True, exist_ok=True)
    with gzip.open(arq, "wt", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, CAMPOS, delimiter=";", extrasaction="ignore")
        w.writeheader()
        w.writerows(linhas)


class TestJoice(unittest.TestCase):
    def test_bolha_redes_e_privacidade(self):
        with tempfile.TemporaryDirectory() as d:
            interno, pub = Path(d) / "int", Path(d) / "pub"
            pub.mkdir()
            gravar(interno / "youtube/comentarios/comentarios.csv.gz", [
                {"comment_id": "x1", "candidate_id": cj.LULA, "autor_canal": "uL"}, {"comment_id": "x2", "candidate_id": cj.FLAVIO, "autor_canal": "uF"},
                {"comment_id": "x3", "candidate_id": cj.LULA, "autor_canal": "uA"}, {"comment_id": "x4", "candidate_id": cj.FLAVIO, "autor_canal": "uA"}])
            priv = interno / "casos/011"
            gravar(priv / "youtube_comentarios.csv.gz", [
                {"comment_id": "1", "channel_id": "CJ", "video_id": "v1", "autor_canal": "uF", "autor_nome": "Fulano", "texto": "segredo", "publicado_em": "2026-10-20T10:00:00Z"},
                {"comment_id": "2", "channel_id": "CJ", "video_id": "v2", "autor_canal": "uL", "texto": "x", "publicado_em": "2026-10-23T10:00:00Z"},
                {"comment_id": "3", "channel_id": "CB", "video_id": "v3", "autor_canal": "uA", "texto": "x", "publicado_em": "2026-10-23T10:00:00Z"},
                {"comment_id": "4", "channel_id": "CP", "video_id": "v4", "autor_canal": "uN", "texto": "x", "publicado_em": "2026-10-23T10:00:00Z"}])
            dados = {"canal": {"id": "CJ", "titulo": "Joice", "inscritos": 100, "lido_em_utc": "2026-10-27T06:00:00Z"},
                     "sementes": [{"id": "v3", "canal": "TV 247", "canal_id": "CB", "inscritos_canal": 2000000, "visualizacoes": 10}],
                     "recortes": [{"id": "v4", "canal": "Pequeno", "canal_id": "CP", "inscritos_canal": 50, "visualizacoes": 7}], "envios": []}
            out = cj.analisar(dados, priv, interno, pub)
            b = out["bolha"]
            self.assertEqual(b["canal_dela_antes"]["pct_flavio"], 100.0)
            self.assertEqual(b["canal_dela_depois"]["pct_lula"], 100.0)
            self.assertEqual(out["recortes"], [])
            self.assertEqual(out["recortes_canais_pequenos"]["videos"], 1)
            txt = json.dumps(out, ensure_ascii=False) + (pub / "rede_canais_autores.gexf").read_text() + (pub / "rede_canais.gexf").read_text()
            for proibido in ("Fulano", "segredo", "uF", "uL", "Pequeno"):
                self.assertNotIn(proibido, txt)
            self.assertIn("ACERVO_LULA", (pub / "rede_canais.gexf").read_text())
            self.assertEqual(len(json.loads((pub / "canal_serie.json").read_text())), 1)
