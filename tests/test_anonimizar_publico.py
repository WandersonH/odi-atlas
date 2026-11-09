"""C19.371: nenhum arquivo público de caso protegido (020, criança) pode trazer o que identifica a criança."""
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
import anonimizar_publico as a  # noqa: E402


class TestAnonimizarPublico(unittest.TestCase):
    def test_arquivos_publicos_sem_ocorrencia(self):
        casos = a.casos_protegidos()
        self.assertIn("020", casos)
        for cid, rx in casos.items():
            for f in a.arquivos(cid):
                with open(f, encoding="utf-8", errors="ignore") as h:
                    self.assertIsNone(rx.search(h.read()), f)

    def test_gexf_nao_funde_nos(self):
        import re
        rx = re.compile(r"[#@]?[\w.]*(?:m+a+t+h?e+u+s+)[\w.]*", re.I)
        g = ('<?xml version="1.0" encoding="UTF-8"?><gexf xmlns="http://gexf.net/1.3" version="1.3"><graph><nodes>'
             '<node id="matheus" label="matheus"/><node id="mateus" label="mateus"/><node id="lula" label="lula"/></nodes>'
             '<edges><edge id="0" source="matheus" target="lula"/><edge id="1" source="mateus" target="lula"/></edges></graph></gexf>')
        with tempfile.NamedTemporaryFile("w", suffix=".gexf", delete=False, encoding="utf-8") as t:
            t.write(g)
        out = a.gexf(t.name, rx)
        os.unlink(t.name)
        self.assertNotRegex(out, rx)
        self.assertIn('id="crianca_1"', out)
        self.assertIn('id="crianca_2"', out)
        self.assertIn('source="crianca_2"', out)


if __name__ == "__main__":
    unittest.main()
