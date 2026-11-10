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
        s = MIG.read_text(encoding="utf-8")
        for t in re.findall(r"create table if not exists public\.(\w+)", s):
            self.assertIn(f"alter table public.{t} enable row level security", s, t)
        self.assertNotRegex(s, r"to anon")
        self.assertIn("revoke all on public.corpus, public.pesquisadores, public.acessos from anon", s)

    def test_sem_chave_no_codigo(self):
        for f in ["area-pesquisador.html", "supabase/functions/odi-area-config/index.ts", ".github/workflows/area-pesquisador.yml"]:
            t = Path(f).read_text(encoding="utf-8")
            self.assertNotRegex(t, r"eyJhbGciOi|sb_publishable_|sb_secret_", f)


if __name__ == "__main__":
    unittest.main()
