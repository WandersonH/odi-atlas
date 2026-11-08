#!/usr/bin/env python3
"""Bloco único de redes de cada caso: desenho interativo + tipo + métricas + corpus por nó (respeitando a anonimização).

Pedido do responsável (07/11/2026, 23h04): "você criou 2 campos de redes, ideal seria confluir" e "meu esquema de rede
favorito é aquele dinâmico que montou no YouTube, onde clico e consigo ver o corpus presente, mantendo nossa anonimização".

Para cada GEXF de data/casos/<id>/ (exceto vazios):
- desenho: os até 220 nós de maior grau ponderado do componente gigante, ForceAtlas 2 (networkx, LinLog, gravidade forte,
  semente 42) e comunidades de Louvain calculadas no gigante inteiro (semente 42), com as 6 maiores resumidas;
- tipo da rede (o que é nó, aresta e para que serve) e métricas (de data/redes/estatisticas_redes.csv e, quando houver,
  da validação no Gephi Toolkit, data/redes/gephi/gephi_resumo.csv);
- corpus por nó, sem quebrar a anonimização:
  · hashtag ou conta pública (10 mil+ seguidores ou perfil declarado ao TSE): até 5 publicações de contas públicas com
    trecho (220 caracteres), data e link, e a contagem total por rede;
  · publicações de pessoas comuns: só contagem (o texto fica no repositório privado);
  · canal do YouTube com 10 mil+ inscritos e veículo de imprensa: títulos e links dos vídeos/notícias do caso;
  · palavra, autor em código e perfil pequeno: só números e vizinhos (com quem aparece/conversa).
Entradas: data/casos/<id>/*.gexf, busca.json, config; ODI_INTERNO_DIR/casos/<id>/itens.csv.gz e busca_coleta.json.
Saída: data/casos/<id>/redes_viewer.json.
Uso: ODI_INTERNO_DIR=… python scripts/build_redes_viewer.py [--caso 001]
"""
from __future__ import annotations

import csv
import glob
import gzip
import json
import os
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

import networkx as nx

sys.path.insert(0, str(Path(__file__).resolve().parent))
from build_redes_pagina import tipo_de  # noqa: E402
from net import now_utc  # noqa: E402

MIN = 10000
TOPN = 220
ORDEM = ["rede", "rede_ofensiva", "rede_candidatos", "rede_circulacao", "rede_palavras_comentarios", "rede_palavras_comentarios_posts",
         "rede_respostas_comentarios", "rede_respostas_comentarios_posts"]
PRIVADO = re.compile(r"^(perfil pequeno|[ACPV]\d{4,5}$)", re.I)


# Caso 020 (criança): o Atlas não identifica a criança. Apelido, variações e condição de saúde citada pela imprensa saem de
# rótulos, trechos e títulos do visualizador (os termos continuam só como termo de busca, no coletor).
MASCARA_CASO = {"020": re.compile(r"[#@]?[\w.]*(?:m+a+t+h?e+u+s+|bomb[oõ]n?s?|bombom\w*|autis\w*)[\w.]*", re.I)}
ROT_CRIANCA = "[referência à criança]"


def num(v) -> int:
    try:
        return int(float(v))
    except (TypeError, ValueError):
        return 0


def ler_csv(p: str) -> list[dict]:
    return list(csv.DictReader(open(p, encoding="utf-8"))) if os.path.exists(p) else []


def desenho(g: nx.Graph) -> dict:
    u = nx.Graph()
    for a, b, d in g.edges(data=True):
        if a == b:
            continue
        w = float(d.get("weight", 1) or 1)
        u.add_edge(a, b, weight=u[a][b]["weight"] + w if u.has_edge(a, b) else w)
    if not u.number_of_edges():
        return {}
    gc = u.subgraph(max(nx.connected_components(u), key=len)).copy()
    coms = sorted(nx.community.louvain_communities(gc, weight="weight", seed=42), key=len, reverse=True)
    com_de = {v: i for i, c in enumerate(coms) for v in c}
    grau = dict(gc.degree(weight="weight"))
    top = sorted(gc.nodes, key=lambda v: -grau[v])[:TOPN]
    s = gc.subgraph(top).copy()
    if s.number_of_nodes() > 1:
        pos = nx.forceatlas2_layout(s, max_iter=400, scaling_ratio=4.0, strong_gravity=True, weight="weight", seed=42)
        pos = {k: (float(v[0]), float(v[1])) for k, v in pos.items()}
        if any(v != v for p in pos.values() for v in p):  # NaN: volta ao spring (mesma semente)
            pos = {k: (float(v[0]), float(v[1])) for k, v in nx.spring_layout(s, seed=42, weight="weight").items()}
    else:
        pos = {top[0]: (0.0, 0.0)}
    xs = [p[0] for p in pos.values()]
    ys = [p[1] for p in pos.values()]
    x0, x1, y0, y1 = min(xs), max(xs), min(ys), max(ys)
    nx_ = lambda v, a, b: round(1000 * (v - a) / ((b - a) or 1), 1)  # noqa: E731
    nos = [{"id": v, "rotulo": str(g.nodes[v].get("label") or v), "tipo": str(g.nodes[v].get("tipo") or ""), "g": round(float(grau[v]), 2),
            "c": com_de[v], "x": nx_(pos[v][0], x0, x1), "y": nx_(pos[v][1], y0, y1),
            "v": [[str(g.nodes[m].get("label") or m), round(float(gc[v][m]["weight"]), 2)] for m in sorted(gc[v], key=lambda m: -gc[v][m]["weight"])[:8]]}
           for v in top]  # v = vizinhos na rede inteira (o desenho só tem as arestas entre os nós desenhados)
    ar = sorted(([a, b, round(d["weight"], 2)] for a, b, d in s.edges(data=True)), key=lambda e: -e[2])[:1500]
    rot = lambda v: str(g.nodes[v].get("label") or v)  # noqa: E731
    resumo = [{"id": i, "nos": len(c), "pct": round(100 * len(c) / gc.number_of_nodes(), 2),
               "principais": [rot(v) for v in sorted(c, key=lambda v: -grau[v]) if not PRIVADO.match(rot(v))][:5]} for i, c in enumerate(coms[:6])]
    return {"nos": nos, "arestas": ar, "comunidades": resumo, "nos_no_desenho": len(nos), "nos_no_gigante": gc.number_of_nodes(),
            "nos_total": g.number_of_nodes(), "arestas_total": g.number_of_edges()}


def mascara(txt: str, tse: set, rede: str | None) -> str:
    """@ de quem não é perfil declarado ao TSE vira "@…" no trecho público (a pessoa citada pode ser comum)."""
    return re.sub(r"@([\w.]{2,30})", lambda m: m.group(0) if (rede, m.group(1).lower()) in tse else "@…", txt)


def corpus_posts(itens: list[dict], tse: set) -> tuple[dict, dict]:
    """hashtag ou conta pública → publicações; só contas públicas trazem texto."""
    por_no = defaultdict(lambda: {"n": 0, "por_rede": Counter(), "pequenos": 0, "pecas": []})

    def publico(r):
        return num(r.get("seguidores")) >= MIN or (r.get("rede"), (r.get("conta") or "").lower()) in tse

    for r in itens:
        pub = publico(r)
        chaves = {"#" + t.lower() for t in re.findall(r"#(\w+)", r.get("texto") or "")}
        chaves |= {t.lower() for t in (r.get("termo") or "").split("|") if t.startswith("#")}
        chaves |= {"@" + t.lower() for t in re.findall(r"@([\w.]{2,30})", r.get("texto") or "")}
        if pub:
            chaves.add(f"{r.get('rede')}:{r.get('conta')}")
        for k in chaves:
            c = por_no[k]
            c["n"] += 1
            c["por_rede"][r.get("rede")] += 1
            if not pub:
                c["pequenos"] += 1
            elif len(c["pecas"]) < 40:
                c["pecas"].append({"rede": r.get("rede"), "conta": "@" + (r.get("conta") or ""), "seguidores": num(r.get("seguidores")),
                                   "data": (r.get("publicado_em") or "")[:10], "trecho": mascara((r.get("texto") or "")[:220], tse, r.get("rede")), "url": r.get("url"),
                                   "alcance": num(r.get("visualizacoes")) or num(r.get("curtidas"))})
    out = {}
    for k, c in por_no.items():
        out[k] = {"n": c["n"], "por_rede": dict(c["por_rede"]), "pequenos": c["pequenos"],
                  "pecas": sorted(c["pecas"], key=lambda p: -p["alcance"])[:5]}
    return out, {}


def sanitizar(out: dict, cid: str, publicos: set, tse: set) -> None:
    """Rótulo de @ citado só aparece se a conta for pública (10 mil+ no caso ou declarada ao TSE); senão vira "@… (perfil citado)".
    No 020, tudo o que remete à criança vira ROT_CRIANCA."""
    rx = MASCARA_CASO.get(cid)

    def rot(t: str) -> str:
        t = str(t)
        if rx and rx.search(t):
            return ROT_CRIANCA
        if t.startswith("@") and t[1:].lower() not in publicos:
            return "@… (perfil citado)"
        return t

    def txt(t):
        return rx.sub("[…]", t) if (rx and isinstance(t, str)) else t

    for r in out["redes"]:
        if rx:  # ids também (o id do GEXF é o próprio termo)
            novo = {n["id"]: f"crianca_{i}" for i, n in enumerate(r["desenho"]["nos"]) if rx.search(n["id"])}
            for n in r["desenho"]["nos"]:
                n["id"] = novo.get(n["id"], n["id"])
            r["desenho"]["arestas"] = [[novo.get(a, a), novo.get(b, b), w] for a, b, w in r["desenho"]["arestas"]]
            r["corpus"] = {novo.get(k, k): v for k, v in r["corpus"].items()}
        for n in r["desenho"]["nos"]:
            n["rotulo"] = rot(n["rotulo"])
            n["v"] = [[rot(x), w] for x, w in n.get("v", [])]
        for c in r["desenho"].get("comunidades", []):
            c["principais"] = list(dict.fromkeys(x for x in map(rot, c["principais"]) if x not in (ROT_CRIANCA, "@… (perfil citado)")))
        for k, c in r["corpus"].items():
            if rx and c.get("pecas"):  # conta cujo nome remete à criança: a peça sai (fica na contagem)
                c["pecas"] = [x for x in c["pecas"] if not rx.search(x["conta"] + " " + str(x.get("url")))]
            for x in c.get("pecas", []):
                x["trecho"] = txt(x["trecho"])
            for x in c.get("itens", []):
                x["titulo"] = txt(x["titulo"])
            if k.startswith("crianca_"):  # nó que remete à criança: só contagem, sem texto
                c.pop("pecas", None), c.pop("itens", None)
                c["tipo"] = "contagem"


def main(argv=None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    so = argv[argv.index("--caso") + 1] if "--caso" in argv else None
    interno = os.environ.get("ODI_INTERNO_DIR") or ""
    est = {(r["caso"], r["rede"]): r for r in ler_csv("data/redes/estatisticas_redes.csv")}
    gep = {(r["caso"], r["rede"]): r for r in ler_csv("data/redes/gephi/gephi_resumo.csv")}
    sys.path.insert(0, "scripts")
    from build_casos import declarados
    tse = {k for k in declarados(Path("."))}
    feitos = 0
    for pasta in sorted(glob.glob("data/casos/*/")):
        cid = Path(pasta).name
        if so and cid != so:
            continue
        gexfs = [f for f in glob.glob(pasta + "*.gexf") if os.path.getsize(f) > 400 and not f.endswith("_dinamica.gexf")]
        if not gexfs:
            continue
        itens = []
        f_it = os.path.join(interno, "casos", cid, "itens.csv.gz")
        if interno and os.path.exists(f_it):
            itens = list(csv.DictReader(gzip.open(f_it, "rt", encoding="utf-8"), delimiter=";"))
        cp, _ = corpus_posts(itens, tse) if itens else ({}, {})
        cp_of = {}
        if itens and os.path.exists(os.path.join(pasta, "rede_ofensiva.gexf")):  # corpus da rede ofensiva: só publicações marcadas
            from build_casos import marcas_intolerancia
            mk = marcas_intolerancia(cid) or {}
            cp_of, _ = corpus_posts([r for r in itens if mk.get(r.get("item_id"))], tse)
        publicos = {(r.get("conta") or "").lower() for r in itens if num(r.get("seguidores")) >= MIN} | {c for _, c in tse}
        # canais e veículos: títulos públicos (YouTube do caso; notícias do caso)
        videos = defaultdict(list)
        f_bc = os.path.join(interno, "casos", cid, "busca_coleta.json")
        if interno and os.path.exists(f_bc):
            for v in ((json.load(open(f_bc, encoding="utf-8")).get("youtube") or {}).get("videos") or []):
                if num(v.get("inscritos")) >= MIN:
                    videos["yt:" + str(v.get("canal_id"))].append({"titulo": v.get("titulo"), "url": f"https://www.youtube.com/watch?v={v.get('id')}",
                                                                   "data": (v.get("publicado_em") or "")[:10], "alcance": num(v.get("visualizacoes"))})
        bj = Path(pasta) / "busca.json"
        if bj.exists():
            for x in json.load(open(bj, encoding="utf-8")).get("noticias") or []:
                videos["imprensa:" + str(x.get("veiculo"))].append({"titulo": x.get("titulo"), "url": x.get("link"), "data": (x.get("data_publicacao") or "")[:10], "alcance": 0})
        redes = []
        for f in sorted(gexfs, key=lambda p: (ORDEM.index(Path(p).stem) if Path(p).stem in ORDEM else 99, p)):
            rede = Path(f).stem
            try:
                g = nx.read_gexf(f)
            except Exception as e:
                print(f"⛔ {f}: {e}")
                continue
            d = desenho(g)
            if not d:
                continue
            fd = f[:-5] + "_dinamica.gexf" if rede != "rede" else os.path.join(pasta, "rede_dinamica.gexf")
            dinamica = None
            if os.path.exists(fd):  # 08/11/2026: data da 1ª publicação de cada nó, para o controle de data da página
                try:
                    gd = nx.read_gexf(fd)
                    d0 = {v: (gd.nodes[v].get("start") or "")[:10] for v in gd.nodes}
                    for n in d["nos"]:
                        n["d"] = d0.get(n["id"]) or None
                    ds = sorted(x for x in d0.values() if x)
                    dinamica = {"gexf": fd, "de": ds[0] if ds else None, "ate": ds[-1] if ds else None}
                except Exception as e:  # noqa: BLE001
                    print(f"⛔ {fd}: {e}")
            nome, no, aresta, serve = tipo_de(rede)
            corpus = {}
            for n in d["nos"]:
                k = n["id"]
                rot = n["rotulo"]
                if PRIVADO.match(rot):
                    continue
                if k in videos:
                    corpus[k] = {"tipo": "titulos", "itens": sorted(videos[k], key=lambda x: -x["alcance"])[:5], "n": len(videos[k])}
                    continue
                chave = k.lower() if k.startswith("#") else ("@" + rot.lstrip("@").lower() if rot.startswith("@") and k.startswith("cand:") is False and ":" not in k else k)
                if k.startswith("cand:"):
                    chave = None
                if k.startswith("tt:"):  # circulação: conta pública do TikTok → as publicações dela no caso
                    chave = "tiktok:" + k[3:]
                fonte = cp_of if rede == "rede_ofensiva" else cp
                if chave and chave in fonte:
                    corpus[k] = {"tipo": "posts", **fonte[chave]}
            m = est.get((cid, rede), {})
            gg = gep.get((cid, rede), {})
            redes.append({"rede": rede, "tipo": nome, "no": no, "aresta": aresta, "serve_para": serve, "gexf": f"data/casos/{cid}/{rede}.gexf", "dinamica": dinamica,
                          "metricas": {k: m.get(k) for k in ("nos", "arestas", "dirigida", "densidade", "componentes", "nos_maior_componente",
                                                              "pct_nos_maior_componente", "modularidade_q", "gc_modularidade_q", "gc_comunidades_1pct_ou_mais",
                                                              "gc_pct_maior", "gc_pct_segunda", "gc_polarizacao_ei_2_maiores", "assortatividade_grau",
                                                              "reciprocidade", "clustering_medio") if m.get(k) not in (None, "")},
                          "gephi": {k: gg.get(k) for k in ("gc_modularidade_q", "gc_comunidades", "separacao_openord_2_maiores", "separacao_openord_edgecut0",
                                                           "estabilidade_fa2_corr_distancias_top50", "pct_arestas_cruzando", "inferencia_estatistica_classes") if gg.get(k)} or None,
                          "imagens": {k: f"data/redes/gephi/{cid}_{rede}_{k}.png" for k in ("comparacao", "forceatlas2", "openord", "fruchterman", "yifanhu")
                                      if os.path.exists(f"data/redes/gephi/{cid}_{rede}_{k}.png")},
                          "desenho": d, "corpus": corpus})
        out = {"gerado_em_utc": now_utc(), "caso": cid, "redes": redes,
               "anonimizacao": "Pessoas comuns (menos de 10 mil seguidores, sem perfil declarado ao TSE) aparecem em código e sem texto; "
                               "o corpus mostrado ao clicar traz só publicações de contas públicas, títulos de canais com 10 mil+ inscritos e de veículos de imprensa. "
                               "As demais publicações entram só na contagem; o texto fica no repositório privado.",
               "universo": "Amostra lida no caso; universo das plataformas ⛔ não informado."}
        sanitizar(out, cid, publicos, tse)
        (Path(pasta) / "redes_viewer.json").write_text(json.dumps(out, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
        feitos += 1
        print(f"{cid}: {len(redes)} redes, corpus em {sum(len(r['corpus']) for r in redes)} nós")
    print(f"redes_viewer: {feitos} casos")
    return 0


if __name__ == "__main__":
    sys.exit(main())
