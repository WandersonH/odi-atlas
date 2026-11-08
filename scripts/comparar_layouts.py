#!/usr/bin/env python3
"""ForceAtlas 2 e OpenOrd lado a lado, alinhados (Mirror/Rotate automáticos) e com rótulos só de contas públicas.

Guia de layouts do responsável (07/11/2026): Mirror e Rotate servem para alinhar dois desenhos ("se o grupo A está à
esquerda num gráfico e à direita no outro, espelhe um deles"); Label Adjust abre espaço para os nomes "quando você já
tem os perfis que quer mostrar".
- Alinhamento: Procrustes ortogonal (rotação e, se preciso, espelhamento) do OpenOrd sobre o ForceAtlas 2, pelas posições
  dos mesmos nós (`<caso>_<rede>_nos_gephi.csv`, gerado por scripts/gephi/RedesGephi.java). Não deforma nenhum dos dois.
- Cores: as 8 maiores comunidades (Modularity Class do componente gigante); as demais em cinza. Tamanho: grau.
- Rótulos: os 12 nós de maior grau cujo rótulo é público. Nunca "perfil pequeno …" nem códigos (A0001, C0001, P0001,
  V0001), que são pessoas comuns. Afastamento dos rótulos com adjustText, quando instalado (equivalente ao Label Adjust).
Saída: data/redes/gephi/<caso>_<rede>_comparacao.png
Uso: python scripts/comparar_layouts.py [data/redes/gephi/026_rede_circulacao_nos_gephi.csv ...]
"""
from __future__ import annotations

import csv
import glob
import re
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402

PRIVADO = re.compile(r"^(perfil pequeno|[ACPV]\d{4}$)", re.I)
CORES = ["#c8102e", "#1f6fb2", "#1f8a3b", "#d7a14a", "#7a5c99", "#e07b39", "#2aa198", "#b3428a"]


def alinhar(a: np.ndarray, b: np.ndarray) -> tuple[np.ndarray, bool]:
    """Gira/espelha b para ficar o mais parecido possível com a (Procrustes ortogonal, mesma escala de a)."""
    a0, b0 = a - a.mean(0), b - b.mean(0)
    sa, sb = np.sqrt((a0 ** 2).sum() / len(a0)), np.sqrt((b0 ** 2).sum() / len(b0))
    a1, b1 = a0 / (sa or 1), b0 / (sb or 1)
    u, _, vt = np.linalg.svd(b1.T @ a1)
    r = u @ vt
    return (b1 @ r) * sa, bool(np.linalg.det(r) < 0)


def rede_arestas(caso: str, rede: str, ids: set[str]) -> list[tuple[str, str]]:
    try:
        import networkx as nx
        g = nx.read_gexf(f"data/casos/{caso}/{rede}.gexf")
        return [(str(a), str(b)) for a, b in g.edges() if str(a) in ids and str(b) in ids][:30000]
    except Exception:
        return []


def desenha(arq: str) -> str:
    nome = Path(arq).name.replace("_nos_gephi.csv", "")
    caso, rede = nome.split("_", 1)
    L = list(csv.DictReader(open(arq, encoding="utf-8")))
    ids = [r["id"] for r in L]
    fa = np.array([[float(r["x_forceatlas2"]), float(r["y_forceatlas2"])] for r in L])
    oo = np.array([[float(r["x_openord"]), float(r["y_openord"])] for r in L])
    oo2, espelhou = alinhar(fa, oo)
    fa = fa - fa.mean(0)
    grau = np.array([float(r["grau"] or 0) for r in L])
    cls = [r["modularity_class"] for r in L]
    ordem = [c for c, _ in sorted(((c, cls.count(c)) for c in set(cls)), key=lambda x: -x[1])]
    cor = {c: CORES[i] if i < len(CORES) else "#c9c9c9" for i, c in enumerate(ordem)}
    pct = {c: 100 * cls.count(c) / len(cls) for c in ordem}
    tam = 4 + 120 * np.sqrt(grau / (grau.max() or 1))
    pos = {i: k for k, i in enumerate(ids)}
    ar = rede_arestas(caso, rede, set(ids))
    rot = [k for k in np.argsort(-grau) if not PRIVADO.match(L[k]["rotulo"] or "")][:12]
    fig, ax = plt.subplots(1, 2, figsize=(18, 9), dpi=100)
    for eixo, P, tit in ((ax[0], fa, "ForceAtlas 2 (comunidades)"), (ax[1], oo2, "OpenOrd (polarização)" + (" · espelhado e girado" if espelhou else " · girado"))):
        for a_, b_ in ar:
            p, q = P[pos[a_]], P[pos[b_]]
            eixo.plot([p[0], q[0]], [p[1], q[1]], color="#999999", lw=0.3, alpha=0.08, zorder=1)
        eixo.scatter(P[:, 0], P[:, 1], s=tam, c=[cor[c] for c in cls], alpha=0.85, linewidths=0, zorder=2)
        txt = [eixo.text(P[k, 0], P[k, 1], L[k]["rotulo"], fontsize=8.5, zorder=3) for k in rot]
        try:
            from adjustText import adjust_text
            adjust_text(txt, ax=eixo, arrowprops=dict(arrowstyle="-", color="#666666", lw=0.5))
        except Exception:
            pass
        # enquadramento pelos percentis 1–99 (nós soltos muito longe achatavam o desenho); os que ficam fora seguem no CSV
        lo, hi = np.percentile(P, 1, axis=0), np.percentile(P, 99, axis=0)
        m = 0.08 * (hi - lo)
        eixo.set_xlim(lo[0] - m[0], hi[0] + m[0]); eixo.set_ylim(lo[1] - m[1], hi[1] + m[1])
        eixo.set_title(tit, fontsize=13, loc="left")
        eixo.set_xticks([]); eixo.set_yticks([])
        for s in eixo.spines.values():
            s.set_visible(False)
    leg = [plt.Line2D([0], [0], marker="o", color="w", markerfacecolor=cor[c], markersize=9, label=f"comunidade {c}: {pct[c]:.1f}% dos nós") for c in ordem[:8]]
    fig.legend(handles=leg, loc="lower center", ncol=4, frameon=False, fontsize=10, bbox_to_anchor=(0.5, 0.035))
    fig.suptitle(f"Caso {caso} · {rede} · componente gigante, {len(L):,} nós".replace(f"{len(L):,}", f"{len(L):,}".replace(",", ".")), x=0.01, ha="left", fontsize=14)
    fig.subplots_adjust(bottom=0.14)
    fig.text(0.01, 0.0, "Mesmos nós e cores nos dois painéis; o OpenOrd foi girado (e espelhado, se indicado) para alinhar com o ForceAtlas 2, sem deformar. "
             "Tamanho = grau. Rótulos só de contas públicas e termos; pessoas comuns ficam em código.", fontsize=8.5, color="#555555")
    out = f"data/redes/gephi/{nome}_comparacao.png"
    fig.savefig(out, bbox_inches="tight")
    plt.close(fig)
    print(f"{out}: {len(L)} nós, {len(ar)} arestas desenhadas, espelhado={espelhou}")
    return out


def main(argv=None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    for a in (argv or sorted(glob.glob("data/redes/gephi/*_nos_gephi.csv"))):
        try:
            desenha(a)
        except Exception as e:
            print(f"⛔ {a}: {e}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
