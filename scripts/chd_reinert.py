#!/usr/bin/env python3
"""Classificação Hierárquica Descendente (CHD) de Reinert — implementação em Python (numpy) para o caderno 02.

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

Passo 3 de cada bipartição (desde 01/11/2026): as formas específicas de uma classe são retiradas da outra (Ratinaud & Marchand,
2012). Diferenças em relação ao IRaMuTeQ (declaradas): desde 01/11/2026 a lematização usa o mesmo dicionário do IRaMuTeQ
(lexique_pt.txt), mas a escolha de formas ativas é uma aproximação; classificação simples (o IRaMuTeQ por padrão faz a dupla e pode deixar segmentos não classificados).
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

# 01/11/2026: parâmetros alinhados ao padrão do IRaMuTeQ (Tutorial IRaMuTeQ em português, Camargo & Justo, 22/11/2021, enviado
# pelo responsável): 10 classes terminais na fase 1, frequência mínima de uma forma = 2, no máximo 3.000 formas analisadas.
K = 10
MIN_FREQ = 2
MAX_FORMAS = 3000
MIN_CLASSE = 10
MIN_CLASSE_PCT = 0.05  # 01/11/2026: regra única do Atlas (era 8% no corpus principal); 3%, 5% e 8% ficam na sensibilidade
SENSIBILIDADE = (0.03, 0.05, 0.08)
CHI_CRIT = 3.84
CC_TEST = 0.3  # rainette (Barnier & Privé): coeficiente de contingência para o passo 3 da bipartição
STOP_EXTRA = set(bc.norm("""tudo todos esse essa isso aqui ali hoje agora sobre para pelo pela pelos pelas mais menos muito
muita como quando onde porque entao tambem ainda ja so voce voces nos eles elas ele ela seu sua seus suas nosso nossa
ser estar ter fazer vai vamos foi sao esta estao tem pode podem deve vez cada outro outra mesmo bem sim nao
""").split())


# 01/11/2026: lematização com o dicionário de português do próprio IRaMuTeQ (data/config/lexique_pt.txt: forma, lema, classe),
# enviado pelo responsável da instalação dele, para que a conferência no IRaMuTeQ compare a mesma coisa. Formas ativas, como no
# padrão do IRaMuTeQ (aproximação, conferir nas propriedades do corpus): nomes, verbos, adjetivos, advérbios e formas não
# reconhecidas; auxiliares (ver_sup), artigos, preposições, pronomes e conjunções ficam de fora. Risadas (kkkk, hahaha, rsrs)
# viram uma forma só ("risada") aqui e no corpus exportado para o IRaMuTeQ (normalizar_risadas), para os dois verem o mesmo texto.
LEXICO_ARQ = Path(__file__).resolve().parents[1] / "data/config/lexique_pt.txt"
ATIVAS = {"nom", "ver", "adj", "nr"}  # tutorial (p. 23): padrão, com o advérbio passado de ativo para suplementar
RISADA = re.compile(r"\b(?:k{3,}\w*|(?:ha|he|hi|ah){2,}h?|(?:rs){2,}|(?:kkk+|ksks+|kakaka+)\w*)\b", re.I)
_LEX: dict | None = None


def lexico() -> dict:
    global _LEX
    if _LEX is None:
        _LEX = {}
        if LEXICO_ARQ.exists():
            for linha in LEXICO_ARQ.read_text(encoding="utf-8").splitlines():
                p = linha.split("\t")
                if len(p) >= 3:
                    _LEX.setdefault(p[0].strip(), (p[1].strip(), p[2].strip()))
    return _LEX


def lematizacao() -> dict:
    """O que a página e os JSON informam sobre a lematização."""
    lx = lexico()
    return {"dicionario": "lexique_pt.txt do IRaMuTeQ (instalação do responsável, 01/11/2026)", "formas_no_dicionario": len(lx),
            "formas_ativas": sorted(ATIVAS), "risadas": "kkkk, hahaha, rsrs… → 'risada'"} if lx else \
           {"dicionario": "⛔ data/config/lexique_pt.txt ausente: sem lematização"}


def normalizar_risadas(texto: str) -> str:
    return RISADA.sub(" risada ", texto or "")


def tokens(texto: str) -> list[str]:
    lx = lexico()
    t = re.sub(r"https?://\S+|[@#]\w+", " ", normalizar_risadas(bc.EMOJI_TAG.sub(" ", texto or ""))).lower()
    out = []
    for w in re.findall(r"[^\W\d_]+", t):
        lema, cl = lx.get(w, (w, "nr")) if lx else (w, "nr")
        if cl.strip() not in ATIVAS:
            continue
        n = bc.norm(lema).strip()
        if not n or n.isdigit() or " " in n:
            continue
        if lx:  # com o dicionário, quem decide é a classe gramatical, como no IRaMuTeQ (sem lista de palavras vazias própria)
            if len(n) >= 2:
                out.append(n)
        elif len(n) >= 3 and n not in bc.STOP and n not in STOP_EXTRA:
            out.append(n)
    return out


def matriz(segs: list[str], min_freq: int = MIN_FREQ):
    docs = [set(tokens(s)) for s in segs]
    df = Counter(t for d in docs for t in d)
    voc = sorted(t for t, n in sorted(df.items(), key=lambda x: (-x[1], x[0]))[:MAX_FORMAS] if n >= min_freq)
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


APROVEITAMENTO_MIN = 75.0  # % de segmentos classificados; Camargo & Justo (2013), citado em Amaral-Rosa (2019, Rev Esc Enferm USP 53:e03468)


def chd(X: np.ndarray, k: int = K, min_classe: int = MIN_CLASSE, max_divisoes: int | None = None, _estados: dict | None = None):
    """Devolve (rótulo de classe por linha, árvore de divisões). Linhas sem forma ativa ou em grupo eliminado ficam com −1.

    01/11/2026 (correção): o corte de cada divisão é o de maior χ², SEM piso de tamanho (antes o piso era imposto no corte e
    empurrava o corte extremo até o mínimo: várias classes saíam com exatamente o tamanho mínimo, efeito da regra e não do corpus).
    Agora, como no rainette (min_split_members) e no IRaMuTeQ (tamanho mínimo de classe): um grupo só é dividido se tiver 2× o
    mínimo; um grupo que sai da divisão com menos que o mínimo não vira classe (fica na árvore como "eliminado" e seus segmentos
    ficam não classificados). A divisão continua pela maior classe até haver k classes ou até max_divisoes (padrão 10k)."""
    ativos = np.where(X.sum(1) > 0)[0]
    arvore = [{"id": 0, "n": int(len(ativos)), "filhos": None}]
    folhas = {0: ativos}
    colunas = {0: np.arange(X.shape[1])}  # formas em jogo em cada grupo (passo 3 de Reinert, abaixo)
    prox = 1
    indivisiveis, eliminados = set(), set()
    divisoes, limite = 0, max_divisoes or 10 * k  # 01/11/2026: regra única, até 10 divisões por classe pedida
    while len([f for f in folhas if f not in eliminados]) < k and divisoes < limite:
        candidatas = [c for c in folhas if c not in indivisiveis and c not in eliminados and len(folhas[c]) >= 2 * min_classe]
        if not candidatas:
            break
        cid = max(candidatas, key=lambda c: (len(folhas[c]), -c))
        linhas = folhas[cid]
        cols = colunas[cid]
        sub = X[np.ix_(linhas, cols)]
        vivas = sub.sum(0) > 0
        cols, sub = cols[vivas], sub[:, vivas]
        com_forma = sub.sum(1) > 0  # segmento que ficou sem nenhuma forma em jogo (passo 3) não é classificável neste ramo
        linhas, sub = linhas[com_forma], sub[com_forma]
        if sub.shape[1] < 2 or len(linhas) < 2:
            indivisiveis.add(cid)
            continue
        try:
            A, ch = dividir(sub, min_lado=1)
        except np.linalg.LinAlgError:
            indivisiveis.add(cid)
            continue
        ga, gb = linhas[A], linhas[~A]
        if not len(ga) or not len(gb):
            indivisiveis.add(cid)
            continue
        divisoes += 1
        # passo 3 da bipartição de Reinert (Ratinaud & Marchand, 2012, §2.1): as formas específicas de uma classe são retiradas da
        # outra nas divisões seguintes. Critério de "específica" do rainette (cc_test): coeficiente de contingência
        # √(χ²/(χ²+n)) > 0,3 — com χ² ≥ 3,84 sobravam segmentos sem forma e o aproveitamento caía (teste de 02/11/2026)
        ca, cb = sub[A].sum(0), sub[~A].sum(0)
        ch_a = chi2_assoc(ca, ca + cb, int(A.sum()), len(A))
        cc = np.sign(ch_a) * np.sqrt(np.abs(ch_a) / (np.abs(ch_a) + len(A)))
        colunas[prox], colunas[prox + 1] = cols[cc > -CC_TEST], cols[cc < CC_TEST]
        del folhas[cid]
        folhas[prox], folhas[prox + 1] = ga, gb
        no = next(n for n in arvore if n["id"] == cid)
        no["filhos"], no["chi2"] = [prox, prox + 1], round(ch, 1)
        for i, g in ((prox, ga), (prox + 1, gb)):
            arvore.append({"id": i, "n": int(len(g)), "filhos": None})
            if len(g) < min_classe:
                eliminados.add(i)
                arvore[-1]["eliminado"] = True
        prox += 2
        if _estados is not None:  # estado da partição a cada nº de classes vivas (para escolher k pelo aproveitamento)
            vivas = {f: folhas[f] for f in folhas if f not in eliminados}
            _estados.setdefault(len(vivas), (vivas, len(arvore), set(eliminados)))
    rot = np.full(X.shape[0], -1)
    # numera as classes finais na ordem da árvore (da esquerda para a direita), como no dendrograma
    ordem_folhas = []

    def visita(i):
        no = next(n for n in arvore if n["id"] == i)
        if no["filhos"]:
            for f in no["filhos"]:
                visita(f)
        elif i not in eliminados:
            ordem_folhas.append(i)
    visita(0)
    mapa = {f: n + 1 for n, f in enumerate(ordem_folhas)}
    for f, linhas in folhas.items():
        if f in mapa:
            rot[linhas] = mapa[f]
    for no in arvore:
        no["classe"] = mapa.get(no["id"])
    return rot, arvore


def _rotular(X: np.ndarray, arvore: list[dict], folhas: dict, eliminados: set):
    by = {n["id"]: n for n in arvore}
    rot = np.full(X.shape[0], -1)
    ordem = []

    def visita(i):
        no = by[i]
        if no["filhos"]:
            for f in no["filhos"]:
                visita(f)
        elif i in folhas:
            ordem.append(i)
    visita(0)
    mapa = {f: n + 1 for n, f in enumerate(ordem)}
    for f, linhas in folhas.items():
        rot[linhas] = mapa[f]
    for no in arvore:
        no["classe"] = mapa.get(no["id"])
    return rot


def chd_iramuteq(X: np.ndarray, min_classe: int = MIN_CLASSE, k_max: int = K, k_min: int = 3, n_textos: int | None = None):
    """CHD com a regra do tutorial do IRaMuTeQ (Camargo & Justo, 2021, p. 31): começa com 10 classes terminais e, se a CHD não
    retiver 75% dos segmentos, muda o número de classes terminais e refaz. Regra fixa do Atlas, declarada antes de ver o resultado
    (01/11/2026): de 10 para baixo (10, 9, …, 3), a primeira partição com aproveitamento ≥ 75%; nenhuma → a de maior aproveitamento,
    marcada ⛔. Como as divisões são sempre as mesmas (a maior classe é dividida primeiro), as partições de 10 a 3 saem de uma só CHD.
    Devolve (rótulos, árvore, informação da escolha com todas as tentativas)."""
    n_textos = n_textos or X.shape[0]
    estados: dict = {}
    rot10, arv10 = chd(X, k=k_max, min_classe=min_classe, _estados=estados)
    tentativas, escolha = [], None
    for k in range(k_max, k_min - 1, -1):
        if k not in estados:
            continue
        folhas, n_nos, elim = estados[k]
        pct = round(100 * sum(len(v) for v in folhas.values()) / max(1, n_textos), 1)
        tentativas.append({"classes_terminais": k, "aproveitamento_pct": pct})
        if escolha is None and pct >= APROVEITAMENTO_MIN:
            escolha = k
    if escolha is None and tentativas:
        escolha = max(tentativas, key=lambda t: t["aproveitamento_pct"])["classes_terminais"]
    if escolha is None:  # nenhuma divisão possível
        return rot10, arv10, {"classes_terminais": None, "tentativas": [], "regra": chd_iramuteq.__doc__.split("Devolve")[0].strip()}
    folhas, n_nos, elim = estados[escolha]
    arvore = [dict(n) for n in arv10[:n_nos]]
    ids = {n["id"] for n in arvore}
    for n in arvore:
        if n.get("filhos") and not set(n["filhos"]) <= ids:
            n["filhos"] = None
            n.pop("chi2", None)
        n.pop("classe", None)
    rot = _rotular(X, arvore, folhas, elim)
    return rot, arvore, {"classes_terminais": escolha, "tentativas": tentativas,
                         "regra": " ".join(chd_iramuteq.__doc__.split("Devolve")[0].split())}


def _ari(a: np.ndarray, b: np.ndarray) -> float:
    """Índice de Rand ajustado (Hubert & Arabie, 1985) entre duas partições dos mesmos segmentos."""
    from math import comb
    _, ia = np.unique(a, return_inverse=True)
    _, ib = np.unique(b, return_inverse=True)
    t = np.zeros((ia.max() + 1, ib.max() + 1), dtype=np.int64)
    np.add.at(t, (ia, ib), 1)
    sc = sum(comb(int(v), 2) for v in t.ravel())
    sa = sum(comb(int(v), 2) for v in t.sum(1))
    sb = sum(comb(int(v), 2) for v in t.sum(0))
    n2 = comb(len(a), 2)
    esp = sa * sb / n2 if n2 else 0
    mx = (sa + sb) / 2
    return round((sc - esp) / (mx - esp), 3) if mx != esp else 1.0


def _cruzar(a: np.ndarray, b: np.ndarray) -> dict:
    """Tabela de contingência entre duas partições: χ², graus de liberdade, p, V de Cramér, resíduos padronizados > 1,96."""
    ka, kb = sorted(set(a.tolist())), sorted(set(b.tolist()))
    t = np.array([[int(((a == i) & (b == j)).sum()) for j in kb] for i in ka], dtype=float)
    n = t.sum()
    esp = np.outer(t.sum(1), t.sum(0)) / n
    with np.errstate(divide="ignore", invalid="ignore"):
        chi = float(np.nansum((t - esp) ** 2 / esp))
        res = (t - esp) / np.sqrt(esp)
    gl = (len(ka) - 1) * (len(kb) - 1)
    try:
        from scipy.stats import chi2 as _c
        p = float(_c.sf(chi, gl))
    except Exception:  # noqa: BLE001 — sem scipy: aproximação de Wilson-Hilferty
        import math
        z = ((chi / gl) ** (1 / 3) - (1 - 2 / (9 * gl))) / math.sqrt(2 / (9 * gl)) if gl else 0
        p = 0.5 * math.erfc(z / math.sqrt(2))
    v = (chi / (n * max(1, min(len(ka), len(kb)) - 1))) ** 0.5 if n else 0
    return {"segmentos": int(n), "chi2": round(chi, 1), "gl": gl, "p": float(f"{p:.3g}"), "v_cramer": round(float(v), 3),
            "celulas_acima_do_esperado": int((res > 1.96).sum()), "celulas": int(res.size),
            "tabela": t.astype(int).tolist(), "linhas": ka, "colunas": kb}


def estabilidade(X: np.ndarray, min_classe: int, rot_principal: np.ndarray, n_textos: int | None = None) -> dict:
    """Teste de estabilidade dos "mundos lexicais" (Reinert, 2008), no desenho de Ratinaud & Marchand (2012): a mesma CHD, com os
    mesmos parâmetros, sobre a metade mais frequente das formas ativas e, separadamente, sobre a metade menos frequente; as duas
    partições são cruzadas (tabela de contingência, χ², V de Cramér, índice de Rand ajustado) e cada uma é comparada com a partição
    principal. Partições dependentes (χ² significativo) indicam que as classes não dependem de um punhado de palavras."""
    ordem = np.argsort(-X.sum(0), kind="stable")
    meio = len(ordem) // 2
    out = {"metodo": " ".join(estabilidade.__doc__.split()), "formas_frequentes": int(meio), "formas_menos_frequentes": int(len(ordem) - meio)}
    rots = {}
    for nome, cols in (("frequentes", ordem[:meio]), ("menos_frequentes", ordem[meio:])):
        r, _, info = chd_iramuteq(X[:, cols], min_classe=min_classe, n_textos=n_textos or X.shape[0])
        rots[nome] = r
        out[nome] = {"classes": int(r.max()) if r.max() > 0 else 0, "aproveitamento_pct": round(100 * float((r > 0).sum()) / max(1, n_textos or X.shape[0]), 1),
                     "classes_terminais": info.get("classes_terminais")}
    ok = (rots["frequentes"] > 0) & (rots["menos_frequentes"] > 0)
    if ok.sum() >= 20 and len(set(rots["frequentes"][ok].tolist())) > 1 and len(set(rots["menos_frequentes"][ok].tolist())) > 1:
        out["frequentes_x_menos_frequentes"] = {**_cruzar(rots["frequentes"][ok], rots["menos_frequentes"][ok]),
                                                "rand_ajustado": _ari(rots["frequentes"][ok], rots["menos_frequentes"][ok])}
    for nome in rots:
        m = (rots[nome] > 0) & (rot_principal > 0)
        if m.sum() >= 20 and len(set(rots[nome][m].tolist())) > 1:
            out[f"principal_x_{nome}"] = {"segmentos": int(m.sum()), "rand_ajustado": _ari(rot_principal[m], rots[nome][m]),
                                         "v_cramer": _cruzar(rot_principal[m], rots[nome][m])["v_cramer"]}
    x = out.get("frequentes_x_menos_frequentes")
    if not x:
        out["leitura"] = "⛔ partições insuficientes para cruzar"
    else:
        v = x["v_cramer"]
        forca = "desprezível" if v < 0.1 else "fraca" if v < 0.3 else "moderada" if v < 0.5 else "forte"
        baixo = [f"{k.replace('_', ' ')} classifica só {out[k]['aproveitamento_pct']}%" for k in ("frequentes", "menos_frequentes")
                 if out[k]["aproveitamento_pct"] < APROVEITAMENTO_MIN]
        out["forca"] = forca
        out["leitura"] = ((f"dependentes (χ² = {x['chi2']}, gl = {x['gl']}, p {'< 0,001' if x['p'] < 0.001 else '= ' + str(x['p'])}), "
                           f"com associação {forca} (V de Cramér {x['v_cramer']}; Rand ajustado {x['rand_ajustado']})")
                          if x["p"] < 0.05 else f"independentes (p = {x['p']}): as classes dependem do vocabulário escolhido") + \
                         (". Teste limitado: " + "; ".join(baixo) + " dos segmentos (vocabulário esparso)" if baixo else "") + \
                         ". Faixas do V de Cramér (convenção usual): < 0,1 desprezível; 0,1–0,3 fraca; 0,3–0,5 moderada; ≥ 0,5 forte."
    return out


def aproveitamento(rot: np.ndarray, n_segmentos: int) -> dict:
    """Taxa de segmentos classificados e o teste do mínimo de 75% (Camargo & Justo, 2013)."""
    pct = round(100 * int((rot > 0).sum()) / max(1, n_segmentos), 1)
    return {"pct_classificados": pct, "minimo_pct": APROVEITAMENTO_MIN, "atinge_minimo": pct >= APROVEITAMENTO_MIN,
            "fonte_minimo": "Camargo & Justo (2013), tutorial do IRaMuTeQ; citado em Amaral-Rosa (2019), Rev Esc Enferm USP 53:e03468",
            "regra": "10 classes terminais (padrão do IRaMuTeQ), reduzidas uma a uma até o aproveitamento chegar a 75% (tutorial do IRaMuTeQ, p. 31); classe mínima de 5% dos segmentos ativos (mín. 10); grupo menor que o mínimo fica não classificado; formas ativas: nomes, verbos, adjetivos e não reconhecidas (lematizadas pelo dicionário do IRaMuTeQ); frequência mínima 2; até 3.000 formas",
            "conferencia_iramuteq": "⛔ pendente: validação do responsável no IRaMuTeQ"}


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
    rot, arvore, escolha_k = chd_iramuteq(X, min_classe=mc, n_textos=len(linhas))
    estab = estabilidade(X, mc, rot, len(linhas))
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
                      f"formas com {MIN_FREQ}+ segmentos, classe mínima de {int(MIN_CLASSE_PCT*100)}% dos segmentos (grupo menor que isso não vira classe e fica não classificado; teste de sensibilidade com 3%, 5% e 8% registrado), aproveitamento mínimo de {APROVEITAMENTO_MIN:.0f}% dos segmentos (Camargo & Justo, 2013), formas características com χ² ≥ {CHI_CRIT} (p < 0,05). "
                      "Sem lematização. Os nomes das classes devem ser dados pelo pesquisador. Conferir no IRaMuTeQ com o corpus exportado."),
           "lematizacao": lematizacao(), "escolha_classes": escolha_k, "estabilidade": estab, "parametros": {"k": K, "min_freq": MIN_FREQ, "min_classe": mc, "min_classe_pct": MIN_CLASSE_PCT, "chi_crit": CHI_CRIT},
           "sensibilidade": sens,
           "nota_sensibilidade": "Regra única do Atlas desde 01/11/2026: classe mínima de 5%, até 60 divisões, aproveitamento mínimo de 75%. Antes, com o corte forçado no mínimo, 8% tinha sido adotado aqui porque 3% e 5% formavam classes por nomes próprios; as três versões ficam registradas para comparação. Aguardando conferência no IRaMuTeQ.",
           "segmentos_total": len(linhas), "segmentos_classificados": n,
           "pct_classificados": round(100 * n / max(1, len(linhas)), 1), "formas_ativas": len(voc),
           "arvore": arvore, "classes": classes, "aproveitamento": aproveitamento(rot, len(linhas))}
    out["plataforma"] = plat
    # 02/11/2026: análise de similitude (ADS) do mesmo corpus, variável = candidato (scripts/similitude.py)
    try:
        import similitude as sim
        res = sim.ads(X, voc, [l["cand"] for l in linhas])
        if res:
            out["similitude"] = res
            sim.gexf(res, pl.caminho(root, plat, "chd").with_name(f"similitude_{plat}.gexf"))
    except Exception as e:  # noqa: BLE001 — sem networkx a CHD sai do mesmo jeito
        out["similitude"] = {"erro": f"{type(e).__name__}: {str(e)[:120]}"}
    pl.caminho(root, plat, "chd").write_text(json.dumps(out, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    # 01/11/2026: classe do Atlas por segmento, na ordem do arquivo de segmentos, para comparar com o IRaMuTeQ (candidatos: dado público)
    saida = pl.caminho(root, plat, "chd").with_name(f"{plat}_classes_atlas_por_segmento.csv")
    with open(saida, "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["linha_no_arquivo_de_segmentos", "video_id", "cand", "classe_atlas"])
        for i, (l, cl) in enumerate(zip(linhas, rot.tolist()), 1):
            w.writerow([i, l.get("video_id", ""), l.get("cand", ""), cl if cl > 0 else "não classificado"])
    print(f"CHD [{plat}]: {len(linhas)} segmentos, {n} classificados ({out['pct_classificados']}%), {len(voc)} formas, {len(classes)} classes")
    for c in classes:
        print(f"  classe {c['classe']} ({c['pct']}%): " + ", ".join(f[0] for f in c["formas"][:10])
              + " | " + " ".join(f"{k}:{v['pct_da_classe']}% χ²{v['chi2']}" for k, v in c["candidatos"].items()))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
