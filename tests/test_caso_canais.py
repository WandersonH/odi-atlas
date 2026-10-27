import csv
import gzip
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import caso_canais as cc  # noqa: E402
from collect_comentarios_youtube import CAMPOS  # noqa: E402


def gravar(arq, linhas):
    arq.parent.mkdir(parents=True, exist_ok=True)
    with gzip.open(arq, "wt", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, CAMPOS, delimiter=";", extrasaction="ignore")
        w.writeheader()
        w.writerows(linhas)


class TestCanais(unittest.TestCase):
    def test_publico_em_comum_temas_e_redes(self):
        with tempfile.TemporaryDirectory() as d:
            interno, pub = Path(d) / "int", Path(d) / "pub"
            pub.mkdir()
            gravar(interno / "youtube/comentarios/comentarios.csv.gz", [{"comment_id": "x", "candidate_id": "280002551544", "autor_canal": "u1"}])
            priv = interno / "casos/012"
            gravar(priv / "youtube_comentarios.csv.gz", [
                {"comment_id": "1", "channel_id": "A", "autor_canal": "u1", "autor_nome": "Fulano", "texto": "segredo"},
                {"comment_id": "2", "channel_id": "B", "autor_canal": "u1", "texto": "x"},
                {"comment_id": "3", "channel_id": "B", "autor_canal": "u2", "texto": "x"}])
            dados = {"canais": [{"id": "A", "titulo": "Canal A", "handle": "a", "inscritos": 1, "visualizacoes": 1, "videos": 1, "lido_em_utc": "t"},
                                {"id": "B", "titulo": "Canal B", "handle": "b", "inscritos": 1, "visualizacoes": 1, "videos": 1, "lido_em_utc": "t"}],
                     "envios": [{"id": "v", "canal_id": "A", "titulo": "Trump e as sanções a Moraes", "descricao": "", "publicado_em": "2026-10-20T10:00:00Z", "visualizacoes": 10}]}
            out = cc.analisar("012", {"titulo": "t", "desde": "d", "comentarios_desde": "d"}, dados, priv, interno, pub)
            self.assertEqual(out["pares"][0]["autores_em_comum"], 1)
            self.assertEqual(out["autores_em_todos_os_canais"], 1)
            a = out["producao"][0]
            self.assertEqual(a["temas"]["EUA, Trump ou Rubio"]["n"], 1)
            self.assertEqual(a["temas"]["sanções, Magnitsky, tarifas ou vistos"]["n"], 1)
            self.assertEqual(out["publico"][0]["pct_flavio"], 100.0)
            txt = json.dumps(out, ensure_ascii=False) + "".join((pub / f).read_text() for f in ("rede_canais.gexf", "rede_canais_autores.gexf", "rede_canais_temas.gexf"))
            for proibido in ("Fulano", "segredo", "u1", "u2"):
                self.assertNotIn(proibido, txt)
            self.assertIn("Alexandre de Moraes", (pub / "rede_canais_temas.gexf").read_text())
