"""C19.377: alfa de Krippendorff (nominal) da área do pesquisador confere com o exemplo clássico (0,743)."""
import json
import shutil
import subprocess
import unittest

JS = r"""
const {alfaNominal, porDimensao} = require('./assets/odi-concordancia.js');
const A=[1,2,3,3,2,1,4,1,2,null,null,null],B=[1,2,3,3,2,2,4,1,2,5,null,3],C=[null,3,3,3,2,3,4,2,2,5,1,null],D=[1,2,3,3,2,4,4,1,2,5,1,null];
const itens=A.map((_,i)=>[A[i],B[i],C[i],D[i]].filter(v=>v!=null).map(String));
console.log(JSON.stringify({classico: alfaNominal(itens), igual: alfaNominal([['a','a'],['b','b']]), oposto: alfaNominal([['a','b'],['b','a']]),
  um: alfaNominal([['a']]), mesma: alfaNominal([['a','a'],['a','a']]),
  dim: porDimensao([{dimensao:'tom',item:'1',pesquisador:1,valor:'x'},{dimensao:'tom',item:'1',pesquisador:2,valor:'x'},{dimensao:'tom',item:'2',pesquisador:1,valor:'y'},{dimensao:'tom',item:'2',pesquisador:2,valor:'y'}])}));
"""


@unittest.skipUnless(shutil.which("node"), "node não instalado")
class TestConcordancia(unittest.TestCase):
    def test_alfa(self):
        r = json.loads(subprocess.run(["node", "-e", JS], capture_output=True, text=True, check=True).stdout)
        # Krippendorff: 4 observadores, 12 unidades (uma com um só valor, fora da conta), alfa nominal = 0,743
        self.assertAlmostEqual(r["classico"]["alfa"], 0.743, places=3)
        self.assertEqual(r["classico"]["itens"], 11)
        self.assertEqual(r["igual"]["alfa"], 1)
        self.assertLess(r["oposto"]["alfa"], 0)
        self.assertIsNone(r["um"]["alfa"])
        self.assertIsNone(r["mesma"]["alfa"])       # uma só categoria: alfa não se define
        self.assertTrue(r["mesma"]["sem_variacao"])
        self.assertEqual(r["dim"]["tom"]["pesquisadores"], 2)


if __name__ == "__main__":
    unittest.main()
