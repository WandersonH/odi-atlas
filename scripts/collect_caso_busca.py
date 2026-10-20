"""Casos de busca (buscas no Google + vídeos do YouTube + imprensa + checagens), grátis. Configuração por caso em CASOS.

- 002: consulta depreciativa associada a um candidato no Google ("onde mora/nasceu o ladrão").
- 005: caso Ana Clara (menina de 5 anos morta por tiro de PM em Niterói, 2021; citado por Lula no debate de 18/10/2026).

Camadas (pedido do usuário em 20/10/2026, 12h45):
1. Google Trends: as variantes da consulta e controles, em 5 anos, 12 meses e 7 dias; interesse por UF (12 meses);
   consultas relacionadas (12 meses). Variantes não são agrupadas.
2. YouTube (Data API, YOUTUBE_API_KEY): vídeos com as expressões, de 2022 em diante; comentários dos mais vistos
   (relevância + recentes, com respostas). Comentários só no privado; no público, contagens e pré-codificação.
3. Google Notícias (RSS) e checagens (Google Fact Check Tools, FACTCHECK_API_KEY ou a chave do YouTube).
4. Linha de base de 2022: cópia do artigo de Victor Gabry no Internet Archive (consulta e, se não houver, pedido de cópia).
A bateria manual de consultas ao Google (com e sem IA) não é automatizada: o Google não oferece API para isso
(a Custom Search API recusou o projeto) e bloqueia robôs. O modelo de registro fica em data/casos/002/bateria_modelo.csv.

Uso: python scripts/collect_caso_busca.py --caso 002|005 [--sem-trends] [--sem-youtube]
"""
from __future__ import annotations

import csv
import datetime as dt
import gzip
import json
import os
import re
import sys
import tempfile
import urllib.error
import urllib.parse
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from net import get_json, now_utc, open_url, read_body  # noqa: E402
import build_conteudo as bc  # noqa: E402

CASOS = {
    "002": {"variantes": ["onde mora o ladrão", "onde nasceu o ladrão", "quantos anos tem o ladrão", "qual a idade do ladrão", "aonde nasceu o ladrão"],
            "controles": ["onde mora o ladrão", "onde mora o político", "onde nasceu o político corrupto", "onde nasceu Lula"],  # 1º = âncora comum
            "janelas": ["today 5-y", "today 12-m", "now 7-d"], "youtube": None, "desde_yt": "2022-01-01T00:00:00Z",
            "rx_titulo": r"ladr[aã]o", "rx_atributo": r"\b(mora|nasceu|nasce|anos|idade|google|pesquis)",
            "checagens": ["onde mora o ladrão", "onde nasceu o ladrão", "quantos anos tem o ladrão", "ladrão Google Lula"],
            "arquivo_web": ["https://victorgabry.com/onde-mora-o-ladrao-resultado-do-google/"]},
    "005": {"variantes": ["caso Ana Clara", "Ana Clara Niterói", "Ana Clara Flávio Bolsonaro", "Ana Clara PM"],
            "controles": ["caso Ana Clara", "Flávio Bolsonaro"],
            "janelas": ["today 5-y", "today 12-m", "now 7-d"],
            "youtube": ["caso Ana Clara", "Ana Clara Niterói", "Ana Clara Flávio Bolsonaro", "Flávio Bolsonaro advogado PM criança", "menina Ana Clara tiro fuzil"],
            "desde_yt": "2021-02-01T00:00:00Z", "rx_titulo": r"ana clara|menina de 5 anos|criança de 5 anos", "rx_atributo": r".",
            "checagens": ["Ana Clara Flávio Bolsonaro", "caso Ana Clara"],
            "arquivo_web": ["https://apublica.org/2026/10/silencio-de-flavio-sobre-ana-clara-foi-desesperador-diz-a-mae-da-menina/"]},
}
CASO = "002"
TOP_COMENTARIOS = 30
MIN_PUBLICO = 10000


def configurar(caso: str) -> None:
    global CASO, VARIANTES, CONTROLES, JANELAS, DESDE_YT, RX_TITULO, RX_ATRIBUTO, ARQUIVO_WEB, BUSCAS_YT, BUSCAS_CHECAGEM
    c = CASOS[caso]
    CASO, VARIANTES, CONTROLES, JANELAS, DESDE_YT = caso, c["variantes"], c["controles"], c["janelas"], c["desde_yt"]
    RX_TITULO, RX_ATRIBUTO = re.compile(c["rx_titulo"], re.I), re.compile(c["rx_atributo"], re.I)
    ARQUIVO_WEB, BUSCAS_YT, BUSCAS_CHECAGEM = c["arquivo_web"], c["youtube"] or c["variantes"], c["checagens"]


configurar("002")
CATEGORIAS = {  # pré-codificação por dicionário (não é decisão)
    "relato de teste": re.compile(r"\b(testei|testa|teste|fiz (a |essa )?pesquisa|pesquisei|perguntei|joguei no google|fiz aqui|fiz agora|aqui (deu|apareceu)|deu (o )?lula|apareceu (o )?lula|é verdade|verdade mesmo)\b", re.I),
    "mudança percebida": re.compile(r"\b(mudou|não aparece mais|nao aparece mais|tiraram|corrigiram|já mudaram|ja mudaram|agora aparece|censur)\w*", re.I),
    "contestação": re.compile(r"\b(fake|montagem|mentira|editad|calúnia|calunia|crime|injúria|injuria|processo|manipula)\w*", re.I),
    "cita Lula": re.compile(r"\b(lula|luladr|petista|pt\b|molusco|nove dedos|9 dedos)", re.I),
}
ERROS: list[str] = []


def priv_dir() -> Path:
    base = os.environ.get("ODI_INTERNO_DIR") or os.path.join(os.environ.get("RUNNER_TEMP") or tempfile.gettempdir(), "odi_casos")
    return Path(base) / "casos" / CASO


def trends() -> dict:
    from collect_trends import Trends
    from collect_trends_agora import relacionados
    t = Trends(pause=4)
    out = {}
    for nome, termos in (("variantes", VARIANTES), ("controles", CONTROLES)):
        g = {"termos": termos}
        for jan in JANELAS:
            try:
                ws = {w["id"]: w for w in t.explore(termos, jan, "BR")}
                ts = t.widget("multiline", ws["TIMESERIES"])
                g[jan] = [{"t": dt.datetime.fromtimestamp(int(p["time"]), dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                           "v": dict(zip(termos, p.get("value") or []))} for p in ts["default"]["timelineData"]]
                if jan == "today 12-m":
                    geo = next((w for k, w in ws.items() if k.startswith("GEO_MAP")), None)
                    if geo:
                        gm = t.widget("comparedgeo", geo)
                        g["uf_12m"] = [{"uf": (r.get("geoCode") or "").replace("BR-", ""), "nome": r.get("geoName"), "v": dict(zip(termos, r.get("value") or []))}
                                       for r in gm["default"]["geoMapData"]]
                    rel = {}
                    for k, w in sorted(ws.items()):
                        if k.startswith("RELATED_QUERIES"):
                            idx = int(k.rsplit("_", 1)[1]) if k.rsplit("_", 1)[-1].isdigit() else 0
                            if idx < len(termos):
                                rel[termos[idx]] = relacionados(t.widget("relatedsearches", w))
                    g["relacionados_12m"] = rel
            except Exception as e:  # noqa: BLE001
                ERROS.append(f"trends {nome} {jan}: {type(e).__name__}: {str(e)[:120]}")
        out[nome] = g
        print(f"trends {nome}: janelas lidas {[j for j in JANELAS if j in g]}")
    out["aviso"] = ("0 a 100, relativo ao pico dentro de cada consulta (variantes e controles são consultas separadas; o termo "
                    "'onde mora o ladrão' está nas duas como âncora). Interesse relativo não diz a quem as pessoas se referiam.")
    return out


def yt(rota: str, **q) -> dict:
    try:
        return get_json(f"https://www.googleapis.com/youtube/v3/{rota}?" + urllib.parse.urlencode(q), timeout=60)
    except urllib.error.HTTPError as e:
        corpo = ""
        try:
            corpo = e.read().decode("utf-8", "replace")
        except Exception:  # noqa: BLE001
            pass
        raise RuntimeError(next((m for m in ("quotaExceeded", "commentsDisabled", "forbidden") if m in corpo), f"HTTP {e.code}")) from None
    except Exception as e:  # noqa: BLE001 — a mensagem pode ter a URL com a chave
        raise RuntimeError(type(e).__name__) from None


def youtube(key: str, agora: str) -> tuple[dict, list[dict]]:
    from collect_comentarios_youtube import linhas_da_conversa
    ids: dict[str, str] = {}
    for q in BUSCAS_YT:
        token = None
        for _ in range(2):
            p = {"part": "snippet", "q": f'"{q}"' if CASO == "002" else q, "type": "video", "maxResults": 50, "publishedAfter": DESDE_YT, "regionCode": "BR",
                 "relevanceLanguage": "pt", "key": key}
            if token:
                p["pageToken"] = token
            try:
                d = yt("search", **p)
            except RuntimeError as e:
                ERROS.append(f"youtube busca '{q}': {e}")
                break
            for it in d.get("items", []):
                ids.setdefault(it["id"]["videoId"], q)
            token = d.get("nextPageToken")
            if not token:
                break
    vids = []
    lista = list(ids)
    for i in range(0, len(lista), 50):
        try:
            d = yt("videos", part="snippet,statistics", id=",".join(lista[i:i + 50]), key=key)
        except RuntimeError as e:
            ERROS.append(f"youtube videos: {e}")
            continue
        for it in d.get("items", []):
            sn, st = it["snippet"], it.get("statistics", {})
            txt = f"{sn.get('title', '')} {sn.get('description', '')[:300]}"
            if not (RX_TITULO.search(txt) and RX_ATRIBUTO.search(txt)):
                continue
            n = lambda k: int(st[k]) if str(st.get(k, "")).isdigit() else None  # noqa: E731
            vids.append({"id": it["id"], "titulo": sn.get("title"), "canal": sn.get("channelTitle"), "canal_id": sn.get("channelId"),
                         "publicado_em": sn.get("publishedAt"), "visualizacoes": n("viewCount"), "curtidas": n("likeCount"),
                         "comentarios": n("commentCount"), "consulta": ids[it["id"]]})
    canais = list({v["canal_id"] for v in vids})
    inscritos = {}
    for i in range(0, len(canais), 50):
        try:
            d = yt("channels", part="statistics", id=",".join(canais[i:i + 50]), key=key)
            for it in d.get("items", []):
                s = it.get("statistics", {})
                inscritos[it["id"]] = int(s["subscriberCount"]) if str(s.get("subscriberCount", "")).isdigit() else None
        except RuntimeError as e:
            ERROS.append(f"youtube canais: {e}")
    for v in vids:
        v["inscritos"] = inscritos.get(v["canal_id"])
    vids.sort(key=lambda v: v["visualizacoes"] or 0, reverse=True)
    rows = []
    for v in [x for x in vids if (x["comentarios"] or 0) > 0][:TOP_COMENTARIOS]:
        meta = {"video_id": v["id"], "candidate_id": "", "channel_id": v["canal_id"]}
        for ordem in ("relevance", "time"):
            try:
                d = yt("commentThreads", part="snippet,replies", videoId=v["id"], maxResults=100, order=ordem, textFormat="plainText", key=key)
            except RuntimeError as e:
                ERROS.append(f"comentários {v['id']}: {e}")
                break
            rows += [l for it in d.get("items", []) for l in linhas_da_conversa(it, meta, ordem, agora)]
    uniq = {r["comment_id"]: r for r in rows}
    print(f"youtube: {len(vids)} vídeos sobre o caso de {len(ids)} achados · {len(uniq)} comentários lidos")
    return {"videos": vids}, list(uniq.values())


def noticias() -> list[dict]:
    from collect_google_busca import RSS, parse_rss
    out, vistos = [], set()
    for q in VARIANTES:
        try:
            url = RSS + "?" + urllib.parse.urlencode({"q": f'"{q}"', "hl": "pt-BR", "gl": "BR", "ceid": "BR:pt-419"})
            for x in parse_rss(read_body(open_url(url, timeout=40))):
                if x.get("link") in vistos or not RX_TITULO.search(x.get("titulo") or ""):
                    continue
                vistos.add(x.get("link"))
                out.append({**{k: x.get(k) for k in ("titulo", "link", "veiculo", "dominio", "data_publicacao")}, "consulta": q})
        except Exception as e:  # noqa: BLE001
            ERROS.append(f"notícias '{q}': {type(e).__name__}")
    return sorted(out, key=lambda x: x.get("data_publicacao") or "")


def checagens(key: str) -> list[dict]:
    import collect_checagens as cc
    out = []
    for q in BUSCAS_CHECAGEM:
        out += cc.buscar(key, q, 3650, ERROS)
    return cc.juntar(out)


def wayback() -> list[dict]:
    """Cópia datada no Internet Archive de cada página de referência do caso (consulta; se não houver cópia, pede uma)."""
    saida = []
    for url in ARQUIVO_WEB:
        res = {"url": url}
        try:
            cdx = get_json("https://web.archive.org/cdx/search/cdx?" + urllib.parse.urlencode({"url": url, "output": "json", "limit": 5}), timeout=60)
            caps = [dict(zip(cdx[0], r)) for r in cdx[1:]] if cdx else []
            res["capturas"] = [{"data": c["timestamp"], "status": c.get("statuscode"), "arquivo": f"https://web.archive.org/web/{c['timestamp']}/{url}"} for c in caps]
        except Exception as e:  # noqa: BLE001
            res["erro_cdx"] = type(e).__name__
        if not res.get("capturas"):
            try:
                with open_url("https://web.archive.org/save/" + url, timeout=120) as r:
                    res["pedido_de_copia"] = f"HTTP {r.status}"
            except Exception as e:  # noqa: BLE001
                res["pedido_de_copia"] = f"falhou: {type(e).__name__} {getattr(e, 'code', '')}"
        saida.append(res)
    return saida


def main(argv=None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    configurar(argv[argv.index("--caso") + 1] if "--caso" in argv else "002")
    agora = now_utc()
    key = os.environ.get("YOUTUBE_API_KEY", "").strip()
    fc_key = os.environ.get("FACTCHECK_API_KEY", "").strip() or key
    out = {"caso": CASO, "coletado_em_utc": agora, "variantes": VARIANTES, "controles": CONTROLES}
    if "--sem-trends" not in argv:
        out["trends"] = trends()
    rows = []
    if key and "--sem-youtube" not in argv:
        out["youtube"], rows = youtube(key, agora)
    out["noticias"] = noticias()
    out["checagens"] = checagens(fc_key) if fc_key else []
    out["arquivo_web"] = wayback()
    out["erros"] = ERROS
    pasta = Path("data/casos") / CASO
    pasta.mkdir(parents=True, exist_ok=True)
    pv = priv_dir()
    pv.mkdir(parents=True, exist_ok=True)
    (pv / "busca_coleta.json").write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    if rows:
        arq = pv / "youtube_comentarios.csv.gz"
        antigos = {r["comment_id"]: r for r in csv.DictReader(gzip.open(arq, "rt", encoding="utf-8"), delimiter=";")} if arq.exists() else {}
        antigos.update({r["comment_id"]: r for r in rows})
        campos = list(rows[0].keys())
        with gzip.open(arq, "wt", encoding="utf-8", newline="") as f:
            w = csv.DictWriter(f, campos, delimiter=";", extrasaction="ignore")
            w.writeheader()
            w.writerows(antigos.values())
    print(f"caso {CASO}: notícias {len(out['noticias'])} · checagens {len(out['checagens'])} · arquivo web "
          f"{[(len(a.get('capturas') or []), a.get('pedido_de_copia')) for a in out['arquivo_web']]} · erros {ERROS[:3]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
