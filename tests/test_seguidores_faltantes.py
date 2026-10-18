import csv, gzip, os, shutil, sys, tempfile, unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import collect_seguidores_faltantes as sf

RAIZ = Path(__file__).resolve().parents[1]
TSE = "data/tse/redes_sociais_candidatos_2026.csv.gz"
CAB = "candidate_id;candidate_name;platform;url;followers;captured_at;source_url\n"


def tse_minimo(t, linhas):
    (Path(t) / "data/tse").mkdir(parents=True)
    with gzip.open(Path(t) / TSE, "wt", encoding="utf-8", newline="") as f:
        w = csv.writer(f, delimiter=";")
        w.writerow(["SQ_CANDIDATO", "DS_URL", "DS_CARGO", "NM_URNA_CANDIDATO", "PLATAFORMA"])
        w.writerows(linhas)


class TestSeguidoresFaltantes(unittest.TestCase):
    def test_usuario(self):
        self.assertEqual(sf.usuario("x", "https://x.com/LulaEvangelicos"), "lulaevangelicos")
        self.assertEqual(sf.usuario("tiktok", "HTTPS://WWW.TIKTOK.COM/@BRASILCOMLULA_"), "brasilcomlula_")
        self.assertEqual(sf.usuario("instagram", "https://www.instagram.com/comitepopularoficial"), "comitepopularoficial")

    def test_alvos_reais_incluem_vices_e_outros(self):
        al = sf.alvos_tse(RAIZ)
        donos = {(a["declarado_por"], a["plataforma"], a["usuario"]) for a in al}
        self.assertIn(("GERALDO ALCKMIN", "tiktok", "alckmingeraldo"), donos)
        self.assertTrue(any(a["declarado_por"] == "ZEMA" for a in al))

    def test_fallback_reaproveita_e_id_do_vice(self):
        chamadas = []

        def fake(ator, pl):
            chamadas.append(ator)
            if ator.startswith("clockworks~tiktok-profile"):
                return {"id": "r1"}, [{"noResults": True}]          # 1º ator falha
            return {"id": "r2"}, [{"authorMeta": {"fans": 321}}]
        cwd = os.getcwd()
        with tempfile.TemporaryDirectory() as t:
            tse_minimo(t, [["1", "https://www.tiktok.com/@novo", "PRESIDENTE", "A", "tiktok"],
                           ["2", "https://www.tiktok.com/@novo", "VICE-PRESIDENTE", "B", "tiktok"],
                           ["2", "https://x.com/vice", "VICE-PRESIDENTE", "B", "x"]])
            (Path(t) / "data/seguidores").mkdir(parents=True)
            (Path(t) / "data/seguidores/x_latest.csv").write_text(CAB + "1;A;X / Twitter;https://x.com/vice;99;2026-10-18;\n", encoding="utf-8")
            os.chdir(t)
            try:
                self.assertEqual(sf.main([], executar=fake), 0)
                txt = Path("data/seguidores/complemento_latest.csv").read_text(encoding="utf-8")
            finally:
                os.chdir(cwd)
        self.assertEqual(chamadas.count("clockworks~tiktok-scraper"), 1)   # um perfil, uma consulta, dois donos
        self.assertIn("1;A;TikTok;https://www.tiktok.com/@novo;321", txt)
        self.assertIn("2;B;TikTok;https://www.tiktok.com/@novo;321", txt)
        self.assertIn("2;B;X / Twitter;https://x.com/vice;99;2026-10-18", txt)  # reaproveitado com o id do vice

    def test_demo_descartado(self):
        def fake(ator, pl):
            return {"id": "r"}, [{"demo": True, "followers": 1}]
        cwd = os.getcwd()
        with tempfile.TemporaryDirectory() as t:
            tse_minimo(t, [["2", "https://x.com/pl22al", "VICE-PRESIDENTE", "B", "x"]])
            os.chdir(t)
            try:
                self.assertEqual(sf.main([], executar=fake), 1)
                txt = Path("data/seguidores/complemento_latest.csv").read_text(encoding="utf-8")
            finally:
                os.chdir(cwd)
        self.assertNotIn("pl22al", txt.lower())


if __name__ == "__main__":
    unittest.main()
