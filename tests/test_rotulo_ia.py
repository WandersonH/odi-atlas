import json, sys, tempfile, unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import collect_rotulo_ia as cr
import build_rotulo_ia as br


class TestRotuloIA(unittest.TestCase):
    def test_campos(self):
        it = {"id": "1", "desc": "x", "aigcLabelType": 1, "AIGCDescription": "", "stats": {"playCount": 3}, "music": {"isAiGenerated": False}}
        c = cr.campos_ia(it)
        self.assertEqual(c, {"aigcLabelType": 1, "AIGCDescription": "", "music.isAiGenerated": False})
        self.assertTrue(cr.tem_rotulo(c))
        self.assertFalse(cr.tem_rotulo({"AIGCDescription": "", "x.isAiGenerated": False}))
        self.assertFalse(cr.tem_rotulo({"ShowAIGC": True, "aigcLabelType": 0, "AIGCDescription": ""}))
        self.assertTrue(cr.tem_rotulo({"ShowAIGC": True, "moderationAigcLabelType": 1}))

    def test_agregados(self):
        y = {"videos": [{"id": "a", "origem": "canal da candidatura", "candidato": "Lula", "canal": "c", "titulo": "t", "publicado_em": "2026-10-01",
                         "campo_presente": True, "sintetico_declarado": True},
                        {"id": "b", "origem": "canal da candidatura", "candidato": "Lula", "canal": "c", "titulo": "t", "publicado_em": "2026-10-02",
                         "campo_presente": False, "sintetico_declarado": None},
                        {"id": "c", "origem": "vídeo sobre o debate", "candidato": None, "canal": "d", "titulo": "t", "publicado_em": "2026-10-19",
                         "campo_presente": True, "sintetico_declarado": False}]}
        r = br.youtube(y)
        self.assertEqual(r["por_candidato"]["Lula"], {"videos": 2, "campo_presente": 1, "declarados": 1, "pct": 50.0})
        self.assertEqual(r["debate"], {"videos": 1, "declarados": 0})
        self.assertEqual([v["id"] for v in r["lista"]], ["a"])
        with tempfile.TemporaryDirectory() as t:
            p = Path(t) / "data/checagens"
            p.mkdir(parents=True)
            (p / "checagens.json").write_text(json.dumps({"itens": [
                {"afirmacao": "Vídeo de Flávio foi gerado por IA", "titulo": "", "candidatos": ["Flávio Bolsonaro"], "agencia": "A", "data_checagem": "2026-10-16"},
                {"afirmacao": "Lula disse que ia votar", "titulo": "", "candidatos": ["Lula"], "agencia": "B", "data_checagem": "2026-10-10"}]}), encoding="utf-8")
            k = br.checagens(Path(t))
        self.assertEqual((k["sobre_ia"], k["total_base"], k["citam_candidato"]), (1, 2, {"Lula": 0, "Flávio Bolsonaro": 1}))


if __name__ == "__main__":
    unittest.main()
