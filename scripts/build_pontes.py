#!/usr/bin/env python3
"""Pontes entre públicos: quem comenta/responde nos conteúdos dos dois candidatos, respostas entre públicos
diferentes e conteúdos que atraem o público frequente do adversário. Só AGREGADOS vão para o público.

Método (texto que a página mostra):
- "Público frequente" de um candidato = autor com pelo menos MIN_HIST comentários no período e pelo menos
  2/3 deles nos conteúdos desse candidato. É um padrão de comportamento na plataforma, NÃO orientação política:
  comentar no canal do adversário pode ser para apoiar, discordar ou atacar.
- "Conta-ponte" = autor que comentou nos conteúdos dos dois candidatos no período (ou na semana, na série semanal).
- "Resposta entre públicos" = resposta (comentário filho) cujo autor e o autor do comentário respondido são
  públicos frequentes de candidatos diferentes. Só existe onde a coleta traz a árvore de respostas (YouTube).
- "Conteúdo que fura bolha" = parcela dos comentaristas com público definido que são público frequente do
  adversário, em conteúdos com pelo menos MIN_AUTORES_ITEM comentaristas com público definido.
- Tom: rótulos do modelo de sentimento já usado no Atlas (pysentimiento, cache no repositório privado).

Entradas privadas (ODI_INTERNO_DIR): <plat>/comentarios/comentarios.csv.gz (X: x/respostas/respostas.csv.gz) e
sentimento.csv.gz. Entradas públicas: data/<plat>/conteudo.json (títulos, temas, datas), data/config/trends.json (fases),
data/config/temas_youtube.json (temas das respostas).
Saída pública: data/pontes/<plat>.json. Nenhum texto, nome ou id de autor.

Uso: python scripts/build_pontes.py --plataforma youtube|x|facebook
"""
from __future__ import annotations

import csv
import datetime as dt
import gzip
import json
import os
import re
import statistics
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import build_conteudo as bc  # noqa: E402
from net import now_utc  # noqa: E402

L, F = "280002542548", "280002551544"
NOMES = {L: "Lula", F: "Flávio Bolsonaro"}
OUTRO = {L: F, F: L}
MIN_HIST = 2
FRACAO_CASA = 2 / 3
MIN_AUTORES_ITEM = 30
TOP = 10
DESDE = "2026-07-20"
PLATS = ("youtube", "x", "facebook")


def ler(p: Path) -> list[dict]:
    if not p.exists():
        return []
    return list(csv.DictReader(gzip.open(p, "rt", encoding="utf-8"), delimiter=";"))


def semana(iso: str) -> str:
    d = dt.date.fromisoformat(iso[:10])
    return (d - dt.timedelta(days=d.weekday())).isoformat()


def fase(iso: str, fases: list[dict]) -> str | None:
    d = iso[:10]
    return next((f["id"] for f in fases if f["de"] <= d <= f["ate"]), None)


def tom(rots: list[str]) -> dict | None:
    rots = [r for r in rots if r]
    if not rots:
        return None
    c = Counter(rots)
    n = len(rots)
    return {"n": n, "positivo": round(100 * c["POS"] / n, 1), "neutro": round(100 * c["NEU"] / n, 1), "negativo": round(100 * c["NEG"] / n, 1)}


def publicos(rows: list[dict]) -> dict[str, str | None]:
    """autor -> candidato de quem é público frequente (ou None)."""
    cont = defaultdict(Counter)
    for r in rows:
        if r["autor_canal"]:
            cont[r["autor_canal"]][r["candidate_id"]] += 1
    out = {}
    for a, c in cont.items():
        n = c[L] + c[F]
        top = L if c[L] >= c[F] else F
        out[a] = top if n >= MIN_HIST and c[top] / n >= FRACAO_CASA else None
    return out


def analisar(rows: list[dict], rot: dict, itens: dict, fases: list[dict], temas_cfg) -> dict:
    rows = [r for r in rows if r.get("candidate_id") in (L, F) and (r.get("publicado_em") or "")[:10] >= DESDE and r.get("autor_canal")]
    casa = publicos(rows)
    por_autor = defaultdict(set)
    for r in rows:
        por_autor[r["autor_canal"]].add(r["candidate_id"])
    pontes = {a for a, s in por_autor.items() if len(s) == 2}
    n_aut = len(por_autor)
    res = {"comentarios": len(rows), "autores": n_aut,
           "publico_frequente": {NOMES[c]: sum(1 for v in casa.values() if v == c) for c in (L, F)},
           "sem_publico_definido": sum(1 for v in casa.values() if v is None),
           "contas_ponte": {"autores": len(pontes), "pct_autores": round(100 * len(pontes) / n_aut, 2) if n_aut else None}}
    # tom: comentários das contas-ponte em cada lado x demais autores
    tom_lado = {}
    for c in (L, F):
        tom_lado[NOMES[c]] = {
            "contas_ponte": tom([rot.get(r["comment_id"]) for r in rows if r["candidate_id"] == c and r["autor_canal"] in pontes]),
            "publico_do_adversario": tom([rot.get(r["comment_id"]) for r in rows if r["candidate_id"] == c and casa.get(r["autor_canal"]) == OUTRO[c]]),
            "proprio_publico": tom([rot.get(r["comment_id"]) for r in rows if r["candidate_id"] == c and casa.get(r["autor_canal"]) == c]),
            "todos": tom([rot.get(r["comment_id"]) for r in rows if r["candidate_id"] == c])}
    res["tom_por_lado"] = tom_lado
    # séries: por semana e por fase (ponte dentro da janela)
    def janela(chave):
        g = defaultdict(lambda: defaultdict(set))
        for r in rows:
            k = chave(r["publicado_em"])
            if k:
                g[k][r["autor_canal"]].add(r["candidate_id"])
        return {k: {"autores": len(v), "contas_ponte": sum(1 for s in v.values() if len(s) == 2),
                    "pct": round(100 * sum(1 for s in v.values() if len(s) == 2) / len(v), 2) if v else None} for k, v in sorted(g.items())}
    res["por_semana"] = janela(semana)
    res["por_fase"] = janela(lambda iso: fase(iso, fases))
    # respostas entre públicos (só onde o pai está no acervo)
    por_id = {r["comment_id"]: r for r in rows}
    filhos = [r for r in rows if r.get("parent_id") and r["parent_id"] in por_id]
    cruz = [r for r in filhos if casa.get(r["autor_canal"]) and casa.get(por_id[r["parent_id"]]["autor_canal"])
            and casa[r["autor_canal"]] != casa[por_id[r["parent_id"]]["autor_canal"]]]
    temas, _ = temas_cfg
    def temas_de(lst):
        c = Counter()
        for r in lst:
            t = bc.norm(r.get("texto") or "")
            for k, regs in temas.items():
                if any(rx.search(t) for rx in regs):
                    c[k] += 1
        return {k: {"n": v, "pct": round(100 * v / len(lst), 1)} for k, v in c.most_common()} if lst else {}
    res["respostas_entre_publicos"] = {
        "respostas_com_pai_no_acervo": len(filhos), "entre_publicos_diferentes": len(cruz),
        "pct": round(100 * len(cruz) / len(filhos), 2) if filhos else None,
        "por_lado": {NOMES[c]: sum(1 for r in cruz if r["candidate_id"] == c) for c in (L, F)},
        "por_fase": dict(Counter(fase(r["publicado_em"], fases) or "fora" for r in cruz)),
        "tom": tom([rot.get(r["comment_id"]) for r in cruz]), "tom_todas_respostas": tom([rot.get(r["comment_id"]) for r in filhos]),
        "temas": temas_de(cruz), "temas_todas_respostas": temas_de(filhos),
        "disponivel": bool(filhos)}
    # conteúdos que furam bolha
    por_item = defaultdict(lambda: defaultdict(set))
    for r in rows:
        por_item[r["video_id"]][casa.get(r["autor_canal"])].add(r["autor_canal"])
    lista = []
    for vid, g in por_item.items():
        it = itens.get(vid)
        if not it:
            continue
        dono = it["candidate_id"]
        definidos = len(g.get(L, set())) + len(g.get(F, set()))
        if definidos < MIN_AUTORES_ITEM:
            continue
        adv = len(g.get(OUTRO[dono], set()))
        lista.append({"candidato": NOMES[dono], "id": vid, "data": it["data"], "titulo": it["titulo"][:140], "url": it["url"],
                      "temas": it["temas"], "comentaristas_com_publico": definidos, "publico_adversario": adv,
                      "pct_publico_adversario": round(100 * adv / definidos, 1)})
    fura = {}
    for c in (L, F):
        meus = [x for x in lista if x["candidato"] == NOMES[c]]
        pcts = [x["pct_publico_adversario"] for x in meus]
        por_tema = defaultdict(list)
        for x in meus:
            for t in x["temas"]:
                por_tema[t].append(x["pct_publico_adversario"])
        fura[NOMES[c]] = {"itens_avaliados": len(meus), "media_pct": round(statistics.mean(pcts), 2) if pcts else None,
                          "pct_itens_com_publico_adversario": round(100 * sum(1 for x in pcts if x > 0) / len(pcts), 1) if pcts else None,
                          "top": sorted(meus, key=lambda x: (-x["pct_publico_adversario"], -x["publico_adversario"]))[:TOP],
                          "por_tema": {t: {"itens": len(v), "media_pct": round(statistics.mean(v), 2),
                                           "pct_itens_com_publico_adversario": round(100 * sum(1 for x in v if x > 0) / len(v), 1)}
                                       for t, v in sorted(por_tema.items(), key=lambda kv: -statistics.mean(kv[1])) if len(v) >= 5}}
    res["conteudos_que_furam_bolha"] = fura
    return res


TOM = {"POS": "pos", "NEG": "neg", "NEU": "neu"}


def exportar(root: Path, interno: Path, plat: str, rows: list[dict], rot: dict, itens: dict, fases: list[dict]) -> dict:
    """Gephi (público, autores pseudonimizados) e IRaMuTeQ (privado, com texto) das pontes entre públicos.

    Pseudônimos: P0001, P0002... na ordem de atividade (mais comentários primeiro); a correspondência com o autor
    real fica só no repositório privado (pontes/<rede>_codigos.csv). Nada de nome ou id de autor no público."""
    import networkx as nx
    rows = [r for r in rows if r.get("candidate_id") in (L, F) and (r.get("publicado_em") or "")[:10] >= DESDE and r.get("autor_canal")]
    casa = publicos(rows)
    por_autor = defaultdict(Counter)
    for r in rows:
        por_autor[r["autor_canal"]][r["candidate_id"]] += 1
    pontes = {a for a, c in por_autor.items() if c[L] and c[F]}
    por_id = {r["comment_id"]: r for r in rows}
    cruz = [r for r in rows if r.get("parent_id") in por_id and casa.get(r["autor_canal"]) and casa.get(por_id[r["parent_id"]]["autor_canal"])
            and casa[r["autor_canal"]] != casa[por_id[r["parent_id"]]["autor_canal"]]]
    envolvidos = pontes | {r["autor_canal"] for r in cruz} | {por_id[r["parent_id"]]["autor_canal"] for r in cruz}
    ordem = sorted(envolvidos, key=lambda a: (-sum(por_autor[a].values()), a))
    cod = {a: f"P{i + 1:04d}" for i, a in enumerate(ordem)}
    pub_nome = lambda a: {L: "Lula", F: "Flávio Bolsonaro"}.get(casa.get(a), "sem público definido")  # noqa: E731
    cor = {L: (200, 16, 46), F: (31, 138, 59), None: (120, 128, 136)}
    pasta = root / "data/pontes"
    # 1) contas-ponte × conteúdos (bipartida)
    g = nx.Graph()
    arest = defaultdict(list)
    for r in rows:
        if r["autor_canal"] in pontes and r["video_id"] in itens:
            arest[(r["autor_canal"], r["video_id"])].append(rot.get(r["comment_id"], ""))
    for (a, v), tons in arest.items():
        if cod[a] not in g:
            rr, gg, bb = cor[casa.get(a)]
            g.add_node(cod[a], label=cod[a], tipo="conta-ponte", publico=pub_nome(a), comentarios_lula=por_autor[a][L], comentarios_flavio=por_autor[a][F],
                       viz={"color": {"r": rr, "g": gg, "b": bb, "a": 1.0}, "size": 4 + sum(por_autor[a].values()) ** 0.5})
        it = itens[v]
        if v not in g:
            rr, gg, bb = cor[it["candidate_id"]]
            g.add_node(v, label=it["titulo"][:60] or v, tipo="conteúdo", candidato=NOMES[it["candidate_id"]], data=it["data"], url=it["url"],
                       temas="|".join(it["temas"]), viz={"color": {"r": rr, "g": gg, "b": bb, "a": 1.0}, "size": 8.0})
        c = Counter(t for t in tons if t)
        g.add_edge(cod[a], v, weight=len(tons), tom_predominante=TOM.get(c.most_common(1)[0][0], "sem") if c else "sem")
    nx.write_gexf(g, pasta / f"{plat}_contas_ponte.gexf")
    # 2) respostas entre públicos (dirigida: quem responde → quem foi respondido)
    h = nx.DiGraph()
    for r in cruz:
        a, b = r["autor_canal"], por_id[r["parent_id"]]["autor_canal"]
        for x in (a, b):
            if cod[x] not in h:
                rr, gg, bb = cor[casa.get(x)]
                h.add_node(cod[x], label=cod[x], publico=pub_nome(x), viz={"color": {"r": rr, "g": gg, "b": bb, "a": 1.0}, "size": 6.0})
        e = h.get_edge_data(cod[a], cod[b]) or {"weight": 0, "neg": 0}
        h.add_edge(cod[a], cod[b], weight=e["weight"] + 1, neg=e["neg"] + int(rot.get(r["comment_id"]) == "NEG"),
                   conteudo_de=NOMES[r["candidate_id"]])
    nx.write_gexf(h, pasta / f"{plat}_respostas_entre_publicos.gexf")
    # 3) privado: códigos e corpus IRaMuTeQ
    priv = interno / "pontes"
    priv.mkdir(parents=True, exist_ok=True)
    with open(priv / f"{plat}_codigos.csv", "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f, delimiter=";", lineterminator="\n")
        w.writerow(["codigo", "autor_canal", "publico"])
        for a in ordem:
            w.writerow([cod[a], a, pub_nome(a)])
    ids_cruz = {r["comment_id"] for r in cruz}
    sel = [r for r in rows if r["autor_canal"] in pontes or r["comment_id"] in ids_cruz]
    slug = {L: "lula", F: "flavio", None: "indef"}
    with open(priv / f"{plat}_corpus_iramuteq.txt", "w", encoding="utf-8", newline="\n") as f:
        for r in sel:
            texto = " ".join(re.sub(r"[*$%]", " ", r.get("texto") or "").split())
            if len(texto) < 3:
                continue
            fz = fase(r["publicado_em"], fases) or "fora"
            f.write(f"**** *rede_{plat} *conteudo_{slug[r['candidate_id']]} *publico_{slug[casa.get(r['autor_canal'])]} "
                    f"*ponte_{'sim' if r['autor_canal'] in pontes else 'nao'} *resposta_entre_publicos_{'sim' if r['comment_id'] in ids_cruz else 'nao'} "
                    f"*tom_{TOM.get(rot.get(r['comment_id']), 'sem')} *fase_{fz}\n{texto}\n")
    return {"gephi_contas_ponte": f"data/pontes/{plat}_contas_ponte.gexf", "gephi_contas_ponte_tamanho": {"nos": g.number_of_nodes(), "arestas": g.number_of_edges()},
            "gephi_respostas": f"data/pontes/{plat}_respostas_entre_publicos.gexf", "gephi_respostas_tamanho": {"nos": h.number_of_nodes(), "arestas": h.number_of_edges()},
            "iramuteq_privado": f"odi-atlas-interno/pontes/{plat}_corpus_iramuteq.txt", "iramuteq_segmentos": len(sel),
            "variaveis_iramuteq": ["*rede_", "*conteudo_", "*publico_", "*ponte_", "*resposta_entre_publicos_", "*tom_", "*fase_"]}


def itens_da_plataforma(root: Path, plat: str) -> dict:
    d = json.loads((root / f"data/{plat}/conteudo.json").read_text(encoding="utf-8"))
    out = {}
    for cid, c in d["candidatos"].items():
        for v in c.get("videos") or []:
            vid = str(v.get("video_id"))
            url = v.get("url") or (f"https://www.youtube.com/watch?v={vid}" if plat == "youtube" else "")
            out[vid] = {"candidate_id": cid, "data": (v.get("publicado_em") or "")[:10], "titulo": v.get("titulo") or v.get("legenda") or "",
                        "url": url, "temas": [t for t in (v.get("temas") or []) if t != "sem_tema"]}
    return out


def main(argv=None) -> int:
    argv = list(argv or [])
    plat = argv[argv.index("--plataforma") + 1] if "--plataforma" in argv else "youtube"
    if plat not in PLATS:
        raise SystemExit(f"plataforma sem análise de pontes: {plat}")
    root = Path(".")
    saida = root / "data/pontes" / f"{plat}.json"
    saida.parent.mkdir(parents=True, exist_ok=True)
    base = {"schema_version": 1, "plataforma": plat, "gerado_em_utc": now_utc(),
            "metodo": {"publico_frequente": f"autor com pelo menos {MIN_HIST} comentários e 2/3 deles nos conteúdos de um candidato; descreve comportamento na plataforma, não orientação política",
                       "conta_ponte": "autor que comentou nos conteúdos dos dois candidatos na janela",
                       "resposta_entre_publicos": "resposta cujo autor e o autor do comentário respondido são públicos frequentes de candidatos diferentes",
                       "fura_bolha": f"parcela dos comentaristas com público definido que são público frequente do adversário; só conteúdos com {MIN_AUTORES_ITEM}+ comentaristas com público definido",
                       "tom": "modelo de sentimento do Atlas (pysentimiento/bertweet-pt-sentiment)", "desde": DESDE}}
    interno = os.environ.get("ODI_INTERNO_DIR")
    if not interno:
        saida.write_text(json.dumps({**base, "status": "⛔ sem acesso ao repositório privado (ODI_INTERNO_DIR)"}, ensure_ascii=False, indent=1), encoding="utf-8")
        print("⛔ ODI_INTERNO_DIR ausente")
        return 1
    d = Path(interno) / plat / ("respostas" if plat == "x" else "comentarios")
    rows = ler(d / ("respostas.csv.gz" if plat == "x" else "comentarios.csv.gz"))
    if not rows:
        saida.write_text(json.dumps({**base, "status": f"⛔ sem comentários coletados em {plat}"}, ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"⛔ sem comentários em {plat}")
        return 1
    rot = {r["comment_id"]: r["rotulo"] for r in ler(d / "sentimento.csv.gz")}
    fases = json.loads((root / "data/config/trends.json").read_text(encoding="utf-8"))["fases"]
    temas_cfg = bc.compile_cfg(json.loads((root / "data/config/temas_youtube.json").read_text(encoding="utf-8")))
    res = analisar(rows, rot, itens_da_plataforma(root, plat), fases, temas_cfg)
    datas = sorted(r["publicado_em"][:10] for r in rows if r.get("publicado_em"))
    out = {**base, "status": "ok", "periodo": {"de": max(DESDE, datas[0]) if datas else None, "ate": datas[-1] if datas else None},
           "comentarios_com_tom": sum(1 for r in rows if r["comment_id"] in rot), **res}
    out["arquivos"] = exportar(root, Path(interno), plat, rows, rot, itens_da_plataforma(root, plat), fases)
    saida.write_text(json.dumps(out, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    cp = res["contas_ponte"]
    print(f"{plat}: {res['comentarios']} comentários · {res['autores']} autores · contas-ponte {cp['autores']} ({cp['pct_autores']}%) · "
          f"respostas entre públicos {res['respostas_entre_publicos']['entre_publicos_diferentes']} de {res['respostas_entre_publicos']['respostas_com_pai_no_acervo']}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
