#!/usr/bin/env python3
"""Análises da transcrição do debate (Band/Estadão, 18/10/2026): quem fala, temas, rede de palavras, CHD de Reinert e
corpus para o IRaMuTeQ.

Entrada (privado): ODI_INTERNO_DIR/debate/transcricao.json (collect_debate_video.py).
Passos:
1. Quem fala — atribuição AUTOMÁTICA por deixas da mediação: quando um trecho chama "candidato/presidente Lula" ou
   "candidato/senador Flávio" junto de palavras de passagem de tempo ("pergunta", "resposta", "réplica", "tréplica",
   "tempo", "minuto", "com a palavra", "direito de resposta", "considerações"), as falas seguintes vão para esse candidato
   até a próxima deixa; o próprio trecho da deixa e falas antes da primeira deixa ficam como "mediação". Não é validado:
   a página diz isso, e `data/config/debate_turnos.json` permite corrigir à mão (início em segundos → orador).
2. Segmentos de texto (~40 palavras, sem cruzar troca de orador), como no IRaMuTeQ.
3. Temas: dicionário do Atlas (data/config/temas_youtube.json) — nº de segmentos e % do tempo de fala por orador e tema.
4. Rede de palavras: coocorrência no mesmo segmento (palavras em 3+ segmentos), por orador; GEXF + desenho.
5. CHD de Reinert (chd_reinert.py) sobre os segmentos dos dois candidatos, com a variável orador.
6. Corpus IRaMuTeQ (**** *orador_ *bloco_) — privado (texto integral da transmissão).
Saída pública: data/debate/analise.json, data/debate/rede_palavras_{lula,flavio,todos}.gexf. Trechos públicos ≤ 25 palavras.
"""
from __future__ import annotations

import json
import os
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import build_conteudo as bc  # noqa: E402
import chd_reinert as cr  # noqa: E402
from build_casos import gexf  # noqa: E402
from net import now_utc  # noqa: E402

ORADORES = {"lula": "Lula", "flavio": "Flávio Bolsonaro", "mediacao": "Mediação", "indefinido": "Não atribuído", "intervalo": "Intervalo"}
FORA = ("mediacao", "intervalo")  # fora das análises de discurso dos candidatos
DEIXA_NOME = {"lula": re.compile(r"\b(candidato|presidente|senhor)\s+lula\b|\blula,", re.I),
              "flavio": re.compile(r"\b(candidato|senador|senhor)\s+fl[aá]vio\b|\bfl[aá]vio( bolsonaro)?,", re.I)}
DEIXA_TEMPO = re.compile(r"pergunt|respost|r[ée]plica|tr[ée]plica|\btempo\b|minuto|segundo|com a palavra|direito de resposta|consider[aã][cç][oõ]es|o senhor tem|a palavra", re.I)
PALAVRAS_SEG = 40


def orador_por_deixas(segs: list[dict], correcoes: dict) -> list[str]:
    atual, out = "mediacao", []
    cor = sorted((float(k), v) for k, v in correcoes.items())
    for s in segs:
        t = s["texto"]
        manual = [v for k, v in cor if k <= s["ini"]]
        if manual:
            out.append(manual[-1])
            continue
        nomes = [k for k, rx in DEIXA_NOME.items() if rx.search(t)]
        if len(nomes) == 1 and DEIXA_TEMPO.search(t):
            out.append("mediacao")
            atual = nomes[0]
            continue
        if ">>" in t:  # a legenda automática marca troca de voz com ">>"; sem deixa, não dá para saber quem entrou
            atual = "indefinido"
        out.append(manual[-1] if manual else atual)  # correção manual vale do seu início até a próxima
    return out


def segmentar(segs: list[dict], quem: list[str]) -> list[dict]:
    out, buf, ini, dono = [], [], None, None
    for s, q in zip(segs, quem):
        if dono is not None and (q != dono or len(buf) >= PALAVRAS_SEG):
            out.append({"orador": dono, "ini": ini, "texto": " ".join(buf)})
            buf, ini = [], None
        if ini is None:
            ini, dono = s["ini"], q
        dono = q
        buf += s["texto"].replace(">>", " ").split()  # ">>" é a marca de troca de voz da legenda automática
    if buf:
        out.append({"orador": dono, "ini": ini, "texto": " ".join(buf)})
    return out


def temas(segmentos: list[dict], cfg: dict) -> dict:
    regs = {t: [bc.term_regex(x) for x in v] for t, v in cfg["temas"].items()}
    cont = {o: Counter() for o in ORADORES}
    tot = Counter()
    exemplos = defaultdict(list)
    for s in segmentos:
        tot[s["orador"]] += 1
        tx = bc.norm(s["texto"])
        for t, rs in regs.items():
            if any(r.search(tx) for r in rs):
                cont[s["orador"]][t] += 1
                if s["orador"] != "mediacao" and len(exemplos[(s["orador"], t)]) < 2:
                    exemplos[(s["orador"], t)].append({"ini": s["ini"], "trecho": " ".join(s["texto"].split()[:25]) + "…"})
    return {"segmentos_por_orador": {ORADORES[o]: tot[o] for o in ORADORES},
            "por_tema": {t: {ORADORES[o]: {"segmentos": cont[o][t], "pct": round(100 * cont[o][t] / tot[o], 1) if tot[o] else None,
                                           "exemplos": exemplos.get((o, t), [])} for o in ORADORES} for t in cfg["temas"]}}


def rede(segmentos: list[dict], minimo: int = 3, top: int = 70) -> tuple[dict, Counter, dict | None]:
    docs = [set(cr.tokens(s["texto"])) for s in segmentos]
    df = Counter(t for d in docs for t in d)
    voc = {t for t, n in df.items() if n >= minimo}
    ar = Counter()
    for d in docs:
        ws = sorted(d & voc)
        for i, a in enumerate(ws):
            for b in ws[i + 1:]:
                ar[(a, b)] += 1
    nos = {t: {"rotulo": t, "tipo": "palavra", "n": df[t]} for t in voc}
    import networkx as nx
    G = nx.Graph()
    for (a, b), w in ar.items():
        if w >= 2:
            G.add_edge(a, b, weight=w)
    if not G.number_of_nodes():
        return nos, ar, None
    manter = sorted(G.nodes, key=lambda k: -df[k])[:top]
    H = G.subgraph(manter).copy()
    H.remove_nodes_from([n for n in list(H.nodes) if H.degree(n) == 0])
    if not H.number_of_nodes():
        return nos, ar, None
    com = {n: i for i, c in enumerate(nx.community.greedy_modularity_communities(H, weight="weight")) for n in c}
    pos = nx.spring_layout(H, seed=7, weight="weight")
    return nos, ar, {"nos": [{"id": n, "n": df[n], "grupo": com.get(n, 0), "x": round(float(pos[n][0]), 4), "y": round(float(pos[n][1]), 4)} for n in H.nodes],
                     "arestas": [[a, b, d["weight"]] for a, b, d in H.edges(data=True) if d["weight"] >= 3][:600],
                     "total_palavras": len(voc), "total_ligacoes": len(ar)}


def chd_debate(segmentos: list[dict]) -> dict | None:
    segs = [s for s in segmentos if s["orador"] not in FORA]  # candidatos + trechos não atribuídos
    if len(segs) < 60:
        return None
    X, voc = cr.matriz([s["texto"] for s in segs])
    n_ativos = int((X.sum(1) > 0).sum())
    rot, arvore = cr.chd(X, k=6, min_classe=max(cr.MIN_CLASSE, int(0.05 * n_ativos)))
    ok = rot > 0
    tot = X[ok].sum(0)
    classes = []
    oradores = np.array([s["orador"] for s in segs])
    for k in sorted(set(rot[ok].tolist())):
        m = rot == k
        ch = cr.chi2_assoc(X[m].sum(0), tot, int(m.sum()), int(ok.sum()))
        idx = [j for j in np.argsort(-ch) if ch[j] >= cr.CHI_CRIT][:15]
        quem = {}
        for o in ("lula", "flavio"):
            dentro = int((m & (oradores == o)).sum())
            total_o = int(((oradores == o) & ok).sum())
            quem[ORADORES[o]] = {"segmentos": dentro, "pct_da_classe": round(100 * dentro / m.sum(), 1), "pct_do_orador": round(100 * dentro / total_o, 1) if total_o else None}
        # segmento mais característico: soma do χ² das formas presentes
        pont = (X[m][:, idx].sum(1)) if idx else np.zeros(int(m.sum()))
        linhas = np.where(m)[0][np.argsort(-pont)[:2]]
        classes.append({"classe": k, "segmentos": int(m.sum()), "pct": round(100 * m.sum() / ok.sum(), 1),
                        "formas": [[voc[j], round(float(ch[j]), 1)] for j in idx], "oradores": quem,
                        "trechos": [{"orador": ORADORES[segs[i]["orador"]], "ini": segs[i]["ini"], "trecho": " ".join(segs[i]["texto"].split()[:25]) + "…"} for i in linhas]})
    return {"segmentos": len(segs), "classificados": int(ok.sum()), "pct_classificados": round(100 * ok.sum() / len(segs), 1),
            "classes": classes, "arvore": arvore,
            "nota": "CHD de Reinert do Atlas (chd_reinert.py): sem lematização e com classificação simples; confira no IRaMuTeQ com o corpus do privado. Os nomes das classes são dados por quem lê as formas e os trechos."}


def iramuteq(segmentos: list[dict], inicio: float) -> str:
    linhas = []
    for s in segmentos:
        if s["orador"] in FORA:
            continue
        bloco = int((s["ini"] - inicio) // 1800) + 1  # blocos de 30 min desde o início do debate
        tx = re.sub(r"[*\-$]", " ", s["texto"])
        linhas.append(f"**** *orador_{s['orador']} *bloco_{bloco}\n{tx}\n")
    return "\n".join(linhas)


def main(argv=None) -> int:
    root = Path(argv[0]) if argv else Path(".")
    interno = os.environ.get("ODI_INTERNO_DIR")
    arq = Path(interno) / "debate/transcricao.json" if interno else None
    if not arq or not arq.exists():
        print("⛔ transcrição não encontrada no privado")
        return 1
    tr = json.loads(arq.read_text(encoding="utf-8"))
    segs = tr["segmentos"]
    pc = root / "data/config/debate_turnos.json"
    cfg_turnos = json.loads(pc.read_text(encoding="utf-8")) if pc.exists() else {}
    correcoes = cfg_turnos.get("turnos", {})
    quem = orador_por_deixas(segs, correcoes)
    segmentos = segmentar(segs, quem)
    tempo = Counter()
    for i, (s, q) in enumerate(zip(segs, quem)):  # legendas automáticas se sobrepõem: o trecho vai até o início do seguinte
        seg_fim = min(s["fim"], segs[i + 1]["ini"]) if i + 1 < len(segs) and segs[i + 1].get("bloco") == s.get("bloco") else s["fim"]
        tempo[q] += max(0.0, seg_fim - s["ini"])
    cfg = json.loads((root / "data/config/temas_youtube.json").read_text(encoding="utf-8"))
    out_dir = root / "data/debate"
    out_dir.mkdir(parents=True, exist_ok=True)
    redes = {}
    for nome, filtro in (("todos", ("lula", "flavio", "indefinido")), ("lula", ("lula",)), ("flavio", ("flavio",))):
        nos, ar, des = rede([s for s in segmentos if s["orador"] in filtro])
        if nos:
            gexf(nos, ar, out_dir / f"rede_palavras_{nome}.gexf")
        redes[nome] = des
    ch = chd_debate(segmentos)
    pi = Path(interno) / "debate"
    (pi / "corpus_iramuteq.txt").write_text(iramuteq(segmentos, segs[0]["ini"] if segs else 0), encoding="utf-8")
    deixas = sum(1 for i, q in enumerate(quem) if q == "mediacao" and i and quem[i - 1] != "mediacao")
    out = {"schema_version": 1, "gerado_em_utc": now_utc(), "video": tr["video"], "fonte_transcricao": tr["fonte"],
           "inicio_s": segs[0]["ini"] if segs else None, "fim_s": segs[-1]["fim"] if segs else None,
           "segmentos": len(segmentos), "palavras": sum(len(s["texto"].split()) for s in segmentos),
           "tempo_de_fala_min": {ORADORES[o]: round(tempo[o] / 60, 1) for o in ORADORES if o != "intervalo"},
           "intervalos_min": round(tempo["intervalo"] / 60, 1),
           "palavras_por_orador": {ORADORES[o]: sum(len(s["texto"].split()) for s in segmentos if s["orador"] == o) for o in ORADORES},
           "atribuicao": {"metodo": (cfg_turnos.get("metodo") or "codificação manual dos turnos") if correcoes else "automática por deixas da mediação (nome do candidato + passagem de tempo); não validada",
                          "manual": bool(correcoes),
                          "deixas_encontradas": deixas, "correcoes_manuais": len(correcoes)},
           "temas": temas(segmentos, cfg), "rede": redes, "chd": ch,
           "palavras_mais_usadas": {ORADORES[o]: bc.nuvem([s["texto"] for s in segmentos if s["orador"] == o], set(), top=40, minimo=3) for o in ("lula", "flavio")},
           "arquivos": {"gexf": {n: f"data/debate/rede_palavras_{n}.gexf" for n in redes if redes[n]}, "iramuteq": "privado: debate/corpus_iramuteq.txt"}}
    (out_dir / "analise.json").write_text(json.dumps(out, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(f"debate: {len(segmentos)} segmentos · tempo de fala (min) {out['tempo_de_fala_min']} · deixas {deixas} · classes CHD {len(ch['classes']) if ch else 0}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
