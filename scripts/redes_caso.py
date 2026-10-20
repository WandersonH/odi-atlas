"""Padrão de análise dos casos (pedido do usuário em 20/10/2026): rede de circulação, rede de palavras e de respostas
nos comentários, e classes no estilo IRaMuTeQ (CHD de Reinert). Pessoas comuns nunca aparecem com nome no público.

- circulacao(): quem publicou × por onde o caso circulou (termo de busca/hashtag ou veículo). Nós: canais do YouTube,
  veículos de imprensa, contas do TikTok; ligados ao termo que os trouxe. Peso = visualizações (ou 1 por notícia).
  Contas/canais abaixo de MIN_PUBLICO aparecem como código (P0001…).
- palavras(): coocorrência de palavras no mesmo comentário (comunidades por modularidade).
- respostas(): quem responde a quem nos comentários; autores sempre como código (A0001…).
- classes(): CHD de Reinert nos comentários (só formas e percentuais no público; trechos ficam no privado).
- corpus_iramuteq(): texto no formato do IRaMuTeQ (privado).
"""
from __future__ import annotations

import re
from collections import Counter, defaultdict
from pathlib import Path

import chd_reinert as cr

MIN_PUBLICO = 10000


def _layout(G, peso="weight") -> dict:
    """Comunidades por modularidade; posições por componente (cada componente ganha uma área própria, em grade,
    proporcional ao tamanho) — o spring_layout do grafo inteiro joga componentes pequenos para os cantos."""
    import math
    import networkx as nx
    com = {n: i for i, c in enumerate(nx.community.greedy_modularity_communities(G, weight=peso)) for n in c} if G.number_of_edges() else {}
    comps = sorted(nx.connected_components(G), key=len, reverse=True)
    pos, x0, y0, linha_h, largura = {}, 0.0, 0.0, 0.0, 4.0
    for comp in comps:
        H = G.subgraph(comp)
        lado = max(0.35, math.sqrt(len(comp)) / math.sqrt(max(1, len(comps[0]))) * 2.0)
        p = nx.spring_layout(H, seed=7, weight=peso, k=1.2 / math.sqrt(max(1, len(comp)))) if len(comp) > 1 else {next(iter(comp)): (0.0, 0.0)}
        if x0 + lado > largura:
            x0, y0, linha_h = 0.0, y0 + linha_h + 0.15, 0.0
        for n, (x, y) in p.items():
            pos[n] = (x0 + (x + 1) / 2 * lado, y0 + (y + 1) / 2 * lado)
        x0 += lado + 0.15
        linha_h = max(linha_h, lado)
    return com, pos


def gexf(nos: dict, arestas: dict, caminho: Path, dirigida: bool = False) -> None:
    esc = lambda s: str(s).replace("&", "&amp;").replace("<", "&lt;").replace('"', "&quot;")  # noqa: E731
    l = ['<?xml version="1.0" encoding="UTF-8"?>', '<gexf xmlns="http://gexf.net/1.3" version="1.3">',
         f'<graph defaultedgetype="{"directed" if dirigida else "undirected"}">',
         '<attributes class="node"><attribute id="0" title="tipo" type="string"/><attribute id="1" title="peso" type="double"/></attributes>', "<nodes>"]
    for k, v in nos.items():
        l.append(f'<node id="{esc(k)}" label="{esc(v.get("rotulo", k))}"><attvalues><attvalue for="0" value="{esc(v.get("tipo", ""))}"/>'
                 f'<attvalue for="1" value="{v.get("n", 0)}"/></attvalues></node>')
    l.append("</nodes><edges>")
    for i, ((a, b), w) in enumerate(arestas.items()):
        l.append(f'<edge id="{i}" source="{esc(a)}" target="{esc(b)}" weight="{w}"/>')
    l += ["</edges>", "</graph>", "</gexf>"]
    caminho.write_text("\n".join(l), encoding="utf-8")


def _desenho(nos: dict, arestas: dict, top: int = 90) -> dict | None:
    import networkx as nx
    G = nx.Graph()
    for (a, b), w in arestas.items():
        G.add_edge(a, b, weight=w)
    if not G.number_of_nodes():
        return None
    manter = sorted(G.nodes, key=lambda k: -(nos.get(k, {}).get("n") or 0))[:top]
    H = G.subgraph(manter).copy()
    H.remove_nodes_from([n for n in list(H.nodes) if H.degree(n) == 0])
    if not H.number_of_nodes():
        return None
    com, pos = _layout(H)
    return {"nos": [{"id": n, "rotulo": nos.get(n, {}).get("rotulo", n), "tipo": nos.get(n, {}).get("tipo", ""), "n": nos.get(n, {}).get("n") or 0,
                     "grupo": com.get(n, 0), "x": round(float(pos[n][0]), 4), "y": round(float(pos[n][1]), 4)} for n in H.nodes],
            "arestas": [[a, b, d["weight"]] for a, b, d in H.edges(data=True)][:700],
            "total_nos": len(nos), "total_arestas": len(arestas), "comunidades": len(set(com.values())) if com else 0}


def circulacao(videos: list[dict], noticias: list[dict], tiktok: list[dict]) -> tuple[dict, dict, dict | None]:
    nos, ar, codigos = {}, Counter(), {}

    def fonte(chave: str, nome: str, tipo: str, publico: bool) -> str:
        if not publico:
            codigos.setdefault(chave, f"P{len(codigos) + 1:04d}")
            nid, rot = codigos[chave], f"perfil pequeno {codigos[chave]}"
        else:
            nid, rot = chave, nome
        nos.setdefault(nid, {"rotulo": rot, "tipo": tipo, "n": 0})
        return nid

    for v in videos:
        s = fonte(f"yt:{v.get('canal_id')}", v.get("canal") or "?", "canal do YouTube", (v.get("inscritos") or 0) >= MIN_PUBLICO)
        t = f"busca: {v.get('consulta') or '?'}"
        nos.setdefault(t, {"rotulo": t, "tipo": "termo", "n": 0})
        peso = v.get("visualizacoes") or 0
        nos[s]["n"] += peso
        nos[t]["n"] += peso
        ar[(s, t)] += max(1, peso)
    for x in noticias:
        s = fonte(f"imprensa:{x.get('veiculo')}", x.get("veiculo") or "?", "veículo de imprensa", True)
        t = f"notícia: {x.get('consulta') or '?'}"
        nos.setdefault(t, {"rotulo": t, "tipo": "termo", "n": 0})
        nos[s]["n"] += 1
        nos[t]["n"] += 1
        ar[(s, t)] += 1
    for r in tiktok:
        seg = int(r["seguidores"]) if str(r.get("seguidores") or "").isdigit() else 0
        s = fonte(f"tt:{r.get('conta')}", "@" + (r.get("conta") or "?"), "conta do TikTok", seg >= MIN_PUBLICO or str(r.get("verificada")) == "1")
        for termo in (r.get("termo") or "").split("|"):
            if not termo:
                continue
            t = f"TikTok {termo}"
            nos.setdefault(t, {"rotulo": t, "tipo": "termo", "n": 0})
            v = int(r["visualizacoes"]) if str(r.get("visualizacoes") or "").isdigit() else 0
            nos[s]["n"] += v
            nos[t]["n"] += v
            ar[(s, t)] += max(1, v)
    return nos, dict(ar), _desenho(nos, ar)


def palavras(textos: list[str], minimo: int = 5, top: int = 80) -> tuple[dict, dict, dict | None]:
    docs = [set(cr.tokens(t)) for t in textos]
    df = Counter(t for d in docs for t in d)
    voc = {t for t, n in df.items() if n >= minimo}
    ar = Counter()
    for d in docs:
        ws = sorted(d & voc)
        for i, a in enumerate(ws):
            for b in ws[i + 1:]:
                ar[(a, b)] += 1
    ar = Counter({k: w for k, w in ar.items() if w >= 3})
    nos = {t: {"rotulo": t, "tipo": "palavra", "n": df[t]} for t in voc}
    return nos, dict(ar), _desenho(nos, ar, top)


def respostas(rows: list[dict]) -> tuple[dict, dict, dict]:
    autor = {r["comment_id"]: (r.get("autor_canal") or r.get("autor_nome") or "?") for r in rows}
    cod = {}
    c = lambda a: cod.setdefault(a, f"A{len(cod) + 1:04d}")  # noqa: E731
    ar = Counter()
    for r in rows:
        if r.get("tipo") == "resposta" and r.get("parent_id") in autor:
            a, b = autor[r["comment_id"]], autor[r["parent_id"]]
            if a != b:
                ar[(c(a), c(b))] += 1
    grau_in = Counter()
    for (a, b), w in ar.items():
        grau_in[b] += w
    grau = Counter()
    for (a, b), w in ar.items():
        grau[a] += w
        grau[b] += w
    # peso do nó = respostas dadas + recebidas (para o desenho escolher as conversas maiores, não só os mais respondidos)
    nos = {k: {"rotulo": k, "tipo": "autor (código)", "n": grau.get(k, 0)} for k in cod.values()}
    resumo = {"autores_na_rede": len(cod), "respostas_entre_autores": int(sum(ar.values())), "pares": len(ar),
              "mais_respondidos": [[k, n] for k, n in grau_in.most_common(10)],
              "concentracao_top10_pct": round(100 * sum(n for _, n in grau_in.most_common(10)) / sum(grau_in.values()), 1) if grau_in else None}
    return nos, dict(ar), {**resumo, "desenho": _desenho(nos, ar, 150)}


def classes(textos: list[str], anos: list[str]) -> dict | None:
    import numpy as np
    if len(textos) < 100:
        return None
    X, voc = cr.matriz(textos)
    n_at = int((X.sum(1) > 0).sum())
    rot, arvore = cr.chd(X, k=6, min_classe=max(cr.MIN_CLASSE, int(0.05 * n_at)))
    ok = rot > 0
    if not ok.any():
        return None
    tot = X[ok].sum(0)
    anos = np.array(anos)
    out = []
    for k in sorted(set(rot[ok].tolist())):
        m = rot == k
        ch = cr.chi2_assoc(X[m].sum(0), tot, int(m.sum()), int(ok.sum()))
        idx = [j for j in np.argsort(-ch) if ch[j] >= cr.CHI_CRIT][:15]
        out.append({"classe": int(k), "segmentos": int(m.sum()), "pct": round(100 * m.sum() / ok.sum(), 1),
                    "formas": [[voc[j], round(float(ch[j]), 1)] for j in idx],
                    "por_ano": {a: int((m & (anos == a)).sum()) for a in sorted(set(anos.tolist()))}})
    return {"comentarios": len(textos), "classificados": int(ok.sum()), "pct_classificados": round(100 * ok.sum() / len(textos), 1), "classes": out,
            "nota": "CHD de Reinert do Atlas (chd_reinert.py), um comentário = um segmento; sem lematização. Os nomes das classes são dados "
                    "por quem lê as formas. O corpus no formato do IRaMuTeQ (com *video_, *ano_ e *tipo_) fica no repositório privado."}


def corpus_iramuteq(rows: list[dict]) -> str:
    l = []
    for r in rows:
        tx = re.sub(r"[*\-$]", " ", r.get("texto") or "").strip()
        if tx:
            l.append(f"**** *video_{re.sub(r'[^A-Za-z0-9]', '', r['video_id'])} *ano_{(r.get('publicado_em') or '0000')[:4]} *tipo_{r.get('tipo')}\n{tx}\n")
    return "\n".join(l)
