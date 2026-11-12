#!/usr/bin/env bash
# Roda os testes e, se falharem, publica cada falha como anotação do GitHub (legível sem acesso ao log completo).
# vários testes importam numpy e networkx (casos 011 e 012, desde 27/10/2026): sem eles, os workflows que não os instalavam
# falhavam no passo de testes e a coleta não rodava (Pardal, Trends, checagens, alienação...; percebido em 30/10/2026)
python -c "import numpy, networkx" 2>/dev/null || pip install -q networkx==3.6.1 numpy==2.3.4
# caso 019 (30/10/2026): identificação de língua dos comentários
python -c "import py3langid" 2>/dev/null || pip install -q py3langid==0.3.0
# emojis por caso e área do pesquisador (10/11/2026): sem o pacote emoji, os testes novos derrubaram 20 coletas em 11 e 12/11 (C19.379)
python -c "import emoji" 2>/dev/null || pip install -q emoji==2.16.0
out=$(python -m unittest discover -s tests 2>&1); rc=$?
echo "$out" | tail -n 3
if [ $rc -ne 0 ]; then
  echo "$out" | grep -E "^(ERROR|FAIL):|Error:|AssertionError" | head -n 15 | while IFS= read -r l; do echo "::error title=Testes::$(echo "$l" | cut -c1-300)"; done
fi
exit $rc
