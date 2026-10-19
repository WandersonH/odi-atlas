#!/usr/bin/env python3
"""Debate do 2º turno (Band/Estadão, 18/10/2026): localiza o vídeo no YouTube e baixa a transcrição.

Pedido do usuário (18/10, 23h07): "pegar o vídeo e colocar no início da página" e analisar a transcrição.
1. YouTube Data API (oficial; chave só por YOUTUBE_API_KEY): busca vídeos publicados desde 18/10 com "debate" + Lula/Flávio,
   guarda os candidatos (canal, título, duração, visualizações) e escolhe o mais longo de canal da Band ou do Estadão
   (o debate inteiro dura mais de 1 h). `--video ID` força um vídeo.
2. Transcrição: legendas do YouTube (manuais, se houver; senão automáticas em português) por yt-dlp, sem baixar o vídeo.
   Se as legendas não vierem, `--whisper` baixa só o áudio e transcreve com faster-whisper (modelo small, CPU).
Saídas: data/debate/video.json (público: id, canal, título, duração, fonte da transcrição) e a transcrição em segmentos com
tempo no repositório privado (ODI_INTERNO_DIR/debate/transcricao.json) — o texto integral é da transmissão; a página
publica só análises agregadas e trechos curtos.
"""
from __future__ import annotations

import glob
import json
import os
import re
import subprocess
import sys
import tempfile
import urllib.parse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from net import get_json, now_utc  # noqa: E402

API = "https://www.googleapis.com/youtube/v3"
DESDE = "2026-10-18T20:00:00Z"
CANAIS_OK = ("band", "estad")


def dur_s(iso: str) -> int:
    m = re.fullmatch(r"P(?:(\d+)D)?T?(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?", iso or "")
    if not m:
        return 0
    d, h, mi, s = (int(x or 0) for x in m.groups())
    return d * 86400 + h * 3600 + mi * 60 + s


def buscar(key: str) -> list[dict]:
    ids = []
    for q in ("debate Band Lula Flávio Bolsonaro", "debate presidencial Band 2º turno", "debate Estadão Lula Flávio"):
        p = {"part": "snippet", "q": q, "type": "video", "publishedAfter": DESDE, "regionCode": "BR", "relevanceLanguage": "pt",
             "maxResults": 15, "order": "relevance", "key": key}
        for it in (get_json(f"{API}/search?{urllib.parse.urlencode(p)}").get("items") or []):
            vid = it["id"].get("videoId")
            if vid and vid not in ids:
                ids.append(vid)
    if not ids:
        return []
    p = {"part": "snippet,contentDetails,statistics,liveStreamingDetails", "id": ",".join(ids[:50]), "key": key}
    out = []
    for v in get_json(f"{API}/videos?{urllib.parse.urlencode(p)}").get("items") or []:
        sn, cd, st = v["snippet"], v["contentDetails"], v.get("statistics") or {}
        out.append({"id": v["id"], "canal": sn.get("channelTitle"), "canal_id": sn.get("channelId"), "titulo": sn.get("title"),
                    "publicado_em": sn.get("publishedAt"), "duracao_s": dur_s(cd.get("duration")), "legenda_manual": cd.get("caption") == "true",
                    "visualizacoes": int(st.get("viewCount") or 0), "ao_vivo": (v.get("liveStreamingDetails") or {}).get("actualStartTime")})
    return sorted(out, key=lambda x: -x["duracao_s"])


def escolher(cands: list[dict]) -> dict | None:
    bons = [c for c in cands if any(k in (c["canal"] or "").lower() for k in CANAIS_OK) and c["duracao_s"] >= 3600]
    return bons[0] if bons else None


def vtt_segmentos(txt: str) -> list[dict]:
    """VTT do YouTube → segmentos (início, fim, texto) sem as repetições das legendas automáticas."""
    segs, ultimo = [], ""
    blocos = re.split(r"\n\n+", txt)
    for b in blocos:
        m = re.search(r"(\d+):(\d+):(\d+)\.(\d+) --> (\d+):(\d+):(\d+)\.(\d+)", b)
        if not m:
            continue
        g = [int(x) for x in m.groups()]
        ini, fim = g[0] * 3600 + g[1] * 60 + g[2] + g[3] / 1000, g[4] * 3600 + g[5] * 60 + g[6] + g[7] / 1000
        linhas = [re.sub(r"<[^>]+>", "", l).strip() for l in b.split("\n")[1:] if "-->" not in l]
        linhas = [l for l in linhas if l]
        if not linhas:
            continue
        texto = linhas[-1]  # nas automáticas, a última linha é a nova; a primeira repete o bloco anterior
        if texto == ultimo or fim - ini < 0.05:
            continue
        ultimo = texto
        segs.append({"ini": round(ini, 2), "fim": round(fim, 2), "texto": texto})
    return segs


ERROS: list[str] = []


CLIENTES = ("default", "tv_embedded,web_embedded", "mweb", "android_vr", "ios")


def faixas_api(vid: str, key: str) -> list[dict]:
    """captions.list (YouTube Data API, só a chave): quais legendas existem (idioma, automática ou não). Baixar exige OAuth do dono."""
    p = {"part": "snippet", "videoId": vid, "key": key}
    return [{"idioma": x["snippet"].get("language"), "tipo": x["snippet"].get("trackKind"), "nome": x["snippet"].get("name")}
            for x in get_json(f"{API}/captions?{urllib.parse.urlencode(p)}").get("items") or []]


def timedtext(vid: str, pasta: Path) -> tuple[list[dict], str | None]:
    """Endpoint público de legendas (o mesmo do player), sem yt-dlp."""
    from net import open_url, read_body
    for q in ({"lang": "pt", "fmt": "vtt"}, {"lang": "pt-BR", "fmt": "vtt"}, {"lang": "pt", "kind": "asr", "fmt": "vtt"}):
        try:
            txt = read_body(open_url(f"https://www.youtube.com/api/timedtext?v={vid}&" + urllib.parse.urlencode(q), timeout=60)).decode("utf-8", "replace")
            if "-->" in txt:
                return vtt_segmentos(txt), f"legenda do YouTube (timedtext, {q.get('kind', 'manual')} {q['lang']})"
            ERROS.append(f"timedtext {q}: vazio ({len(txt)} bytes)")
        except Exception as e:  # noqa: BLE001
            ERROS.append(f"timedtext {q}: {type(e).__name__} {getattr(e, 'code', '')}")
    return [], None


def apify_legendas(vids: list[str]) -> dict[str, tuple[list[dict], str | None]]:
    """Legendas pela Apify (seemuapps/youtube-transcript-scraper; US$ 0,0001 por transcrição + início), conta 1 (APIFY_TOKEN),
    teto US$ 0,05 — autorizado pelo usuário em 19/10/2026, 02h2x, só para os 3 blocos do debate."""
    from collect_meta_apify import run_actor
    tok = os.environ.get("APIFY_TOKEN", "").strip()
    if not tok:
        return {}
    run, itens = run_actor(tok, "seemuapps~youtube-transcript-scraper",
                           {"videoUrls": [f"https://www.youtube.com/watch?v={v}" for v in vids], "languages": ["pt", "pt-BR"], "preferManualCaptions": True}, 0.05)
    out = {}
    for x in itens or []:
        vid = str(x.get("videoId") or "") or str(x.get("inputUrl") or "").split("v=")[-1].split("&")[0]
        segs = x.get("segments") or x.get("transcriptSegments") or []
        lista = [{"ini": round((s.get("startMs") or 0) / 1000, 2), "fim": round(((s.get("startMs") or 0) + (s.get("durationMs") or 0)) / 1000, 2),
                  "texto": " ".join(str(s.get("text") or "").split())} for s in segs if s.get("text")]
        tipo = "automática" if x.get("isAutoGenerated") or x.get("isGenerated") or x.get("autoGenerated") else "manual" if x.get("isAutoGenerated") is False else "?"
        out[vid] = (lista, f"legenda {tipo} do YouTube ({x.get('language') or x.get('languageCode') or 'pt'}) lida pela Apify (seemuapps/youtube-transcript-scraper)")
        if not lista:
            ERROS.append(f"apify {vid or x.get('inputUrl')}: sem segmentos · status {x.get('status')} · erro {str(x.get('error'))[:200]}")
    ERROS.append(f"apify run {run.get('id')} · status {run.get('status')} · itens {len(itens or [])} · custo US$ {run.get('usageTotalUsd')}")
    return out


def blocos_anteriores() -> dict[str, tuple[list[dict], str | None]]:
    """Segmentos por vídeo já guardados no privado (tempos do próprio vídeo). Arquivos antigos sem `ini_video`:
    o deslocamento é refeito pela mesma regra usada ao gravar (fim do último segmento do bloco anterior + 1 s)."""
    interno = os.environ.get("ODI_INTERNO_DIR")
    arq = Path(interno) / "debate/transcricao.json" if interno else None
    if not arq or not arq.exists():
        return {}
    tr = json.loads(arq.read_text(encoding="utf-8"))
    por, ordem = {}, []
    for x in tr.get("segmentos") or []:
        if x.get("video"):
            if x["video"] not in por:
                ordem.append(x["video"])
            por.setdefault(x["video"], []).append(x)
    out, desloc = {}, 0.0
    for v in ordem:
        xs = por[v]
        rel = [{"ini": x["ini_video"] if "ini_video" in x else round(x["ini"] - desloc, 2),
                "fim": round(x["fim"] - (x["ini"] - x["ini_video"]), 2) if "ini_video" in x else round(x["fim"] - desloc, 2),
                "texto": x["texto"]} for x in xs]
        desloc += rel[-1]["fim"] + 1
        out[v] = (rel, xs[0].get("fonte") or tr.get("fonte"))
    return out


def legendas(vid: str, pasta: Path) -> tuple[list[dict], str | None]:
    for cli in CLIENTES:
        segs, fonte = legendas_cliente(vid, pasta, cli)
        if segs:
            return segs, f"{fonte} · cliente {cli}"
    return timedtext(vid, pasta)


def legendas_cliente(vid: str, pasta: Path, cliente: str) -> tuple[list[dict], str | None]:
    extra = [] if cliente == "default" else ["--extractor-args", f"youtube:player_client={cliente}"]
    base = ["yt-dlp", *extra, "--skip-download", "--sub-format", "vtt", "-o", str(pasta / "%(id)s.%(ext)s"), f"https://www.youtube.com/watch?v={vid}"]
    for modo, args in (("manual", ["--write-subs", "--sub-langs", "pt.*,pt"]), ("automática", ["--write-auto-subs", "--sub-langs", "pt-orig,pt"])):
        r = subprocess.run(base[:1] + args + base[1:], capture_output=True, text=True, timeout=600)
        ERROS.append(f"{cliente} {modo}: " + " | ".join(l for l in (r.stderr or "").splitlines() if "ERROR" in l or "WARNING" in l)[-300:])
        arqs = sorted(glob.glob(str(pasta / f"{vid}*.vtt")))
        if arqs:
            return vtt_segmentos(Path(arqs[0]).read_text(encoding="utf-8")), f"legenda {modo} do YouTube ({Path(arqs[0]).name.split('.')[-2]})"
    return [], None


def whisper(vid: str, pasta: Path, trecho: str | None = None) -> tuple[list[dict], str | None]:
    """Só o áudio do trecho do debate (ex.: "4:00:00-6:12:26"), mono 16 kHz; tempos devolvidos já no relógio do vídeo."""
    extra = ["--download-sections", f"*{trecho}"] if trecho else []
    r = subprocess.run(["yt-dlp", "-f", "bestaudio", "-x", "--audio-format", "mp3", "--audio-quality", "9", *extra, "-o", str(pasta / "audio.%(ext)s"),
                        f"https://www.youtube.com/watch?v={vid}"], capture_output=True, text=True, timeout=3600)
    ERROS.append("áudio: " + " | ".join(l for l in (r.stderr or "").splitlines() if "ERROR" in l)[-300:])
    arq = next(iter(glob.glob(str(pasta / "audio.*"))), None)
    if not arq:
        return [], None
    from faster_whisper import WhisperModel
    m = WhisperModel("small", device="cpu", compute_type="int8")
    segs, info = m.transcribe(arq, language="pt", vad_filter=True, beam_size=1)
    desloc = 0
    if trecho:
        h = [int(x) for x in trecho.split("-")[0].split(":")]
        desloc = h[0] * 3600 + h[1] * 60 + h[2] if len(h) == 3 else h[0] * 60 + h[1]
    out = []
    for s in segs:
        out.append({"ini": round(s.start + desloc, 2), "fim": round(s.end + desloc, 2), "texto": s.text.strip()})
        if len(out) % 200 == 0:
            print(f"whisper: {len(out)} segmentos, {round(s.end / 60)} min", flush=True)
    _ = r
    return out, "faster-whisper small (CPU), transcrição automática do áudio"


def main(argv=None) -> int:
    argv = list(argv or [])
    root = Path(".")
    pasta = root / "data/debate"
    pasta.mkdir(parents=True, exist_ok=True)
    key = os.environ.get("YOUTUBE_API_KEY", "")
    man = {"coletado_em_utc": now_utc(), "debate": "Band/Estadão · 2º turno · 18/10/2026, 20h (Brasília)"}
    cands = []
    if key:
        try:
            cands = buscar(key)
        except Exception as e:  # noqa: BLE001 — a URL tem a chave: só o tipo do erro
            man["erro_busca"] = type(e).__name__
    man["candidatos"] = cands[:15]
    escolhido = next((c for c in cands if c["id"] == argv[argv.index("--video") + 1]), None) if "--video" in argv else escolher(cands)
    if "--video" in argv and not escolhido:
        escolhido = {"id": argv[argv.index("--video") + 1], "canal": None, "titulo": None, "duracao_s": None}
    man["video"] = escolhido
    if not escolhido:
        man["status"] = "⛔ vídeo do debate não encontrado (canal da Band/Estadão com mais de 1 h)"
        (pasta / "video.json").write_text(json.dumps(man, ensure_ascii=False, indent=1), encoding="utf-8")
        print(man["status"], [(c["canal"], c["titulo"], c["duracao_s"]) for c in cands[:8]])
        return 1
    blocos = argv[argv.index("--blocos") + 1].split(",") if "--blocos" in argv else []
    if blocos:  # vídeos do debate por bloco (indicados pelo usuário em 19/10): uma transcrição por bloco, em sequência
        segs, fontes, desloc, man["blocos"] = [], [], 0.0, []
        anteriores = blocos_anteriores()  # o que já foi lido em runs anteriores (privado): só pede à Apify o que falta
        faltam = [b for b in blocos if not anteriores.get(b)]
        via_apify = apify_legendas(faltam) if "--apify" in argv and faltam else {}
        for i, b in enumerate(blocos, 1):
            info = {"bloco": i, "id": b}
            if key:
                try:
                    v = (get_json(f"{API}/videos?" + urllib.parse.urlencode({"part": "snippet,contentDetails", "id": b, "key": key})).get("items") or [{}])[0]
                    info.update(titulo=(v.get("snippet") or {}).get("title"), canal=(v.get("snippet") or {}).get("channelTitle"),
                                duracao_api_s=dur_s((v.get("contentDetails") or {}).get("duration")))
                except Exception as e:  # noqa: BLE001
                    info["titulo_erro"] = type(e).__name__
                try:
                    info["faixas_api"] = faixas_api(b, key)
                except Exception as e:  # noqa: BLE001
                    info["faixas_api_erro"] = type(e).__name__
            if anteriores.get(b):
                sb, fb = anteriores[b]
            elif via_apify.get(b, ([], None))[0]:
                sb, fb = via_apify[b]
            else:
                with tempfile.TemporaryDirectory() as t:
                    sb, fb = legendas(b, Path(t))
            for x in sb:
                segs.append({"ini": round(x["ini"] + desloc, 2), "fim": round(x["fim"] + desloc, 2), "texto": x["texto"], "bloco": i, "video": b,
                             "ini_video": x["ini"], "fonte": fb})
            info.update(segmentos=len(sb), fonte=fb, duracao_s=round(sb[-1]["fim"], 1) if sb else None)
            desloc += (sb[-1]["fim"] if sb else 0) + 1
            fontes.append(fb)
            man["blocos"].append(info)
            print(f"bloco {i} ({b}): {len(sb)} segmentos · {fb} · faixas API {info.get('faixas_api')}")
        fonte = "; ".join(sorted({f for f in fontes if f})) or None
        escolhido = {**escolhido, "blocos": blocos}
    else:
        with tempfile.TemporaryDirectory() as t:
            segs, fonte = legendas(escolhido["id"], Path(t))
            if not segs and "--whisper" in argv:
                segs, fonte = whisper(escolhido["id"], Path(t), argv[argv.index("--trecho") + 1] if "--trecho" in argv else None)
    man.update(diagnostico=[e for e in ERROS if e.split(": ", 1)[-1]], trecho=argv[argv.index("--trecho") + 1] if "--trecho" in argv else None, transcricao_fonte=fonte, segmentos=len(segs), palavras=sum(len(s["texto"].split()) for s in segs),
               status="ok" if segs else "⛔ sem legendas (tente --whisper)")
    interno = os.environ.get("ODI_INTERNO_DIR")
    if segs and interno:
        d = Path(interno) / "debate"
        d.mkdir(parents=True, exist_ok=True)
        (d / "transcricao.json").write_text(json.dumps({"video": escolhido, "fonte": fonte, "segmentos": segs}, ensure_ascii=False), encoding="utf-8")
    (pasta / "video.json").write_text(json.dumps(man, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"vídeo {escolhido['id']} · {escolhido.get('canal')} · {escolhido.get('titulo')} · {escolhido.get('duracao_s')} s · transcrição: {fonte} · {len(segs)} segmentos")
    return 0 if segs else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
