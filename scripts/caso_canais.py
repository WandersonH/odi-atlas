#!/usr/bin/env python3
"""Casos de canais do YouTube (grátis, API): produção, temas, público em comum e cruzamento com o acervo das campanhas.

Pedido do responsável (27/10/2026, 03h02): caso 012, "frente transnacionalização bolsonarismo", com os canais
@allandossantosbr, @PauloFigueiredoShow e @delegadoramagem. Configuração em data/config/caso_canais.json.

Coleta (YOUTUBE_API_KEY):
  1. canais pelo @ (channels?forHandle=), estatísticas e envios desde `desde`;
  2. comentários dos vídeos publicados desde `comentarios_desde` (até `paginas` páginas de 100 conversas por vídeo, ordem por data);
     a cada execução, vídeos com menos de 3 dias são relidos (comentários novos), os demais só na primeira vez.
Análise:
  - produção: vídeos por semana, visualizações, média por vídeo; temas por expressão regular no título e na descrição (TEMAS);
  - público: autores em comum entre os canais (contagem e índice de Jaccard) e lado de cada autor no acervo do Atlas de comentários
    nos canais das campanhas (Lula, Flávio, ambos, nenhum), como no caso 011;
  - série de inscritos a cada leitura.
Redes (Gephi, data/casos/<caso>/): canais × canais (autores em comum, com as âncoras do acervo), canais × autores (autores em
código) e canais × temas/pessoas citadas nos títulos (peso = vídeos). Texto e autor dos comentários só no privado.
Uso: python scripts/caso_canais.py --caso 012 [--sem-coleta]
"""
from __future__ import annotations

import csv
import gzip
import json
import os
import re
import sys
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from caso_joice import codigo, detalhes, lados_do_acervo, perfil, yt  # noqa: E402
from collect_comentarios_youtube import CAMPOS, linhas_da_conversa  # noqa: E402
from net import now_utc  # noqa: E402
from redes_caso import gexf  # noqa: E402

TEMAS = {
    "EUA, Trump ou Rubio": r"\beua\b|estados unidos|\busa\b|america|trump|rubio|casa branca|white house|washington|departamento de estado|state department",
    "sanções, Magnitsky, tarifas ou vistos": r"san[cç]\w*|sanction\w*|magnitsk\w*|tarif\w*|\bvistos?\b|\bvisa\b",
    "exílio, asilo ou perseguição": r"ex[ií]li\w*|asilo|perseg\w*|refugiad\w*|foragid\w*|extradi\w*|pris[aã]o|preso\w*",
    "Moraes, STF ou censura": r"moraes|xand[aã]o|\bstf\b|supremo|ministro|censur\w*|ditadura|toga",
    "eleição, urna ou fraude": r"elei[cç]\w*|\beleit\w*|\burnas?\b|fraud\w*|apura[cç]\w*|\btse\b|\bvot[oa]\w*|2[ºo°] turno|segundo turno",
    "golpe ou 8 de janeiro": r"\bgolpe\w*|8 de janeiro|8/1|anistia|\bcoup\b",
    "Lula ou PT": r"\blula\w*|\bpt\b|petist\w*|esquerd\w*|comunis\w*",
    "Bolsonaro e família": r"bolsonar\w*|\bjair\b|fl[aá]vio|eduardo\b|carluxo|michelle",
    "Venezuela, Cuba ou América Latina": r"venezuel\w*|maduro|cuba|nicar[aá]gua|argentin\w*|milei|am[eé]rica latina|col[oô]mbia|petro\b",
}
PESSOAS = {
    "Trump": r"trump", "Rubio": r"rubio", "Eduardo Bolsonaro": r"eduardo bolsonaro|\beduardo\b", "Jair Bolsonaro": r"jair|bolsonaro(?! *fl)",
    "Flávio Bolsonaro": r"fl[aá]vio", "Lula": r"\blula", "Alexandre de Moraes": r"moraes|xand[aã]o", "Allan dos Santos": r"allan",
    "Paulo Figueiredo": r"figueiredo", "Alexandre Ramagem": r"ramagem", "Elon Musk": r"musk", "Maduro": r"maduro", "Milei": r"milei",
}
LIMITE_RELEITURA_DIAS = 3


def coletar(cfg: dict, key: str, priv: Path, erros: list) -> dict:
    agora = now_utc()
    q = lambda **k: {**k, "key": key}  # noqa: E731
    estado_arq = priv / "estado.json"
    estado = json.loads(estado_arq.read_text(encoding="utf-8")) if estado_arq.exists() else {"lidos": {}}
    canais, envios = [], []
    for h in cfg["handles"]:
        try:
            it = (yt("channels", **q(part="snippet,statistics,contentDetails", forHandle=h)).get("items") or [None])[0]
        except RuntimeError as e:
            erros.append(f"canal @{h}: {e}")
            continue
        if not it:
            erros.append(f"canal @{h}: não encontrado")
            continue
        st, sn = it.get("statistics", {}), it.get("snippet", {})
        canais.append({"handle": h, "id": it["id"], "titulo": sn.get("title"), "pais": sn.get("country"), "criado_em": sn.get("publishedAt"),
                       "inscritos": int(st.get("subscriberCount", 0) or 0), "visualizacoes": int(st.get("viewCount", 0) or 0),
                       "videos": int(st.get("videoCount", 0) or 0), "lido_em_utc": agora})
        up, ids, tok = it["contentDetails"]["relatedPlaylists"]["uploads"], [], None
        for _ in range(60):
            p = q(part="contentDetails", playlistId=up, maxResults=50)
            if tok:
                p["pageToken"] = tok
            try:
                r = yt("playlistItems", **p)
            except RuntimeError as e:
                erros.append(f"envios @{h}: {e}")
                break
            itens = r.get("items", [])
            ids += [x["contentDetails"]["videoId"] for x in itens]
            tok = r.get("nextPageToken")
            datas = [x["contentDetails"].get("videoPublishedAt") or "" for x in itens]
            if not tok or (datas and max(datas) < cfg["desde"]):
                break
        envios += [v for v in detalhes(ids, q, erros) if (v["publicado_em"] or "") >= cfg["desde"]]
    limite = (datetime.now(timezone.utc) - timedelta(days=LIMITE_RELEITURA_DIAS)).strftime("%Y-%m-%dT%H:%M:%SZ")
    rows = []
    for v in envios:
        if (v["publicado_em"] or "") < cfg["comentarios_desde"] or not v.get("comentarios"):
            continue
        if v["id"] in estado["lidos"] and (v["publicado_em"] or "") < limite:
            continue
        meta, tok = {"video_id": v["id"], "candidate_id": "", "channel_id": v["canal_id"]}, None
        for _ in range(cfg.get("paginas", 3)):
            p = q(part="snippet,replies", videoId=v["id"], maxResults=100, order="time", textFormat="plainText")
            if tok:
                p["pageToken"] = tok
            try:
                r = yt("commentThreads", **p)
            except RuntimeError as e:
                erros.append(f"comentários {v['id']}: {e}")
                if "quotaExceeded" in str(e):
                    break
                break
            rows += [l for it in r.get("items", []) for l in linhas_da_conversa(it, meta, "caso", agora)]
            tok = r.get("nextPageToken")
            if not tok:
                break
        estado["lidos"][v["id"]] = agora
    priv.mkdir(parents=True, exist_ok=True)
    arq = priv / "youtube_comentarios.csv.gz"
    antigos = {r["comment_id"]: r for r in csv.DictReader(gzip.open(arq, "rt", encoding="utf-8"), delimiter=";")} if arq.exists() else {}
    antigos.update({r["comment_id"]: r for r in rows})
    with gzip.open(arq, "wt", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, CAMPOS, delimiter=";", lineterminator="\n", extrasaction="ignore")
        w.writeheader()
        w.writerows(antigos.values())
    estado_arq.write_text(json.dumps(estado, ensure_ascii=False), encoding="utf-8")
    return {"lido_em_utc": agora, "canais": canais, "envios": sorted(envios, key=lambda v: v["publicado_em"] or ""),
            "comentarios_lidos_nesta_execucao": len({r["comment_id"] for r in rows})}


def semana(iso: str) -> str:
    d = datetime.fromisoformat(iso.replace("Z", "+00:00")) - timedelta(hours=3)
    return (d - timedelta(days=d.weekday())).strftime("%Y-%m-%d")


def analisar(caso: str, cfg: dict, dados: dict, priv: Path, interno: Path, pub: Path) -> dict:
    arq = priv / "youtube_comentarios.csv.gz"
    rows = list(csv.DictReader(gzip.open(arq, "rt", encoding="utf-8"), delimiter=";")) if arq.exists() else []
    lados = lados_do_acervo(interno)
    canais = dados.get("canais", [])
    nome = {c["id"]: c["titulo"] for c in canais}
    envios = dados.get("envios", [])
    prod = []
    for c in canais:
        vs = [v for v in envios if v["canal_id"] == c["id"]]
        sem = Counter(semana(v["publicado_em"]) for v in vs if v.get("publicado_em"))
        temas = Counter(t for v in vs for t, rx in TEMAS.items() if re.search(rx, f"{v['titulo']} {v['descricao']}", re.I))
        views = [v["visualizacoes"] for v in vs if v["visualizacoes"] is not None]
        prod.append({**c, "videos_no_periodo": len(vs), "visualizacoes_no_periodo": sum(views), "media_por_video": round(sum(views) / len(views)) if views else None,
                     "por_semana": dict(sorted(sem.items())), "temas": {t: {"n": temas.get(t, 0), "pct": round(100 * temas.get(t, 0) / len(vs), 1) if vs else None} for t in TEMAS},
                     "mais_vistos": sorted(vs, key=lambda v: -(v["visualizacoes"] or 0))[:10]})
    autores = defaultdict(set)
    for r in rows:
        if r.get("autor_canal"):
            autores[r["channel_id"]].add(r["autor_canal"])
    publico = [{"canal_id": c["id"], "canal": c["titulo"], **perfil([r for r in rows if r["channel_id"] == c["id"]], lados)} for c in canais]
    pares = []
    ids = [c["id"] for c in canais]
    for i, a in enumerate(ids):
        for b in ids[i + 1:]:
            x, y = autores.get(a, set()), autores.get(b, set())
            inter = len(x & y)
            pares.append({"a": nome[a], "b": nome[b], "autores_em_comum": inter, "jaccard": round(inter / len(x | y), 4) if x | y else None,
                          "pct_de_a": round(100 * inter / len(x), 1) if x else None, "pct_de_b": round(100 * inter / len(y), 1) if y else None})
    todos = set().union(*autores.values()) if autores else set()
    em_todos = set.intersection(*[autores.get(i, set()) for i in ids]) if ids else set()
    # redes
    nos = {"ACERVO_LULA": {"rotulo": "Acervo: comentou em canais de Lula", "tipo": "âncora", "n": 0},
           "ACERVO_FLAVIO": {"rotulo": "Acervo: comentou em canais de Flávio", "tipo": "âncora", "n": 0}}
    ar = Counter()
    for c in canais:
        nos[c["id"]] = {"rotulo": c["titulo"], "tipo": "canal", "n": len(autores.get(c["id"], ()))}
    for r in rows:
        a = r.get("autor_canal")
        if a and r["channel_id"] in nos:
            k = codigo(a)
            nos.setdefault(k, {"rotulo": k, "tipo": f"autor · acervo: {lados.get(a, 'nenhum')}", "n": 0})
            nos[k]["n"] += 1
            ar[(r["channel_id"], k)] += 1
    for a in todos:
        lado = lados.get(a, "nenhum")
        if lado in ("lula", "ambos"):
            ar[("ACERVO_LULA", codigo(a))] += 1
        if lado in ("flavio", "ambos"):
            ar[("ACERVO_FLAVIO", codigo(a))] += 1
    gexf(nos, dict(ar), pub / "rede_canais_autores.gexf")
    cn = {k: v for k, v in nos.items() if v["tipo"] in ("canal", "âncora")}
    conj = {**autores, "ACERVO_LULA": {a for a, l in lados.items() if l in ("lula", "ambos")},
            "ACERVO_FLAVIO": {a for a, l in lados.items() if l in ("flavio", "ambos")}}
    cc, ks = Counter(), list(cn)
    for i, x in enumerate(ks):
        for y in ks[i + 1:]:
            w = len(conj.get(x, set()) & conj.get(y, set()))
            if w:
                cc[(x, y)] = w
    gexf(cn, dict(cc), pub / "rede_canais.gexf")
    nt, at = {c["id"]: {"rotulo": c["titulo"], "tipo": "canal", "n": 0} for c in canais}, Counter()
    for v in envios:
        txt = f"{v['titulo']} {v['descricao']}"
        for p, rx in PESSOAS.items():
            if re.search(rx, txt, re.I):
                nt.setdefault("P:" + p, {"rotulo": p, "tipo": "pessoa citada", "n": 0})
                nt["P:" + p]["n"] += 1
                at[(v["canal_id"], "P:" + p)] += 1
        for t, rx in TEMAS.items():
            if re.search(rx, txt, re.I):
                nt.setdefault("T:" + t, {"rotulo": t, "tipo": "tema", "n": 0})
                nt["T:" + t]["n"] += 1
                at[(v["canal_id"], "T:" + t)] += 1
    for c in canais:
        nt[c["id"]]["n"] = sum(1 for v in envios if v["canal_id"] == c["id"])
    gexf(nt, dict(at), pub / "rede_canais_temas.gexf")
    serie_arq = pub / "canais_serie.json"
    serie = json.loads(serie_arq.read_text(encoding="utf-8")) if serie_arq.exists() else []
    for c in canais:
        if all(not (x["id"] == c["id"] and x["lido_em_utc"] == c["lido_em_utc"]) for x in serie):
            serie.append({k: c[k] for k in ("id", "titulo", "lido_em_utc", "inscritos", "visualizacoes", "videos")})
    serie_arq.write_text(json.dumps(serie, ensure_ascii=False, indent=1), encoding="utf-8")
    return {"caso": caso, "gerado_em_utc": now_utc(), "titulo": cfg["titulo"], "desde": cfg["desde"], "comentarios_desde": cfg["comentarios_desde"],
            "producao": prod, "publico": publico, "pares": pares, "autores_total": len(todos), "autores_em_todos_os_canais": len(em_todos),
            "comentarios_total": len(rows), "acervo_autores": len(lados), "serie": serie, "temas_regex": TEMAS,
            "redes": {"canais": len(cn), "canais_autores": len(nos), "canais_temas": len(nt)},
            "nota": "Lado no acervo: o autor já comentou (desde a pré-campanha) em vídeos dos canais da campanha de Lula, de Flávio, dos dois ou de nenhum. "
                    "Temas por expressão regular no título e no começo da descrição; um vídeo pode ter vários temas."}


def main(argv=None) -> int:
    argv = sys.argv[1:] if argv is None else list(argv)
    caso = argv[argv.index("--caso") + 1] if "--caso" in argv else "012"
    cfg = json.loads(Path("data/config/caso_canais.json").read_text(encoding="utf-8"))[caso]
    interno, key = os.environ.get("ODI_INTERNO_DIR"), os.environ.get("YOUTUBE_API_KEY", "")
    if not interno:
        print("⛔ ODI_INTERNO_DIR ausente")
        return 1
    priv, pub = Path(interno) / "casos" / caso, Path("data/casos") / caso
    pub.mkdir(parents=True, exist_ok=True)
    priv.mkdir(parents=True, exist_ok=True)
    erros, bruto = [], priv / "youtube_dados.json"
    if "--sem-coleta" not in argv:
        if not key:
            print("⛔ YOUTUBE_API_KEY ausente")
            return 1
        bruto.write_text(json.dumps(coletar(cfg, key, priv, erros), ensure_ascii=False), encoding="utf-8")
    dados = json.loads(bruto.read_text(encoding="utf-8")) if bruto.exists() else {}
    out = analisar(caso, cfg, dados, priv, Path(interno), pub)
    out["erros"] = erros
    (pub / "youtube.json").write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"caso {caso}: " + " · ".join(f"{p['titulo']}: {p['inscritos']} inscritos, {p['videos_no_periodo']} vídeos" for p in out["producao"])
          + f" · comentários {out['comentarios_total']} · autores em todos os canais {out['autores_em_todos_os_canais']} · erros {erros[:4]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
