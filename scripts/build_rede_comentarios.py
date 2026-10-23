#!/usr/bin/env python3
"""Caderno 04 — redes dos comentários do YouTube para o Gephi, e corpus-amostra para o IRaMuTeQ.

1) Rede de coocorrência de termos (pública: só palavras): nó = palavra presente em muitos comentários; aresta = as duas
   aparecem no mesmo comentário; cor = proporção de uso na audiência de Lula (vermelho) e de Flávio (verde).
   Mesmo método do caderno 02 (build_rede.montar/analisar: Louvain, ForceAtlas2, semente 42).
2) Rede de respostas entre comentaristas (Recuero: rede de conversação). Aresta dirigida: quem responde → autor do
   comentário respondido; peso = nº de respostas. No PÚBLICO, os autores viram códigos P00001… (sorteio com semente
   fixa; a tabela código → canal fica só no repositório privado). Métricas: grau de entrada, comunidades (Louvain),
   centralização de Freeman do grau de entrada, no todo e por comunidade.
3) Corpus IRaMuTeQ de amostra (privado): os mesmos comentários sorteados para a CHD (até 4.000 por candidato, 8+ palavras),
   tamanho que o IRaMuTeQ processa num computador comum. O corpus completo continua ao lado.

Entrada: arquivo bruto (ODI_INTERNO_DIR/youtube/comentarios/comentarios.csv.gz ou caminho no argumento).
Saída pública: data/youtube/comentarios/rede_termos.{json,gexf}, rede_termos_nos.csv, rede_termos_arestas.csv,
               rede_respostas.{json,gexf}, rede_respostas_nos.csv, rede_respostas_arestas.csv
Saída privada: rede_respostas_identificada.gexf, codigos_autores.csv, corpus_iramuteq_amostra.txt
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

sys.path.insert(0, str(Path(__file__).resolve().parent))
import build_comentarios as bcm  # noqa: E402
import build_conteudo as bc  # noqa: E402
import build_rede as br  # noqa: E402
import chd_reinert as chd  # noqa: E402
import corpus_populismo as cp  # noqa: E402
from collect_comentarios_youtube import destino, plataforma  # noqa: E402

SEMENTE = 42
MAX_NOS_DESENHO = 400


def termos_comentario(txt: str, excluir: set) -> set[str]:
    return {t for t in bc.termos(txt, excluir) if " " not in t and not t.startswith("#")}


def rede_termos(rows: list[dict], ids: tuple[str, str], excluir: set) -> tuple[nx.Graph, dict, dict]:
    docs = [(r["candidate_id"], termos_comentario(bcm.limpo(r["texto"]), excluir)) for r in rows]
    docs = [d for d in docs if len(d[1]) >= 2 and d[0] in ids]
    n = len(docs)
    if n >= 10000:  # acervos grandes (YouTube, Facebook): regra original
        par = {"min_comentarios": max(50, n // 500), "max_nos": 150, "min_peso": max(10, n // 4000), "top_arestas": 8}
    else:  # acervos pequenos (Instagram, TikTok, Kwai): o piso fixo de 50 deixava a rede com poucas dezenas de palavras (23/10/2026)
        par = {"min_comentarios": max(10, n // 300), "max_nos": 150, "min_peso": max(3, n // 1500), "top_arestas": 8}
    g = br.montar(docs, ids, min_videos=par["min_comentarios"], max_nos=par["max_nos"], min_peso=par["min_peso"],
                  top_arestas=par["top_arestas"])
    info = br.analisar(g)
    # lado normalizado pelo tamanho de cada audiência (a de Lula tem mais comentários): 0,5 = uso proporcional igual
    nl, nf = sum(1 for c, _ in docs if c == ids[0]), sum(1 for c, _ in docs if c == ids[1])
    for v in g:
        d = g.nodes[v]
        tl, tf = d["lula"] / max(1, nl), d["flavio"] / max(1, nf)
        d["lado"] = round(tl / (tl + tf), 3) if tl + tf else 0.5
    par["comentarios_lula"], par["comentarios_flavio"] = nl, nf
    # Nos comentários, poucas palavras ("presidente", "brasil", "deus") ligam-se a quase todas: o ForceAtlas2 LinLog
    # empurra esses polos para as bordas e a contagem bruta os puxa todos para o centro. A posição usa a força da
    # associação (cosseno de Salton: coocorrências ÷ √(frequência A × frequência B)), não a contagem; semente fixa.
    for a_, b_, d in g.edges(data=True):
        d["w_log"] = d["weight"] / math.sqrt(g.nodes[a_]["videos"] * g.nodes[b_]["videos"])
    pos = nx.spring_layout(g, weight="w_log", seed=SEMENTE, k=2.2 / math.sqrt(max(1, g.number_of_nodes())), iterations=400)
    xs, ys = [p[0] for p in pos.values()] or [0], [p[1] for p in pos.values()] or [0]  # rede vazia em amostras pequenas
    span = max(max(xs) - min(xs), max(ys) - min(ys)) or 1
    for v, (x, y) in pos.items():
        g.nodes[v]["x"] = round(float(x - min(xs)) / span * 1000, 1)
        g.nodes[v]["y"] = round(float(y - min(ys)) / span * 1000, 1)
    for _, _, d in g.edges(data=True):
        d.pop("w_log")
    info["layout"] = "Fruchterman-Reingold (networkx spring_layout) sobre o cosseno de Salton"
    par["comentarios"] = n
    return g, info, par


def freeman_in(g: nx.DiGraph) -> float | None:
    """Centralização de Freeman do grau de entrada (sem peso): Σ(max − d_i) / (n − 1)²."""
    n = g.number_of_nodes()
    if n < 3:
        return None
    d = [g.in_degree(v) for v in g]
    return round(sum(max(d) - x for x in d) / ((n - 1) ** 2), 4)


RX_MENCAO = re.compile(r"(?<![\w.])@([A-Za-z0-9_](?:[A-Za-z0-9_.]{0,28}[A-Za-z0-9_])?)")


def tem_respostas(rows: list[dict]) -> bool:
    return any(r["tipo"] == "resposta" and r.get("parent_id") for r in rows)


def rede_respostas(rows: list[dict]) -> tuple[nx.DiGraph, list]:
    """Com respostas coletadas: quem responde → autor respondido. Sem respostas (Instagram, TikTok e Facebook foram coletados
    só com comentários de primeiro nível): quem comenta → conta marcada com @ no comentário (rede de menções, também de
    conversação em Recuero). A conta marcada é identificada pelo @ (nome de usuário), o autor pelo id do canal ou nome."""
    por_id = {r["comment_id"]: r for r in rows}
    g = nx.DiGraph()
    lado = defaultdict(Counter)
    usuario = {}
    for r in rows:
        k = r["autor_canal"] or r["autor_nome"]
        lado[k][r["candidate_id"]] += 1
        if r.get("autor_nome"):
            usuario[r["autor_nome"].lower().lstrip("@")] = k
    def ligar(a, b):
        if not a or not b or a == b:
            return
        w = g.get_edge_data(a, b, {}).get("weight", 0)
        g.add_edge(a, b, weight=w + 1)
    if tem_respostas(rows):
        for r in rows:
            if r["tipo"] == "resposta" and r["parent_id"] in por_id:
                ligar(r["autor_canal"] or r["autor_nome"], por_id[r["parent_id"]]["autor_canal"] or por_id[r["parent_id"]]["autor_nome"])
    else:
        for r in rows:
            for m in {x.lower() for x in RX_MENCAO.findall(r["texto"] or "")}:
                ligar(r["autor_canal"] or r["autor_nome"], usuario.get(m, "@" + m))
    for v in g:
        g.nodes[v]["lado"] = lado[v]
    comms = nx.community.louvain_communities(g.to_undirected(), weight="weight", seed=SEMENTE)
    comms = sorted(comms, key=lambda c: (-len(c), min(c)))
    for i, c in enumerate(comms):
        for v in c:
            g.nodes[v]["comunidade"] = i
    return g, comms


def main(argv=None) -> int:
    root = Path(".")
    plat, argv = plataforma(argv)
    dest, modo = destino(plat)
    bruto = Path(argv[0]) if argv else dest / "comentarios.csv.gz"
    pub = root / f"data/{plat}/comentarios"
    pub.mkdir(parents=True, exist_ok=True)
    if not bruto.exists():
        print(f"⛔ sem arquivo bruto ({bruto})")
        return 1
    rows = [r for r in csv.DictReader(gzip.open(bruto, "rt", encoding="utf-8"), delimiter=";") if (r["publicado_em"][:10] or bcm.DESDE) >= bcm.DESDE]
    if len(rows) < 2:
        print(f"⛔ comentários insuficientes para a rede ({len(rows)})")
        return 1
    cfg = json.loads((root / "data/config/temas_youtube.json").read_text(encoding="utf-8"))
    ids = tuple(cfg["candidatos"])
    L, F = ids
    nomes = {t for c in cfg["candidatos"].values() for t in bc.norm(c["nome"]).split()}
    agora = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    coletado = max((r["coletado_em"] for r in rows), default=None)

    # 1) coocorrência de termos
    g, info, par = rede_termos(rows, ids, bcm.EXCLUIR | nomes)
    for v in g:
        d = g.nodes[v]
        d["cor"] = br.cor_lado(d["lado"])
    metodo_t = (f"Rede de coocorrência de palavras nos comentários: nó = palavra em {par['min_comentarios']}+ comentários (até "
                f"{par['max_nos']}); aresta = as duas no mesmo comentário (peso mínimo {par['min_peso']}; até {par['top_arestas']} "
                f"arestas mais fortes por nó). Sem os nomes dos dois candidatos (dominariam a rede). Comunidades: Louvain; posição: "
                f"{info.get('layout')}; semente {SEMENTE}. Cor: vermelho = mais usada na audiência de Lula, verde = na de Flávio, em proporção ao tamanho de cada audiência. "
                f"{par['comentarios']} comentários com 2+ palavras válidas.")
    comms = info.get("comunidades", [])
    out_t = {"schema_version": 1, "gerado_em_utc": agora, "coletado_em_utc": coletado, "metodo": metodo_t, "parametros": par,
             "nos_total": g.number_of_nodes(), "arestas_total": g.number_of_edges(), "modularidade": info.get("modularidade"),
             "comunidades": [{"id": i, "nos": len(c), "principais": sorted(c, key=lambda n: (-g.nodes[n]["videos"], n))[:8],
                              "lado_medio": round(sum(g.nodes[n]["lado"] * g.nodes[n]["videos"] for n in c) / sum(g.nodes[n]["videos"] for n in c), 3)}
                             for i, c in enumerate(comms)],
             "nos": [{"id": n, "x": d["x"], "y": d["y"], "v": d["videos"], "l": d["lula"], "f": d["flavio"], "lado": d["lado"],
                      "c": d["comunidade"], "g": d["grau"], "b": d["intermediacao"]} for n, d in sorted(g.nodes(data=True))],
             "arestas": [[a, b, d["weight"]] for a, b, d in sorted(g.edges(data=True))]}
    (pub / "rede_termos.json").write_text(json.dumps(out_t, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    with open(pub / "rede_termos_nos.csv", "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(["Id", "Label", "comentarios", "comentarios_lula", "comentarios_flavio", "lado_lula", "comunidade", "grau", "intermediacao", "x", "y"])
        for n in out_t["nos"]:
            w.writerow([n["id"], n["id"], n["v"], n["l"], n["f"], n["lado"], n["c"] + 1, n["g"], n["b"], n["x"], n["y"]])
    with open(pub / "rede_termos_arestas.csv", "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(["Source", "Target", "Weight", "Type"])
        w.writerows([a, b, p, "Undirected"] for a, b, p in out_t["arestas"])
    gx = nx.Graph()
    for n, d in g.nodes(data=True):
        r_, g_, b_ = (int(d["cor"][i:i + 2], 16) for i in (1, 3, 5))
        gx.add_node(n, label=n, comentarios=d["videos"], lado_lula=d["lado"], comunidade=d["comunidade"] + 1,
                    viz={"position": {"x": d["x"], "y": -d["y"], "z": 0.0}, "size": 2 + 3 * math.sqrt(d["videos"] / 10),
                         "color": {"r": r_, "g": g_, "b": b_, "a": 1.0}})
    for a, b, d in g.edges(data=True):
        gx.add_edge(a, b, weight=d["weight"])
    nx.write_gexf(gx, pub / "rede_termos.gexf")
    print(f"rede de termos: {g.number_of_nodes()} nós, {g.number_of_edges()} arestas, {len(comms)} comunidades, modularidade {info.get('modularidade')}")

    # 2) rede de respostas (pseudonimizada no público)
    gr, comms_r = rede_respostas(rows)
    autores = sorted(gr.nodes)
    random.Random(SEMENTE).shuffle(autores)
    cod = {a: f"P{i + 1:05d}" for i, a in enumerate(autores)}
    indeg = dict(gr.in_degree())
    indeg_w = dict(gr.in_degree(weight="weight"))
    tot_l = lambda v: gr.nodes[v]["lado"][L]  # noqa: E731
    tot_f = lambda v: gr.nodes[v]["lado"][F]  # noqa: E731
    resumo_com = []
    for i, c in enumerate(comms_r[:15]):
        sub = gr.subgraph(c)
        l_, f_ = sum(tot_l(v) for v in c), sum(tot_f(v) for v in c)
        top = sorted(c, key=lambda v: (-indeg.get(v, 0), cod[v]))[:5]
        resumo_com.append({"comunidade": i + 1, "autores": len(c), "respostas": int(sum(d["weight"] for *_, d in sub.edges(data=True))),
                           "grau_entrada_max": max(sub.in_degree(v) for v in c), "grau_entrada_medio": round(sum(sub.in_degree(v) for v in c) / len(c), 2),
                           "centralizacao_freeman": freeman_in(sub), "pct_comentarios_em_videos_de_lula": round(100 * l_ / max(1, l_ + f_), 1),
                           "mais_respondidos": [[cod[v], indeg.get(v, 0)] for v in top]})
    # desenho: maiores comunidades, nós de maior grau
    keep = sorted(gr.nodes, key=lambda v: (-(gr.in_degree(v) + gr.out_degree(v)), cod[v]))[:MAX_NOS_DESENHO]
    sub = gr.subgraph(keep).copy()
    sub.remove_nodes_from([v for v in list(sub) if sub.degree(v) == 0])
    pos = nx.spring_layout(sub.to_undirected(), seed=SEMENTE, k=1.2 / math.sqrt(max(1, sub.number_of_nodes())), iterations=200)
    xs, ys = [p[0] for p in pos.values()] or [0], [p[1] for p in pos.values()] or [0]
    span = max(max(xs) - min(xs), max(ys) - min(ys)) or 1
    # conta marcada que não comentou no acervo: sem lado conhecido, cor neutra (0,5)
    frac = lambda v: round(tot_l(v) / (tot_l(v) + tot_f(v)), 3) if tot_l(v) + tot_f(v) else 0.5  # noqa: E731
    por_mencao = not tem_respostas(rows)
    out_r = {"schema_version": 1, "gerado_em_utc": agora, "coletado_em_utc": coletado,
             "tipo_rede": "mencoes" if por_mencao else "respostas",
             "metodo": ("Rede de conversação por menções (Recuero): esta plataforma foi coletada só com comentários de primeiro nível "
                        "(sem respostas), então a aresta dirigida vai de quem comenta para a conta marcada com @ no comentário; "
                        "peso = nº de comentários com a marcação. Só entram comentários com @. Autores e contas marcadas "
                        "pseudonimizados (P00001…; tabela só no repositório privado). Comunidades: Louvain (semente 42). "
                        "Cor: proporção dos comentários da conta feitos em posts de Lula (vermelho) ou de Flávio (verde); "
                        "marrom (meio-termo) = conta marcada que não comentou no acervo.") if por_mencao else ("Rede de conversação (Recuero): aresta dirigida de quem responde para o autor do comentário respondido; "
                        "peso = nº de respostas. A coleta traz só parte das respostas de cada conversa (YouTube: até 5; Instagram: até 6 nos comentários mais populares dos posts com mais respostas), então conversas longas aparecem "
                        "incompletas. Autores pseudonimizados (P00001…; tabela de correspondência só no repositório privado). "
                        "Comunidades: Louvain (semente 42). Centralização de Freeman do grau de entrada: 0 = respostas espalhadas, "
                        "1 = todas para um só autor. Cor: proporção dos comentários do autor feitos em vídeos de Lula (vermelho) "
                        "ou de Flávio (verde)."),
             "comentarios_com_mencao": sum(1 for r in rows if RX_MENCAO.search(r["texto"] or "")) if por_mencao else None,
             "autores": gr.number_of_nodes(), "ligacoes": gr.number_of_edges(),
             "respostas": int(sum(d["weight"] for *_, d in gr.edges(data=True))), "comunidades_total": len(comms_r),
             "centralizacao_freeman_total": freeman_in(gr),
             "maior_componente": len(max(nx.weakly_connected_components(gr), key=len)) if gr.number_of_nodes() else 0,
             "comunidades": resumo_com,
             "desenho": {"nos": [{"id": cod[v], "x": round(float(pos[v][0] - min(xs)) / span * 1000, 1), "y": round(float(pos[v][1] - min(ys)) / span * 1000, 1),
                                  "e": indeg.get(v, 0), "s": gr.out_degree(v), "c": gr.nodes[v]["comunidade"] + 1, "lado": frac(v)} for v in sub],
                         "arestas": [[cod[a], cod[b], d["weight"]] for a, b, d in sub.edges(data=True)]}}
    (pub / "rede_respostas.json").write_text(json.dumps(out_r, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    with open(pub / "rede_respostas_nos.csv", "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(["Id", "Label", "grau_entrada", "grau_saida", "respostas_recebidas", "comunidade", "pct_em_videos_de_lula"])
        for v in sorted(gr, key=lambda v: cod[v]):
            w.writerow([cod[v], cod[v], indeg.get(v, 0), gr.out_degree(v), indeg_w.get(v, 0), gr.nodes[v]["comunidade"] + 1, round(100 * frac(v), 1)])
    with open(pub / "rede_respostas_arestas.csv", "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(["Source", "Target", "Weight", "Type"])
        w.writerows(sorted([cod[a], cod[b], d["weight"], "Directed"] for a, b, d in gr.edges(data=True)))

    def gexf(g_, nome, rotulo):
        gg = nx.DiGraph()
        for v in g_:
            fr = frac(v)
            gg.add_node(rotulo(v), label=rotulo(v), comunidade=g_.nodes[v]["comunidade"] + 1, grau_entrada=indeg.get(v, 0),
                        pct_em_videos_de_lula=round(100 * fr, 1),
                        viz={"color": {"r": round(0x1f + (0xc8 - 0x1f) * fr), "g": round(0x8a + (0x10 - 0x8a) * fr), "b": round(0x3b + (0x2e - 0x3b) * fr), "a": 1.0},
                             "size": 2 + 2 * math.sqrt(indeg.get(v, 0))})
        for a, b, d in g_.edges(data=True):
            gg.add_edge(rotulo(a), rotulo(b), weight=d["weight"])
        nx.write_gexf(gg, nome)
    gexf(gr, pub / "rede_respostas.gexf", lambda v: cod[v])
    print(f"rede de respostas: {gr.number_of_nodes()} autores, {gr.number_of_edges()} ligações, {len(comms_r)} comunidades, "
          f"centralização {out_r['centralizacao_freeman_total']}, maior componente {out_r['maior_componente']}")

    if modo == "interno":  # material identificável: só no privado
        dest.mkdir(parents=True, exist_ok=True)
        nomes_aut = {}
        for r in rows:
            nomes_aut.setdefault(r["autor_canal"] or r["autor_nome"], r["autor_nome"])
        with open(dest / "codigos_autores.csv", "w", encoding="utf-8", newline="") as f:
            w = csv.writer(f, delimiter=";", lineterminator="\n")
            w.writerow(["codigo", "autor_canal", "autor_nome"])
            w.writerows(sorted([cod[v], v, nomes_aut.get(v, "")] for v in gr))
        gexf(gr, dest / "rede_respostas_identificada.gexf", lambda v: f"{cod[v]} {nomes_aut.get(v, '')}".strip())
        # corpus de amostra para o IRaMuTeQ (mesmo sorteio da CHD)
        with open(dest / "corpus_iramuteq_amostra.txt", "w", encoding="utf-8") as f:
            for cid in ids:
                meus = [r for r in rows if r["candidate_id"] == cid]
                tx = [bcm.limpo(r["texto"]) for r in meus]
                idx = [i for i, t in enumerate(tx) if len(chd.tokens(t)) >= bcm.CHD_MIN_TOKENS]
                random.Random(bcm.SEMENTE).shuffle(idx)
                nome = cp.var(cfg["candidatos"][cid]["nome"].split()[0])
                for i in sorted(idx[:bcm.CHD_AMOSTRA]):
                    r = meus[i]
                    f.write(f"**** *cand_{nome} *sem_{cp.semana(r['publicado_em'])} *tipo_{r['tipo']}\n{cp.limpar_iramuteq(tx[i])}\n")
        print(f"privado: codigos_autores.csv, rede_respostas_identificada.gexf, corpus_iramuteq_amostra.txt em {dest}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
