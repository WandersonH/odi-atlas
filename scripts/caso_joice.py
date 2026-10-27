#!/usr/bin/env python3
"""Caso 011: Joice Hasselmann depois da entrevista à TV 247 (22/10/2026), em que declara voto em Lula. YouTube, grátis (API).

Pedido do responsável (27/10/2026, 02h46): "iniciado aqui [jTeWOpW7fg4] com um recorte de análise de recortes pós data da entrevista;
queria entender se ela furou ou não a bolha e entender o padrão de crescimento do perfil dela pós vídeo; redes Gephi".

Coleta (YOUTUBE_API_KEY; cota gratuita):
  1. vídeos de partida (SEMENTES) e o canal dela (canal do vídeo 9LLIWExnoK4): estatísticas do canal e todos os envios;
  2. recortes: busca do YouTube por BUSCAS desde 22/10 (data e relevância), só vídeos com "Joice" ou "Hasselmann" no título ou
     na descrição; estatísticas e inscritos de cada canal;
  3. comentários de cada vídeo do caso (sementes, recortes e envios dela desde 15/10), até PAGINAS páginas de 100 conversas.
Análise ("furou a bolha?"): cada autor de comentário é cruzado com o acervo do Atlas de comentários nos canais das campanhas
(ODI_INTERNO_DIR/youtube/comentarios/comentarios.csv.gz; candidate_id 280002542548 = Lula, 280002551544 = Flávio Bolsonaro).
Mede-se, por canal e no canal dela antes × depois de 22/10, a parcela de quem já tinha comentado no lado de Lula, no de Flávio,
nos dois ou em nenhum. Indício, não prova: o acervo cobre só os canais das campanhas desde a pré-campanha.
Crescimento: inscritos e visualizações do canal a cada leitura (série que cresce a cada execução), envios e comentários por dia.
Redes (Gephi, data/casos/011/): canais × autores (autores como código, com o lado no acervo; dois nós-âncora "Acervo Lula" e
"Acervo Flávio") e canais × canais (peso = autores em comum). Texto e autor só no privado.
Uso: python scripts/caso_joice.py [--sem-coleta]
"""
from __future__ import annotations

import csv
import gzip
import hashlib
import json
import os
import re
import sys
import time
from collections import Counter, defaultdict
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from collect_caso_busca import yt as yt_api  # noqa: E402
from collect_comentarios_youtube import CAMPOS, linhas_da_conversa  # noqa: E402
from net import now_utc  # noqa: E402
from redes_caso import gexf  # noqa: E402

CASO = "011"
MARCO = "2026-10-22T00:00:00Z"
SEMENTES = {"jTeWOpW7fg4": "entrevista à TV 247 (partida do caso)", "9LLIWExnoK4": "vídeo no canal dela"}
CANAL_DELA_VIA = "9LLIWExnoK4"
BUSCAS = ["Joice Hasselmann", "Joice Hasselmann Lula", "Joice Hasselmann Bolsonaro", "Joice Hasselmann 247", "Joice Lula voto"]
RX = re.compile(r"joice|hasselmann|hasselman", re.I)
PAGINAS = 10
LULA, FLAVIO = "280002542548", "280002551544"
MIN_PUBLICO = 10000
TEMAS = {  # comentários (pedido de 27/10/2026, 03h04: "análise geral dos comentários")
    "elogia ou acolhe Joice": r"parab[eé]ns|coragem|corajos\w*|bem[- ]vinda|respeito|admir\w*|l[uú]cid\w*|obrigad\w*|gratid\w*",
    "chama de traidora ou oportunista": r"tra[ií]d\w*|tra[ií]ra|vira[- ]?casaca|oportunist\w*|mudou de lado|cargo|mamata|hip[oó]crit\w*|interesseir\w*",
    "duvida ou desmente": r"mentir\w*|mentira|mentirosa|\bfake\b|n[aã]o acredito|inventou|lorota|vitimis\w*|teatro",
    "cita a agressão": r"agress\w*|\bmatar\b|tentou me matar|apanh\w*|espanc\w*|pancada|atentado|surr\w*",
    "cita golpe ou 8 de janeiro": r"\bgolpe\w*|8 de janeiro|ditadura",
    "cita Lula ou PT": r"\blula\w*|\bpt\b|petist\w*|esquerd\w*",
    "cita Bolsonaro e família": r"bolsonar\w*|\bjair\b|fl[aá]vio|\beduardo\b|carluxo|\bbozo\b",
    "cita eleição ou voto": r"elei[cç]\w*|\bvot\w*|urna\w*|2[ºo°] turno|segundo turno",
    "ofensa ou ataque pessoal": r"\bpeppa\b|porca|gorda|\bfeia\b|\blixo\b|vagabund\w*|\blouca\b|\bdoida\b|nojent\w*|\bburra\b",
}


def yt(rota, **q):
    for t in range(3):
        try:
            return yt_api(rota, **q)
        except RuntimeError as e:
            if "429" in str(e) and t < 2:
                time.sleep(20 * (t + 1))
                continue
            raise


def coletar(key: str, priv: Path, erros: list) -> dict:
    agora = now_utc()
    q = lambda **k: {**k, "key": key}  # noqa: E731
    # 1. sementes e canal dela
    d = yt("videos", **q(part="snippet,statistics", id=",".join(SEMENTES)))
    sem = {it["id"]: it for it in d.get("items", [])}
    canal_id = (sem.get(CANAL_DELA_VIA) or {}).get("snippet", {}).get("channelId")
    canal = {}
    envios = []
    if canal_id:
        c = (yt("channels", **q(part="snippet,statistics,contentDetails", id=canal_id)).get("items") or [{}])[0]
        st = c.get("statistics", {})
        canal = {"id": canal_id, "titulo": c.get("snippet", {}).get("title"), "handle": c.get("snippet", {}).get("customUrl"),
                 "criado_em": c.get("snippet", {}).get("publishedAt"), "inscritos": int(st.get("subscriberCount", 0) or 0),
                 "visualizacoes": int(st.get("viewCount", 0) or 0), "videos": int(st.get("videoCount", 0) or 0), "lido_em_utc": agora}
        up = c.get("contentDetails", {}).get("relatedPlaylists", {}).get("uploads")
        ids, tok = [], None
        for _ in range(40):  # até 2.000 envios
            p = q(part="contentDetails", playlistId=up, maxResults=50)
            if tok:
                p["pageToken"] = tok
            try:
                r = yt("playlistItems", **p)
            except RuntimeError as e:
                erros.append(f"envios: {e}")
                break
            ids += [it["contentDetails"]["videoId"] for it in r.get("items", [])]
            tok = r.get("nextPageToken")
            if not tok:
                break
        envios = detalhes(ids, q, erros)
    else:
        erros.append("canal dela: vídeo 9LLIWExnoK4 não encontrado pela API")
    # 2. recortes
    achados = {}
    for b in BUSCAS:
        for ordem in ("date", "relevance"):
            tok = None
            for _ in range(2):
                p = q(part="snippet", q=b, type="video", maxResults=50, publishedAfter=MARCO, regionCode="BR", relevanceLanguage="pt", order=ordem)
                if tok:
                    p["pageToken"] = tok
                try:
                    r = yt("search", **p)
                except RuntimeError as e:
                    erros.append(f"busca '{b}' ({ordem}): {e}")
                    break
                for it in r.get("items", []):
                    achados.setdefault(it["id"]["videoId"], b)
                tok = r.get("nextPageToken")
                if not tok:
                    break
                time.sleep(1)
    recortes = [v for v in detalhes([i for i in achados if i not in SEMENTES], q, erros) if RX.search(f"{v['titulo']} {v['descricao']}")]
    for v in recortes:
        v["busca"] = achados.get(v["id"])
    sementes = detalhes(list(SEMENTES), q, erros)
    for v in sementes:
        v["papel"] = SEMENTES[v["id"]]
    # inscritos dos canais
    canais = list({v["canal_id"] for v in recortes + sementes})
    insc = {}
    for i in range(0, len(canais), 50):
        try:
            for it in yt("channels", **q(part="statistics", id=",".join(canais[i:i + 50]))).get("items", []):
                s = it.get("statistics", {})
                insc[it["id"]] = int(s["subscriberCount"]) if str(s.get("subscriberCount", "")).isdigit() else None
        except RuntimeError as e:
            erros.append(f"canais: {e}")
    for v in recortes + sementes:
        v["inscritos_canal"] = insc.get(v["canal_id"])
    # 3. comentários
    # linha de base: os 10 envios dela anteriores ao marco; depois do marco, todos
    base = [e for e in envios if (e["publicado_em"] or "") < MARCO][-10:]
    alvo = {v["id"]: v for v in sementes + recortes + base + [e for e in envios if (e["publicado_em"] or "") >= MARCO]}
    rows = []
    for vid, v in alvo.items():
        if not v.get("comentarios"):
            continue
        meta, tok = {"video_id": vid, "candidate_id": "", "channel_id": v["canal_id"]}, None
        for _ in range(PAGINAS):
            p = q(part="snippet,replies", videoId=vid, maxResults=100, order="time", textFormat="plainText")
            if tok:
                p["pageToken"] = tok
            try:
                r = yt("commentThreads", **p)
            except RuntimeError as e:
                erros.append(f"comentários {vid}: {e}")
                break
            rows += [l for it in r.get("items", []) for l in linhas_da_conversa(it, meta, "caso011", agora)]
            tok = r.get("nextPageToken")
            if not tok:
                break
    priv.mkdir(parents=True, exist_ok=True)
    arq = priv / "youtube_comentarios.csv.gz"
    antigos = {r["comment_id"]: r for r in csv.DictReader(gzip.open(arq, "rt", encoding="utf-8"), delimiter=";")} if arq.exists() else {}
    antigos.update({r["comment_id"]: r for r in rows})
    with gzip.open(arq, "wt", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, CAMPOS, delimiter=";", lineterminator="\n", extrasaction="ignore")
        w.writeheader()
        w.writerows(antigos.values())
    return {"lido_em_utc": agora, "canal": canal, "sementes": sementes, "recortes": sorted(recortes, key=lambda v: -(v["visualizacoes"] or 0)),
            "envios": sorted(envios, key=lambda v: v["publicado_em"] or ""), "comentarios_lidos_nesta_execucao": len({r["comment_id"] for r in rows}),
            "achados_na_busca": len(achados)}


def detalhes(ids: list[str], q, erros: list) -> list[dict]:
    out = []
    for i in range(0, len(ids), 50):
        try:
            r = yt("videos", **q(part="snippet,statistics,contentDetails", id=",".join(ids[i:i + 50])))
        except RuntimeError as e:
            erros.append(f"vídeos: {e}")
            continue
        for it in r.get("items", []):
            sn, st = it["snippet"], it.get("statistics", {})
            n = lambda k: int(st[k]) if str(st.get(k, "")).isdigit() else None  # noqa: E731
            out.append({"id": it["id"], "titulo": sn.get("title"), "canal": sn.get("channelTitle"), "canal_id": sn.get("channelId"),
                        "publicado_em": sn.get("publishedAt"), "visualizacoes": n("viewCount"), "curtidas": n("likeCount"),
                        "comentarios": n("commentCount"), "duracao": it.get("contentDetails", {}).get("duration"),
                        "descricao": (sn.get("description") or "")[:300]})
    return out


def lados_do_acervo(interno: Path) -> dict[str, str]:
    arq = interno / "youtube/comentarios/comentarios.csv.gz"
    vis = defaultdict(set)
    if arq.exists():
        for r in csv.DictReader(gzip.open(arq, "rt", encoding="utf-8"), delimiter=";"):
            if r.get("autor_canal"):
                vis[r["autor_canal"]].add(r["candidate_id"])
    return {a: ("ambos" if {LULA, FLAVIO} <= s else "lula" if LULA in s else "flavio" if FLAVIO in s else "nenhum") for a, s in vis.items()}


def perfil(rs: list[dict], lados: dict) -> dict:
    autores = {r["autor_canal"] for r in rs if r.get("autor_canal")}
    c = Counter(lados.get(a, "nenhum") for a in autores)
    n = len(autores)
    return {"comentarios": len(rs), "autores": n, **{f"pct_{k}": round(100 * c.get(k, 0) / n, 1) if n else None for k in ("lula", "flavio", "ambos", "nenhum")},
            **{f"n_{k}": c.get(k, 0) for k in ("lula", "flavio", "ambos", "nenhum")}}


def codigo(a: str) -> str:
    return "A" + hashlib.sha256(a.encode()).hexdigest()[:8]


def analisar(dados: dict, priv: Path, interno: Path, pub: Path) -> dict:
    arq = priv / "youtube_comentarios.csv.gz"
    rows = list(csv.DictReader(gzip.open(arq, "rt", encoding="utf-8"), delimiter=";")) if arq.exists() else []
    lados = lados_do_acervo(interno)
    vids = {v["id"]: v for v in dados.get("sementes", []) + dados.get("recortes", []) + dados.get("envios", [])}
    canal_dela = (dados.get("canal") or {}).get("id")
    por_canal = defaultdict(list)
    for r in rows:
        por_canal[r["channel_id"]].append(r)
    nome = {v["canal_id"]: v["canal"] for v in vids.values()}
    insc = {v["canal_id"]: v.get("inscritos_canal") for v in vids.values() if v.get("inscritos_canal") is not None}
    canais = []
    for cid, rs in sorted(por_canal.items(), key=lambda kv: -len(kv[1])):
        canais.append({"canal_id": cid, "canal": nome.get(cid, "?"), "inscritos": insc.get(cid), "e_o_canal_dela": cid == canal_dela,
                       "videos": len({r["video_id"] for r in rs}), **perfil(rs, lados)})
    dela = por_canal.get(canal_dela, [])
    antes = [r for r in dela if (r["publicado_em"] or "") < MARCO]
    depois = [r for r in dela if (r["publicado_em"] or "") >= MARCO]
    fora = [r for r in rows if r["channel_id"] != canal_dela]
    dia = lambda iso: (datetime.fromisoformat(iso.replace("Z", "+00:00")) - timedelta(hours=3)).strftime("%Y-%m-%d")  # noqa: E731
    com_dia = Counter(dia(r["publicado_em"]) for r in dela if r.get("publicado_em"))
    envios = dados.get("envios", [])
    # série de inscritos (cresce a cada execução)
    serie_arq = pub / "canal_serie.json"
    serie = json.loads(serie_arq.read_text(encoding="utf-8")) if serie_arq.exists() else []
    c = dados.get("canal") or {}
    if c.get("lido_em_utc") and all(x["lido_em_utc"] != c["lido_em_utc"] for x in serie):
        serie.append({k: c.get(k) for k in ("lido_em_utc", "inscritos", "visualizacoes", "videos")})
    serie_arq.write_text(json.dumps(serie, ensure_ascii=False, indent=1), encoding="utf-8")
    # redes
    nos, ar = {"ACERVO_LULA": {"rotulo": "Acervo: comentou em canais de Lula", "tipo": "âncora", "n": 0},
               "ACERVO_FLAVIO": {"rotulo": "Acervo: comentou em canais de Flávio", "tipo": "âncora", "n": 0}}, Counter()
    autores_por_canal = defaultdict(set)
    for r in rows:
        a = r.get("autor_canal")
        if not a:
            continue
        cid = r["channel_id"]
        nos.setdefault(cid, {"rotulo": nome.get(cid, "?") if (insc.get(cid) or 0) >= MIN_PUBLICO or cid == canal_dela else "canal (código)",
                             "tipo": "canal dela" if cid == canal_dela else "canal", "n": 0})
        nos[cid]["n"] += 1
        k = codigo(a)
        nos.setdefault(k, {"rotulo": k, "tipo": f"autor · acervo: {lados.get(a, 'nenhum')}", "n": 0})
        nos[k]["n"] += 1
        ar[(cid, k)] += 1
        autores_por_canal[cid].add(a)
    for a in {r["autor_canal"] for r in rows if r.get("autor_canal")}:
        lado = lados.get(a, "nenhum")
        if lado in ("lula", "ambos"):
            ar[("ACERVO_LULA", codigo(a))] += 1
            nos["ACERVO_LULA"]["n"] += 1
        if lado in ("flavio", "ambos"):
            ar[("ACERVO_FLAVIO", codigo(a))] += 1
            nos["ACERVO_FLAVIO"]["n"] += 1
    gexf(nos, dict(ar), pub / "rede_canais_autores.gexf")
    cn = {k: v for k, v in nos.items() if v["tipo"] in ("canal", "canal dela", "âncora")}
    aut = {**autores_por_canal, "ACERVO_LULA": {a for a, l in lados.items() if l in ("lula", "ambos")},
           "ACERVO_FLAVIO": {a for a, l in lados.items() if l in ("flavio", "ambos")}}
    cc = Counter()
    ks = list(cn)
    for i, x in enumerate(ks):
        for y in ks[i + 1:]:
            w = len(aut.get(x, set()) & aut.get(y, set()))
            if w:
                cc[(x, y)] = w
    gexf(cn, dict(cc), pub / "rede_canais.gexf")
    grandes = [v for v in dados.get("recortes", []) if (v.get("inscritos_canal") or 0) >= MIN_PUBLICO]
    pequenos = [v for v in dados.get("recortes", []) if (v.get("inscritos_canal") or 0) < MIN_PUBLICO]
    for x in canais:
        if not x["e_o_canal_dela"] and (x["inscritos"] or 0) < MIN_PUBLICO:
            x.update(canal="canal com menos de 10 mil inscritos", canal_id=None)
    # público histórico × público da entrevista e dos recortes (o vídeo dela de 23/10 está com comentários desligados)
    hist = {r["autor_canal"] for r in antes if r.get("autor_canal")}
    novos = {r["autor_canal"] for r in fora if r.get("autor_canal")}
    sobre = {"autores_historicos": len(hist), "autores_entrevista_recortes": len(novos), "em_comum": len(hist & novos),
             "pct_dos_recortes_que_ja_comentavam_no_canal_dela": round(100 * len(hist & novos) / len(novos), 1) if novos else None,
             "pct_do_historico_que_apareceu_nos_recortes": round(100 * len(hist & novos) / len(hist), 1) if hist else None}
    import comentarios_caso as cmc
    analise = cmc.analisar(fora, TEMAS, pub, priv)
    temas_hist = cmc.temas_pct([r.get("texto") or "" for r in antes], TEMAS)
    # comentários do reel no Instagram (coleta paga do caso, casos/011/apify; texto e autor só no privado)
    ig = []
    for f in sorted((priv / "apify").glob("*.json")):
        try:
            dd = json.loads(f.read_text(encoding="utf-8"))
        except ValueError:
            continue
        if "datadoping" in str(dd.get("ator", "")):
            for x in dd.get("items") or []:
                ts = x.get("created_at_utc") or x.get("created_at")
                iso = datetime.utcfromtimestamp(int(ts)).strftime("%Y-%m-%dT%H:%M:%SZ") if str(ts or "").isdigit() else str(ts or "")
                ig.append({"comment_id": str(x.get("comment_id") or x.get("id")), "texto": x.get("text") or "", "publicado_em": iso,
                           "autor_canal": str(x.get("user_id") or x.get("username") or ""), "tipo": "comentario", "parent_id": ""})
    ig = list({r["comment_id"]: r for r in ig}.values())
    ig_inf = None
    for f in sorted((priv / "apify").glob("*.json")):
        try:
            dd = json.loads(f.read_text(encoding="utf-8"))
        except ValueError:
            continue
        if "reel-scraper" in str(dd.get("ator", "")):
            ig_inf = next((int(x["commentsCount"]) for x in dd.get("items") or [] if str(x.get("commentsCount", "")).isdigit()), ig_inf)
    # universo × amostra (pedido de 27/10/2026, 03h24: "é sempre importante ter o universo e qual o real tamanho da amostra")
    lidos = Counter(r["video_id"] for r in rows)
    def linha(conj, vs, criterio):
        inf = sum(v.get("comentarios") or 0 for v in vs)
        li = sum(lidos.get(v["id"], 0) for v in vs)
        return {"conjunto": conj, "videos": len(vs), "universo": inf if vs else None, "fonte_universo": "contagem de comentários informada pelo YouTube (inclui respostas)",
                "amostra": li, "pct": round(100 * li / inf, 1) if inf else None, "criterio": criterio}
    crit = f"até {PAGINAS * 100} conversas por vídeo, das mais recentes para as mais antigas, com até 5 respostas cada"
    base_v = [v for v in vids.values() if v["canal_id"] == canal_dela and (v.get("publicado_em") or "") < MARCO and lidos.get(v["id"])]
    universo = [linha("Entrevista na TV 247", [v for v in dados.get("sementes", []) if v["id"] == "jTeWOpW7fg4"], crit),
                linha("Recortes desde 22/10 (todos os canais)", dados.get("recortes", []), crit),
                linha("Canal dela, 10 vídeos anteriores a 22/10 (público histórico)", base_v, crit),
                {"conjunto": "Reel no Instagram (Dez0LqMp0Xz)", "videos": 1, "universo": ig_inf, "fonte_universo": "contagem de comentários informada pelo Instagram",
                 "amostra": len(ig), "pct": round(100 * len(ig) / ig_inf, 2) if ig_inf else None, "criterio": "2.000 comentários pedidos, ordem \"populares\" do Instagram, sem respostas"},
                {"conjunto": "Recortes encontrados", "videos": None, "universo": None, "fonte_universo": "⛔ não há contagem total de vídeos sobre o tema; a busca do YouTube devolve até 100 por consulta",
                 "amostra": len(dados.get("recortes", [])), "pct": None, "criterio": f"{len(BUSCAS)} buscas × data e relevância, 2 páginas cada; só vídeos com Joice/Hasselmann no título ou descrição"}]
    analise_ig = cmc.analisar(ig, TEMAS, pub, priv, "_instagram") if ig else None
    circ_videos = [{**v, "inscritos": v.get("inscritos_canal"), "consulta": v.get("busca") or "entrevista (partida)"} for v in
                   dados.get("sementes", []) + dados.get("recortes", [])]
    circ = cmc.circulacao(circ_videos, pub)
    sr_arq = pub / "recortes_serie.json"
    sr = json.loads(sr_arq.read_text(encoding="utf-8")) if sr_arq.exists() else []
    lido = dados.get("lido_em_utc")
    if lido and all(x["lido_em_utc"] != lido for x in sr):
        sr.append({"lido_em_utc": lido, "videos": len(circ_videos), "canais": len({v["canal_id"] for v in circ_videos}),
                   "visualizacoes": sum(v.get("visualizacoes") or 0 for v in circ_videos),
                   "entrevista": next((v.get("visualizacoes") for v in dados.get("sementes", []) if v["id"] == "jTeWOpW7fg4"), None)})
    sr_arq.write_text(json.dumps(sr, ensure_ascii=False, indent=1), encoding="utf-8")
    return {"caso": CASO, "gerado_em_utc": now_utc(), "marco": MARCO, "canal": c, "serie_canal": serie,
            "sobreposicao": sobre, "comentarios_entrevista_recortes": analise, "comentarios_instagram": analise_ig, "universo": universo, "temas_publico_historico": temas_hist,
            "circulacao": circ, "serie_recortes": sr,
            "aviso_canal_dela": "O vídeo dela de 23/10 (\"Meu voto é pelo futuro do Brasil\") está com os comentários desligados, e o envio anterior é de "
                                "dezembro de 2025; por isso o público de depois de 22/10 é medido na entrevista e nos recortes, não no canal dela.",
            "sementes": dados.get("sementes", []), "recortes": grandes,
            "recortes_canais_pequenos": {"videos": len(pequenos), "visualizacoes": sum(v["visualizacoes"] or 0 for v in pequenos)},
            "recortes_total": {"videos": len(dados.get("recortes", [])), "canais": len({v["canal_id"] for v in dados.get("recortes", [])}),
                               "visualizacoes": sum(v["visualizacoes"] or 0 for v in dados.get("recortes", []))},
            "envios_resumo": {"total": len(envios), "antes": [v for v in envios if (v["publicado_em"] or "") < MARCO][-15:],
                              "depois": [v for v in envios if (v["publicado_em"] or "") >= MARCO]},
            "bolha": {"canal_dela_antes": perfil(antes, lados), "canal_dela_depois": perfil(depois, lados), "fora_do_canal_dela": perfil(fora, lados),
                      "por_canal": canais, "acervo_autores": len(lados)},
            "comentarios_no_canal_dela_por_dia": dict(sorted(com_dia.items())),
            "redes": {"canais_autores": {"nos": len(nos), "arestas": len(ar)}, "canais": {"nos": len(cn), "arestas": len(cc)}},
            "nota": "Lado no acervo: o autor já comentou (desde a pré-campanha) em vídeos dos canais da campanha de Lula, de Flávio, dos dois "
                    "ou de nenhum. Indício de bolha, não prova de voto. Canais com menos de 10 mil inscritos aparecem como código nas redes."}


def main(argv=None) -> int:
    argv = sys.argv[1:] if argv is None else list(argv)
    interno = os.environ.get("ODI_INTERNO_DIR")
    key = os.environ.get("YOUTUBE_API_KEY", "")
    if not interno:
        print("⛔ ODI_INTERNO_DIR ausente")
        return 1
    priv, pub = Path(interno) / "casos" / CASO, Path("data/casos") / CASO
    pub.mkdir(parents=True, exist_ok=True)
    erros = []
    bruto = priv / "youtube_dados.json"
    if "--sem-coleta" not in argv:
        if not key:
            print("⛔ YOUTUBE_API_KEY ausente")
            return 1
        dados = coletar(key, priv, erros)
        bruto.write_text(json.dumps(dados, ensure_ascii=False), encoding="utf-8")
    dados = json.loads(bruto.read_text(encoding="utf-8")) if bruto.exists() else {}
    out = analisar(dados, priv, Path(interno), pub)
    out["erros"] = erros
    (pub / "youtube.json").write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    b = out["bolha"]
    print(f"caso 011: canal {out['canal'].get('titulo')} · {out['canal'].get('inscritos')} inscritos · recortes {len(out['recortes'])} · "
          f"autores no canal dela antes {b['canal_dela_antes']['autores']} (Lula {b['canal_dela_antes']['pct_lula']}%) × depois "
          f"{b['canal_dela_depois']['autores']} (Lula {b['canal_dela_depois']['pct_lula']}%) · erros {erros[:5]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
