import csv
import gzip
import json
import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "scripts"))
import build_bardin_caso as bb  # noqa: E402

CAMPOS = ["rede", "item_id", "conta", "nome_conta", "seguidores", "verificada", "publicado_em", "texto", "visualizacoes", "curtidas",
          "comentarios", "compartilhamentos", "termo", "url", "capa_url", "coletado_em"]


class TestBardin(unittest.TestCase):
    def test_categorias_blocos_amostra_e_privacidade(self):
        with tempfile.TemporaryDirectory() as d:
            pub, priv = Path(d) / "pub", Path(d) / "int"
            (pub / "data/config").mkdir(parents=True)
            for f in ("casos.json", "livro_codigos_caso014.json"):
                shutil.copy(RAIZ / "data/config" / f, pub / "data/config" / f)
            (priv / "casos/014").mkdir(parents=True)
            linhas = [("x", "1", "fulano", "50", "Demita um petista, não contrate ninguém do PT", "demitir petista"),
                      ("x", "2", "beltrano", "20000", "Fui demitida por votar no Lula, isso é assédio eleitoral, denuncie ao MPT", "demitido por votar"),
                      ("tiktok", "3", "ciclano", "10", "direita apoia direita: só compre de quem é conservador", "direita apoia direita"),
                      ("x", "4", "x4", "10", "bom dia", "demitir petista")]
            with gzip.open(priv / "casos/014/itens.csv.gz", "wt", encoding="utf-8", newline="") as f:
                w = csv.DictWriter(f, CAMPOS, delimiter=";", extrasaction="ignore")
                w.writeheader()
                for rede, i, conta, seg, txt, termo in linhas:
                    w.writerow({"rede": rede, "item_id": i, "conta": conta, "seguidores": seg, "publicado_em": "2026-10-26T12:00:00Z", "texto": txt,
                                "termo": termo, "url": f"https://x/{i}"})
            cwd = os.getcwd()
            os.chdir(pub)
            try:
                with mock.patch.dict(os.environ, {"ODI_INTERNO_DIR": str(priv)}):
                    bb.main(["--caso", "014"])
                b = json.loads((pub / "data/casos/014/bardin.json").read_text(encoding="utf-8"))
            finally:
                os.chdir(cwd)
            self.assertEqual(b["publicacoes"], 4)
            self.assertEqual(b["categorias"]["incita_demissao"]["n"], 1)
            self.assertEqual(b["categorias"]["relato_vitima"]["n"], 1)
            self.assertEqual(b["categorias"]["denuncia_ilegalidade"]["n"], 1)
            self.assertEqual(b["categorias"]["preferencia_intragrupo"]["n"], 1)
            self.assertEqual(b["sem_categoria"]["n"], 1)
            ex = json.dumps(b["exemplos_contas_10mil"], ensure_ascii=False)
            self.assertNotIn("fulano", ex)
            self.assertIn("beltrano", ex)
            self.assertNotIn("Demita um petista, não contrate", json.dumps(b, ensure_ascii=False))
            self.assertEqual(len(b["pontos"]), 4)
            self.assertNotIn("fulano", json.dumps(b["pontos"]))
            self.assertIn("beltrano", json.dumps(b["pontos"]))
            plan = priv / "casos/014/codificacao/amostra_bardin_v1.csv"
            self.assertTrue(plan.exists())
            antes = plan.read_text(encoding="utf-8")
            os.chdir(pub)
            try:
                with mock.patch.dict(os.environ, {"ODI_INTERNO_DIR": str(priv)}):
                    bb.main(["--caso", "014"])
            finally:
                os.chdir(cwd)
            self.assertEqual(plan.read_text(encoding="utf-8"), antes)  # nunca sobrescrita
