#!/usr/bin/env bash
# Commita data/ e envia, tolerando pushes concorrentes. Se falhar, publica a causa
# como anotação do GitHub (legível pela API, mesmo sem acesso ao log completo).
set -u
msg="$1"
git config user.name "odi-atlas-coletor"
git config user.email "41898282+github-actions[bot]@users.noreply.github.com"
git add data/
if git diff --cached --quiet; then echo "nada novo"; exit 0; fi
git commit -q -m "$msg"
for i in 1 2 3 4; do
  out=$(git pull --rebase --autostash origin "${GITHUB_REF_NAME:-main}" 2>&1); rc=$?
  # conflito com outra coleta que gravou os mesmos arquivos: resolve (união das tabelas de seguidores) e continua
  n=0
  while [ $rc -ne 0 ] && [ -d .git/rebase-merge -o -d .git/rebase-apply ] && [ $n -lt 10 ]; do
    if python3 scripts/resolver_conflitos.py; then
      out="$out
$(GIT_EDITOR=true git rebase --continue 2>&1)"; rc=$?
    else
      break
    fi
    n=$((n + 1))
  done
  if [ $rc -eq 0 ] && out="$out
$(git push 2>&1)"; then
    echo "$out"; echo "enviado na tentativa $i"; exit 0
  fi
  echo "$out"
  git rebase --abort 2>/dev/null || true
  sleep $((i * 5))
done
echo "::error title=commit_push falhou::$(echo "$out" | tail -n 6 | tr '\n' ' ' | cut -c1-900)"
echo "::error title=git status::$(git status --short | head -n 15 | tr '\n' ' ' | cut -c1-900)"
exit 1
