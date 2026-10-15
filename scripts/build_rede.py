#!/usr/bin/env python3
"""Caderno 13 — rede de coocorrência de termos e tags nos vídeos de YouTube de Lula e Flávio Bolsonaro.

Entrada: data/youtube/videos_latest.csv.gz + data/config/temas_youtube.json
Saída:   data/youtube/rede.json  (desenhada no caderno 13)
         data/youtube/rede.gexf  (abre direto no Gephi, com posição, cor, tamanho e comunidade)

Método (mesmo texto útil do build_conteudo: sem links, sem rodapé repetido, sem nome do canal):
  - nó = palavra (sem acento, sem palavras funcionais) ou tag (#) do vídeo, fora do pacote fixo do canal;
  - um nó entra se aparece em MIN_VIDEOS+ vídeos (somando os dois candidatos), até MAX_NOS nós;
  - aresta = os dois termos aparecem no mesmo vídeo; peso = nº de vídeos em comum; peso mínimo MIN_PESO;
    cada nó guarda só as TOP_ARESTAS arestas mais fortes (evita o "novelo");
  - comunidades: Louvain (networkx, semente fixa); posição: ForceAtlas2 (networkx, semente fixa);
  - lado = fração dos vídeos com o termo que são de Lula (1 = só Lula, 0 = só Flávio).
Tudo determinístico: a mesma entrada gera a mesma rede.
"""
from __future__ import annotations

import csv
import datetime as dt
import gzip
import json
import math
import re
import sys
from collections import Counter
from itertools import combinations
from pathlib import Path

import networkx as nx

sys.path.insert(0, str(Path(__file__).resolve().parent))
import build_conteudo as bc  # noqa: E402
import plataformas as pl  # noqa: E402

MIN_VIDEOS = 8
MAX_NOS = 150
MIN_PESO = 3
TOP_ARESTAS = 8
SEMENTE = 42


def termos_do_video(r: dict, cand: dict, padrao, pacotes, tira_canal) -> set[str]:
    nome = bc.norm(cand["nome"]).split()
    excluir = set(nome) | {"".join(nome)}
    txt = tira_canal.sub(" ", bc.texto_util(r, padrao))
    palavras = {t for t in bc.termos(txt, excluir) if " " not in t and not t.startswith("#")}
    tags = {"#" + t for t in bc.tags_do_video(r, pacotes, padrao) if t not in excluir}
    return palavras | tags


def montar(videos: list[tuple[str, set]], ids: tuple[str, str], min_videos=MIN_VIDEOS, max_nos=MAX_NOS,
           min_peso=MIN_PESO, top_arestas=TOP_ARESTAS) -> nx.Graph:
    """videos = [(candidate_id, termos)]. ids = (id_lula, id_flavio)."""
    df = Counter()
    por_cand = {c: Counter() for c in ids}
    for cid, ts in videos:
        df.update(ts)
        por_cand[cid].update(ts)
    nos = [t for t, n in sorted(df.items(), key=lambda x: (-x[1], x[0])) if n >= min_videos][:max_nos]
    sel = set(nos)
    co = Counter()
    for _, ts in videos:
        for a, b in combinations(sorted(ts & sel), 2):
            co[(a, b)] += 1
    g = nx.Graph()
    for t in nos:
        a, b = por_cand[ids[0]][t], por_cand[ids[1]][t]
        g.add_node(t, videos=df[t], lula=a, flavio=b, lado=round(a / (a + b), 3))
    viz: dict[str, list] = {t: [] for t in nos}
    for (a, b), w in co.items():
        if w >= min_peso:
            viz[a].append((w, b))
            viz[b].append((w, a))
    for t, lst in viz.items():
        for w, u in sorted(lst, key=lambda x: (-x[0], x[1]))[:top_arestas]:
            g.add_edge(t, u, weight=w)
    g.remove_nodes_from([n for n in list(g.nodes) if g.degree(n) == 0])
    return g


def analisar(g: nx.Graph) -> dict:
    if g.number_of_nodes() == 0:
        return {}
    comms = nx.community.louvain_communities(g, weight="weight", seed=SEMENTE)
    comms = sorted(comms, key=lambda c: (-len(c), sorted(c)[0]))
    for i, c in enumerate(comms):
        for n in c:
            g.nodes[n]["comunidade"] = i
    btw = nx.betweenness_centrality(g, seed=SEMENTE)
    if hasattr(nx, "forceatlas2_layout"):
        inicio = nx.spring_layout(g, weight="weight", seed=SEMENTE)  # ponto de partida sem nós sobrepostos
        pos = nx.forceatlas2_layout(g, pos=inicio, weight="weight", seed=SEMENTE, max_iter=800, scaling_ratio=2.0, linlog=True,
                                    strong_gravity=False, distributed_action=True, gravity=1.0)
        layout = "ForceAtlas2 LinLog (networkx)"
    else:  # networkx < 3.4
        pos = nx.spring_layout(g, weight="weight", seed=SEMENTE, iterations=300)
        layout = "Fruchterman-Reingold (networkx spring_layout)"
    if any(not (math.isfinite(float(p[0])) and math.isfinite(float(p[1]))) for p in pos.values()):
        raise RuntimeError("layout gerou posição inválida (NaN); rede não publicada")
    xs, ys = [p[0] for p in pos.values()], [p[1] for p in pos.values()]
    span = max(max(xs) - min(xs), max(ys) - min(ys)) or 1
    for n, (x, y) in pos.items():
        g.nodes[n]["x"] = round(float(x - min(xs)) / float(span) * 1000, 1)
        g.nodes[n]["y"] = round(float(y - min(ys)) / float(span) * 1000, 1)
        g.nodes[n]["intermediacao"] = round(float(btw[n]), 4)
        g.nodes[n]["grau"] = g.degree(n)
    return {"comunidades": comms, "layout": layout,
            "modularidade": round(nx.community.modularity(g, comms, weight="weight"), 3)}


def cor_lado(lado: float) -> str:
    """Vermelho (Lula) ↔ verde (Flávio), padrão dos cadernos 12–15."""
    a, b = (0xc8, 0x10, 0x2e), (0x1f, 0x8a, 0x3b)
    return "#" + "".join(f"{round(b[i] + (a[i] - b[i]) * lado):02x}" for i in range(3))


def main(argv=None) -> int:
    root, plat = pl.args(argv)
    cfg = json.loads((root / "data/config/temas_youtube.json").read_text(encoding="utf-8"))
    ids = tuple(cfg["candidatos"])  # (Lula, Flávio) na ordem do arquivo
    rows = pl.videos(root, plat)
    padrao, pacotes = bc.texto_padrao(rows), bc.pacotes_de_tags(rows)
    videos, video_ids = [], []
    for cid in ids:
        cand = cfg["candidatos"][cid]
        canais = sorted({r["canal"] for r in rows if r["candidate_id"] == cid}, key=len, reverse=True)
        tira = re.compile("|".join(re.escape(c) for c in canais) or "(?!)", re.I)
        meus = [r for r in rows if r["candidate_id"] == cid]
        videos += [(cid, termos_do_video(r, cand, padrao, pacotes, tira)) for r in meus]
        video_ids += [r["video_id"] for r in meus]
    g = montar(videos, ids)
    info = analisar(g)
    for n in g.nodes:
        d = g.nodes[n]
        d["label"] = n
        d["cor"] = cor_lado(d["lado"])
        d["viz"] = {"position": {"x": d["x"], "y": -d["y"], "z": 0.0}, "size": 2 + 3 * d["videos"] ** 0.5,
                    "color": {"r": int(d["cor"][1:3], 16), "g": int(d["cor"][3:5], 16), "b": int(d["cor"][5:7], 16), "a": 1.0}}
    metodo = (f"Rede de coocorrência: nó = palavra ou #tag presente em {MIN_VIDEOS}+ vídeos (até {MAX_NOS}); "
              f"aresta = aparecem no mesmo vídeo (peso = nº de vídeos, mínimo {MIN_PESO}; até {TOP_ARESTAS} arestas mais fortes por nó). "
              f"Comunidades: Louvain; posição: {info.get('layout', '—')}; semente {SEMENTE}. "
              "Texto sem links, rodapés repetidos, nome do canal, nome do próprio candidato e pacote fixo de tags. "
              "Cor = proporção de uso por Lula (vermelho) e Flávio (verde).")
    coletado = max((r["coletado_em"] for r in rows), default=None)
    comms = info.get("comunidades", [])
    out = {"schema_version": 1, "gerado_em_utc": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
           "coletado_em_utc": coletado, "metodo": metodo, "networkx": nx.__version__,
           "videos": {cid: sum(1 for c, _ in videos if c == cid) for cid in ids},
           "nos_total": g.number_of_nodes(), "arestas_total": g.number_of_edges(),
           "modularidade": info.get("modularidade"),
           "comunidades": [{"id": i, "nos": len(c),
                            "lado_medio": round(sum(g.nodes[n]["lado"] * g.nodes[n]["videos"] for n in c) /
                                                sum(g.nodes[n]["videos"] for n in c), 3),
                            "principais": sorted(c, key=lambda n: (-g.nodes[n]["videos"], n))[:8]} for i, c in enumerate(comms)],
           "nos": [{"id": n, "x": d["x"], "y": d["y"], "v": d["videos"], "l": d["lula"], "f": d["flavio"],
                    "lado": d["lado"], "c": d["comunidade"], "g": d["grau"], "b": d["intermediacao"]}
                   for n, d in sorted(g.nodes(data=True))],
           "arestas": [[a, b, d["weight"]] for a, b, d in sorted(g.edges(data=True))]}
    pl.caminho(root, plat, "rede").with_suffix(".json").write_text(json.dumps(out, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    # Planilhas para conferência e importação no Gephi (Laboratório de dados → Importar planilha)
    yt = pl.caminho(root, plat, "rede").parent
    with open(yt / "rede_nos.csv", "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(["Id", "Label", "videos", "videos_lula", "videos_flavio", "lado_lula", "comunidade", "grau",
                    "intermediacao", "x", "y"])
        for n in out["nos"]:
            w.writerow([n["id"], n["id"], n["v"], n["l"], n["f"], n["lado"], n["c"] + 1, n["g"], n["b"], n["x"], n["y"]])
    with open(yt / "rede_arestas.csv", "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(["Source", "Target", "Weight", "Type"])
        for a, b2, wt in out["arestas"]:
            w.writerow([a, b2, wt, "Undirected"])
    # Matriz de origem: que termos da rede cada vídeo contém (permite refazer a contagem de qualquer aresta)
    nos_set = set(g.nodes)
    with open(yt / "rede_videos_termos.csv", "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(["candidate_id", "candidato", "video_id", "url", "termos_na_rede"])
        for (cid, ts), vid in zip(videos, video_ids):
            dentro = sorted(ts & nos_set)
            if dentro:
                w.writerow([cid, cfg["candidatos"][cid]["nome"], vid, f"https://www.youtube.com/watch?v={vid}", "|".join(dentro)])
    gx = g.copy()
    for n in gx.nodes:
        gx.nodes[n].pop("x"); gx.nodes[n].pop("y")
    gx.graph.update({"descricao": metodo, "coletado_em_utc": coletado or ""})
    nx.write_gexf(gx, pl.caminho(root, plat, "rede").with_suffix(".gexf"))
    print(f"rede: {g.number_of_nodes()} nós, {g.number_of_edges()} arestas, {len(comms)} comunidades, "
          f"modularidade {info.get('modularidade')}, layout {info.get('layout')}")
    for c in out["comunidades"]:
        print(f"  C{c['id']} ({c['nos']} nós, lado médio {c['lado_medio']}): {', '.join(c['principais'])}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
