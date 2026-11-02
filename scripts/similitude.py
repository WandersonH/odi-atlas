#!/usr/bin/env python3
"""Análise de similitude (ADS) no desenho do IRaMuTeQ (Marchand & Ratinaud, 2012; Flament & Rouquette, 2003).

Pedido do responsável (02/11/2026, 00h21: "acho importante"), a partir do material sobre o IRaMuTeQ enviado em 01/11.
- Matriz: os mesmos segmentos e formas ativas da CHD (chd_reinert.matriz: lematizadas pelo dicionário do IRaMuTeQ).
- Índice: coocorrência (número de segmentos em que as duas formas aparecem juntas), o índice padrão do IRaMuTeQ.
- Formas: as N mais frequentes (padrão 100), com frequência mínima declarada no JSON.
- Árvore máxima: o grafo conexo e sem ciclos com as ligações mais fortes (networkx.maximum_spanning_tree), que é a
  representação da ADS: "o grafo mais simples, mas o mais pesado em informação".
- Com uma variável (ex.: candidato), cada forma recebe a modalidade em que é mais específica (χ² ≥ 3,84) — como a coloração
  por locutor de Marchand & Ratinaud (2012, fig. 11); a parte comum fica sem cor.
- Comunidades (modularidade) e posições (redes_caso._layout) só para o desenho.
Saída: dicionário com nós, arestas da árvore e o desenho; GEXF opcional (Gephi; GraphML e NodeXL pela página).
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import chd_reinert as cr  # noqa: E402

TOP = 100


def ads(X: np.ndarray, voc: list[str], grupos: list[str] | None = None, top: int = TOP) -> dict | None:
    import networkx as nx
    from redes_caso import _layout
    freq = X.sum(0)
    ordem = [j for j in np.argsort(-freq, kind="stable") if freq[j] > 0][:top]
    if len(ordem) < 3:
        return None
    B = (X[:, ordem] > 0).astype(np.float64)
    C = B.T @ B
    G = nx.Graph()
    for i, j in enumerate(ordem):
        G.add_node(voc[j], freq=int(freq[j]))
    for a in range(len(ordem)):
        for b in range(a + 1, len(ordem)):
            if C[a, b] > 0:
                G.add_edge(voc[ordem[a]], voc[ordem[b]], weight=int(C[a, b]))
    T = nx.maximum_spanning_tree(G, weight="weight") if G.number_of_edges() else G
    espec = {}
    if grupos is not None:
        g = np.array(grupos)
        mods = sorted(set(g.tolist()))
        n = X.shape[0]
        for m in mods:
            em = g == m
            ch = cr.chi2_assoc(B[em].sum(0), B.sum(0), int(em.sum()), n)
            for k, j in enumerate(ordem):
                if ch[k] >= cr.CHI_CRIT and ch[k] > espec.get(voc[j], ("", 0))[1]:
                    espec[voc[j]] = (m, round(float(ch[k]), 1))
    com, pos = _layout(T) if T.number_of_edges() else ({}, {n: (0.0, 0.0) for n in T.nodes})
    nos = [{"id": n, "freq": T.nodes[n]["freq"], "grupo": com.get(n, 0), "especifica_de": espec.get(n, (None, None))[0],
            "chi2": espec.get(n, (None, None))[1], "x": round(float(pos[n][0]), 4), "y": round(float(pos[n][1]), 4)} for n in T.nodes]
    return {"metodo": " ".join(__doc__.split("Saída:")[0].split()[2:]), "indice": "coocorrência (segmentos)", "formas": len(ordem),
            "frequencia_minima_das_formas": int(freq[ordem[-1]]), "segmentos": int(X.shape[0]),
            "nos": nos, "arestas": [[a, b, d["weight"]] for a, b, d in T.edges(data=True)],
            "comunidades": len(set(com.values())) if com else 0}


def gexf(res: dict, caminho: Path) -> None:
    from redes_caso import gexf as _g
    _g({n["id"]: {"rotulo": n["id"], "tipo": n["especifica_de"] or "comum", "n": n["freq"]} for n in res["nos"]},
       {(a, b): w for a, b, w in res["arestas"]}, caminho)
