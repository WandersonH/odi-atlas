#!/usr/bin/env python3
"""Cada rede publicada em GEXF (Gephi) ganha também GraphML e as planilhas do NodeXL, para validação em outros programas.

Pedido do responsável (01/11/2026, 21h04): "temos que ter, nos dados que podem ser validados, arquivo pra IRaMuTeQ, Gephi e NodeXL".
Para cada data/**/<nome>.gexf, escreve ao lado:
  - <nome>.graphml           — GraphML (NodeXL: Import › From GraphML File; também abre no Gephi, Cytoscape, igraph);
  - <nome>_nodexl_arestas.csv — planilha Edges do NodeXL: "Vertex 1", "Vertex 2", "Edge Weight" e os demais atributos da aresta;
  - <nome>_nodexl_vertices.csv — planilha Vertices do NodeXL: "Vertex", "Label" e os atributos do nó.
Os arquivos são gerados a partir do GEXF, sem nenhum dado a mais: se o GEXF só tem códigos para contas pequenas, os outros também.
Só refaz quando o GEXF é mais novo que as saídas. Uso: python scripts/exportar_redes.py [pasta=data]
"""
from __future__ import annotations

import csv
import sys
from pathlib import Path

import networkx as nx


def exportar(gexf: Path, forcar: bool = False) -> bool:
    stem = gexf.with_suffix("")
    saidas = [stem.with_suffix(".graphml"), Path(f"{stem}_nodexl_arestas.csv"), Path(f"{stem}_nodexl_vertices.csv")]
    if not forcar and all(s.exists() and s.stat().st_mtime >= gexf.stat().st_mtime for s in saidas):
        return False
    g = nx.read_gexf(gexf)
    # GraphML não aceita atributos de estrutura (listas/dicionários, ex.: 'viz' do Gephi): ficam fora, o resto passa
    h = g.__class__()
    h.add_nodes_from((n, {k: v for k, v in d.items() if isinstance(v, (str, int, float, bool))}) for n, d in g.nodes(data=True))
    h.add_edges_from((a, b, {k: v for k, v in d.items() if isinstance(v, (str, int, float, bool))}) for a, b, d in g.edges(data=True))
    nx.write_graphml(h, saidas[0])
    ea = sorted({k for _, _, d in h.edges(data=True) for k in d if k not in ("weight", "id")})
    with open(saidas[1], "w", newline="", encoding="utf-8-sig") as f:  # utf-8 com BOM: o Excel (NodeXL) lê os acentos
        w = csv.writer(f)
        w.writerow(["Vertex 1", "Vertex 2", "Edge Weight", *ea])
        for a, b, d in h.edges(data=True):
            w.writerow([a, b, d.get("weight", 1), *[d.get(k, "") for k in ea]])
    na = sorted({k for _, d in h.nodes(data=True) for k in d if k != "label"})
    with open(saidas[2], "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(["Vertex", "Label", *na])
        for n, d in h.nodes(data=True):
            w.writerow([n, d.get("label", n), *[d.get(k, "") for k in na]])
    return True


def main(argv: list[str]) -> int:
    raiz = Path(argv[0]) if argv and not argv[0].startswith("--") else Path("data")
    feitos, erros = 0, []
    for gexf in sorted(raiz.rglob("*.gexf")):
        try:
            feitos += exportar(gexf, "--forcar" in argv)
        except Exception as e:  # noqa: BLE001 — um GEXF com defeito não impede os outros
            erros.append(f"{gexf}: {type(e).__name__}: {str(e)[:120]}")
    print(f"redes exportadas para GraphML e NodeXL: {feitos} · erros: {len(erros)}")
    for e in erros[:10]:
        print("  ⛔", e)
    return 1 if erros else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
