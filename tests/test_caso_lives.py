"""C19.380: caso 039 (lives de Lula com Janones) — só contagens no público, universo ao lado da amostra, ⛔ quando falta leitura."""
import json
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
import caso_lives as c  # noqa: E402


def video(i, data, vis, com):
    return {"video_id": i, "canal": "Lula", "titulo": "t " + i, "publicado_em": data, "duracao": "PT1H", "visualizacoes": str(vis), "curtidas": "1", "comentarios": str(com)}


def linha(v, autor, quando, cand=c.LULA, pai=""):
    return {"video_id": v, "autor_canal": autor, "publicado_em": quando, "candidate_id": cand, "parent_id": pai, "coletado_em": "2026-11-01T00:00:00Z"}


class TestCasoLives(unittest.TestCase):
    def setUp(self):
        self.conteudo = {"candidatos": {c.LULA: {"videos": [video("L1", "2026-10-22T00:00:00Z", 900, 50), video("L2", "2026-11-06T00:00:00Z", 500, 40),
                                                             video("a", "2026-08-01T00:00:00Z", 100, 4), video("b", "2026-09-01T00:00:00Z", 300, 60)]}}}

    def test_posicao_e_mediana_no_canal(self):
        lives, canal = c.canal_publico(self.conteudo, ["L1", "L2", "X9"])
        self.assertEqual((lives[0]["posicao_visualizacoes"], lives[0]["posicao_comentarios"]), (1, 2))
        self.assertEqual(canal["mediana_visualizacoes_demais"], 200)
        self.assertEqual(canal["soma_comentarios_lives"], 90)
        self.assertFalse(lives[2]["no_canal"])
        self.assertIn("⛔", lives[2]["situacao"])

    def test_publico_anterior_so_conta_antes_da_live(self):
        lives, _ = c.canal_publico(self.conteudo, ["L1", "L2"])
        linhas = {"L1": [linha("L1", "u1", "2026-10-22T01:00:00Z"), linha("L1", "u2", "2026-10-22T01:00:00Z"), linha("L1", "u3", "2026-10-22T02:00:00Z"),
                         linha("L1", "u1", "2026-10-22T03:00:00Z", pai="x")]}
        primeiro = {c.LULA: {"u1": "2026-09-01T00:00:00Z", "u2": "2026-10-30T00:00:00Z"}, c.FLAVIO: {"u1": "2026-09-02T00:00:00Z"}}
        r = c.analisar(lives, linhas, primeiro)
        a = lives[0]
        self.assertEqual((a["comentarios_lidos"], a["autores"], a["respostas_lidas"]), (4, 3, 1))
        self.assertEqual(a["publico"], {"lula": 0, "ambos": 1, "flavio": 0, "nenhum": 2})  # u2 comentou em Lula só DEPOIS da live
        self.assertEqual(a["pct_lido"], 8.0)
        self.assertIsNone(lives[1]["pct_lido"])
        self.assertIn("⛔", lives[1]["situacao"])  # live sem leitura nunca aparece como zero
        self.assertEqual(r["retorno"], [])

    def test_retorno_entre_lives(self):
        lives, _ = c.canal_publico(self.conteudo, ["L1", "L2"])
        linhas = {"L1": [linha("L1", "u1", "2026-10-22T01:00:00Z"), linha("L1", "u2", "2026-10-22T01:00:00Z")], "L2": [linha("L2", "u2", "2026-11-06T01:00:00Z")]}
        r = c.analisar(lives, linhas, {c.LULA: {}, c.FLAVIO: {}})
        self.assertEqual((r["retorno"][0]["em_comum"], r["retorno"][0]["pct_de_a"], r["retorno"][0]["pct_de_b"]), (1, 50.0, 100.0))
        self.assertEqual(r["autores_por_numero_de_lives"], {"1": 1, "2": 1})

    def test_publicado_sem_texto_nem_autor_e_com_universo(self):
        p = "data/casos/039/lives.json"
        if not os.path.exists(p):
            self.skipTest("caso ainda não gerado")
        s = open(p, encoding="utf-8").read()
        for proibido in ('"texto"', '"autor_nome"', '"autor_canal"', '"comment_id"'):
            self.assertNotIn(proibido, s)
        d = json.loads(s)
        u = d["universo"][0]
        self.assertEqual(u["conjunto"], "Comentários das lives")
        self.assertTrue(u["fonte_universo"] and u["criterio"])
        for x in d["lives"]:
            if not x.get("comentarios_lidos"):
                self.assertIn("⛔", x.get("situacao", ""))
        self.assertEqual(c.cfg_caso()["videos_youtube"], [x["id"] for x in d["lives"]])


class TestRetransmissoes(unittest.TestCase):
    """C19.381: retransmissões em outros canais — filtro de título, tipo e canal pequeno sem título nem link."""

    def setUp(self):
        import caso_lives_retransmissoes as r
        self.r = r
        self.orig = {"inicio": "2026-11-21T13:00:00Z", "segundos": 5400}

    def test_filtro_de_titulo(self):
        self.assertTrue(self.r.titulo_serve("🔴 LULA & JANONES: Exército do Lula"))
        self.assertTrue(self.r.titulo_serve("Lula fala ao exercito"))
        self.assertFalse(self.r.titulo_serve("Lula no podcast Flow"))
        self.assertFalse(self.r.titulo_serve("Janones comenta a semana"))

    def test_tipos(self):
        c = self.r.classificar
        self.assertEqual(c({"inicio_ao_vivo": "2026-11-21T12:50:00Z", "segundos": 5000}, self.orig), "ao vivo simultânea")
        self.assertEqual(c({"inicio_ao_vivo": "2026-11-21T20:00:00Z", "segundos": 5000}, self.orig), "transmissão ao vivo em outro horário")
        self.assertEqual(c({"inicio_ao_vivo": "2026-11-21T13:00:00Z", "segundos": 600}, self.orig), "transmissão ao vivo em outro horário")
        self.assertEqual(c({"inicio_ao_vivo": None, "segundos": 5400}, self.orig), "outro vídeo sobre a live")

    def test_cada_video_em_uma_live_so_e_dentro_da_janela(self):
        ini = {"A": "2026-11-05T22:00:00Z", "B": "2026-11-12T13:00:00Z"}
        longo = {"inicio_ao_vivo": "2026-11-05T21:00:00Z"}
        self.assertEqual(self.r.mais_proxima(longo, ini), "A")
        self.assertFalse(self.r.na_janela(longo, {"inicio": ini["B"]}))
        self.assertTrue(self.r.na_janela(longo, {"inicio": ini["A"]}))
        self.assertFalse(self.r.na_janela({"publicado_em": "2026-11-09T00:00:00Z"}, {"inicio": ini["A"]}))  # mais de 72 h depois

    def test_canal_pequeno_vira_codigo(self):
        v = {"id": "abc", "titulo": "Lula e Janones", "canal": "Canal do Zé", "canal_id": "UCx", "tipo": "outro vídeo sobre a live", "visualizacoes": 10}
        for insc in (None, 0, 9_999):
            s = json.dumps(self.r.publicar({**v, "inscritos_canal": insc}, 7), ensure_ascii=False)
            self.assertIn("canal_007", s)
            for proibido in ("abc", "Canal do Zé", "UCx", "Lula e Janones", "youtube.com"):
                self.assertNotIn(proibido, s)
        g = self.r.publicar({**v, "inscritos_canal": 10_000}, 7)
        self.assertEqual((g["canal"], g["url"]), ("Canal do Zé", "https://www.youtube.com/watch?v=abc"))

    def test_publicado_sem_canal_pequeno_identificado(self):
        p = "data/casos/039/retransmissoes.json"
        if not os.path.exists(p):
            self.skipTest("retransmissões ainda não coletadas")
        d = json.load(open(p, encoding="utf-8"))
        self.assertIn("⛔", d["universo"][0]["fonte_universo"])  # a busca não informa o universo
        for s in d["lives"]:
            for v in s.get("videos", []):
                if not v["identificado"]:
                    self.assertRegex(v["canal"], r"^canal_\d{3}$")
                    self.assertFalse({"id", "url", "titulo"} & set(v))
                else:
                    self.assertGreaterEqual(v["inscritos_canal"], 10_000)


if __name__ == "__main__":
    unittest.main()
