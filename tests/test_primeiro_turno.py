import csv, gzip, json, os, shutil, sys, tempfile, unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import collect_primeiro_turno as pt
import build_primeiro_turno as bpt
import collect_socialblade as sb

RAIZ = Path(__file__).resolve().parents[1]


class TestPrimeiroTurno(unittest.TestCase):
    def test_alvos(self):
        a = pt.alvos(RAIZ)
        nums = {x["numero"] for x in a}
        self.assertFalse(nums & {"13", "22", "28"})                       # 13 e 22 têm coletor próprio; 28 não foi às urnas
        self.assertIn(("tiktok", "clarianabr"), {(x["rede"], x["perfil"]) for x in a})   # "Tik Tok - @clarianabr" (site_ou_outro)
        self.assertIn(("kwai", "wilsongrassi"), {(x["rede"], x["perfil"]) for x in a})  # kwai-video.com/u/@wilsongrassi
        kassab = next(x for x in a if x["perfil"] == "gilbertokassab_")
        self.assertEqual((kassab["candidato"], kassab["cargo"]), ("Ronaldo Caiado", "Vice-Presidente"))  # vice na chapa do titular
        self.assertFalse(any("/share/" in x["perfil"].lower() for x in a if x["rede"] == "facebook"))

    def test_socialblade_todas_as_chapas(self):
        a = sb.alvos(RAIZ)
        self.assertIn("280002551932", {x["candidate_id"] for x in a})          # Caiado (55) entra
        self.assertIn(("youtube", "AugustoCury"), {(x["plataforma"], x["perfil"]) for x in a})  # canal corrigido
        self.assertFalse(any(x["plataforma"] == "instagram" for x in a))      # série do Instagram bloqueada no Social Blade

    def test_explicito_e_soltos(self):
        self.assertEqual(pt.explicito("X - @Clarianabr"), ("x", "Clarianabr"))
        self.assertIsNone(pt.explicito("@clarianabarao"))                 # sem rede declarada: não é atribuído

    def test_por_perfil(self):
        self.assertEqual(pt.por_perfil(3.4, 13, 0.005, 0.001, 1, 50), 49)
        self.assertEqual(pt.por_perfil(0.9, 29, 5e-5, 0, 2, 600), 294)    # Instagram: duas leituras por perfil
        self.assertEqual(pt.por_perfil(1.0, 0, 0.1, 0, 1, 10), 0)

    def test_main_pago(self):
        itens = {"x": [{"id": "1", "createdAt": "2026-08-20T10:00:00.000Z", "fullText": "Oi  Brasil", "author": {"userName": "RONALDOCAIADO"}, "type": "tweet",
                        "likeCount": 5, "replyCount": 1, "retweetCount": 2, "viewCount": 100},
                       {"id": "2", "createdAt": "2026-08-20T10:00:00.000Z", "fullText": "repost", "author": {"userName": "outro"}, "type": "tweet"},
                       {"id": "3", "createdAt": "2026-06-01T10:00:00.000Z", "fullText": "antes", "author": {"userName": "RONALDOCAIADO"}, "type": "tweet"}]}
        cwd = os.getcwd()
        with tempfile.TemporaryDirectory() as t:
            for d in ("data/tse", "data/config"):
                (Path(t) / d).mkdir(parents=True)
            shutil.copy(RAIZ / "data/tse/redes_sociais_candidatos_2026.csv.gz", Path(t) / "data/tse/")
            shutil.copy(RAIZ / "data/config/primeiro_turno.json", Path(t) / "data/config/")
            shutil.copy(RAIZ / "data/elections.json", Path(t) / "data/")
            os.chdir(t)
            try:
                cfg = json.loads(Path("data/config/primeiro_turno.json").read_text(encoding="utf-8"))
                perfis = [p for p in pt.alvos(Path(".")) if p["rede"] == "x" and p["perfil"] == "RONALDOCAIADO"]
                man = pt.paga(Path("."), "x", cfg, perfis, True, "2026-10-18T12:00:00Z", set(), executar=lambda pl, cap: ({"id": "r"}, itens["x"]))
                rows = list(csv.DictReader(gzip.open("data/primeiro_turno/x/videos.csv.gz", "rt", encoding="utf-8"), delimiter=";"))
            finally:
                os.chdir(cwd)
        self.assertEqual(man["status"], "ok")
        self.assertEqual([r["video_id"] for r in rows], ["1"])           # repost de outro autor e post anterior a 20/07 ficam fora
        self.assertEqual((rows[0]["candidate_id"], rows[0]["legenda"], rows[0]["compartilhamentos"]), ("280002551932", "Oi Brasil", "2"))
        self.assertLessEqual(man["custo_usd"], 0.05)

    def test_resumo(self):
        cwd = os.getcwd()
        with tempfile.TemporaryDirectory() as t:
            for d in ("data/tse", "data/config", "data/seguidores", "data/youtube", "data/primeiro_turno/x"):
                (Path(t) / d).mkdir(parents=True)
            shutil.copy(RAIZ / "data/tse/redes_sociais_candidatos_2026.csv.gz", Path(t) / "data/tse/")
            shutil.copy(RAIZ / "data/config/trends.json", Path(t) / "data/config/")
            shutil.copy(RAIZ / "data/elections.json", Path(t) / "data/")
            with gzip.open(Path(t) / "data/primeiro_turno/x/videos.csv.gz", "wt", encoding="utf-8") as f:
                w = csv.DictWriter(f, ["candidate_id", "perfil", "video_id", "publicado_em", "visualizacoes", "curtidas", "comentarios", "compartilhamentos"], delimiter=";")
                w.writeheader()
                w.writerow({"candidate_id": "280002551932", "perfil": "RONALDOCAIADO", "video_id": "1", "publicado_em": "2026-08-20T10:00:00Z",
                            "visualizacoes": "100", "curtidas": "5", "comentarios": "1", "compartilhamentos": "2"})
            (Path(t) / "data/seguidores/latest.csv").write_text(
                "candidate_id;candidate_name;platform;url;followers;captured_at;source_url\n"
                "280002551933;GILBERTO KASSAB;Instagram;u;1000;2026-10-18;https://www.instagram.com/gilbertokassab_\n", encoding="utf-8")
            bpt.main([t])
            out = json.loads((Path(t) / "data/primeiro_turno/resumo.json").read_text(encoding="utf-8"))
        caiado = next(c for c in out["chapas"] if c["numero"] == "55")
        self.assertEqual(caiado["redes"]["x"]["por_fase"]["turno1"]["posts"], 1)
        self.assertEqual(caiado["redes"]["x"]["por_fase"]["turno1"]["interacoes"], 8)
        self.assertEqual(caiado["redes"]["instagram"]["seguidores"], 1000)   # vice soma na chapa
        self.assertEqual(out["chapas"][0]["numero"], "22")                    # ordem pelos votos do 1º turno


if __name__ == "__main__":
    unittest.main()


class TestWayback(unittest.TestCase):
    def test_extrair(self):
        import collect_wayback_seguidores as wb
        self.assertEqual(wb.extrair("tiktok", '{"followerCount":12345,"x":1}'), 12345)
        self.assertEqual(wb.extrair("youtube", '"subscriberCountText":{"simpleText":"1,2 mi de inscritos"}'), 1200000)
        self.assertEqual(wb.extrair("instagram", '<meta property="og:description" content="1M Followers, 10 Following, 300 Posts">'), 1000000)
        self.assertIsNone(wb.extrair("x", "<html>sem número</html>"))
        self.assertEqual(wb.endereco("tiktok", "https://www.tiktok.com/@LulaOficial?x=1"), "tiktok.com/@lulaoficial")

    def test_main(self):
        import collect_wayback_seguidores as wb
        with tempfile.TemporaryDirectory() as t:
            for d in ("data/tse", "data/config"):
                (Path(t) / d).mkdir(parents=True)
            shutil.copy(RAIZ / "data/tse/redes_sociais_candidatos_2026.csv.gz", Path(t) / "data/tse/")
            shutil.copy(RAIZ / "data/elections.json", Path(t) / "data/")
            get = lambda u: [["timestamp", "original"], ["20260315120000", "https://www.tiktok.com/@x"]] if "tiktok" in u else []  # noqa: E731
            wb.time.sleep = lambda s: None
            wb.main([t], get=get, pagina=lambda u: '"followerCount":777')
            with open(Path(t) / "data/seguidores/wayback_historico.csv", encoding="utf-8") as f:
                rows = list(csv.DictReader(f, delimiter=";"))
        self.assertTrue(rows)
        self.assertEqual((rows[0]["data"], rows[0]["seguidores"]), ("2026-03-15", "777"))
        self.assertTrue(rows[0]["captura"].startswith("https://web.archive.org/web/20260315120000/"))
