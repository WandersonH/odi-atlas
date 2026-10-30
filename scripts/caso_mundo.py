#!/usr/bin/env python3
"""Caso 019 — Como o mundo viu a eleição brasileira de 2026 no YouTube (grátis, YouTube Data API).

Pedido do responsável (30/10/2026): "assim como fizemos a página do debate, uma análise de como o mundo viu nossas eleições:
visão por continente e país; coleta de conteúdo no YouTube em outras línguas, com rede de comentários por língua materna".

O que faz, a cada execução (cota estimada: ~100 unidades por busca + ~1 por lote de 50 vídeos/canais + 1 por página de comentários):
  1. search.list, uma ou mais consultas por língua (config data/config/caso_mundo.json), vídeos publicados desde 16/08/2026
     (início da propaganda eleitoral), por visualizações. Guarda o total que a API informa (pageInfo.totalResults, estimativa
     do próprio YouTube) como universo da consulta.
  2. Filtro de pertinência: título ou descrição citam o Brasil, Lula, Flávio/Bolsonaro (na língua da consulta).
  3. videos.list (números e idioma declarado) e channels.list (país declarado pelo canal e inscritos).
  4. commentThreads.list nos vídeos mais vistos de cada língua (até 100 conversas por relevância, com as respostas que vierem).
  5. Língua de cada comentário por identificação automática (py3langid, restrita a 26 línguas, nomes próprios removidos,
     só com 20+ letras e confiança ≥ 0,90; o resto fica "indeterminado").

"Língua materna" não é observável: o Atlas mede a LÍNGUA EM QUE O COMENTÁRIO FOI ESCRITO. País do canal é o que o canal
declara (muitos não declaram: ⛔ não informado). Vídeos em português (ou de canais do Brasil) achados pelas consultas em outras
línguas são contados à parte: não são "o mundo de fora".

Acumula entre execuções (vídeos achados em dias anteriores continuam e têm os números atualizados).
Privado (ODI_INTERNO_DIR/casos/019): estado.json, comentarios.csv.gz (texto e autor — pessoas comuns).
Público (data/casos/019): mundo.json, rede_linguas.gexf, rede_canais_linguas.gexf (só contagens; nomes de canais só com 10 mil+).
Uso: python scripts/caso_mundo.py [--sem-coleta]
"""
from __future__ import annotations

import csv
import gzip
import json
import os
import re
import sys
import urllib.error
import urllib.parse
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from net import get_json, now_utc  # noqa: E402

API = "https://www.googleapis.com/youtube/v3"
ERROS: list[str] = []

NOMES_LINGUA = {"en": "inglês", "es": "espanhol", "pt": "português", "fr": "francês", "de": "alemão", "it": "italiano", "ja": "japonês",
                "zh": "chinês", "ru": "russo", "ar": "árabe", "ko": "coreano", "hi": "hindi", "tr": "turco", "nl": "neerlandês",
                "pl": "polonês", "uk": "ucraniano", "he": "hebraico", "fa": "persa", "id": "indonésio", "sv": "sueco", "ro": "romeno",
                "el": "grego", "cs": "tcheco", "hu": "húngaro", "vi": "vietnamita", "th": "tailandês", "?": "indeterminado"}
LINGUAS_ID = [k for k in NOMES_LINGUA if k != "?"]

# ISO 3166-1 alfa-2 → continente (Américas separadas em Norte/Central/Caribe e Sul, como no IBGE)
_CONT = {
    "América do Sul": "AR BO BR CL CO EC FK GF GY PE PY SR UY VE",
    "América do Norte, Central e Caribe": "AG AI AW BB BL BM BQ BS BZ CA CR CU CW DM DO GD GL GP GT HN HT JM KN KY LC MF MQ MS MX NI PA PM PR SV SX TC TT US VC VG VI",
    "Europa": "AD AL AT AX BA BE BG BY CH CY CZ DE DK EE ES FI FO FR GB GG GI GR HR HU IE IM IS IT JE LI LT LU LV MC MD ME MK MT NL NO PL PT RO RS RU SE SI SJ SK SM UA VA XK",
    "Ásia": "AE AF AM AZ BD BH BN BT CN GE HK ID IL IN IQ IR JO JP KG KH KP KR KW KZ LA LB LK MM MN MO MV MY NP OM PH PK PS QA SA SG SY TH TJ TL TM TR TW UZ VN YE",
    "África": "AO BF BI BJ BW CD CF CG CI CM CV DJ DZ EG EH ER ET GA GH GM GN GQ GW KE KM LR LS LY MA MG ML MR MU MW MZ NA NE NG RE RW SC SD SH SL SN SO SS ST SZ TD TG TN TZ UG YT ZA ZM ZW",
    "Oceania": "AS AU CK FJ FM GU KI MH MP NC NF NR NU NZ PF PG PN PW SB TK TO TV VU WF WS",
}
CONTINENTE = {c: k for k, v in _CONT.items() for c in v.split()}

# Pertinência: o vídeo precisa citar o Brasil ou os candidatos (em várias escritas)
PERTINENTE = re.compile(
    r"lula|bolsonar|brazil|brasil|br[eé]sil|brasilien|brasile|brazilië|brazylia|brezilya|brazílie|brazília|brasilia|bra[sz]il|"
    r"ブラジル|ルラ|ボルソナロ|巴西|卢拉|盧拉|博索纳罗|бразил|лула|болсонару|البرازيل|لولا|بولسونارو|브라질|룰라|보우소나루|"
    r"ब्राज़ील|ब्राजील|लूला|ברזיל|לולה|برزیل|ลูลา|บราซิล|βραζιλ|λούλα", re.I)
MENCIONA = {"Lula": re.compile(r"lula|ルラ|卢拉|盧拉|лула|لولا|룰라|लूला|לולה|ลูลา|λούλα", re.I),
            "Flávio Bolsonaro": re.compile(r"fl[aá]vio|bolsonar|ボルソナロ|博索纳罗|болсонару|بولسونارو|보우소나루", re.I)}
NOMES_PROPRIOS = re.compile(r"\b(lula|bolsonaro\w*|fl[aá]vio|jair|haddad|moraes|trump|brasil|brazil|br[eé]sil|lulinha|pt)\b", re.I)


def lingua_base(c: str | None) -> str | None:
    c = (c or "").strip().lower()
    if not c or c in ("zxx", "und"):
        return None
    return c.split("-")[0].split("_")[0]


def continente(pais: str | None) -> str:
    return CONTINENTE.get((pais or "").upper(), "⛔ não informado")


def pertinente(titulo: str, descricao: str) -> bool:
    return bool(PERTINENTE.search(f"{titulo or ''} {(descricao or '')[:600]}"))


def mencoes(titulo: str, descricao: str) -> list[str]:
    t = f"{titulo or ''} {(descricao or '')[:600]}"
    return [k for k, rx in MENCIONA.items() if rx.search(t)]


_ID = None


def identificar(texto: str) -> str:
    """Língua do texto ('?' = indeterminado). Remove nomes próprios, URLs e menções; exige 20+ letras e confiança ≥ 0,90."""
    global _ID
    t = re.sub(r"https?://\S+|@\S+|#\S+", " ", texto or "")
    t = NOMES_PROPRIOS.sub(" ", t)
    if sum(ch.isalpha() for ch in t) < 20:
        return "?"
    if _ID is None:
        from py3langid.langid import MODEL_FILE, LanguageIdentifier
        _ID = LanguageIdentifier.from_pickled_model(MODEL_FILE, norm_probs=True)
        _ID.set_languages(LINGUAS_ID)
    lang, p = _ID.classify(t)
    return lang if float(p) >= 0.90 else "?"


def chamar(rota: str, **q) -> dict:
    try:
        return get_json(f"{API}/{rota}?" + urllib.parse.urlencode(q), timeout=60)
    except urllib.error.HTTPError as e:
        corpo = ""
        try:
            corpo = e.read().decode("utf-8", "replace")
        except Exception:  # noqa: BLE001
            pass
        motivo = next((m for m in ("quotaExceeded", "commentsDisabled", "forbidden", "videoNotFound") if m in corpo), f"HTTP {e.code}")
        raise RuntimeError(motivo) from None
    except Exception as e:  # noqa: BLE001 — a mensagem pode trazer a URL com a chave
        raise RuntimeError(type(e).__name__) from None


def buscar(key: str, cfg: dict, agora: str) -> list[dict]:
    """Uma linha por consulta: universo informado pela API, lidos, ids."""
    out = []
    for L in cfg["linguas"]:
        for consulta in L["consultas"]:
            reg = {"lingua": L["codigo"], "consulta": consulta, "lido_em_utc": agora, "total_informado": None, "lidos": 0, "ids": [], "erro": None}
            token = None
            for _ in range(int(L.get("paginas", cfg.get("paginas", 1)))):
                q = dict(part="snippet", q=consulta, type="video", maxResults=50, order="viewCount", publishedAfter=cfg["desde"],
                         relevanceLanguage=L["codigo"], key=key)
                if token:
                    q["pageToken"] = token
                try:
                    d = chamar("search", **q)
                except RuntimeError as e:
                    reg["erro"] = str(e)
                    ERROS.append(f"search {L['codigo']} '{consulta}': {e}")
                    break
                if reg["total_informado"] is None:
                    reg["total_informado"] = (d.get("pageInfo") or {}).get("totalResults")
                ids = [it["id"]["videoId"] for it in d.get("items", []) if (it.get("id") or {}).get("videoId")]
                reg["ids"] += ids
                reg["lidos"] += len(ids)
                token = d.get("nextPageToken")
                if not token:
                    break
            out.append(reg)
            if reg["erro"] == "quotaExceeded":
                return out
    return out


def videos(key: str, ids: list[str]) -> dict[str, dict]:
    out = {}
    for i in range(0, len(ids), 50):
        try:
            d = chamar("videos", part="snippet,statistics", id=",".join(ids[i:i + 50]), key=key)
        except RuntimeError as e:
            ERROS.append(f"videos.list: {e}")
            continue
        for it in d.get("items", []):
            sn, st = it["snippet"], it.get("statistics", {})
            n = lambda k: int(st[k]) if str(st.get(k, "")).isdigit() else None  # noqa: E731
            out[it["id"]] = {"id": it["id"], "titulo": sn.get("title") or "", "descricao": (sn.get("description") or "")[:600],
                             "canal_id": sn.get("channelId"), "canal": sn.get("channelTitle"), "publicado_em": sn.get("publishedAt"),
                             "lingua_declarada": lingua_base(sn.get("defaultAudioLanguage") or sn.get("defaultLanguage")),
                             "visualizacoes": n("viewCount"), "curtidas": n("likeCount"), "comentarios": n("commentCount"),
                             "comentarios_abertos": "commentCount" in st}
    return out


def canais(key: str, ids: list[str]) -> dict[str, dict]:
    out = {}
    for i in range(0, len(ids), 50):
        try:
            d = chamar("channels", part="snippet,statistics", id=",".join(ids[i:i + 50]), key=key)
        except RuntimeError as e:
            ERROS.append(f"channels.list: {e}")
            continue
        for it in d.get("items", []):
            sn, st = it["snippet"], it.get("statistics", {})
            insc = int(st["subscriberCount"]) if str(st.get("subscriberCount", "")).isdigit() else None
            out[it["id"]] = {"id": it["id"], "titulo": sn.get("title"), "pais": (sn.get("country") or "").upper() or None,
                             "inscritos": insc, "inscritos_ocultos": bool(st.get("hiddenSubscriberCount")),
                             "lingua_declarada": lingua_base(sn.get("defaultLanguage"))}
    return out


def comentarios(key: str, vid: str, agora: str) -> tuple[list[dict], str]:
    try:
        d = chamar("commentThreads", part="snippet,replies", videoId=vid, maxResults=100, order="relevance", textFormat="plainText", key=key)
    except RuntimeError as e:
        return [], f"⛔ {e}"
    rows = []
    for it in d.get("items", []):
        top = it["snippet"]["topLevelComment"]
        for c, tipo, pai in [(top, "comentario", "")] + [(r, "resposta", top["id"]) for r in (it.get("replies") or {}).get("comments", [])]:
            s = c["snippet"]
            rows.append({"comment_id": c["id"], "parent_id": pai, "tipo": tipo, "video_id": vid,
                         "autor_canal": (s.get("authorChannelId") or {}).get("value", ""), "autor_nome": s.get("authorDisplayName", ""),
                         "texto": (s.get("textOriginal") or s.get("textDisplay") or "").replace("\r", " "), "curtidas": s.get("likeCount", 0),
                         "publicado_em": s.get("publishedAt", ""), "coletado_em": agora})
    return rows, f"{len(rows)} lidos"


CAMPOS_COM = ["comment_id", "parent_id", "tipo", "video_id", "autor_canal", "autor_nome", "texto", "curtidas", "publicado_em", "coletado_em", "lingua"]


def ler_csv(f: Path) -> dict[str, dict]:
    if not f.exists():
        return {}
    return {r["comment_id"]: r for r in csv.DictReader(gzip.open(f, "rt", encoding="utf-8"))}


def gravar_csv(f: Path, rows: dict[str, dict]) -> None:
    with gzip.open(f, "wt", encoding="utf-8", newline="") as g:
        w = csv.DictWriter(g, fieldnames=CAMPOS_COM, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows.values())


def lingua_video(v: dict, lingua_consulta: str) -> tuple[str, str]:
    if v.get("lingua_declarada"):
        return v["lingua_declarada"], "declarada pelo canal"
    t = identificar(f"{v.get('titulo', '')}. {v.get('descricao', '')[:300]}")
    if t != "?":
        return t, "identificada no título e na descrição"
    return lingua_consulta, "a da consulta (título curto demais para identificar)"


def coletar(cfg: dict, key: str, estado: dict, priv: Path, agora: str) -> None:
    consultas = buscar(key, cfg, agora)
    estado.setdefault("consultas", []).extend({k: v for k, v in c.items() if k != "ids"} for c in consultas)
    achados = estado.setdefault("achados", {})  # id -> {linguas_consulta: [...], primeira_vez}
    for c in consultas:
        for vid in c["ids"]:
            a = achados.setdefault(vid, {"linguas_consulta": [], "primeira_vez_utc": agora})
            if c["lingua"] not in a["linguas_consulta"]:
                a["linguas_consulta"].append(c["lingua"])
    V = videos(key, list(achados))
    for vid, v in V.items():
        estado.setdefault("videos", {})[vid] = {**estado.get("videos", {}).get(vid, {}), **v, "lido_em_utc": agora}
    cids = sorted({v["canal_id"] for v in estado.get("videos", {}).values() if v.get("canal_id")})
    C = canais(key, cids)
    for cid, c in C.items():
        estado.setdefault("canais", {})[cid] = {**c, "lido_em_utc": agora}
    # comentários: os K vídeos pertinentes mais vistos de cada língua (fora do português), com comentários abertos
    por_l = defaultdict(list)
    for vid, v in estado.get("videos", {}).items():
        if not pertinente(v.get("titulo", ""), v.get("descricao", "")) or not v.get("comentarios_abertos") or not v.get("comentarios"):
            continue
        lv = v.get("lingua") or lingua_video(v, (achados.get(vid) or {}).get("linguas_consulta", ["?"])[0])[0]
        if lv == "pt":
            continue
        por_l[lv].append(v)
    f = priv / "comentarios.csv.gz"
    acervo = ler_csv(f)
    st = estado.setdefault("comentarios_status", {})
    for lv, vs in por_l.items():
        for v in sorted(vs, key=lambda x: -(x.get("visualizacoes") or 0))[: int(cfg.get("videos_com_comentarios_por_lingua", 8))]:
            rows, s = comentarios(key, v["id"], agora)
            st[v["id"]] = {"status": s, "lido_em_utc": agora}
            for r in rows:
                r["lingua"] = identificar(r["texto"])
                acervo[r["comment_id"]] = r
            if "quotaExceeded" in s:
                ERROS.append("commentThreads: quotaExceeded")
                break
    gravar_csv(f, acervo)


def analisar(cfg: dict, estado: dict, priv: Path, pub: Path, agora: str) -> dict:
    achados = estado.get("achados", {})
    C = estado.get("canais", {})
    vids, fora_pt, nao_pert = [], [], 0
    for vid, v in estado.get("videos", {}).items():
        if not pertinente(v.get("titulo", ""), v.get("descricao", "")):
            nao_pert += 1
            continue
        lc = (achados.get(vid) or {}).get("linguas_consulta", ["?"])
        lv, como = lingua_video(v, lc[0])
        v["lingua"] = lv
        c = C.get(v.get("canal_id")) or {}
        pais = c.get("pais")
        grande = (c.get("inscritos") or 0) >= 10000
        reg = {"id": vid, "titulo": v["titulo"], "publicado_em": v.get("publicado_em"), "lingua": lv, "lingua_como": como,
               "linguas_consulta": lc, "canal": c.get("titulo") if grande else "canal com menos de 10 mil inscritos (ou número oculto)",
               "canal_id": v.get("canal_id") if grande else None, "inscritos": c.get("inscritos") if grande else None,
               "pais": pais, "continente": continente(pais), "visualizacoes": v.get("visualizacoes"), "curtidas": v.get("curtidas"),
               "comentarios": v.get("comentarios"), "mencoes": mencoes(v["titulo"], v.get("descricao", ""))}
        (fora_pt if (lv == "pt" or pais == "BR") else vids).append(reg)
    soma = lambda arr, k: sum((x.get(k) or 0) for x in arr)  # noqa: E731

    def agrupa(chave):
        g = defaultdict(list)
        for x in vids:
            g[x[chave] or "⛔ não informado"].append(x)
        return {k: {"videos": len(a), "visualizacoes": soma(a, "visualizacoes"), "canais": len({x["canal_id"] or x["id"] for x in a}),
                    "lula": sum("Lula" in x["mencoes"] for x in a), "flavio": sum("Flávio Bolsonaro" in x["mencoes"] for x in a)}
                for k, a in sorted(g.items(), key=lambda kv: -soma(kv[1], "visualizacoes"))}

    # comentários
    acervo = ler_csv(priv / "comentarios.csv.gz")
    vid_ling = {x["id"]: x["lingua"] for x in vids}
    vid_cont = {x["id"]: x["continente"] for x in vids}
    matriz = defaultdict(Counter)
    por_cont = defaultdict(Counter)
    lidos_por_video = Counter()
    for r in acervo.values():
        if r["video_id"] not in vid_ling:
            continue
        lidos_por_video[r["video_id"]] += 1
        matriz[vid_ling[r["video_id"]]][r.get("lingua") or "?"] += 1
        por_cont[vid_cont[r["video_id"]]][r.get("lingua") or "?"] += 1
    amostra = []
    for lv in sorted({vid_ling[v] for v in lidos_por_video}):
        vs = [x for x in vids if x["lingua"] == lv and lidos_por_video.get(x["id"])]
        uni = soma(vs, "comentarios")
        lid = sum(lidos_por_video[x["id"]] for x in vs)
        amostra.append({"lingua_video": lv, "videos": len(vs), "universo": uni,
                        "fonte_universo": "contagem de comentários informada pelo YouTube nos vídeos lidos (inclui respostas)",
                        "amostra": lid, "pct": round(100 * lid / uni, 1) if uni else None,
                        "criterio": f"os {cfg.get('videos_com_comentarios_por_lingua', 8)} vídeos mais vistos da língua com comentários abertos; "
                                    "até 100 conversas por relevância por vídeo, com as respostas que a API devolve"})
    # redes (GEXF): língua do vídeo → língua do comentário; canal → língua do comentário
    nos, ar = {}, Counter()
    for lv, cs in matriz.items():
        nos[f"V:{lv}"] = {"rotulo": f"vídeo em {NOMES_LINGUA.get(lv, lv)}", "tipo": "lingua_video", "n": sum(cs.values())}
        for lc, n in cs.items():
            nos.setdefault(f"C:{lc}", {"rotulo": f"comentário em {NOMES_LINGUA.get(lc, lc)}", "tipo": "lingua_comentario", "n": 0})
            nos[f"C:{lc}"]["n"] += n
            ar[(f"V:{lv}", f"C:{lc}")] += n
    from redes_caso import gexf
    pub.mkdir(parents=True, exist_ok=True)
    gexf(nos, dict(ar), pub / "rede_linguas.gexf", dirigida=True)
    nc, ac = {}, Counter()
    vid_canal = {x["id"]: x for x in vids}
    for r in acervo.values():
        x = vid_canal.get(r["video_id"])
        if not x:
            continue
        k = f"canal:{x['canal_id'] or 'pequeno:' + x['id']}"
        nc.setdefault(k, {"rotulo": f"{x['canal']} ({x['pais'] or '⛔'})" if x["canal_id"] else "canal pequeno", "tipo": f"canal · {x['continente']}", "n": 0})
        nc[k]["n"] += 1
        lc = r.get("lingua") or "?"
        nc.setdefault(f"C:{lc}", {"rotulo": f"comentário em {NOMES_LINGUA.get(lc, lc)}", "tipo": "lingua_comentario", "n": 0})
        nc[f"C:{lc}"]["n"] += 1
        ac[(k, f"C:{lc}")] += 1
    gexf(nc, dict(ac), pub / "rede_canais_linguas.gexf", dirigida=True)
    # universo das consultas: a última leitura de cada consulta
    ult = {}
    for c in estado.get("consultas", []):
        ult[(c["lingua"], c["consulta"])] = c
    cons = [{k: c[k] for k in ("lingua", "consulta", "lido_em_utc", "total_informado", "lidos", "erro")} |
            {"pct": round(100 * c["lidos"] / c["total_informado"], 2) if c.get("total_informado") else None,
             "fonte_universo": "pageInfo.totalResults da busca do YouTube (estimativa informada pela própria API)",
             "criterio": "vídeos publicados desde " + cfg["desde"][:10] + ", ordenados por visualizações; 50 por página"}
            for c in ult.values()]
    semanas = defaultdict(Counter)
    for x in vids:
        if x.get("publicado_em"):
            import datetime as dt
            d = dt.date.fromisoformat(x["publicado_em"][:10])
            semanas[(d - dt.timedelta(days=d.weekday())).isoformat()][x["continente"]] += 1
    out = {"caso": "019", "gerado_em_utc": agora, "desde": cfg["desde"], "linguas_consultadas": [L["codigo"] for L in cfg["linguas"]],
           "nomes_lingua": NOMES_LINGUA, "consultas": cons,
           "videos_achados": len(estado.get("videos", {})), "nao_pertinentes": nao_pert, "em_portugues_ou_canal_brasileiro": len(fora_pt),
           "videos": sorted(vids, key=lambda x: -(x.get("visualizacoes") or 0)),
           "por_continente": agrupa("continente"), "por_pais": agrupa("pais"), "por_lingua": agrupa("lingua"),
           "serie_semanal_continente": {k: dict(v) for k, v in sorted(semanas.items())},
           "comentarios": {"lidos": sum(lidos_por_video.values()), "amostra": amostra,
                           "matriz": {k: dict(v) for k, v in matriz.items()}, "por_continente": {k: dict(v) for k, v in por_cont.items()},
                           "indeterminados": sum(c.get("?", 0) for c in matriz.values())},
           "comentarios_status": estado.get("comentarios_status", {}),
           "metodo": ("Língua do comentário = identificação automática (py3langid 0.3.0, 26 línguas, nomes próprios removidos, 20+ letras e confiança "
                      "≥ 0,90; o resto é 'indeterminado'). Não é a língua materna de quem escreve, que não é observável. País = o que o canal declara "
                      "no YouTube. Vídeos em português ou de canais do Brasil ficam fora das contagens do 'mundo' e são informados à parte."),
           "erros": ERROS[-40:]}
    (pub / "mundo.json").write_text(json.dumps(out, ensure_ascii=False, indent=0), encoding="utf-8")
    return out


def main(argv=None) -> int:
    argv = sys.argv[1:] if argv is None else list(argv)
    interno, key = os.environ.get("ODI_INTERNO_DIR"), os.environ.get("YOUTUBE_API_KEY", "")
    if not interno:
        print("⛔ ODI_INTERNO_DIR ausente")
        return 1
    cfg = json.loads(Path("data/config/caso_mundo.json").read_text(encoding="utf-8"))
    priv = Path(interno) / "casos" / "019"
    priv.mkdir(parents=True, exist_ok=True)
    fe = priv / "estado.json"
    estado = json.loads(fe.read_text(encoding="utf-8")) if fe.exists() else {}
    agora = now_utc()
    if "--sem-coleta" not in argv:
        if not key:
            print("⛔ YOUTUBE_API_KEY ausente")
            return 1
        coletar(cfg, key, estado, priv, agora)
        fe.write_text(json.dumps(estado, ensure_ascii=False), encoding="utf-8")
    out = analisar(cfg, estado, priv, Path("data/casos/019"), agora)
    fe.write_text(json.dumps(estado, ensure_ascii=False), encoding="utf-8")
    print(f"caso 019: {out['videos_achados']} vídeos achados · {len(out['videos'])} do mundo (fora do português) · "
          f"{out['em_portugues_ou_canal_brasileiro']} em português/canal BR · {out['nao_pertinentes']} não pertinentes · "
          f"comentários lidos {out['comentarios']['lidos']} (indeterminados {out['comentarios']['indeterminados']})")
    for c in out["consultas"]:
        print(f"  {c['lingua']} '{c['consulta']}': universo {c['total_informado']} · lidos {c['lidos']} · {c['erro'] or 'ok'}")
    print("  continentes:", {k: v["videos"] for k, v in out["por_continente"].items()})
    if ERROS:
        print("  erros:", ERROS[:8])
    return 0 if out["videos"] or not ERROS else 1


if __name__ == "__main__":
    sys.exit(main())
