import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import importar_transcricao_pdf as itp  # noqa: E402


class TestFalas(unittest.TestCase):
    def test_rotulos_blocos_e_quebra_de_pagina(self):
        linhas = ["CÉSAR TRALLI: Bem-vindos.", "FLÁVIO BOLSONARO: Boa noite", "a todos.", "[INTERVALO]",
                  "CÉSAR TRALLI: Estamos de volta ao vivo.", "LULA: Eu vou usar", "o tempo.",
                  "LUIZ INÁCIO LULA DA SILVA: Obrigado."]
        f = itp.falas(linhas)
        self.assertEqual([x["orador"] for x in f], ["mediacao", "flavio", "mediacao", "lula", "lula"])
        self.assertEqual([x["bloco"] for x in f], [1, 1, 2, 2, 2])
        self.assertEqual(f[1]["texto"], "Boa noite a todos.")
        self.assertEqual((f[1]["ini"], f[1]["fim"]), (1, 5))

    def test_lixo_de_pagina(self):
        for l in ("31", "Poder360 – www.poder360.com.br", "[transcrição – debate entre Lula e Flávio na Globo – 23.out.2026]"):
            self.assertTrue(itp.RX_LIXO.match(l))


if __name__ == "__main__":
    unittest.main()
