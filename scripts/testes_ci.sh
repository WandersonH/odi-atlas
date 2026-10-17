#!/usr/bin/env bash
# Roda os testes e, se falharem, publica cada falha como anotação do GitHub (legível sem acesso ao log completo).
out=$(python -m unittest discover -s tests 2>&1); rc=$?
echo "$out" | tail -n 3
if [ $rc -ne 0 ]; then
  echo "$out" | grep -E "^(ERROR|FAIL):|Error:|AssertionError" | head -n 15 | while IFS= read -r l; do echo "::error title=Testes::$(echo "$l" | cut -c1-300)"; done
fi
exit $rc
