#!/usr/bin/env python3
"""Rede de influenciadores do YouTube que citam Lula (vermelho) ou Flávio Bolsonaro (verde) — caderno 02.

Entrada: data/youtube/influenciadores/videos.csv.gz + canais.csv (collect_influenciadores.py)
Saída (data/youtube/influenciadores/):
  rede.json            desenhada na página
  rede.gexf            Gephi (posição, cor, tamanho)
  rede_nos.csv         Id;Label;tipo;inscritos;videos_lula;videos_flavio;... (Importar planilha do Gephi)
  rede_arestas.csv     Source;Target;Weight;Type (canal → candidato; peso = nº de vídeos que citam)
  videos_validos.csv   base de conferência: cada vídeo que gerou aresta, com link

Rede bipartida: 2 nós de candidato + canais. Só canais com min_inscritos+ (contagem pública).
"Cita" não é "apoia": o vídeo pode ser favorável, contrário ou neutro.
Até MAX_CANAIS canais, pelos que mais publicaram vídeos citando (desempate: visualizações).
Posição: ForceAtlas2 LinLog (networkx), semente fixa.
"""
from __future__ import annotations

import csv
import datetime as dt
import gzip
import json
import math
import sys
from pathlib import Path

import networkx as nx

sys.path.insert(0, str(Path(__file__).resolve().parent))
from collect_influenciadores import avaliar, canais_de_campanha, compilar  # noqa: E402

MAX_CANAIS = 200
SEMENTE = 42


def mistura(c1: str, c2: str, f: float) -> str:
    """f=1 → c1; f=0 → c2."""
    a = [int(c1[i:i + 2], 16) for i in (1, 3, 5)]
    b = [int(c2[i:i + 2], 16) for i in (1, 3, 5)]
    return "#" + "".join(f"{round(b[i] + (a[i] - b[i]) * f):02x}" for i in range(3))


def montar(videos: list[dict], canais: dict, cfg: dict, max_canais: int = MAX_CANAIS):
    ids = list(cfg["candidatos"])
    agg: dict[str, dict] = {}
    for v in videos:
        if v["excluido"]:
            continue
        ch = canais.get(v["channel_id"])
        if not ch or not ch.get("inscritos") or int(ch["inscritos"]) < cfg["min_inscritos"]:
            continue
        a = agg.setdefault(v["channel_id"], {cid: 0 for cid in ids} | {f"voto_{cid}": 0 for cid in ids} | {"views": 0, "videos": 0})
        a["videos"] += 1
        a["views"] += int(v["visualizacoes"] or 0)
        for cid in ids:
            a[cid] += int(v[f"cita_{cid}"])
            a[f"voto_{cid}"] += int(str(v.get(f"nivel_{cid}", "0")) == "2")
    escolhidos = sorted(agg, key=lambda c: (-agg[c]["videos"], -agg[c]["views"], c))[:max_canais]
    g = nx.Graph()
    for cid, c in cfg["candidatos"].items():
        g.add_node("cand:" + cid, label=c["nome"], tipo="candidato", cor=c["cor"], inscritos=0, views=0,
                   **{f"v_{x}": 0 for x in ids}, **{f"voto_{x}": 0 for x in ids})
    for ch in escolhidos:
        a, info = agg[ch], canais[ch]
        tot = sum(a[cid] for cid in ids) or 1
        g.add_node(ch, label=info["canal"], tipo="canal", handle=info.get("handle", ""), inscritos=int(info["inscritos"]),
                   views=a["views"], videos=a["videos"], frac_lula=round(a[ids[0]] / tot, 3),
                   cor=mistura(cfg["candidatos"][ids[0]]["cor"], cfg["candidatos"][ids[1]]["cor"], a[ids[0]] / tot),
                   **{f"v_{x}": a[x] for x in ids}, **{f"voto_{x}": a[f"voto_{x}"] for x in ids})
        for cid in ids:
            if a[cid]:
                g.add_edge(ch, "cand:" + cid, weight=a[cid], pede_voto=a[f"voto_{cid}"],
                           nivel=2 if a[f"voto_{cid}"] else 1)
                g.nodes["cand:" + cid][f"v_{cid}"] += a[cid]
                g.nodes["cand:" + cid][f"voto_{cid}"] += a[f"voto_{cid}"]
                g.nodes["cand:" + cid]["views"] += a["views"]
    return g


def posicionar(g: nx.Graph):
    if g.number_of_nodes() < 3:
        for i, n in enumerate(g.nodes):
            g.nodes[n]["x"], g.nodes[n]["y"] = 500.0, 500.0 + i
        return
    ini = nx.spring_layout(g, weight="weight", seed=SEMENTE)
    pos = nx.forceatlas2_layout(g, pos=ini, weight="weight", seed=SEMENTE, max_iter=800, linlog=True,
                                distributed_action=True)
    if any(not (math.isfinite(float(x)) and math.isfinite(float(y))) for x, y in pos.values()):
        raise RuntimeError("layout gerou posição inválida (NaN); rede não publicada")
    xs, ys = [float(p[0]) for p in pos.values()], [float(p[1]) for p in pos.values()]
    span = max(max(xs) - min(xs), max(ys) - min(ys)) or 1.0
    for n, (x, y) in pos.items():
        g.nodes[n]["x"] = round((float(x) - min(xs)) / span * 1000, 1)
        g.nodes[n]["y"] = round((float(y) - min(ys)) / span * 1000, 1)


def main(argv=None) -> int:
    root = Path(argv[0]) if argv else Path(".")
    cfg = json.loads((root / "data/config/influenciadores_youtube.json").read_text(encoding="utf-8"))
    d = root / "data/youtube/influenciadores"
    vp = d / "videos.csv.gz"
    if not vp.exists():
        print("⛔ sem coleta de influenciadores (data/youtube/influenciadores/videos.csv.gz)")
        return 1
    videos = list(csv.DictReader(gzip.open(vp, "rt", encoding="utf-8"), delimiter=";"))
    canais = {r["channel_id"]: r for r in csv.DictReader(open(d / "canais.csv", encoding="utf-8"), delimiter=";")}
    ids = list(cfg["candidatos"])
    # reaplica as regras do config a todo o acervo (mudar a regra não exige coletar de novo)
    men, excl = compilar(cfg)
    campanha = canais_de_campanha(root)
    for v in videos:
        v.update(avaliar(v, men, excl, cfg["excluir_categorias"]))
        if v["channel_id"] in campanha:
            v["excluido"] = "canal de campanha (declarado ao TSE)"
    metodo = (f"{cfg['nota']} Busca do YouTube (search.list) por " +
              "; ".join(f"{c['nome']}: {', '.join(c['buscas'])}" for c in cfg["candidatos"].values()) +
              f", desde {cfg['desde']}, acumulada a cada coleta diária. Só conta vídeo com o nome no título ou na descrição; "
              f"excluídos canais de campanha declarados ao TSE, categorias {', '.join(cfg['excluir_categorias'].values())} e termos de culinária. "
              f"Canal com {cfg['min_inscritos']:,}+ inscritos públicos; até {MAX_CANAIS} canais (os que mais citam). ".replace(",", ".") + NIVEIS)
    return gerar(videos, canais, cfg, d, metodo, lambda c: f"https://www.youtube.com/channel/{c}",
                 lambda v: f"https://www.youtube.com/watch?v={v['video_id']}")


NIVEIS = ("Níveis por vídeo (iguais para os dois): 1 = falou do candidato (nome, @, hashtag ou o número como voto, ex.: 'Flávio 22', '#lula13'); "
          "2 = pediu voto (ex.: 'vote 22', 'dia 25 é Flávio', 'vote 13', 'dia 25 é Lula'). Regra por palavras: notícia que relata um pedido "
          "de voto também cai no nível 2; o trecho que disparou cada caso está na planilha. Aresta = nº de vídeos do canal que falam do "
          "candidato; linha cheia quando algum desses vídeos pede voto. Posição: ForceAtlas2 LinLog (networkx), semente 42.")


def gerar(videos, canais, cfg, d: Path, metodo: str, url_canal, url_video) -> int:
    """Monta, posiciona e grava rede.json, rede_nos.csv, rede_arestas.csv, videos_validos.csv e rede.gexf em `d`.
    Usada pelo YouTube (influenciadores) e pelo TikTok (contas que publicam com hashtags dos candidatos)."""
    ids = list(cfg["candidatos"])
    g = montar(videos, canais, cfg)
    posicionar(g)
    canais_n = [n for n in g.nodes if g.nodes[n]["tipo"] == "canal"]
    so = {cid: sum(1 for n in canais_n if g.nodes[n][f"v_{cid}"] and not any(g.nodes[n][f"v_{o}"] for o in ids if o != cid)) for cid in ids}
    ambos = sum(1 for n in canais_n if all(g.nodes[n][f"v_{cid}"] for cid in ids))
    coleta = max((v["ultima_coleta"] for v in videos), default=None)
    validos = [v for v in videos if not v["excluido"] and v["channel_id"] in g]
    out = {"schema_version": 1, "gerado_em_utc": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
           "coletado_em_utc": coleta, "metodo": metodo,
           "niveis": cfg["niveis"],
           "candidatos": {cid: {"nome": c["nome"], "cor": c["cor"], "numero": c["numero"],
                                "canais": sum(1 for n in canais_n if g.nodes[n][f"v_{cid}"]),
                                "canais_pedem_voto": sum(1 for n in canais_n if g.nodes[n][f"voto_{cid}"]),
                                "so_ele": so[cid], "videos": g.nodes["cand:" + cid][f"v_{cid}"],
                                "videos_pedem_voto": g.nodes["cand:" + cid][f"voto_{cid}"]} for cid, c in cfg["candidatos"].items()},
           "canais_ambos": ambos, "canais_total": len(canais_n), "videos_validos": len(validos),
           "nos": [{"id": n, "label": a["label"], "tipo": a["tipo"], "x": a["x"], "y": a["y"], "cor": a["cor"],
                    "inscritos": a["inscritos"], "views": a["views"], "videos": a.get("videos", 0), "handle": a.get("handle", ""),
                    **{f"v_{cid}": a[f"v_{cid}"] for cid in ids}, **{f"voto_{cid}": a[f"voto_{cid}"] for cid in ids}}
                   for n, a in sorted(g.nodes(data=True))],
           "arestas": [[a, b, w["weight"], w["pede_voto"]] for a, b, w in sorted(g.edges(data=True))]}
    # até 5 vídeos mais vistos de cada canal, para o painel de detalhe
    por_canal: dict[str, list] = {}
    for v in validos:
        por_canal.setdefault(v["channel_id"], []).append(v)
    for n in out["nos"]:
        if n["tipo"] == "canal":
            vs = sorted(por_canal.get(n["id"], []), key=lambda v: -int(v["visualizacoes"] or 0))[:5]
            n["top"] = [[v["video_id"], v["titulo"], int(v["visualizacoes"] or 0), int(v[f"nivel_{ids[0]}"]), int(v[f"nivel_{ids[1]}"])] for v in vs]
    (d / "rede.json").write_text(json.dumps(out, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    nomes = {cid: c["nome"] for cid, c in cfg["candidatos"].items()}
    with open(d / "rede_nos.csv", "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(["Id", "Label", "tipo", "inscritos", "videos_falou_lula", "videos_pediu_voto_lula", "videos_falou_flavio",
                    "videos_pediu_voto_flavio", "visualizacoes_videos", "url", "cor", "x", "y"])
        for n in out["nos"]:
            url = "" if n["tipo"] == "candidato" else url_canal(n["id"])
            w.writerow([n["id"], n["label"], n["tipo"], n["inscritos"], n[f"v_{ids[0]}"], n[f"voto_{ids[0]}"], n[f"v_{ids[1]}"],
                        n[f"voto_{ids[1]}"], n["views"], url, n["cor"], n["x"], n["y"]])
    with open(d / "rede_arestas.csv", "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(["Source", "Target", "Weight", "Type", "videos_pediu_voto", "nivel_maximo"])
        for a, b, wt, pv in out["arestas"]:
            w.writerow([a, b, wt, "Undirected", pv, 2 if pv else 1])
    with open(d / "videos_validos.csv", "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(["video_id", "url", "channel_id", "canal", "publicado_em", "titulo", "visualizacoes", "nivel_lula", "trecho_lula", "nivel_flavio", "trecho_flavio"])
        for v in sorted(validos, key=lambda v: v["publicado_em"], reverse=True):
            w.writerow([v["video_id"], url_video(v), v["channel_id"], v["canal"], v["publicado_em"],
                        v["titulo"], v["visualizacoes"], v[f"nivel_{ids[0]}"], v[f"gatilho_{ids[0]}"],
                        v[f"nivel_{ids[1]}"], v[f"gatilho_{ids[1]}"]])
    gx = g.copy()
    for n in gx.nodes:
        a = gx.nodes[n]
        r, gg, b = (int(a["cor"][i:i + 2], 16) for i in (1, 3, 5))
        size = 30.0 if a["tipo"] == "candidato" else 3 + 2 * math.log10(max(a["inscritos"], 10))
        a["viz"] = {"position": {"x": a.pop("x"), "y": -a.pop("y"), "z": 0.0}, "size": size, "color": {"r": r, "g": gg, "b": b, "a": 1.0}}
    nx.write_gexf(gx, d / "rede.gexf")
    print(f"influenciadores: {len(canais_n)} canais, {len(validos)} vídeos, {g.number_of_edges()} arestas; "
          + "; ".join(f"{nomes[c]}: {out['candidatos'][c]['canais']} canais (só ele {so[c]})" for c in ids) + f"; ambos {ambos}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
