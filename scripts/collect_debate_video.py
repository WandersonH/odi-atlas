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


def legendas(vid: str, pasta: Path) -> tuple[list[dict], str | None]:
    base = ["yt-dlp", "--skip-download", "--sub-format", "vtt", "-o", str(pasta / "%(id)s.%(ext)s"), f"https://www.youtube.com/watch?v={vid}"]
    for modo, args in (("manual", ["--write-subs", "--sub-langs", "pt.*,pt"]), ("automática", ["--write-auto-subs", "--sub-langs", "pt-orig,pt"])):
        subprocess.run(base[:1] + args + base[1:], capture_output=True, text=True, timeout=600)
        arqs = sorted(glob.glob(str(pasta / f"{vid}*.vtt")))
        if arqs:
            return vtt_segmentos(Path(arqs[0]).read_text(encoding="utf-8")), f"legenda {modo} do YouTube ({Path(arqs[0]).name.split('.')[-2]})"
    return [], None


def whisper(vid: str, pasta: Path) -> tuple[list[dict], str | None]:
    r = subprocess.run(["yt-dlp", "-f", "bestaudio", "-x", "--audio-format", "mp3", "--audio-quality", "9", "-o", str(pasta / "audio.%(ext)s"),
                        f"https://www.youtube.com/watch?v={vid}"], capture_output=True, text=True, timeout=3600)
    arq = next(iter(glob.glob(str(pasta / "audio.*"))), None)
    if not arq:
        return [], None
    from faster_whisper import WhisperModel
    m = WhisperModel("small", device="cpu", compute_type="int8")
    segs, info = m.transcribe(arq, language="pt", vad_filter=True, beam_size=1)
    out = [{"ini": round(s.start, 2), "fim": round(s.end, 2), "texto": s.text.strip()} for s in segs]
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
    with tempfile.TemporaryDirectory() as t:
        segs, fonte = legendas(escolhido["id"], Path(t))
        if not segs and "--whisper" in argv:
            segs, fonte = whisper(escolhido["id"], Path(t))
    man.update(transcricao_fonte=fonte, segmentos=len(segs), palavras=sum(len(s["texto"].split()) for s in segs),
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
