#!/usr/bin/env python3
"""Caderno 15 — rede de menções no TikTok: quem os perfis das campanhas de Lula e Flávio marcam (@) nas legendas.

Entrada: data/tiktok/videos.csv.gz (vídeos desde 16/08/2026)
Saída (data/tiktok/):
  rede_mencoes.json   desenhada na página
  rede_mencoes.gexf   Gephi
  rede_mencoes_nos.csv / rede_mencoes_arestas.csv   (Importar planilha do Gephi)
  rede_mencoes_videos.csv   base de conferência: cada menção com o link do vídeo

Rede dirigida: perfil da campanha → conta marcada; peso = nº de vídeos com a marcação.
É a rede de SAÍDA (quem as campanhas citam). A de entrada (quem fala delas) não tem coleta gratuita no TikTok
(diagnóstico D1.1); o usuário optou por não usar serviço pago.
"""
from __future__ import annotations

import csv
import datetime as dt
import gzip
import json
import math
import re
import sys
from collections import defaultdict
from pathlib import Path

import networkx as nx

INICIO = "2026-08-16"
SEMENTE = 42
MENCAO = re.compile(r"(?<![\w.])@([A-Za-z0-9._]{2,30})")
CORES = {"280002542548": "#c8102e", "280002551544": "#1f8a3b"}


def mencoes(legenda: str) -> set[str]:
    return {m.lower().rstrip(".") for m in MENCAO.findall(legenda or "") if len(m.rstrip(".")) >= 2}


def mistura(fr: float) -> str:
    a, b = (0xc8, 0x10, 0x2e), (0x1f, 0x8a, 0x3b)
    return "#" + "".join(f"{round(b[i] + (a[i] - b[i]) * fr):02x}" for i in range(3))


def montar(rows: list[dict]) -> nx.DiGraph:
    g = nx.DiGraph()
    vids = defaultdict(list)
    for r in rows:
        if r["publicado_em"] < INICIO:
            continue
        origem = r["perfil"]
        if origem not in g:
            g.add_node(origem, tipo="campanha", candidato=r["candidate_name"], cid=r["candidate_id"])
        for alvo in mencoes(r["legenda"]) - {origem}:
            vids[(origem, alvo)].append(r)
    for (o, a), lst in vids.items():
        if a not in g:
            g.add_node(a, tipo="marcada")
        g.add_edge(o, a, weight=len(lst), videos=[x["video_id"] for x in lst])
    # lado de cada conta marcada: fração das marcações vindas da campanha de Lula
    for n, d in g.nodes(data=True):
        if d["tipo"] == "campanha":
            d["cor"] = CORES.get(d["cid"], "#5b7894")
            d["lula"] = d["cid"] == "280002542548"
        else:
            de_l = sum(w for u, _, w in g.in_edges(n, data="weight") if g.nodes[u].get("cid") == "280002542548")
            tot = sum(w for _, _, w in g.in_edges(n, data="weight"))
            d["frac_lula"] = round(de_l / tot, 3) if tot else 0.5
            d["cor"] = mistura(d["frac_lula"])
        d["marcacoes_recebidas"] = sum(w for _, _, w in g.in_edges(n, data="weight"))
        d["marcacoes_feitas"] = sum(w for _, _, w in g.out_edges(n, data="weight"))
    return g


def posicionar(g: nx.DiGraph):
    """Cada componente (em geral, uma campanha) é disposto separadamente e os blocos ficam lado a lado,
    com largura proporcional ao tamanho. Perfis sem nenhuma marcação saem do desenho (seguem no resumo)."""
    g.remove_nodes_from([n for n in list(g.nodes) if g.degree(n) == 0])
    if g.number_of_nodes() == 0:
        return
    comps = sorted(nx.weakly_connected_components(g), key=lambda c: (-len(c), sorted(c)[0]))
    # campanha de Lula à esquerda, de Flávio à direita
    lado = lambda c: 0 if any(g.nodes[n].get("cid") == "280002542548" for n in c) else 1  # noqa: E731
    comps.sort(key=lambda c: (lado(c), -len(c)))
    larg = [math.sqrt(len(c)) for c in comps]
    total, x0 = sum(larg), 0.0
    for c, w in zip(comps, larg):
        sub = g.subgraph(c).to_undirected()
        pos = nx.kamada_kawai_layout(sub, weight=None) if len(c) > 2 else {n: (i * 0.5, 0.0) for i, n in enumerate(sorted(c))}
        xs, ys = [p[0] for p in pos.values()], [p[1] for p in pos.values()]
        spx, spy = (max(xs) - min(xs)) or 1.0, (max(ys) - min(ys)) or 1.0
        bw = 1000 * w / total
        for n, (x, y) in pos.items():
            g.nodes[n]["x"] = round(x0 + 40 + (float(x) - min(xs)) / spx * max(bw - 80, 10), 1)
            g.nodes[n]["y"] = round(60 + (float(y) - min(ys)) / spy * 700, 1)
        x0 += bw


def main(argv=None) -> int:
    root = Path(argv[0]) if argv else Path(".")
    d = root / "data/tiktok"
    src = d / "videos.csv.gz"
    if not src.exists():
        print("⛔ sem acervo do TikTok")
        return 1
    rows = list(csv.DictReader(gzip.open(src, "rt", encoding="utf-8"), delimiter=";"))
    por_id = {r["video_id"]: r for r in rows}
    g = montar(rows)
    sem = sorted(n for n in g.nodes if g.degree(n) == 0)
    posicionar(g)
    out = {"schema_version": 1, "gerado_em_utc": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
           "metodo": ("Rede dirigida de menções: perfil de TikTok da campanha (declarado ao TSE) → conta marcada com @ na legenda; "
                      "peso = nº de vídeos com a marcação, desde 16/08/2026. Mostra quem as campanhas CITAM (aliados, adversários, "
                      "os próprios perfis). Quem fala DELAS no TikTok não é coletado: não há coleta gratuita (diagnóstico D1.1). "
                      "Cor: vermelho = campanha de Lula, verde = campanha de Flávio; contas marcadas pelas duas ficam na mistura."),
           "nos": [{"id": n, **{k: v for k, v in a.items()}} for n, a in sorted(g.nodes(data=True))],
           "arestas": [{"de": u, "para": v, "peso": a["weight"],
                        "videos": [{"id": i, "legenda": por_id[i]["legenda"][:160], "url": por_id[i]["url"],
                                    "publicado_em": por_id[i]["publicado_em"]} for i in a["videos"][:6]]}
                       for u, v, a in sorted(g.edges(data=True))]}
    out["perfis_sem_marcacao"] = sem
    out["resumo"] = {c: {"perfis_com_marcacao": sum(1 for _, a in g.nodes(data=True) if a.get("cid") == c),
                         "contas_marcadas": len({v for u, v in g.edges() if g.nodes[u].get("cid") == c}),
                         "marcacoes": sum(a["weight"] for u, _, a in g.edges(data=True) if g.nodes[u].get("cid") == c)}
                     for c in CORES}
    (d / "rede_mencoes.json").write_text(json.dumps(out, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    with open(d / "rede_mencoes_nos.csv", "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(["Id", "Label", "tipo", "candidato", "marcacoes_recebidas", "marcacoes_feitas", "frac_lula", "url", "x", "y"])
        for n, a in sorted(g.nodes(data=True)):
            w.writerow([n, "@" + n, a["tipo"], a.get("candidato", ""), a["marcacoes_recebidas"], a["marcacoes_feitas"],
                        a.get("frac_lula", ""), f"https://www.tiktok.com/@{n}", a.get("x"), a.get("y")])
    with open(d / "rede_mencoes_arestas.csv", "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(["Source", "Target", "Weight", "Type"])
        for u, v, a in sorted(g.edges(data=True)):
            w.writerow([u, v, a["weight"], "Directed"])
    with open(d / "rede_mencoes_videos.csv", "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(["perfil_campanha", "conta_marcada", "video_id", "url", "publicado_em", "legenda"])
        for u, v, a in sorted(g.edges(data=True)):
            for i in a["videos"]:
                r = por_id[i]
                w.writerow([u, v, i, r["url"], r["publicado_em"], r["legenda"]])
    gx = nx.DiGraph()
    for n, a in g.nodes(data=True):
        r, gg, b = (int(a["cor"][i:i + 2], 16) for i in (1, 3, 5))
        gx.add_node(n, label="@" + n, tipo=a["tipo"], candidato=a.get("candidato", ""), marcacoes_recebidas=a["marcacoes_recebidas"],
                    viz={"position": {"x": a.get("x", 0), "y": -a.get("y", 0), "z": 0.0},
                         "size": 6 + 3 * math.sqrt(a["marcacoes_recebidas"] + a["marcacoes_feitas"]),
                         "color": {"r": r, "g": gg, "b": b, "a": 1.0}})
    for u, v, a in g.edges(data=True):
        gx.add_edge(u, v, weight=a["weight"])
    nx.write_gexf(gx, d / "rede_mencoes.gexf")
    print(f"menções TikTok: {g.number_of_nodes()} contas, {g.number_of_edges()} ligações; " +
          "; ".join(f"{c}: {v}" for c, v in out["resumo"].items()))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
