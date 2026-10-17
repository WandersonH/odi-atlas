#!/usr/bin/env python3
"""Caderno 05 (Buscas) — o universo das notícias do Google Notícias sobre cada candidato, no período todo:
nuvem de palavras, CHD de Reinert, rede de coocorrência (Gephi) e corpus no formato do IRaMuTeQ.

Entrada: data/trends/noticias/universo.csv.gz (collect_google_noticias_diario.py: tudo o que o feed devolve por dia e
candidato, até 100 itens por busca). Unidade de análise: o título da notícia, uma vez por candidato (títulos repetidos
por republicação contam uma vez).
Saídas (data/trends/noticias/): texto.json · rede_termos.json/.gexf · rede_termos_nos.csv · rede_termos_arestas.csv ·
corpus_iramuteq.txt · titulos_unicos.csv
"""
from __future__ import annotations

import csv
import datetime as dt
import gzip
import json
import math
import random
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

import networkx as nx
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import build_conteudo as bc  # noqa: E402
import build_rede as br  # noqa: E402
import chd_reinert as chd  # noqa: E402
from net import now_utc  # noqa: E402

SEMENTE = 42
CHD_MIN_TOKENS = 4
CHD_MIN_FREQ = 10
CHD_AMOSTRA = 6000
SLUG = {"280002542548": "lula", "280002551544": "flavio"}


def chave(t: str) -> str:
    return re.sub(r"\W+", " ", bc.norm(t)).strip()


def fase_de(dia: str, fases: list[dict]) -> str:
    for f in fases:
        if f["de"] <= dia <= f["ate"]:
            return f["id"]
    return "fora"


def unicos(rows: list[dict]) -> list[dict]:
    """Um título por candidato: o primeiro dia em que apareceu; conta em quantos veículos/dias se repetiu."""
    vistos: dict[tuple, dict] = {}
    for r in sorted(rows, key=lambda r: (r["dia"], int(r["posicao"]))):
        k = (r["candidate_id"], chave(r["titulo"]))
        if not k[1]:
            continue
        if k in vistos:
            vistos[k]["repeticoes"] += 1
        else:
            vistos[k] = {**r, "repeticoes": 1}
    return list(vistos.values())


def chd_titulos(titulos: list[dict], semente: int = SEMENTE) -> dict:
    idx = [i for i, t in enumerate(titulos) if len(chd.tokens(t["titulo"])) >= CHD_MIN_TOKENS]
    random.Random(semente).shuffle(idx)
    idx = sorted(idx[:CHD_AMOSTRA])
    if len(idx) < 200:
        return {"status": f"⛔ só {len(idx)} títulos com {CHD_MIN_TOKENS}+ palavras"}
    segs = [titulos[i]["titulo"] for i in idx]
    X, voc = chd.matriz(segs, min_freq=CHD_MIN_FREQ)
    X = X.astype(np.float32)
    ativos = int((X.sum(1) > 0).sum())
    mc = max(chd.MIN_CLASSE, int(chd.MIN_CLASSE_PCT * ativos))
    rot, _ = chd.chd(X, min_classe=mc)
    cl = rot > 0
    n = int(cl.sum())
    tot = X[cl].sum(0)
    classes = []
    for k in sorted(set(rot[cl].tolist())):
        m = rot == k
        nk = int(m.sum())
        ch = chd.chi2_assoc(X[m].sum(0), tot, nk, n)
        top = [j for j in np.argsort(-ch)[:20] if ch[j] >= chd.CHI_CRIT]
        peso = {j: ch[j] for j in range(len(voc)) if ch[j] > 0}
        sc = sorted(((sum(peso.get(j, 0) for j in np.nonzero(X[i])[0]), i) for i in np.where(m)[0]), reverse=True)[:5]
        classes.append({"classe": int(k), "titulos": nk, "pct": round(100 * nk / n, 1),
                        "formas": [[voc[j], round(float(ch[j]), 1)] for j in top], "nome": None,
                        "exemplos": [{"titulo": titulos[idx[i]]["titulo"], "veiculo": titulos[idx[i]]["veiculo"],
                                      "dia": titulos[idx[i]]["dia"], "link": titulos[idx[i]]["link"]} for _, i in sc]})
    return {"amostra": len(idx), "classificados": n, "pct_classificados": round(100 * n / len(idx), 1),
            "formas_ativas": len(voc), "min_classe": mc, "classes": classes}


def rede(docs: list[tuple[str, set]], ids: tuple[str, str]) -> tuple[nx.Graph, dict, dict]:
    n = len(docs)
    pequeno = n < 1500  # recortes curtos (7 dias, 24 horas): limiares menores
    par = {"min_titulos": max(3 if pequeno else 15, n // 600), "max_nos": 150, "min_peso": max(2 if pequeno else 5, n // 3000),
           "top_arestas": 8, "titulos": n}
    g = br.montar(docs, ids, min_videos=par["min_titulos"], max_nos=par["max_nos"], min_peso=par["min_peso"], top_arestas=par["top_arestas"])
    info = br.analisar(g)
    nl, nf = sum(1 for c, _ in docs if c == ids[0]), sum(1 for c, _ in docs if c == ids[1])
    for v in g:
        d = g.nodes[v]
        tl, tf = d["lula"] / max(1, nl), d["flavio"] / max(1, nf)
        d["lado"] = round(tl / (tl + tf), 3) if tl + tf else 0.5
    for a_, b_, d in g.edges(data=True):
        d["w_log"] = d["weight"] / math.sqrt(g.nodes[a_]["videos"] * g.nodes[b_]["videos"])
    pos = nx.spring_layout(g, weight="w_log", seed=SEMENTE, k=2.2 / math.sqrt(max(1, g.number_of_nodes())), iterations=400)
    xs, ys = [p[0] for p in pos.values()], [p[1] for p in pos.values()]
    span = max(max(xs) - min(xs), max(ys) - min(ys)) or 1
    for v, (x, y) in pos.items():
        g.nodes[v]["x"] = round(float(x - min(xs)) / span * 1000, 1)
        g.nodes[v]["y"] = round(float(y - min(ys)) / span * 1000, 1)
    for _, _, d in g.edges(data=True):
        d.pop("w_log")
    par["titulos_lula"], par["titulos_flavio"] = nl, nf
    info["layout"] = "Fruchterman-Reingold (networkx spring_layout) sobre o cosseno de Salton"
    return g, info, par


def rede_veiculos(tit: list[dict], ids: tuple[str, str], excluir: set, min_titulos: int = 10, vizinhos: int = 5,
                  min_cos: float = 0.15) -> tuple[nx.Graph, dict]:
    """Veículos ligados pela semelhança de agenda: cosseno entre os perfis TF-IDF de palavras dos títulos de cada veículo.
    Nó = veículo com min_titulos+ títulos; aresta = um dos `vizinhos` mais parecidos (cosseno ≥ min_cos)."""
    por_v: dict[str, list] = defaultdict(list)
    for t in tit:
        por_v[t["veiculo"] or t["dominio"]].append(t)
    vs = sorted(v for v, ts in por_v.items() if len(ts) >= min_titulos)
    nl = sum(1 for t in tit if t["candidate_id"] == ids[0]) or 1
    nf = sum(1 for t in tit if t["candidate_id"] == ids[1]) or 1
    perfis = {}
    for v in vs:
        c = Counter()
        for t in por_v[v]:
            c.update(x for x in bc.termos(t["titulo"], excluir) if " " not in x and not x.startswith("#"))
        perfis[v] = c
    df = Counter(w for c in perfis.values() for w in c)
    nv = len(vs)
    vec = {v: {w: n * (math.log((1 + nv) / (1 + df[w])) + 1) for w, n in c.items()} for v, c in perfis.items()}  # idf suavizado
    norma = {v: math.sqrt(sum(x * x for x in d.values())) or 1 for v, d in vec.items()}
    def cos(a, b):  # noqa: E306
        da, db = vec[a], vec[b]
        if len(da) > len(db):
            da, db = db, da
        return sum(x * db.get(w, 0) for w, x in da.items()) / (norma[a] * norma[b])
    g = nx.Graph()
    for v in vs:
        ts = por_v[v]
        l_, f_ = sum(1 for t in ts if t["candidate_id"] == ids[0]), sum(1 for t in ts if t["candidate_id"] == ids[1])
        tl, tf = l_ / nl, f_ / nf
        g.add_node(v, titulos=len(ts), lula=l_, flavio=f_, lado=round(tl / (tl + tf), 3) if tl + tf else 0.5,
                   dominio=Counter(t["dominio"] for t in ts).most_common(1)[0][0],
                   palavras=[w for w, _ in sorted(perfis[v].items(), key=lambda x: (-x[1] * math.log((1 + nv) / (1 + df[x[0]])), x[0]))[:8]])  # distintivas
    for v in vs:
        sims = sorted(((cos(v, u), u) for u in vs if u != v), reverse=True)[:vizinhos]
        for c_, u in sims:
            if c_ >= min_cos:
                g.add_edge(v, u, weight=round(c_, 4))
    g.remove_nodes_from([n for n in list(g) if g.degree(n) == 0])
    info = {"min_titulos": min_titulos, "vizinhos": vizinhos, "min_cos": min_cos, "veiculos_considerados": nv}
    if g.number_of_nodes() < 3:
        return g, info
    comms = sorted(nx.community.louvain_communities(g, weight="weight", seed=SEMENTE), key=lambda c: (-len(c), sorted(c)[0]))
    for i, c in enumerate(comms):
        for n in c:
            g.nodes[n]["comunidade"] = i
    btw = nx.betweenness_centrality(g, seed=SEMENTE)
    # componente maior: Fruchterman-Reingold (sem scipy); componentes soltos em fila na base do desenho
    comps = sorted(nx.connected_components(g), key=lambda c: (-len(c), sorted(c)[0]))
    gm = g.subgraph(comps[0]).copy()
    pos = nx.spring_layout(gm, weight="weight", seed=SEMENTE, k=2.5 / math.sqrt(max(1, gm.number_of_nodes())), iterations=500)  # sem scipy
    xs, ys = [p[0] for p in pos.values()], [p[1] for p in pos.values()]
    span = max(max(xs) - min(xs), max(ys) - min(ys)) or 1
    pos = {n: ((x - min(xs)) / span, (y - min(ys)) / span * 0.85) for n, (x, y) in pos.items()}
    resto = [n for c in comps[1:] for n in sorted(c)]
    for i, n in enumerate(resto):
        pos[n] = ((i + 0.5) / max(1, len(resto)), 0.97)
    xs, ys, span = [0.0], [0.0], 1.0
    for n, (x, y) in pos.items():
        g.nodes[n].update(x=round(float(x - min(xs)) / span * 1000, 1), y=round(float(y - min(ys)) / span * 1000, 1),
                          intermediacao=round(float(btw[n]), 4), grau=g.degree(n))
    info.update(comunidades=comms, modularidade=round(nx.community.modularity(g, comms, weight="weight"), 3))
    return g, info


def slug(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", bc.norm(s))[:30] or "na"


def main(argv=None) -> int:
    root = Path(argv[0]) if argv else Path(".")
    pasta = root / "data/trends/noticias"
    up = pasta / "universo.csv.gz"
    if not up.exists():
        print("⛔ sem universo de notícias")
        return 1
    with gzip.open(up, "rt", encoding="utf-8") as f:
        rows = list(csv.DictReader(f, delimiter=";"))
    cfg = json.loads((root / "data/config/google_busca.json").read_text(encoding="utf-8"))
    fases = json.loads((root / "data/config/trends.json").read_text(encoding="utf-8")).get("fases", [])
    agora = dt.datetime.now(dt.timezone.utc)
    for sfx, horas, rotulo in (("", None, "período todo"), ("_7d", 24 * 7, "últimos 7 dias"), ("_24h", 24, "últimas 24 horas")):
        if horas is None:
            sub = rows
        else:
            corte = (agora - dt.timedelta(hours=horas)).strftime("%Y-%m-%dT%H:%M:%SZ")
            sub = [r for r in rows if (r.get("data_publicacao") or "") >= corte]
        print(f"== {rotulo}: {len(sub)} itens")
        if not sub:
            (pasta / f"texto{sfx}.json").write_text(json.dumps({"schema_version": 1, "recorte": rotulo, "status": f"⛔ nenhuma notícia nas {rotulo}"},
                                                              ensure_ascii=False), encoding="utf-8")
            continue
        gerar(sub, pasta, sfx, rotulo, cfg, fases)
    return 0


def gerar(rows: list[dict], pasta: Path, sfx: str, rotulo: str, cfg: dict, fases: list[dict]) -> None:
    """Uma rodada completa (nuvem, CHD, redes, corpus) para um recorte do universo; arquivos com sufixo sfx."""
    pequeno = len(rows) < 1500
    nomes = {c["nome"] for c in cfg["consultas"].values()}
    excluir = {t for nm in nomes for t in bc.norm(nm).split()} | {"luiz", "inacio", "silva", "flavio"}
    ids = tuple(cfg["consultas"])
    tit = unicos(rows)
    por = defaultdict(list)
    for t in tit:
        por[t["candidate_id"]].append(t)
    out = {"schema_version": 1, "recorte": rotulo, "gerado_em_utc": now_utc(), "fonte": "Google Notícias · RSS de busca (universo diário)",
           "periodo": [min(r["dia"] for r in rows), max(r["dia"] for r in rows)] if rows else None,
           "metodo": ("Universo: tudo o que o RSS de busca do Google Notícias devolve, dia a dia, para o nome de cada candidato "
                      "(até 100 itens por dia e busca: dias que atingem o limite estão subrepresentados). Unidade: o título, uma vez "
                      "por candidato (republicações contam uma vez). Palavras sem acento, sem palavras funcionais e sem os nomes dos "
                      f"candidatos ({', '.join(sorted(excluir))}). Nuvem: títulos em que a palavra ou par de palavras aparece. CHD de "
                      f"Reinert (mesmo algoritmo dos cadernos 02 e 04): títulos com {CHD_MIN_TOKENS}+ palavras, formas em {CHD_MIN_FREQ}+ "
                      f"títulos, até {CHD_AMOSTRA} títulos por candidato, semente {SEMENTE}; sem lematização. O corpus para o IRaMuTeQ "
                      "traz todos os títulos únicos com as variáveis *cand_ *fase_ *mes_ *veic_."),
           "candidatos": {}}
    for cid in ids:
        ts = por.get(cid, [])
        dias = Counter(r["dia"] for r in rows if r["candidate_id"] == cid)
        veic = Counter(t["veiculo"] or t["dominio"] for t in ts)
        out["candidatos"][cid] = {
            "nome": cfg["consultas"][cid]["nome"], "itens": sum(dias.values()), "titulos_unicos": len(ts), "dias": len(dias),
            "dias_no_limite_do_feed": sum(1 for n in dias.values() if n >= 100), "veiculos": len(veic),
            "top_veiculos": veic.most_common(15),
            "por_fase": {f["id"]: sum(1 for t in ts if fase_de(t["dia"], fases) == f["id"]) for f in fases},
            "nuvem": bc.nuvem([t["titulo"] for t in ts], excluir, top=70, minimo=2 if pequeno else 5),
            "chd": chd_titulos(ts)}
    # rede (palavras soltas, como no caderno 04)
    docs = [(t["candidate_id"], {x for x in bc.termos(t["titulo"], excluir) if " " not in x and not x.startswith("#")}) for t in tit]
    docs = [d for d in docs if len(d[1]) >= 2]
    g, info, par = rede(docs, ids)
    for v in g:
        g.nodes[v]["cor"] = br.cor_lado(g.nodes[v]["lado"])
    comms = info.get("comunidades", [])
    rt = {"schema_version": 1, "gerado_em_utc": out["gerado_em_utc"], "parametros": par,
          "metodo": (f"Coocorrência de palavras nos títulos: nó = palavra em {par['min_titulos']}+ títulos (até {par['max_nos']}); "
                     f"aresta = as duas no mesmo título (peso mínimo {par['min_peso']}; até {par['top_arestas']} arestas mais fortes por nó). "
                     f"Comunidades: Louvain; posição: {info.get('layout')}; semente {SEMENTE}. Cor: vermelho = mais presente nas notícias "
                     "sobre Lula, verde = nas sobre Flávio, em proporção ao total de títulos de cada um."),
          "nos_total": g.number_of_nodes(), "arestas_total": g.number_of_edges(), "modularidade": info.get("modularidade"),
          "comunidades": [{"id": i, "nos": len(c), "principais": sorted(c, key=lambda n: (-g.nodes[n]["videos"], n))[:8],
                           "lado_medio": round(sum(g.nodes[n]["lado"] * g.nodes[n]["videos"] for n in c) / sum(g.nodes[n]["videos"] for n in c), 3)}
                          for i, c in enumerate(comms)],
          "nos": [{"id": n, "x": d["x"], "y": d["y"], "v": d["videos"], "l": d["lula"], "f": d["flavio"], "lado": d["lado"],
                   "c": d["comunidade"], "g": d["grau"], "b": d["intermediacao"]} for n, d in sorted(g.nodes(data=True))],
          "arestas": [[a, b, d["weight"]] for a, b, d in sorted(g.edges(data=True))]}
    (pasta / f"rede_termos{sfx}.json").write_text(json.dumps(rt, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    with open(pasta / f"rede_termos_nos{sfx}.csv", "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(["Id", "Label", "titulos", "titulos_lula", "titulos_flavio", "lado_lula", "comunidade", "grau", "intermediacao", "x", "y"])
        for n in rt["nos"]:
            w.writerow([n["id"], n["id"], n["v"], n["l"], n["f"], n["lado"], n["c"] + 1, n["g"], n["b"], n["x"], n["y"]])
    with open(pasta / f"rede_termos_arestas{sfx}.csv", "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(["Source", "Target", "Weight", "Type"])
        w.writerows([a, b, p, "Undirected"] for a, b, p in rt["arestas"])
    gx = nx.Graph()
    for n, d in g.nodes(data=True):
        r_, g_, b_ = (int(d["cor"][i:i + 2], 16) for i in (1, 3, 5))
        gx.add_node(n, label=n, titulos=d["videos"], lado_lula=d["lado"], comunidade=d["comunidade"] + 1,
                    viz={"position": {"x": d["x"], "y": -d["y"], "z": 0.0}, "size": 2 + 3 * math.sqrt(d["videos"] / 10),
                         "color": {"r": r_, "g": g_, "b": b_, "a": 1.0}})
    for a, b, d in g.edges(data=True):
        gx.add_edge(a, b, weight=d["weight"])
    nx.write_gexf(gx, pasta / f"rede_termos{sfx}.gexf")
    # rede de veículos (semelhança de agenda)
    gv, iv = rede_veiculos(tit, ids, excluir, min_titulos=3 if pequeno else 10)
    cv = iv.get("comunidades", [])
    rv = {"schema_version": 1, "gerado_em_utc": out["gerado_em_utc"],
          "metodo": (f"Rede dos veículos que publicaram: nó = veículo com {iv['min_titulos']}+ títulos sobre os candidatos "
                     f"({gv.number_of_nodes()} de {len(set(t['veiculo'] or t['dominio'] for t in tit))}); aresta = semelhança de agenda, "
                     f"cosseno entre os perfis de palavras dos títulos de cada veículo (TF-IDF), ligando cada veículo aos seus "
                     f"{iv['vizinhos']} mais parecidos com cosseno ≥ {iv['min_cos']}. Comunidades: Louvain (semente {SEMENTE}); posição: "
                     "Fruchterman-Reingold no componente principal (peso = cosseno; veículos sem ligação com ele ficam em fila na base). Tamanho = nº de títulos; cor = proporção de títulos sobre Lula (vermelho) ou Flávio "
                     "Bolsonaro (verde), relativa ao total de cada um. Mede semelhança de pauta e vocabulário, não linha editorial."),
          "parametros": {k: v for k, v in iv.items() if k != "comunidades"},
          "nos_total": gv.number_of_nodes(), "arestas_total": gv.number_of_edges(), "modularidade": iv.get("modularidade"),
          "comunidades": [{"id": i, "nos": len(c), "principais": sorted(c, key=lambda n: (-gv.nodes[n]["titulos"], n))[:8],
                           "palavras": [w for w, _ in Counter(w for n in c for w in gv.nodes[n]["palavras"]).most_common(8)],
                           "lado_medio": round(sum(gv.nodes[n]["lado"] * gv.nodes[n]["titulos"] for n in c) / sum(gv.nodes[n]["titulos"] for n in c), 3)}
                          for i, c in enumerate(cv)],
          "nos": [{"id": n, "dominio": d["dominio"], "x": d.get("x", 0), "y": d.get("y", 0), "v": d["titulos"], "l": d["lula"],
                   "f": d["flavio"], "lado": d["lado"], "c": d.get("comunidade", 0), "g": d.get("grau", 0),
                   "b": d.get("intermediacao", 0), "palavras": d["palavras"]} for n, d in sorted(gv.nodes(data=True))],
          "arestas": [[a, b, d["weight"]] for a, b, d in sorted(gv.edges(data=True))]}
    (pasta / f"rede_veiculos{sfx}.json").write_text(json.dumps(rv, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    with open(pasta / f"rede_veiculos_nos{sfx}.csv", "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(["Id", "Label", "dominio", "titulos", "titulos_lula", "titulos_flavio", "lado_lula", "comunidade", "grau", "intermediacao", "palavras", "x", "y"])
        for n in rv["nos"]:
            w.writerow([n["id"], n["id"], n["dominio"], n["v"], n["l"], n["f"], n["lado"], n["c"] + 1, n["g"], n["b"], " ".join(n["palavras"]), n["x"], n["y"]])
    with open(pasta / f"rede_veiculos_arestas{sfx}.csv", "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(["Source", "Target", "Weight", "Type"])
        w.writerows([a, b, p, "Undirected"] for a, b, p in rv["arestas"])
    gx = nx.Graph()
    for n, d in gv.nodes(data=True):
        r_, g_, b_ = (int(br.cor_lado(d["lado"])[i:i + 2], 16) for i in (1, 3, 5))
        gx.add_node(n, label=n, dominio=d["dominio"], titulos=d["titulos"], titulos_lula=d["lula"], titulos_flavio=d["flavio"],
                    lado_lula=d["lado"], comunidade=d.get("comunidade", 0) + 1,
                    viz={"position": {"x": d.get("x", 0), "y": -d.get("y", 0), "z": 0.0}, "size": 2 + 3 * math.sqrt(d["titulos"] / 5),
                         "color": {"r": r_, "g": g_, "b": b_, "a": 1.0}})
    for a, b, d in gv.edges(data=True):
        gx.add_edge(a, b, weight=d["weight"])
    nx.write_gexf(gx, pasta / f"rede_veiculos{sfx}.gexf")
    out["rede_veiculos"] = {"nos": rv["nos_total"], "arestas": rv["arestas_total"], "comunidades": len(cv), "modularidade": rv["modularidade"]}
    print(f"rede de veículos: {rv['nos_total']} veículos, {rv['arestas_total']} ligações, {len(cv)} comunidades, modularidade {rv['modularidade']}")
    # corpus IRaMuTeQ e lista de títulos únicos
    with open(pasta / f"corpus_iramuteq{sfx}.txt", "w", encoding="utf-8") as f:
        for t in sorted(tit, key=lambda t: (t["candidate_id"], t["dia"], int(t["posicao"]))):
            txt = re.sub(r"[*\n\r]", " ", t["titulo"]).strip()
            f.write(f"**** *cand_{SLUG.get(t['candidate_id'], t['candidate_id'])} *fase_{fase_de(t['dia'], fases)} "
                    f"*mes_{t['dia'][5:7]} *veic_{slug(t['veiculo'] or t['dominio'])}\n{txt}\n")
    with open(pasta / f"titulos_unicos{sfx}.csv", "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, ["candidate_id", "dia", "posicao", "titulo", "veiculo", "dominio", "link", "repeticoes"],
                           delimiter=";", lineterminator="\n", extrasaction="ignore")
        w.writeheader()
        w.writerows(sorted(tit, key=lambda t: (t["candidate_id"], t["dia"], int(t["posicao"]))))
    out["rede"] = {"nos": rt["nos_total"], "arestas": rt["arestas_total"], "comunidades": len(comms), "modularidade": rt["modularidade"]}
    (pasta / f"texto{sfx}.json").write_text(json.dumps(out, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    for c in out["candidatos"].values():
        k = c["chd"].get("classes")
        print(f"{c['nome']}: {c['itens']} itens, {c['titulos_unicos']} títulos únicos, {c['veiculos']} veículos, "
              f"{c['dias_no_limite_do_feed']} dias no limite; CHD {len(k) if k else c['chd'].get('status')} classes")
    print(f"rede: {rt['nos_total']} nós, {rt['arestas_total']} arestas, {len(comms)} comunidades, modularidade {rt['modularidade']}")


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
