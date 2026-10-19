import csv, gzip, json, os, shutil, sys, tempfile, unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import collect_casos as cc
import build_casos as bk

RAIZ = Path(__file__).resolve().parents[1]


def item_x(i, conta, seg, quando, texto="#brasilinteiro oi", views=10):
    return {"id": str(i), "createdAt": quando, "fullText": texto, "author": {"userName": conta, "followers": seg}, "viewCount": views, "likeCount": 1}


class TestCasos(unittest.TestCase):
    def test_pedidos_e_norm(self):
        cfg = json.loads((RAIZ / "data/config/casos.json").read_text(encoding="utf-8"))
        caso = cfg["casos"][0]
        self.assertEqual([t for t, _, _ in cc.pedidos("x", caso, 5)], ["#brasilinteiro", "#verdeeamarelo"])   # duas hashtags (correção do usuário, 18/10)
        self.assertEqual(cc.pedidos("instagram", caso, 5)[0][2]["hashtags"], ["brasilinteiro"])
        self.assertEqual(cc.pedidos("tiktok", caso, 5)[0][1], "novi~multiple-tiktok-hashtag-scraper")
        r = cc.norm("tiktok", {"id": "7", "desc": "oi #brasilinteiro", "createTime": 1760670000, "author": {"uniqueId": "fulana"},
                               "authorStats": {"followerCount": 20000}, "stats": {"playCount": 100}}, "#brasilinteiro", "agora")
        self.assertEqual((r["conta"], r["seguidores"], r["visualizacoes"], r["url"]), ("fulana", 20000, 100, "https://www.tiktok.com/@fulana/video/7"))
        r = cc.norm("x", item_x(1, "fulano", 50, "2026-10-17T03:00:00.000Z"), "#brasilinteiro", "agora")
        self.assertEqual((r["item_id"], r["conta"], r["seguidores"], r["publicado_em"]), ("1", "fulano", 50, "2026-10-17T03:00:00Z"))
        self.assertIsNone(cc.norm("x", {"noResults": True}, "t", "a"))
        self.assertTrue(cc.iso("1760670000000").startswith("2025-10-17"))   # epoch em milissegundos

    def test_coleta_e_agregados(self):
        itens = [item_x(1, "pequeno", 50, "2026-10-17T03:10:00.000Z"),          # marco zero: conta pequena → código
                 item_x(2, "grande", 50000, "2026-10-17T04:00:00.000Z", "#brasilinteiro #lula força", 1000),
                 item_x(3, "LulaOficial", 9, "2026-10-17T04:30:00.000Z", "#brasilinteiro", 500),
                 item_x(4, "velho", 10, "2026-09-01T00:00:00.000Z")]           # antes da janela: fora
        cwd = os.getcwd()
        with tempfile.TemporaryDirectory() as t:
            for d in ("data/tse", "data/config"):
                (Path(t) / d).mkdir(parents=True)
            for f in ("data/tse/redes_sociais_candidatos_2026.csv.gz", "data/config/casos.json", "data/elections.json"):
                shutil.copy(RAIZ / f, Path(t) / f)
            os.chdir(t)
            os.environ["ODI_INTERNO_DIR"] = str(Path(t) / "interno")
            try:
                rc = cc.main(["--rede", "x"], executar=lambda ator, pl, cap: ({"id": "r"}, itens if "brasilinteiro" in pl["searchTerms"][0] else []))
                self.assertEqual(rc, 0)
                bk.main(["."])
                caso = json.loads(Path("data/casos/001/caso.json").read_text(encoding="utf-8"))
                indice = json.loads(Path("data/casos/indice.json").read_text(encoding="utf-8"))
                man = json.loads(Path("data/casos/001/manifesto_latest.json").read_text(encoding="utf-8"))
                gexf = Path("data/casos/001/rede.gexf").read_text(encoding="utf-8")
            finally:
                os.environ.pop("ODI_INTERNO_DIR", None)
                os.chdir(cwd)
        self.assertEqual(caso["publicacoes"], 3)
        mz = caso["marco_zero"]["geral"]
        self.assertFalse(mz["publico"])
        self.assertTrue(mz["conta"].startswith("perfil pequeno C"))
        self.assertIsNone(mz["url"])                                             # conta pequena: sem link
        self.assertEqual(mz["hora_brt"], "2026-10-17T00:00")                     # 03h10 UTC = 00h BRT
        self.assertEqual(caso["galeria"][0]["conta"], "@grande")
        self.assertIn("perfil de Lula", next(g["conta"] for g in caso["galeria"] if "LulaOficial" in g["conta"]))  # perfil declarado ao TSE
        self.assertNotIn("pequeno\"", gexf)
        self.assertNotIn("custo", json.dumps(caso))                              # custo da coleta nunca vai para a página
        self.assertEqual([c["estado"] for c in indice["casos"] if c["id"] in ("002", "004")], ["aguardando confirmação de datas e termos"] * 2)
        self.assertEqual(man["redes"][0]["itens_pedidos_por_termo"], 6000)       # teto do X (2,40) cabe o máximo por termo


if __name__ == "__main__":
    unittest.main()


class TestComplemento(unittest.TestCase):
    def test_so_complemento(self):
        caso = {"desde": "2026-10-16", "hashtags": ["a"], "_so_complemento": True, "complementos_x": [{"termo": "#a", "busca": "#a until:2026-10-17"}]}
        p = cc.pedidos("x", caso, 7)
        self.assertEqual(len(p), 1)
        self.assertEqual(p[0][2]["searchTerms"], ["#a until:2026-10-17"])
        self.assertEqual(cc.pedidos("instagram", {**caso, "perfis_instagram": []}, 7)[0][0], "#a")
