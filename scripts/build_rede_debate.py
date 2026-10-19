#!/usr/bin/env python3
"""Redes do debate (Google Trends em alta + Google Notícias) para a página e para o Gephi.

Pedido do usuário (18/10/2026, 23h05): "pode gerar as redes de canais e palavras-chave".
- Rede de canais: termo em alta (Política) — veículo cuja matéria está entre as 5 primeiras do Google Notícias para o termo.
  Peso = número de matérias do veículo no topo do termo (melhor posição guardada). Mostra quais veículos pautam cada busca.
- Rede de palavras-chave: termo em alta (Política) — termos que o próprio Trends agrupa nele ("detalhamento"), e
  Lula / Flávio Bolsonaro / "debate" — suas consultas relacionadas (principais e em alta) nas últimas 24 h.
Entrada: data/trends/agora/debate.json. Saída: data/trends/agora/rede_canais.{gexf,json}, rede_palavras.{gexf,json} e CSVs.
Os desenhos (JSON) trazem posições calculadas (networkx, semente fixa) e o GEXF leva a rede inteira.
"""
from __future__ import annotations

import csv
import json
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from build_casos import gexf  # noqa: E402
from net import now_utc  # noqa: E402


def norm(s: str) -> str:
    """Chave do nó: minúsculas, sem acento e sem espaços repetidos ("flávio miliciano" e "flavio miliciano" viram um nó só)."""
    import unicodedata
    t = unicodedata.normalize("NFKD", str(s or "").lower())
    return " ".join("".join(c for c in t if not unicodedata.combining(c)).split())


def canais(d: dict) -> tuple[dict, Counter]:
    nos, ar = {}, Counter()
    for t in d["termos"]:
        if not t.get("politica") or not t.get("materias"):
            continue
        a = "t:" + norm(t["termo"])
        nos.setdefault(a, {"rotulo": t["termo"], "tipo": "termo em alta", "n": 0, "volume": t.get("volume_max")})
        for m in t["materias"]:
            v = (m.get("veiculo") or m.get("dominio") or "").strip()
            if not v:
                continue
            b = "v:" + norm(v)
            nos.setdefault(b, {"rotulo": v, "tipo": "veículo", "n": 0})["n"] += 1
            nos[a]["n"] += 1
            ar[(a, b)] += 1
    return nos, ar


def palavras(d: dict) -> tuple[dict, Counter]:
    nos, ar = {}, Counter()
    for t in d["termos"]:
        if not t.get("politica"):
            continue
        a = "t:" + norm(t["termo"])
        nos.setdefault(a, {"rotulo": t["termo"], "tipo": "termo em alta", "n": 0, "volume": t.get("volume_max")})
        for r in t.get("relacionados") or []:
            if norm(r) == norm(t["termo"]):
                continue
            b = "t:" + norm(r)
            nos.setdefault(b, {"rotulo": r, "tipo": "termo agrupado pelo Trends", "n": 0})["n"] += 1
            nos[a]["n"] += 1
            ar[(a, b)] += 1
    for alvo, listas in ((d.get("curvas") or {}).get("relacionados_24h") or {}).items():
        a = "c:" + norm(alvo)
        nos.setdefault(a, {"rotulo": alvo, "tipo": "termo acompanhado", "n": 0})
        for lista, itens in listas.items():
            for x in itens[:15]:
                b = "t:" + norm(x["texto"])
                nos.setdefault(b, {"rotulo": x["texto"], "tipo": "consulta relacionada", "n": 0})["n"] += 1
                nos[a]["n"] += 1
                ar[(a, b)] += 1
    return nos, ar


def desenho(nos: dict, ar: Counter, maximo: int = 90) -> dict | None:
    import networkx as nx
    G = nx.Graph()
    for (a, b), w in ar.items():
        G.add_edge(a, b, weight=w)
    if not G.number_of_nodes():
        return None
    grau = dict(G.degree(weight="weight"))
    manter = set(sorted(grau, key=lambda k: -grau[k])[:maximo])
    H = G.subgraph(manter).copy()
    H.remove_nodes_from([n for n in list(H.nodes) if H.degree(n) == 0])
    pos = nx.spring_layout(H, seed=7, weight="weight", k=1.4 / max(1, H.number_of_nodes()) ** 0.5)
    return {"nos": [{"id": k, "rotulo": nos[k]["rotulo"], "tipo": nos[k]["tipo"], "grau": grau[k], "volume": nos[k].get("volume"),
                     "x": round(float(pos[k][0]), 4), "y": round(float(pos[k][1]), 4)} for k in H.nodes],
            "arestas": [[a, b, dd["weight"]] for a, b, dd in H.edges(data=True)],
            "total_nos": G.number_of_nodes(), "total_arestas": G.number_of_edges()}


def salvar(pasta: Path, nome: str, nos: dict, ar: Counter, meta: dict):
    gexf(nos, ar, pasta / f"{nome}.gexf")
    with open(pasta / f"{nome}_nos.csv", "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f, delimiter=";")
        w.writerow(["id", "rotulo", "tipo", "ligacoes"])
        for k, v in nos.items():
            w.writerow([k, v["rotulo"], v["tipo"], v["n"]])
    with open(pasta / f"{nome}_arestas.csv", "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f, delimiter=";")
        w.writerow(["origem", "destino", "peso"])
        for (a, b), p in ar.items():
            w.writerow([a, b, p])
    (pasta / f"{nome}.json").write_text(json.dumps({**meta, "desenho": desenho(nos, ar)}, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")


def main(argv=None) -> int:
    root = Path(argv[0]) if argv else Path(".")
    pasta = root / "data/trends/agora"
    d = json.loads((pasta / "debate.json").read_text(encoding="utf-8"))
    base = {"gerado_em_utc": now_utc(), "fonte_em_utc": d.get("gerado_em_utc")}
    n1, a1 = canais(d)
    v = Counter({k: x["n"] for k, x in n1.items() if x["tipo"] == "veículo"})
    salvar(pasta, "rede_canais", n1, a1, {**base, "o_que_e": "termo em alta (Política) — veículo com matéria entre as 5 primeiras do Google Notícias para o termo",
                                         "veiculos_mais_presentes": [[n1[k]["rotulo"], c] for k, c in v.most_common(15)]})
    n2, a2 = palavras(d)
    salvar(pasta, "rede_palavras", n2, a2, {**base, "o_que_e": "termo em alta (Política) — termos que o Trends agrupa nele; Lula, Flávio Bolsonaro e debate — consultas relacionadas (24 h)"})
    print(f"rede de canais: {len(n1)} nós, {len(a1)} ligações · rede de palavras: {len(n2)} nós, {len(a2)} ligações")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
