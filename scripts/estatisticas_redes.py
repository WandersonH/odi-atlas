#!/usr/bin/env python3
"""Estatísticas das redes do Atlas (os mesmos indicadores do painel Statistics do Gephi), para todas as redes dos casos.

Pedido do responsável (07/11/2026, 19h25): "existem 2 tipos de redes que vamos explorar no Gephi: Force Atlas 2 para ver
comunidades e OpenOrd para ver polarização. Vamos ver grupos pelo modularity e identificar qual a % desses; registre o
csv com os cálculos".

Por rede (data/casos/<id>/*.gexf):
- nós, arestas, dirigida, densidade (Graph Density), grau médio e grau ponderado médio (Average Degree);
- componentes conectados (Connected Components; fracamente conectados quando dirigida) e % de nós no maior;
- coeficiente de clustering médio (Avg. Clustering Coefficient, como grafo não dirigido);
- Modularity: Louvain (Blondel et al., 2008), o mesmo algoritmo do Gephi, resolução 1,0, pesos das arestas, semente fixa
  (42) para ser reproduzível; Q, número de comunidades, % de nós nas 1ª, 2ª e 3ª maiores, % nas comunidades com 1% ou
  mais dos nós;
- índice de polarização entre as duas maiores comunidades: E-I de Krackhardt e Stern (1988) restrito a elas,
  (externas − internas) / (externas + internas), pelos pesos: −1 = duas bolhas sem contato; +1 = só contato cruzado.
- diâmetro e caminho médio (Network Diameter, Avg. Path Length) só no maior componente e só até 3.000 nós (acima disso
  ficam vazios: o cálculo exato fica caro demais para a rotina).

Saídas: data/redes/estatisticas_redes.csv (uma linha por rede) e data/redes/comunidades_redes.csv (uma linha por
comunidade com 1% ou mais dos nós: tamanho, % de nós, % do peso interno e os 5 nós de maior grau — os rótulos são os do
GEXF público, que já trazem pessoas comuns como código).
Uso: python scripts/estatisticas_redes.py [--caso 026] [--max-nos 200000]
"""
from __future__ import annotations

import csv
import glob
import sys
from collections import Counter, defaultdict
from pathlib import Path

import networkx as nx

sys.path.insert(0, str(Path(__file__).resolve().parent))
from net import now_utc  # noqa: E402

SEMENTE = 42


def ler(arq: str) -> nx.Graph:
    g = nx.read_gexf(arq)
    for _, _, d in g.edges(data=True):
        try:
            d["weight"] = float(d.get("weight", 1) or 1)
        except (TypeError, ValueError):
            d["weight"] = 1.0
    return g


def estatisticas(arq: str) -> tuple[dict, list[dict]]:
    g = ler(arq)
    u = nx.Graph()
    u.add_nodes_from(g.nodes(data=True))
    for a, b, d in g.edges(data=True):
        if a == b:
            continue
        w = d.get("weight", 1.0)
        if u.has_edge(a, b):
            u[a][b]["weight"] += w
        else:
            u.add_edge(a, b, weight=w)
    n, m = g.number_of_nodes(), g.number_of_edges()
    caso = Path(arq).parent.name
    lin = {"caso": caso, "rede": Path(arq).stem, "arquivo": arq, "dirigida": g.is_directed(), "nos": n, "arestas": m,
           "densidade": round(nx.density(g), 6) if n > 1 else None,
           "grau_medio": round((m if g.is_directed() else 2 * m) / n, 3) if n else None,
           "grau_ponderado_medio": round(sum(dict(u.degree(weight="weight")).values()) / n, 3) if n else None}
    if n == 0:
        return lin, []
    comps = sorted(nx.connected_components(u), key=len, reverse=True)
    lin.update({"componentes": len(comps), "pct_nos_maior_componente": round(100 * len(comps[0]) / n, 2),
                "clustering_medio": round(nx.average_clustering(u, weight=None), 4)})
    if len(comps[0]) <= 3000 and len(comps[0]) > 1:
        h = u.subgraph(comps[0])
        lin["diametro_maior_componente"] = nx.diameter(h)
        lin["caminho_medio_maior_componente"] = round(nx.average_shortest_path_length(h), 3)
    if u.number_of_edges() == 0:
        return lin, []
    coms = nx.community.louvain_communities(u, weight="weight", resolution=1.0, seed=SEMENTE)
    coms = sorted(coms, key=len, reverse=True)
    q = nx.community.modularity(u, coms, weight="weight")
    pct = [100 * len(c) / n for c in coms]
    rel = [c for c, p in zip(coms, pct) if p >= 1]
    lin.update({"modularidade_q": round(q, 4), "comunidades": len(coms), "comunidades_1pct_ou_mais": len(rel),
                "pct_maior": round(pct[0], 2), "pct_segunda": round(pct[1], 2) if len(pct) > 1 else None,
                "pct_terceira": round(pct[2], 2) if len(pct) > 2 else None,
                "pct_nos_em_comunidades_1pct": round(sum(p for p in pct if p >= 1), 2)})
    de = {v: i for i, c in enumerate(coms) for v in c}
    peso_int, peso_tot = Counter(), sum(d["weight"] for _, _, d in u.edges(data=True))
    cruz = defaultdict(float)
    for a, b, d in u.edges(data=True):
        ca, cb = de[a], de[b]
        if ca == cb:
            peso_int[ca] += d["weight"]
        else:
            cruz[tuple(sorted((ca, cb)))] += d["weight"]
    if len(coms) > 1:
        i_, e_ = peso_int[0] + peso_int[1], cruz.get((0, 1), 0.0)
        lin["polarizacao_ei_2_maiores"] = round((e_ - i_) / (e_ + i_), 4) if (e_ + i_) else None
    grau = dict(u.degree(weight="weight"))
    rot = {v: (g.nodes[v].get("label") or v) for v in g.nodes}
    linhas_c = []
    for i, c in enumerate(coms):
        if 100 * len(c) / n < 1:
            continue
        top = sorted(c, key=lambda v: grau.get(v, 0), reverse=True)[:5]
        linhas_c.append({"caso": caso, "rede": lin["rede"], "comunidade": i + 1, "nos": len(c), "pct_nos": round(100 * len(c) / n, 2),
                         "pct_peso_interno": round(100 * peso_int[i] / peso_tot, 2) if peso_tot else None,
                         "nos_de_maior_grau": " | ".join(str(rot[v]) for v in top)})
    return lin, linhas_c


def main(argv=None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    so = argv[argv.index("--caso") + 1] if "--caso" in argv else "*"
    maxn = int(argv[argv.index("--max-nos") + 1]) if "--max-nos" in argv else 200000
    arqs = sorted(glob.glob(f"data/casos/{so}/*.gexf"))
    linhas, coms, erros = [], [], []
    for a in arqs:
        try:
            lin, c = estatisticas(a)
            if lin["nos"] > maxn:
                continue
            lin["calculado_em_utc"] = now_utc()
            linhas.append(lin)
            coms += c
            print(f"{a}: {lin['nos']} nós, Q={lin.get('modularidade_q')}, {lin.get('comunidades_1pct_ou_mais')} comunidades ≥1%", flush=True)
        except Exception as e:  # rede vazia ou GEXF malformado: registra e segue
            erros.append((a, f"{type(e).__name__}: {e}"))
            print(f"⛔ {a}: {e}", flush=True)
    Path("data/redes").mkdir(parents=True, exist_ok=True)
    campos = sorted({k for l in linhas for k in l}, key=lambda k: list(linhas[0]).index(k) if k in linhas[0] else 99)
    with open("data/redes/estatisticas_redes.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=campos)
        w.writeheader()
        w.writerows(linhas)
    with open("data/redes/comunidades_redes.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["caso", "rede", "comunidade", "nos", "pct_nos", "pct_peso_interno", "nos_de_maior_grau"])
        w.writeheader()
        w.writerows(coms)
    print(f"{len(linhas)} redes, {len(coms)} comunidades ≥1%, {len(erros)} erros")
    return 0


if __name__ == "__main__":
    sys.exit(main())
