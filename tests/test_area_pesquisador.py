"""C19.374: área do pesquisador — corpus só com autor público, 020 anonimizado, RLS em todas as tabelas."""
import csv
import gzip
import json
import os
import re
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
import carregar_area_pesquisador as c  # noqa: E402

MIG = Path("supabase/migrations/20261110_area_pesquisador.sql")
MIG2 = Path("supabase/migrations/20261111_area_validacao.sql")
MIG3 = Path("supabase/migrations/20261111b_area_busca_rapida.sql")


class TestArea(unittest.TestCase):
    def _privado(self, d, cid, linhas):
        p = Path(d) / "casos" / cid
        p.mkdir(parents=True)
        with gzip.open(p / "itens.csv.gz", "wt", encoding="utf-8") as h:
            w = csv.DictWriter(h, fieldnames=["rede", "item_id", "conta", "seguidores", "publicado_em", "texto"], delimiter=";")
            w.writeheader()
            w.writerows(linhas)
        return Path(d)

    def test_autor_so_com_10_mil(self):
        with tempfile.TemporaryDirectory() as d:
            raiz = self._privado(d, "999", [
                {"rede": "x", "item_id": "1", "conta": "comum", "seguidores": "120", "publicado_em": "2026-10-01", "texto": "oi 🇧🇷"},
                {"rede": "x", "item_id": "2", "conta": "grande", "seguidores": "15000", "publicado_em": "2026-10-01", "texto": "oi"}])
            r = {x["item_id"]: x for x in c.linhas("999", raiz, {})}
            self.assertIsNone(r["1"]["autor"])
            self.assertEqual(r["2"]["autor"], "@grande")
            self.assertEqual(r["1"]["emojis"], ["🇧🇷"])
            self.assertNotIn("url", r["1"])

    def test_020_anonimizado(self):
        cfg = c.casos_cfg()["020"]
        rx = re.compile(cfg["anonimizar_publico_regex"], re.I)
        with tempfile.TemporaryDirectory() as d:
            raiz = self._privado(d, "020", [{"rede": "x", "item_id": "1", "conta": "a", "seguidores": "1", "publicado_em": "", "texto": "Matheus vendia bombons"}])
            r = list(c.linhas("020", raiz, cfg))[0]
            self.assertIsNone(rx.search(r["texto"]))

    def test_rls_em_todas_as_tabelas(self):
        for mig in (MIG, MIG2):
            s = mig.read_text(encoding="utf-8")
            tabelas = re.findall(r"create table if not exists public\.(\w+)", s)
            self.assertTrue(tabelas)
            for t in tabelas:
                self.assertIn(f"alter table public.{t} enable row level security", s, t)
            self.assertNotRegex(s, r"to anon")
        self.assertIn("revoke all on public.corpus, public.pesquisadores, public.acessos from anon", MIG.read_text(encoding="utf-8"))

    def test_busca_interna_checa_permissao_antes_de_ler(self):
        # C19.378: as funções que leem o corpus sem RLS (para usar o índice) ficam fora da API e recusam quem não é pesquisador
        s = MIG3.read_text(encoding="utf-8")
        fs = re.findall(r"create or replace function (\S+?)\((.*?)\$\$(.*?)\$\$", s, re.S)
        definer = [(n, corpo) for n, cab, corpo in fs if "security definer" in cab]
        self.assertEqual(sorted(n for n, _ in definer), ["odi_interno.busca_contagem", "odi_interno.busca_ids"])
        for n, corpo in definer:
            self.assertRegex(corpo.split("return query")[0], r"if not odi_interno\.eh_pesquisador\(\) then raise exception", n)
        self.assertNotRegex(s, r"to (anon|public)\b")
        self.assertNotIn("c.texto,", s.split("create or replace function public.textos")[0])  # as internas não devolvem texto

    def test_validacao_sem_privilegio_elevado_no_schema_exposto(self):
        # funções que o pesquisador chama (schema public) não rodam como dono; só a carga (service role) tem exceção
        s = MIG2.read_text(encoding="utf-8")
        elevadas = re.findall(r"create or replace function (public\.\w+)\([^$]*?security definer", s)
        self.assertEqual(elevadas, ["public.preparar_area"])
        self.assertIn("revoke execute on function public.preparar_area(int) from public, anon, authenticated", s)
        # a regra de leitura avalia a permissão uma vez por consulta (a forma por linha levava 7,5 s)
        self.assertIn("alter policy corpus_so_pesquisador on public.corpus using ((select odi_interno.eh_pesquisador()))", s)

    def test_livro_de_codigos_igual_ao_banco(self):
        livro = json.loads(Path("data/config/livro_codigos_validacao.json").read_text(encoding="utf-8"))
        s = MIG2.read_text(encoding="utf-8")
        d = {x["id"]: [o["id"] for o in x["opcoes"]] for x in livro["dimensoes"]}

        def lista(padrao):
            return re.findall(r"'(\w+)'", re.search(padrao, s).group(1))
        self.assertEqual(sorted(d["ofensivo"]), sorted(lista(r"ofensivo text check \(ofensivo in \(([^)]*)\)")))
        self.assertEqual(sorted(d["odio"]), sorted(lista(r"odio text check \(odio in \(([^)]*)\)")))
        self.assertEqual(sorted(d["odio_alvo"]), sorted(lista(r"odio_alvo text check \(odio_alvo in \(([^)]*)\)")))
        self.assertEqual(sorted(d["tom"]), sorted(lista(r"tom text check \(tom in \(([^)]*)\)")))
        self.assertEqual(sorted(d["emoji_funcao"]), sorted(lista(r"<> all \(array\[([^\]]*)\]")))
        dic = {c["id"]: [o["id"] for o in c["opcoes"]] for c in livro["dicionario"]["campos"] if c.get("opcoes")}
        for campo in ("tipo", "sentimento", "alinhamento"):
            self.assertEqual(sorted(dic[campo]), sorted(lista(campo + r" text check \(" + campo + r" in \(([^)]*)\)")), campo)
        self.assertEqual(sorted(d["emoji_funcao"]), sorted(lista(r"funcao text check \(funcao in \(([^)]*)\)")))
        self.assertIn("revisto", livro["estado"])  # v0 declarada como rascunho

    def test_sem_chave_no_codigo(self):
        for f in ["area-pesquisador.html", "assets/odi-concordancia.js", "supabase/functions/odi-area-config/index.ts", ".github/workflows/area-pesquisador.yml"]:
            t = Path(f).read_text(encoding="utf-8")
            self.assertNotRegex(t, r"eyJhbGciOi|sb_publishable_|sb_secret_", f)


if __name__ == "__main__":
    unittest.main()
