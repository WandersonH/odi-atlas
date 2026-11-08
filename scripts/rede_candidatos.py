#!/usr/bin/env python3
"""Rede da influência dos candidatos na circulação dos casos (para o Gephi).

Pedido do responsável (07/11/2026, 21h46): "gere uma rede Gephi para entender a influência na circulação dos candidatos".

Nós e arestas (dirigidas):
- candidato → caso: o candidato publicou sobre o caso numa conta declarada ao TSE (data/casos/<id>/candidatos.json).
  Peso = nº de publicações; atributos curtidas (soma) e posição codificada, quando houver.
- conta → candidato: uma conta citou o @ de um candidato em posts lidos nos casos (itens privados). Peso = nº de citações.
  Mede quem puxa o candidato para a conversa: o candidato pode circular muito sem publicar nada sobre o caso.
Candidatos (todos os cargos, contas declaradas ao TSE) aparecem com nome, partido, cargo e UF. As demais contas aparecem com
nome só com 10 mil+ seguidores; as outras ficam em código (P00001…), como nas redes públicas.
Universo: as publicações e citações são as da amostra de cada caso (⛔ universo das plataformas não informado).
Entradas: data/casos/*/candidatos.json; ODI_INTERNO_DIR/casos/*/itens.csv.gz; data/tse/redes_sociais_candidatos_2026.csv.gz.
Saídas: data/redes/rede_candidatos.gexf e data/redes/rede_candidatos_resumo.csv (um candidato por linha).
Uso: ODI_INTERNO_DIR=… python scripts/rede_candidatos.py
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
from xml.sax.saxutils import escape

sys.path.insert(0, str(Path(__file__).resolve().parent))
from collect_primeiro_turno import perfil_de  # noqa: E402
from net import now_utc  # noqa: E402

MIN = 10000


def num(v) -> int:
    try:
        return int(float(v))
    except (TypeError, ValueError):
        return 0


def main() -> int:
    root = Path(".")
    cfg = {c["id"]: c for c in json.loads((root / "data/config/casos.json").read_text(encoding="utf-8"))["casos"]}
    # contas declaradas ao TSE → candidato (todos os cargos)
    handle = {}
    info = {}
    for r in csv.DictReader(gzip.open(root / "data/tse/redes_sociais_candidatos_2026.csv.gz", "rt", encoding="utf-8"), delimiter=";"):
        p = perfil_de(r.get("PLATAFORMA", ""), r.get("DS_URL", ""))
        if not p or p[0] not in ("x", "instagram", "tiktok"):
            continue
        nome = (r.get("NM_URNA_CANDIDATO") or "").title()
        handle[(p[0], p[1].lower().lstrip("@"))] = nome
        info.setdefault(nome, {"partido": r.get("SG_PARTIDO", ""), "cargo": (r.get("DS_CARGO") or "").title(), "uf": r.get("SG_UF_CAND") or r.get("SG_UF", "")})
    nos, ar = {}, Counter()
    curt = Counter()
    posicao = {}

    def no(k, rot, tipo, **at):
        nos.setdefault(k, {"label": rot, "tipo": tipo, **at})
        return k

    # 1) candidato → caso
    pubs = Counter()
    for f in sorted(glob.glob("data/casos/*/candidatos.json")):
        cid = Path(f).parent.name
        d = json.loads(Path(f).read_text(encoding="utf-8"))
        for x in d.get("candidatos", []):
            nome = x["candidato"].title()
            c = no(f"cand:{nome}", nome, "candidato", partido=x.get("partido", ""), cargo=(x.get("cargo") or "").title(), uf=x.get("uf", ""),
                   situacao=x.get("situacao", ""))
            k = no(f"caso:{cid}", f"Caso {cid}: {cfg.get(cid, {}).get('titulo', '')[:60]}", "caso")
            for p in x.get("publicacoes", []):
                ar[(c, k)] += 1
                curt[(c, k)] += num(p.get("curtidas"))
                pubs[nome] += 1
            if x.get("posicao") and x["posicao"] != "nao_codificada":
                posicao[(c, k)] = x["posicao"]
    # 2) conta → candidato (citações do @ do candidato nos posts lidos)
    interno = os.environ.get("ODI_INTERNO_DIR")
    citacoes, codigo = Counter(), {}
    lidos = 0
    if interno:
        for f in sorted(glob.glob(os.path.join(interno, "casos/*/itens.csv.gz"))):
            for r in csv.DictReader(gzip.open(f, "rt", encoding="utf-8"), delimiter=";"):
                lidos += 1
                rede = r.get("rede")
                for h in set(re.findall(r"@([\w.]{2,30})", r.get("texto") or "")):
                    nome = handle.get((rede, h.lower()))
                    if not nome or (rede, (r.get("conta") or "").lower()) in handle and handle[(rede, (r.get("conta") or "").lower())] == nome:
                        continue
                    seg = num(r.get("seguidores"))
                    conta = r.get("conta") or "?"
                    if (rede, conta.lower()) in handle:
                        a = no(f"cand:{handle[(rede, conta.lower())]}", handle[(rede, conta.lower())], "candidato", **info.get(handle[(rede, conta.lower())], {}))
                    elif seg >= MIN:
                        a = no(f"{rede}:{conta}", f"@{conta}", "conta pública", rede=rede, seguidores=seg)
                    else:
                        codigo.setdefault((rede, conta), f"P{len(codigo) + 1:05d}")
                        a = no(codigo[(rede, conta)], f"perfil pequeno {codigo[(rede, conta)]}", "perfil pequeno", rede=rede)
                    c = no(f"cand:{nome}", nome, "candidato", **info.get(nome, {}))
                    ar[(a, c)] += 1
                    citacoes[nome] += 1
    # GEXF
    Path("data/redes").mkdir(parents=True, exist_ok=True)
    attrs = ["tipo", "partido", "cargo", "uf", "situacao", "rede", "seguidores"]
    with open("data/redes/rede_candidatos.gexf", "w", encoding="utf-8") as f:
        f.write('<?xml version="1.0" encoding="UTF-8"?>\n<gexf xmlns="http://gexf.net/1.3" version="1.3">\n'
                f'<meta lastmodifieddate="{now_utc()[:10]}"><description>Candidatos × casos (publicações) e contas × candidatos (citações do @), '
                f'amostra dos casos do ODI Atlas; {lidos} posts lidos para as citações</description></meta>\n'
                '<graph defaultedgetype="directed">\n<attributes class="node">'
                + "".join(f'<attribute id="{i}" title="{a}" type="string"/>' for i, a in enumerate(attrs))
                + '</attributes>\n<attributes class="edge"><attribute id="0" title="tipo" type="string"/><attribute id="1" title="curtidas" type="integer"/>'
                  '<attribute id="2" title="posicao" type="string"/></attributes>\n<nodes>\n')
        for k, v in nos.items():
            f.write(f'<node id="{escape(k, {chr(34): "&quot;"})}" label="{escape(str(v["label"]), {chr(34): "&quot;"})}"><attvalues>'
                    + "".join(f'<attvalue for="{i}" value="{escape(str(v.get(a, "")), {chr(34): "&quot;"})}"/>' for i, a in enumerate(attrs) if v.get(a, "") != "")
                    + "</attvalues></node>\n")
        f.write("</nodes>\n<edges>\n")
        for i, ((s, t), w) in enumerate(ar.items()):
            tp = "publicou no caso" if t.startswith("caso:") else "citou o candidato"
            f.write(f'<edge id="{i}" source="{escape(s, {chr(34): "&quot;"})}" target="{escape(t, {chr(34): "&quot;"})}" weight="{w}" label="{tp}"><attvalues>'
                    f'<attvalue for="0" value="{tp}"/><attvalue for="1" value="{curt.get((s, t), 0)}"/>'
                    + (f'<attvalue for="2" value="{escape(posicao[(s, t)])}"/>' if (s, t) in posicao else "") + "</attvalues></edge>\n")
        f.write("</edges>\n</graph>\n</gexf>\n")
    # resumo por candidato (Lula primeiro, depois por citações + publicações)
    casos_de = defaultdict(set)
    for (s, t) in ar:
        if s.startswith("cand:") and t.startswith("caso:"):
            casos_de[s[5:]].add(t[5:])
    quem_cita = defaultdict(set)
    for (s, t) in ar:
        if t.startswith("cand:") and not t.startswith("caso:"):
            quem_cita[t[5:]].add(s)
    nomes = sorted(set(pubs) | set(citacoes), key=lambda n: (0 if n.lower().startswith("lula") else 1, -(citacoes[n] + pubs[n])))
    with open("data/redes/rede_candidatos_resumo.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["candidato", "partido", "cargo", "uf", "publicacoes_nos_casos", "casos_em_que_publicou", "citacoes_recebidas", "contas_que_citaram"])
        for n in nomes:
            i = info.get(n, {})
            w.writerow([n, i.get("partido", ""), i.get("cargo", ""), i.get("uf", ""), pubs[n], len(casos_de[n]), citacoes[n], len(quem_cita[n])])
    por_caso_saida(root, cfg, handle, info, interno)
    print(f"rede_candidatos: {len(nos)} nós, {len(ar)} arestas · {len(pubs)} candidatos publicaram ({sum(pubs.values())} publicações) · "
          f"{len(citacoes)} candidatos citados ({sum(citacoes.values())} citações em {lidos} posts lidos)")
    return 0


def por_caso_saida(root: Path, cfg: dict, handle: dict, info: dict, interno: str | None) -> None:
    """07/11/2026, 22h04 (responsável: "as redes de candidatos vão pro ODI Atlas naquele campo candidato", "por caso"):
    uma rede por caso — contas que citam o @ de candidatos nos posts lidos do caso (e candidatos que citam candidatos) —,
    com os candidatos que publicaram sobre o caso marcados. Saídas: data/casos/<id>/rede_candidatos.gexf e
    data/casos/<id>/candidatos_influencia.json (métricas da rede e ranking por citações recebidas)."""
    import networkx as nx
    if not interno:
        return
    for f in sorted(glob.glob(os.path.join(interno, "casos/*/itens.csv.gz"))):
        cid = Path(f).parent.name
        if cid not in cfg:
            continue
        pub = Counter()
        cj = root / "data/casos" / cid / "candidatos.json"
        if cj.exists():
            for x in json.loads(cj.read_text(encoding="utf-8")).get("candidatos", []):
                pub[x["candidato"].title()] += len(x.get("publicacoes", []))
        g = nx.DiGraph()
        codigo, lidos, cit, quem = {}, 0, Counter(), defaultdict(set)
        pub_contas = defaultdict(Counter)
        for r in csv.DictReader(gzip.open(f, "rt", encoding="utf-8"), delimiter=";"):
            lidos += 1
            rede, conta = r.get("rede"), r.get("conta") or "?"
            for h in set(re.findall(r"@([\w.]{2,30})", r.get("texto") or "")):
                nome = handle.get((rede, h.lower()))
                if not nome:
                    continue
                autor_cand = handle.get((rede, conta.lower()))
                if autor_cand == nome:
                    continue
                seg = num(r.get("seguidores"))
                if autor_cand:
                    a = f"cand:{autor_cand}"
                    g.add_node(a, label=autor_cand, tipo="candidato", **{k: v for k, v in info.get(autor_cand, {}).items()})
                elif seg >= MIN:
                    a = f"{rede}:{conta}"
                    g.add_node(a, label=f"@{conta}", tipo="conta pública", rede=rede)
                    pub_contas[nome][f"@{conta}"] += 1
                else:
                    codigo.setdefault((rede, conta), f"P{len(codigo) + 1:05d}")
                    a = codigo[(rede, conta)]
                    g.add_node(a, label=f"perfil pequeno {a}", tipo="perfil pequeno", rede=rede)
                c = f"cand:{nome}"
                g.add_node(c, label=nome, tipo="candidato", publicou_no_caso=str(pub.get(nome, 0)), **{k: v for k, v in info.get(nome, {}).items()})
                w = g[a][c]["weight"] + 1 if g.has_edge(a, c) else 1
                g.add_edge(a, c, weight=w, tipo="citou o candidato")
                cit[nome] += 1
                quem[nome].add(a)
        for nome, k in pub.items():  # quem publicou sobre o caso entra mesmo sem ser citado
            g.add_node(f"cand:{nome}", label=nome, tipo="candidato", publicou_no_caso=str(k), **{kk: v for kk, v in info.get(nome, {}).items()})
        out = root / "data/casos" / cid
        nx.write_gexf(g, out / "rede_candidatos.gexf")
        met = {"nos": g.number_of_nodes(), "arestas": g.number_of_edges()}
        if g.number_of_edges():
            u = g.to_undirected()
            comps = sorted(nx.connected_components(u), key=len, reverse=True)
            h = u.subgraph(comps[0])
            coms = sorted(nx.community.louvain_communities(h, weight="weight", seed=42), key=len, reverse=True)
            pr = nx.pagerank(g, weight="weight")
            met.update({"densidade": round(nx.density(g), 6), "componentes": len(comps), "nos_componente_gigante": len(comps[0]),
                        "pct_componente_gigante": round(100 * len(comps[0]) / g.number_of_nodes(), 2),
                        "modularidade_q_gigante": round(nx.community.modularity(h, coms, weight="weight"), 4) if h.number_of_edges() else None,
                        "comunidades_gigante": len(coms)})
            com_de = {v: i + 1 for i, cc in enumerate(coms) for v in cc}
        else:
            pr, com_de = {}, {}
        nomes = sorted(set(pub) | set(cit), key=lambda n: (0 if n.lower().startswith("lula") else 1, -cit[n], -pub[n]))
        rank = [{"candidato": n, **info.get(n, {}), "citacoes_recebidas": cit[n], "contas_que_citaram": len(quem[n]),
                 "publicacoes_no_caso": pub[n], "pagerank": round(pr.get(f"cand:{n}", 0), 6),
                 "comunidade_no_gigante": com_de.get(f"cand:{n}"),
                 "contas_publicas_que_mais_citaram": [f"{k} ({v})" for k, v in pub_contas[n].most_common(5)]} for n in nomes]
        (out / "candidatos_influencia.json").write_text(json.dumps({
            "gerado_em_utc": now_utc(), "caso": cid, "posts_lidos": lidos,
            "tipo_de_rede": "Influência dos candidatos na circulação do caso: conta → candidato quando a conta cita o @ do candidato num post lido do caso "
                            "(peso = citações); candidatos que publicaram sobre o caso entram como nós mesmo sem citação. Dirigida.",
            "universo": "⛔ universo das plataformas não informado: são os posts que as buscas do caso devolveram.",
            "metricas": met, "candidatos": rank,
            "nota": "Candidatos (contas declaradas ao TSE, todos os cargos) com nome; contas com menos de 10 mil seguidores em código. "
                    "PageRank alto = candidato citado por quem também é citado (centro da conversa). GEXF: data/casos/" + cid + "/rede_candidatos.gexf."},
            ensure_ascii=False, indent=1), encoding="utf-8")


if __name__ == "__main__":
    sys.exit(main())
