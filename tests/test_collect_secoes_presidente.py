import io
import json
import os
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import collect_secoes_presidente as cs  # noqa: E402

CAB = "NR_TURNO;SG_UF;CD_MUNICIPIO;NM_MUNICIPIO;NR_ZONA;NR_SECAO;DS_CARGO;NR_VOTAVEL;NM_VOTAVEL;QT_VOTOS\n"


def zipar(d, linhas):
    zp = Path(d) / "v.zip"
    with zipfile.ZipFile(zp, "w") as z:
        z.writestr("votacao_secao_2026_BR.csv", (CAB + "".join(";".join(map(str, l)) + "\n" for l in linhas)).encode("latin-1"))
    return zp


class TestSecoes(unittest.TestCase):
    def test_vencedor_empate_zero_e_cem(self):
        L = []
        for sec, (a, b) in {"1": (10, 5), "2": (3, 3), "3": (0, 7), "4": (8, 0)}.items():
            L += [[2, "SP", "1", "X", "1", sec, "Presidente", "13", "LULA", a], [2, "SP", "1", "X", "1", sec, "Presidente", "22", "FLAVIO", b],
                  [2, "SP", "1", "X", "1", sec, "Presidente", "95", "Branco", 1], [1, "SP", "1", "X", "1", sec, "Presidente", "13", "LULA", 99]]
        with tempfile.TemporaryDirectory() as d:
            zp = zipar(d, L)
            cwd = os.getcwd()
            os.chdir(d)
            try:
                cs.main(["--turno", "2", "--arquivo", str(zp)])
                r = json.loads(Path("data/tse/secoes/presidente_2t_resumo.json").read_text(encoding="utf-8"))
            finally:
                os.chdir(cwd)
        c = {x["nome"]: x for x in r["candidatos"]}
        self.assertEqual(r["secoes"], 4)
        self.assertEqual(c["LULA"]["secoes_vencidas"], 2)
        self.assertEqual(c["FLAVIO"]["secoes_vencidas"], 1)
        self.assertEqual(r["empates"], 1)
        self.assertEqual(c["LULA"]["secoes_com_zero_votos"], 1)
        self.assertEqual(c["LULA"]["secoes_com_100pct_dos_validos"], 1)
        self.assertEqual(c["LULA"]["votos"], 21)
        self.assertEqual(r["brancos"], 4)

    def test_sem_o_turno_e_bloqueio(self):
        with tempfile.TemporaryDirectory() as d:
            zp = zipar(d, [[1, "SP", "1", "X", "1", "1", "Presidente", "13", "LULA", 5]])
            cwd = os.getcwd()
            os.chdir(d)
            try:
                cs.main(["--turno", "2", "--arquivo", str(zp)])
                r = json.loads(Path("data/tse/secoes/presidente_2t_resumo.json").read_text(encoding="utf-8"))
            finally:
                os.chdir(cwd)
        self.assertTrue(r["status"].startswith("⛔"))
