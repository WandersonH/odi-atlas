#!/usr/bin/env python3
"""Caso 032: "Revelando" (Calma Urgente), série de reportagens no YouTube e nas redes. Análise como a do caso 011 (Joice), grátis.

Pedido do responsável (02/11/2026, 20h12): "quero a análise como caso da Joice, e uma análise geral por episódio e buscas
[dos] assuntos abordados; crescimento também deve ser abordado; esse canal estava na bolha da esquerda".

Coleta (YOUTUBE_API_KEY; cota gratuita, sem busca: só canal, envios e comentários):
  1. canal @revelando_br (channels.forHandle): estatísticas e todos os envios (episódios) com detalhes;
  2. comentários de cada episódio, até PAGINAS páginas de 100 conversas (ordem: mais recentes);
  3. histórico de inscritos pelo Internet Archive (CDX da página do canal; melhor esforço: a página pode não ter sido guardada).
Google Trends (grátis): o assunto de cada episódio (título limpo) em janelas de 12 meses e 7 dias, Brasil, 5 por consulta.
Análise:
  - por episódio: visualizações, curtidas, comentários, duração, assunto, hashtags; comentários lidos e perfil dos autores;
  - "bolha": cada autor de comentário é cruzado com o acervo do Atlas (comentários nos canais das campanhas; Lula × Flávio);
    perfil no total, por episódio e por mês. Indício de bolha, não prova de voto;
  - crescimento: série de inscritos/visualizações a cada execução (cresce a cada dia) + envios e visualizações por mês;
  - redes (Gephi): episódios × autores (autores como código) e os dois nós-âncora do acervo.
Texto e autor dos comentários só no privado. Canal de figura pública (projeto de mídia): nomeado.
Uso: python scripts/caso_revelando.py [--sem-coleta] [--sem-trends]
"""
from __future__ import annotations

import csv
import datetime as dt
import gzip
import hashlib
import json
import os
import re
import sys
import time
import urllib.parse
import urllib.request
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from caso_joice import detalhes, lados_do_acervo, perfil, codigo, yt  # noqa: E402
from collect_comentarios_youtube import CAMPOS, linhas_da_conversa  # noqa: E402
from net import now_utc  # noqa: E402
from redes_caso import gexf  # noqa: E402

CASO = "032"
HANDLE = "@revelando_br"
PAGINAS = 5
MIN_PUBLICO = 10000
REDES = {"instagram": "https://www.instagram.com/revelando.brasil/", "x": "https://x.com/revelandobr", "tiktok": "https://www.tiktok.com/@revelando.br",
         "kwai": "https://k.kwai.com/u/@dzpve839/I7XDoACH", "youtube": "https://www.youtube.com/@revelando_br"}
TEMAS = {
    "elogia a série ou o canal": r"parab[eé]ns|excelente|incr[ií]vel|obrigad\w*|gratid\w*|necess[aá]ri\w*|importante|melhor canal|reportagem|jornalismo",
    "duvida ou desmente": r"mentir\w*|\bfake\b|n[aã]o acredito|inventou|narrativa|manipula\w*|distor\w*|parcial|tendencios\w*",
    "cita Lula ou PT": r"\blula\w*|\bpt\b|petist\w*|esquerd\w*",
    "cita Bolsonaro e família": r"bolsonar\w*|\bjair\b|fl[aá]vio|\beduardo\b|\bbozo\b|direit\w*",
    "cita golpe, ditadura ou 8 de janeiro": r"\bgolpe\w*|8 de janeiro|ditadura|militar\w*",
    "cita eleição ou voto": r"elei[cç]\w*|\bvot\w*|urna\w*|2[ºo°] turno|segundo turno",
    "cita mídia ou imprensa": r"\bglobo\b|m[ií]dia|imprensa|jornalist\w*|\bjn\b|record|sbt|cnn",
    "pede mais episódios": r"pr[oó]xim\w*|continua\w*|mais epis\w*|parte 2|quando sai",
    "ofensa ou ataque": r"\blixo\b|vagabund\w*|nojent\w*|\bburr\w*|idiot\w*|imbecil|canalha|bandid\w*",
}
UA = {"User-Agent": "Mozilla/5.0 (ODI Atlas; pesquisa acadêmica)"}


def assunto(titulo: str) -> str:
    """Assunto do episódio para o Trends: o maior pedaço do título sem a marca, o número do episódio e a pontuação."""
    t = re.sub(r"\bREVELANDO\b|#\d+|\bEP\.?\s*\d+|\bepis[oó]dio\s*\d+|\bparte\s*\d+", " ", titulo or "", flags=re.I)
    partes = [p.strip(" .,:;—–-|!?\"'“”‘’") for p in re.split(r"[|—–]|\s-\s|\s:\s|:\s", t)]
    partes = [p for p in partes if len(p.split()) >= 2] or [t]
    t = re.sub(r"[\"'“”‘’!?]", "", partes[0]).strip(" .,:;-")  # a primeira parte com 2+ palavras: costuma ser a manchete
    return " ".join(re.sub(r"\s+", " ", t).split()[:8])


def coletar(key: str, priv: Path, erros: list) -> dict:
    agora = now_utc()
    q = lambda **k: {**k, "key": key}  # noqa: E731
    c = (yt("channels", **q(part="snippet,statistics,contentDetails", forHandle=HANDLE)).get("items") or [{}])[0]
    if not c:
        erros.append(f"canal {HANDLE} não encontrado pela API")
        return {"lido_em_utc": agora, "canal": {}, "envios": []}
    st = c.get("statistics", {})
    canal = {"id": c["id"], "titulo": c.get("snippet", {}).get("title"), "handle": c.get("snippet", {}).get("customUrl"),
             "descricao": (c.get("snippet", {}).get("description") or "")[:600], "criado_em": c.get("snippet", {}).get("publishedAt"),
             "inscritos": int(st.get("subscriberCount", 0) or 0), "visualizacoes": int(st.get("viewCount", 0) or 0),
             "videos": int(st.get("videoCount", 0) or 0), "lido_em_utc": agora}
    up = c.get("contentDetails", {}).get("relatedPlaylists", {}).get("uploads")
    ids, tok = [], None
    for _ in range(40):
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
    # comentários de todos os episódios
    rows = []
    for v in envios:
        if not v.get("comentarios"):
            continue
        meta, tok = {"video_id": v["id"], "candidate_id": "", "channel_id": v["canal_id"]}, None
        for _ in range(PAGINAS):
            p = q(part="snippet,replies", videoId=v["id"], maxResults=100, order="time", textFormat="plainText")
            if tok:
                p["pageToken"] = tok
            try:
                r = yt("commentThreads", **p)
            except RuntimeError as e:
                erros.append(f"comentários {v['id']}: {e}")
                break
            rows += [l for it in r.get("items", []) for l in linhas_da_conversa(it, meta, f"caso{CASO}", agora)]
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
    return {"lido_em_utc": agora, "canal": canal, "envios": sorted(envios, key=lambda v: v["publicado_em"] or ""),
            "comentarios_lidos_nesta_execucao": len({r["comment_id"] for r in rows})}


def wayback_inscritos(erros: list) -> list[dict]:
    """Inscritos em capturas antigas da página do canal no Internet Archive (melhor esforço)."""
    out = []
    try:
        cdx = ("https://web.archive.org/cdx/search/cdx?url=youtube.com/" + HANDLE + "*&output=json&fl=timestamp,original&filter=statuscode:200"
               "&collapse=timestamp:8&limit=60")
        rows = json.loads(urllib.request.urlopen(urllib.request.Request(cdx, headers=UA), timeout=60).read())[1:]
    except Exception as e:  # noqa: BLE001
        erros.append(f"wayback cdx: {type(e).__name__}")
        return out
    for ts, orig in rows:
        try:
            html = urllib.request.urlopen(urllib.request.Request(f"https://web.archive.org/web/{ts}id_/{orig}", headers=UA), timeout=60).read().decode("utf-8", "replace")
        except Exception:  # noqa: BLE001
            continue
        m = re.search(r'"subscriberCountText"\s*:\s*\{[^}]*?"simpleText"\s*:\s*"([^"]+)"', html) or re.search(r'([\d.,]+\s*(?:mil|mi|K|M)?\s*(?:inscritos|subscribers))', html)
        if m:
            out.append({"captura_utc": dt.datetime.strptime(ts, "%Y%m%d%H%M%S").strftime("%Y-%m-%dT%H:%M:%SZ"), "texto": m.group(1).strip(),
                        "fonte": f"https://web.archive.org/web/{ts}/{orig}"})
        time.sleep(1)
    return out


def trends_assuntos(assuntos: list[str], erros: list) -> dict:
    from collect_trends import Trends
    t = Trends(pause=4)
    out = {"janelas": ["today 12-m", "now 7-d"], "grupos": [], "aviso": "0 a 100, relativo ao pico dentro de cada consulta (5 assuntos por consulta; grupos "
                                                                        "diferentes não se comparam entre si). Busca por palavra: ambígua."}
    for i in range(0, len(assuntos), 5):
        termos = assuntos[i:i + 5]
        g = {"termos": termos}
        for jan in out["janelas"]:
            try:
                ws = {w["id"]: w for w in t.explore(termos, jan, "BR")}
                ts = t.widget("multiline", ws["TIMESERIES"])
                g[jan] = [{"t": dt.datetime.fromtimestamp(int(p["time"]), dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                           "v": dict(zip(termos, p.get("value") or []))} for p in ts["default"]["timelineData"]]
            except Exception as e:  # noqa: BLE001
                erros.append(f"trends {termos[0]}… {jan}: {type(e).__name__}")
        out["grupos"].append(g)
    return out


def analisar(dados: dict, priv: Path, interno: Path, pub: Path, trends: dict | None) -> dict:
    arq = priv / "youtube_comentarios.csv.gz"
    rows = list(csv.DictReader(gzip.open(arq, "rt", encoding="utf-8"), delimiter=";")) if arq.exists() else []
    lados = lados_do_acervo(interno)
    envios = dados.get("envios", [])
    c = dados.get("canal") or {}
    por_video = defaultdict(list)
    for r in rows:
        por_video[r["video_id"]].append(r)
    mes = lambda iso: (iso or "")[:7]  # noqa: E731
    episodios = []
    for v in envios:
        rs = por_video.get(v["id"], [])
        tags = sorted({h.lower() for h in re.findall(r"#(\w+)", v.get("descricao") or "")})
        episodios.append({"id": v["id"], "titulo": v["titulo"], "assunto": assunto(v["titulo"] or ""), "publicado_em": v["publicado_em"],
                          "duracao": v.get("duracao"), "visualizacoes": v.get("visualizacoes"), "curtidas": v.get("curtidas"),
                          "comentarios_informados": v.get("comentarios"), "hashtags": tags[:12], "url": f"https://www.youtube.com/watch?v={v['id']}",
                          "comentarios_lidos": len(rs), "pct_lidos": round(100 * len(rs) / v["comentarios"], 1) if v.get("comentarios") else None,
                          "bolha": perfil(rs, lados)})
    por_mes = defaultdict(lambda: {"episodios": 0, "visualizacoes": 0, "comentarios_informados": 0})
    for e in episodios:
        m = mes(e["publicado_em"])
        por_mes[m]["episodios"] += 1
        por_mes[m]["visualizacoes"] += e["visualizacoes"] or 0
        por_mes[m]["comentarios_informados"] += e["comentarios_informados"] or 0
    bolha_mes = {m: perfil(rs, lados) for m, rs in sorted(defaultdict(list, {k: [r for r in rows if mes(r.get("publicado_em")) == k]
                                                                               for k in {mes(r.get("publicado_em")) for r in rows}}).items()) if m}
    serie_arq = pub / "canal_serie.json"
    serie = json.loads(serie_arq.read_text(encoding="utf-8")) if serie_arq.exists() else []
    if c.get("lido_em_utc") and all(x["lido_em_utc"] != c["lido_em_utc"] for x in serie):
        serie.append({k: c.get(k) for k in ("lido_em_utc", "inscritos", "visualizacoes", "videos")})
    serie_arq.write_text(json.dumps(serie, ensure_ascii=False, indent=1), encoding="utf-8")
    # redes
    nos, ar = {"ACERVO_LULA": {"rotulo": "Acervo: comentou em canais de Lula", "tipo": "âncora", "n": 0},
               "ACERVO_FLAVIO": {"rotulo": "Acervo: comentou em canais de Flávio", "tipo": "âncora", "n": 0}}, Counter()
    tit = {e["id"]: e["titulo"] for e in episodios}
    for r in rows:
        a = r.get("autor_canal")
        if not a:
            continue
        vid = r["video_id"]
        nos.setdefault(vid, {"rotulo": (tit.get(vid) or vid)[:60], "tipo": "episódio", "n": 0})
        nos[vid]["n"] += 1
        k = codigo(a)
        nos.setdefault(k, {"rotulo": k, "tipo": f"autor · acervo: {lados.get(a, 'nenhum')}", "n": 0})
        nos[k]["n"] += 1
        ar[(vid, k)] += 1
    for a in {r["autor_canal"] for r in rows if r.get("autor_canal")}:
        lado = lados.get(a, "nenhum")
        if lado in ("lula", "ambos"):
            ar[("ACERVO_LULA", codigo(a))] += 1
            nos["ACERVO_LULA"]["n"] += 1
        if lado in ("flavio", "ambos"):
            ar[("ACERVO_FLAVIO", codigo(a))] += 1
            nos["ACERVO_FLAVIO"]["n"] += 1
    gexf(nos, dict(ar), pub / "rede_episodios_autores.gexf")
    import comentarios_caso as cmc
    analise = cmc.analisar(rows, TEMAS, pub, priv) if rows else None
    # autores recorrentes: em quantos episódios cada autor comentou (só contagens)
    ep_por_autor = Counter()
    for a, vs in defaultdict(set, {a: {r["video_id"] for r in rows if r.get("autor_canal") == a} for a in {r.get("autor_canal") for r in rows if r.get("autor_canal")}}).items():
        ep_por_autor[min(len(vs), 5)] += 1
    inf = sum(e["comentarios_informados"] or 0 for e in episodios)
    li = sum(e["comentarios_lidos"] for e in episodios)
    universo = [{"conjunto": "Comentários dos episódios", "videos": len(episodios), "universo": inf, "fonte_universo": "contagem de comentários informada pelo YouTube (inclui respostas)",
                 "amostra": li, "pct": round(100 * li / inf, 1) if inf else None, "criterio": f"até {PAGINAS * 100} conversas por episódio, das mais recentes para as mais antigas, com até 5 respostas cada"},
                {"conjunto": "Episódios do canal", "videos": len(episodios), "universo": c.get("videos"), "fonte_universo": "contagem de vídeos informada pelo YouTube para o canal",
                 "amostra": len(episodios), "pct": round(100 * len(episodios) / c["videos"], 1) if c.get("videos") else None, "criterio": "lista de envios do canal (até 2.000)"},
                {"conjunto": "Acervo do Atlas (lado dos autores)", "videos": None, "universo": None, "fonte_universo": "⛔ não há universo: o acervo cobre só comentários nos canais das campanhas desde a pré-campanha",
                 "amostra": len(lados), "pct": None, "criterio": "autor visto no acervo recebe o lado dos canais em que comentou"}]
    return {"caso": CASO, "gerado_em_utc": now_utc(), "canal": c, "redes_do_projeto": REDES, "serie_canal": serie, "wayback_inscritos": dados.get("wayback_inscritos", []),
            "episodios": sorted(episodios, key=lambda e: e["publicado_em"] or ""), "por_mes": dict(sorted(por_mes.items())),
            "bolha": {"total": perfil(rows, lados), "por_mes": bolha_mes, "acervo_autores": len(lados),
                      "autores_por_numero_de_episodios": {("5 ou mais" if k == 5 else str(k)): v for k, v in sorted(ep_por_autor.items())}},
            "comentarios": analise, "universo": universo, "trends_assuntos": trends,
            "redes": {"episodios_autores": {"nos": len(nos), "arestas": len(ar)}},
            "hipotese_do_responsavel": "\"esse canal estava na bolha da esquerda\" (02/11/2026): testada pelo lado dos autores no acervo; o acervo só diz quem já comentou nos canais das campanhas.",
            "nota": "Lado no acervo: o autor já comentou (desde a pré-campanha) em vídeos dos canais da campanha de Lula, de Flávio, dos dois ou de nenhum. "
                    "Indício de bolha, não prova de voto. Comentários: texto e autor só no privado. Trends: busca por palavra, ambígua; interesse relativo."}


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
        velho = json.loads(bruto.read_text(encoding="utf-8")) if bruto.exists() else {}
        dados["wayback_inscritos"] = velho.get("wayback_inscritos") or wayback_inscritos(erros)
        bruto.write_text(json.dumps(dados, ensure_ascii=False), encoding="utf-8")
    dados = json.loads(bruto.read_text(encoding="utf-8")) if bruto.exists() else {}
    tr_arq = pub / "trends_assuntos.json"
    trends = None
    if "--sem-trends" not in argv:
        assuntos = sorted({assunto(v["titulo"] or "") for v in dados.get("envios", []) if assunto(v["titulo"] or "")})
        trends = trends_assuntos(assuntos, erros)
        tr_arq.write_text(json.dumps(trends, ensure_ascii=False), encoding="utf-8")
    elif tr_arq.exists():
        trends = json.loads(tr_arq.read_text(encoding="utf-8"))
    out = analisar(dados, priv, Path(interno), pub, trends)
    out["erros"] = erros
    (pub / "youtube.json").write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    b = out["bolha"]["total"]
    print(f"caso {CASO}: canal {out['canal'].get('titulo')} · {out['canal'].get('inscritos')} inscritos · {len(out['episodios'])} episódios · "
          f"comentários lidos {b['comentarios']} de {b['autores']} autores · no acervo: Lula {b['pct_lula']}% · Flávio {b['pct_flavio']}% · ambos {b['pct_ambos']}% · "
          f"wayback {len(out['wayback_inscritos'])} capturas · erros {erros[:5]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
