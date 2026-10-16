#!/usr/bin/env python3
"""Classificação Hierárquica Descendente (CHD) de Reinert — implementação em Python (numpy) para o caderno 11.

Entrada: data/corpus/youtube_candidatos_segmentos.csv (corpus_populismo.py)
Saída:   data/corpus/chd_reinert.json

Procedimento (Reinert, 1983/1990; o mesmo descrito no IRaMuTeQ e no pacote R rainette, Barnier & Privé):
  1. Matriz segmentos × formas ativas, binária (presença/ausência). Formas: palavras sem acento, sem
     palavras funcionais, com 3+ letras e presentes em MIN_FREQ+ segmentos.
  2. Começa com todos os segmentos numa classe. Enquanto houver menos de K classes, divide a MAIOR:
     a. análise de correspondência da sub-matriz; ordena os segmentos pelo 1º fator;
     b. testa todos os cortes nessa ordem e escolhe o de MAIOR qui-quadrado da tabela 2 × formas;
     c. troca segmentos de lado, um a um, enquanto isso aumentar o qui-quadrado.
  3. Cada classe final é descrita pelas formas e variáveis com qui-quadrado positivo e significativo
     (χ² ≥ 3,84; p < 0,05), e pelos segmentos mais característicos.

Diferenças em relação ao IRaMuTeQ (declaradas): sem lematização (o IRaMuTeQ usa dicionário de lemas do
português); classificação simples (o IRaMuTeQ por padrão faz a dupla e pode deixar segmentos não classificados).
Por isso o corpus também é exportado no formato do IRaMuTeQ, para conferência no programa de referência.
Os NOMES das classes são dados pelo pesquisador, lendo formas e segmentos (como em Montuori Fernandes, 2022).
"""
from __future__ import annotations

import csv
import datetime as dt
import json
import re
import sys
from collections import Counter
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import build_conteudo as bc  # noqa: E402
import plataformas as pl  # noqa: E402

K = 6
MIN_FREQ = 3
MIN_CLASSE = 10
MIN_CLASSE_PCT = 0.08  # classe mínima = 8% dos segmentos (ver 'sensibilidade' no JSON)
SENSIBILIDADE = (0.03, 0.05, 0.08)
CHI_CRIT = 3.84
STOP_EXTRA = set(bc.norm("""tudo todos esse essa isso aqui ali hoje agora sobre para pelo pela pelos pelas mais menos muito
muita como quando onde porque entao tambem ainda ja so voce voces nos eles elas ele ela seu sua seus suas nosso nossa
ser estar ter fazer vai vamos foi sao esta estao tem pode podem deve vez cada outro outra mesmo bem sim nao
""").split())


def tokens(texto: str) -> list[str]:
    return [t for t in bc.norm(texto).split()
            if len(t) >= 3 and not t.isdigit() and t not in bc.STOP and t not in STOP_EXTRA and not t.startswith("#")]


def matriz(segs: list[str], min_freq: int = MIN_FREQ):
    docs = [set(tokens(s)) for s in segs]
    df = Counter(t for d in docs for t in d)
    voc = sorted(t for t, n in df.items() if n >= min_freq)
    idx = {t: i for i, t in enumerate(voc)}
    X = np.zeros((len(docs), len(voc)), dtype=np.float64)
    for i, d in enumerate(docs):
        for t in d:
            j = idx.get(t)
            if j is not None:
                X[i, j] = 1.0
    return X, voc


def chi2_dois_grupos(a: np.ndarray, tot: np.ndarray) -> float:
    """Qui-quadrado da tabela 2 × formas: linha A = a, linha B = tot − a (só colunas com total > 0)."""
    m = tot > 0
    a, t = a[m], tot[m]
    b = t - a
    na, nb, n = a.sum(), b.sum(), t.sum()
    if na == 0 or nb == 0:
        return 0.0
    ea, eb = na * t / n, nb * t / n
    return float(((a - ea) ** 2 / ea).sum() + ((b - eb) ** 2 / eb).sum())


def primeiro_fator(X: np.ndarray) -> np.ndarray:
    """Coordenadas das linhas no 1º fator da análise de correspondência."""
    P = X / X.sum()
    r, c = P.sum(1), P.sum(0)
    keep = c > 0
    P, c = P[:, keep], c[keep]
    S = (P - np.outer(r, c)) / np.sqrt(np.outer(r, c))
    U, s, _ = np.linalg.svd(S, full_matrices=False)
    return U[:, 0] * s[0] / np.sqrt(r)


def dividir(X: np.ndarray, max_iter: int = 30, min_lado: int = 1) -> tuple[np.ndarray, float]:
    """Divide as linhas de X em dois grupos (máscara booleana do grupo A) maximizando o qui-quadrado."""
    ordem = np.argsort(primeiro_fator(X), kind="stable")
    Xo = X[ordem]
    tot = X.sum(0)
    cum = np.cumsum(Xo, axis=0)
    melhor, corte = -1.0, 1
    for j in range(max(1, min_lado), len(ordem) - max(1, min_lado) + 1):
        ch = chi2_dois_grupos(cum[j - 1], tot)
        if ch > melhor:
            melhor, corte = ch, j
    A = np.zeros(len(ordem), dtype=bool)
    A[ordem[:corte]] = True
    a = X[A].sum(0)
    for _ in range(max_iter):  # realocação: troca um segmento de lado se isso aumenta o χ²
        mudou = False
        for i in range(len(A)):
            novo_a = a - X[i] if A[i] else a + X[i]
            if (A.sum() - 1 if A[i] else (~A).sum() - 1) < max(1, min_lado):
                continue
            ch = chi2_dois_grupos(novo_a, tot)
            if ch > melhor + 1e-9:
                melhor, a = ch, novo_a
                A[i] = not A[i]
                mudou = True
        if not mudou:
            break
    return A, melhor


def chd(X: np.ndarray, k: int = K, min_classe: int = MIN_CLASSE):
    """Devolve (rótulo de classe por linha, árvore de divisões). Linhas sem forma ativa ficam com −1."""
    ativos = np.where(X.sum(1) > 0)[0]
    classes = [ativos]
    arvore = [{"id": 0, "n": int(len(ativos)), "filhos": None}]
    folhas = {0: ativos}
    prox = 1
    indivisiveis = set()
    while len(folhas) < k:
        candidatas = [c for c in folhas if c not in indivisiveis and len(folhas[c]) >= 2 * min_classe]
        if not candidatas:
            break
        cid = max(candidatas, key=lambda c: (len(folhas[c]), -c))
        linhas = folhas[cid]
        sub = X[linhas]
        sub = sub[:, sub.sum(0) > 0]
        A, ch = dividir(sub, min_lado=min_classe)
        ga, gb = linhas[A], linhas[~A]
        if min(len(ga), len(gb)) < min_classe:
            indivisiveis.add(cid)  # não divide: passa a vez para a próxima maior (como no rainette)
            continue
        del folhas[cid]
        folhas[prox], folhas[prox + 1] = ga, gb
        no = next(n for n in arvore if n["id"] == cid)
        no["filhos"], no["chi2"] = [prox, prox + 1], round(ch, 1)
        arvore += [{"id": prox, "n": int(len(ga)), "filhos": None}, {"id": prox + 1, "n": int(len(gb)), "filhos": None}]
        prox += 2
    rot = np.full(X.shape[0], -1)
    # numera as classes finais na ordem da árvore (da esquerda para a direita), como no dendrograma
    ordem_folhas = []

    def visita(i):
        no = next(n for n in arvore if n["id"] == i)
        if no["filhos"]:
            for f in no["filhos"]:
                visita(f)
        else:
            ordem_folhas.append(i)
    visita(0)
    mapa = {f: n + 1 for n, f in enumerate(ordem_folhas)}
    for f, linhas in folhas.items():
        rot[linhas] = mapa[f]
    for no in arvore:
        no["classe"] = mapa.get(no["id"])
    return rot, arvore


def chi2_assoc(dentro: np.ndarray, total: np.ndarray, n_dentro: int, n: int) -> np.ndarray:
    """χ² 2×2 (na classe/fora × com/sem a forma), com sinal: + se super-representada na classe."""
    a = dentro
    b = n_dentro - a
    c = total - a
    d = (n - n_dentro) - c
    num = n * (a * d - b * c) ** 2
    den = (a + b) * (c + d) * (a + c) * (b + d)
    with np.errstate(divide="ignore", invalid="ignore"):
        ch = np.where(den > 0, num / den, 0.0)
    esperado = (a + c) * n_dentro / n
    return np.where(a >= esperado, ch, -ch)


def main(argv=None) -> int:
    root, plat = pl.args(argv)
    linhas = list(csv.DictReader(open(pl.caminho(root, plat, "segmentos"), encoding="utf-8")))
    X, voc = matriz([l["texto"] for l in linhas])
    n_ativos = int((X.sum(1) > 0).sum())
    mc = max(MIN_CLASSE, int(MIN_CLASSE_PCT * n_ativos))
    # teste de sensibilidade: o mesmo corpus com outras classes mínimas (registrado para auditoria)
    sens = []
    for pct in SENSIBILIDADE:
        r, _ = chd(X, min_classe=max(MIN_CLASSE, int(pct * n_ativos)))
        ok = r > 0
        tot_s = X[ok].sum(0)
        resumo = []
        for k in sorted(set(r[ok].tolist())):
            m = r == k
            ch = chi2_assoc(X[m].sum(0), tot_s, int(m.sum()), int(ok.sum()))
            resumo.append({"classe": k, "pct": round(100 * m.sum() / ok.sum(), 1), "formas": [voc[j] for j in np.argsort(-ch)[:8]]})
        sens.append({"min_classe_pct": pct, "min_classe": max(MIN_CLASSE, int(pct * n_ativos)), "classes": resumo})
    rot, arvore = chd(X, min_classe=mc)
    cl = rot > 0
    n = int(cl.sum())
    Xc, rc = X[cl], rot[cl]
    tot = Xc.sum(0)
    cands = sorted({l["cand"] for l in linhas})
    cand_arr = np.array([l["cand"] for l in linhas])[cl]
    classes = []
    for k in sorted(set(rc.tolist())):
        m = rc == k
        nk = int(m.sum())
        ch = chi2_assoc(Xc[m].sum(0), tot, nk, n)
        top = np.argsort(-ch)[:25]
        formas = [[voc[j], round(float(ch[j]), 1), int(Xc[m][:, j].sum())] for j in top if ch[j] >= CHI_CRIT]
        var = {}
        for c in cands:
            em = (cand_arr == c)
            vch = chi2_assoc(np.array([float((em & m).sum())]), np.array([float(em.sum())]), nk, n)[0]
            var[c] = {"segmentos": int((em & m).sum()), "pct_da_classe": round(100 * (em & m).sum() / nk, 1),
                      "pct_do_candidato": round(100 * (em & m).sum() / max(1, em.sum()), 1), "chi2": round(float(vch), 1)}
        # segmentos característicos: soma do χ² positivo das formas presentes
        idx = np.where(cl)[0][m]
        peso = {j: ch[j] for j in range(len(voc)) if ch[j] > 0}
        score = [(sum(peso.get(j, 0) for j in np.nonzero(X[i])[0]), i) for i in idx]
        segs = [{"video_id": linhas[i]["video_id"], "cand": linhas[i]["cand"], "texto": linhas[i]["texto"][:300],
                 "score": round(float(s), 1)} for s, i in sorted(score, reverse=True)[:5]]
        classes.append({"classe": k, "segmentos": nk, "pct": round(100 * nk / n, 1), "formas": formas,
                        "candidatos": var, "segmentos_caracteristicos": segs, "nome": None})
    out = {"schema_version": 1, "gerado_em_utc": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
           "metodo": (f"CHD de Reinert (implementação própria em Python/numpy, classificação simples): {K} classes no máximo, "
                      f"formas com {MIN_FREQ}+ segmentos, classe mínima de {int(MIN_CLASSE_PCT*100)}% dos segmentos (teste de sensibilidade com 3%, 5% e 8% registrado), formas características com χ² ≥ {CHI_CRIT} (p < 0,05). "
                      "Sem lematização. Os nomes das classes devem ser dados pelo pesquisador. Conferir no IRaMuTeQ com o corpus exportado."),
           "parametros": {"k": K, "min_freq": MIN_FREQ, "min_classe": mc, "min_classe_pct": MIN_CLASSE_PCT, "chi_crit": CHI_CRIT},
           "sensibilidade": sens,
           "nota_sensibilidade": "Com classe mínima de 3% ou 5%, várias classes se formam por nomes próprios de convidados (ex.: Dani Marques, Jeffrey Chiquini), sem leitura temática; 8% foi adotado por isso. As três versões ficam registradas aqui.",
           "segmentos_total": len(linhas), "segmentos_classificados": n,
           "pct_classificados": round(100 * n / max(1, len(linhas)), 1), "formas_ativas": len(voc),
           "arvore": arvore, "classes": classes}
    out["plataforma"] = plat
    pl.caminho(root, plat, "chd").write_text(json.dumps(out, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(f"CHD [{plat}]: {len(linhas)} segmentos, {n} classificados ({out['pct_classificados']}%), {len(voc)} formas, {len(classes)} classes")
    for c in classes:
        print(f"  classe {c['classe']} ({c['pct']}%): " + ", ".join(f[0] for f in c["formas"][:10])
              + " | " + " ".join(f"{k}:{v['pct_da_classe']}% χ²{v['chi2']}" for k, v in c["candidatos"].items()))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
