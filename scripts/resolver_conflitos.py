"""Resolve conflitos do `git pull --rebase` entre coletas que gravam os mesmos arquivos de data/ ao mesmo tempo.

Chamado por commit_push.sh quando o rebase para em conflito. Durante o rebase, o estágio 2 é o que já está no
GitHub (outra coleta) e o estágio 3 é o commit desta coleta.
- Tabelas de seguidores (colunas candidate_id, platform, url, captured_at): junta as duas versões, uma linha por
  (candidato, rede, endereço), ficando com a captura mais recente (empate: a desta coleta). Nenhuma coleta apaga a outra.
- Demais arquivos (derivados, como variacao.json): fica a versão desta coleta; a próxima execução recalcula.
Sai com 0 se resolveu tudo.
"""
from __future__ import annotations

import csv
import io
import subprocess
import sys

CHAVE = ("candidate_id", "platform", "url")


def git(*a: str, entrada: str | None = None) -> str:
    return subprocess.run(["git", *a], check=True, capture_output=True, text=True, input=entrada).stdout


def unir_csv(base: str, nova: str) -> str | None:
    def ler(t):
        r = csv.DictReader(io.StringIO(t), delimiter=";")
        return r.fieldnames or [], list(r)
    cb, lb = ler(base)
    cn, ln = ler(nova)
    if not all(c in cn for c in CHAVE + ("captured_at",)) or cb != cn:
        return None
    por = {}
    for origem, linhas in ((0, lb), (1, ln)):
        for x in linhas:
            k = tuple(x[c] for c in CHAVE)
            a = por.get(k)
            if a is None or (x["captured_at"], origem) >= (a[0]["captured_at"], a[1]):
                por[k] = (x, origem)
    ordem = {tuple(x[c] for c in CHAVE): i for i, x in enumerate(ln + lb)}
    s = io.StringIO()
    w = csv.DictWriter(s, fieldnames=cn, delimiter=";", lineterminator="\n")
    w.writeheader()
    w.writerows(x for x, _ in sorted(por.values(), key=lambda v: ordem[tuple(v[0][c] for c in CHAVE)]))
    return s.getvalue()


def main() -> int:
    arquivos = [p for p in git("diff", "--name-only", "--diff-filter=U").splitlines() if p]
    if not arquivos:
        return 1
    for p in arquivos:
        feito = None
        if p.endswith(".csv"):
            try:
                feito = unir_csv(git("show", f":2:{p}"), git("show", f":3:{p}"))
            except subprocess.CalledProcessError:
                feito = None
        if feito is not None:
            open(p, "w", encoding="utf-8").write(feito)
            print(f"conflito resolvido (união por candidato/rede/endereço): {p}")
        else:
            git("checkout", "--theirs", "--", p)
            print(f"conflito resolvido (versão desta coleta): {p}")
        git("add", "--", p)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
