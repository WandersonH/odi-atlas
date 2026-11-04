#!/usr/bin/env python3
"""Transcrição completa de um vídeo do YouTube, para um caso (texto integral só no repositório privado).

Pedido do responsável (04/11/2026, 00h23, caso 034): "quero transcrição completa" do vídeo
https://www.youtube.com/watch?v=SvVd0Nu2XpQ (sessão do TSE sobre o vídeo de Jair Bolsonaro feito com IA na convenção do PL).
Ordem das tentativas (as mesmas funções do debate, collect_debate_video.py):
1. legendas do YouTube por yt-dlp (manuais; senão automáticas em português) e o endpoint público timedtext — grátis;
2. `--apify`: legendas pela Apify (seemuapps/youtube-transcript-scraper, conta 1), só com autorização e teto de US$ 0,05;
3. `--whisper`: áudio por yt-dlp e faster-whisper (CPU) — grátis, mas o YouTube costuma recusar o download no runner.
Metadados (título, canal, data, duração) pela YouTube Data API (YOUTUBE_API_KEY).
Saídas: privado ODI_INTERNO_DIR/casos/<caso>/transcricoes/<video>.json (segmentos com tempo) e .txt (texto corrido com
marcas de tempo a cada ~minuto); público data/casos/<caso>/transcricoes.json (só metadados, fonte, nº de palavras, situação).
Falha vira ⛔ com o diagnóstico, nunca texto inventado.
Uso: ODI_INTERNO_DIR=... python scripts/transcrever_video.py --caso 034 --video SvVd0Nu2XpQ [--apify] [--whisper]
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
import urllib.parse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import collect_debate_video as cdv  # noqa: E402
from net import get_json, now_utc  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]


def metadados(vid: str) -> dict:
    key = os.environ.get("YOUTUBE_API_KEY", "").strip()
    if not key:
        return {"id": vid, "erro": "YOUTUBE_API_KEY ausente"}
    p = {"part": "snippet,contentDetails,statistics", "id": vid, "key": key}
    try:
        it = (get_json(f"{cdv.API}/videos?{urllib.parse.urlencode(p)}").get("items") or [None])[0]
    except Exception as e:  # noqa: BLE001
        return {"id": vid, "erro": f"{type(e).__name__} {getattr(e, 'code', '')}"}
    if not it:
        return {"id": vid, "erro": "vídeo não encontrado pela API"}
    sn, st = it["snippet"], it.get("statistics") or {}
    return {"id": vid, "titulo": sn.get("title"), "canal": sn.get("channelTitle"), "canal_id": sn.get("channelId"),
            "publicado_em": sn.get("publishedAt"), "duracao_s": cdv.dur_s(it["contentDetails"].get("duration")),
            "visualizacoes": int(st["viewCount"]) if st.get("viewCount") else None, "lido_em_utc": now_utc()}


def texto_corrido(segs: list[dict]) -> str:
    linhas, marca = [], -60.0
    for s in segs:
        if s["ini"] - marca >= 60:
            marca = s["ini"]
            h, r = divmod(int(s["ini"]), 3600)
            linhas.append(f"\n[{h:d}:{r // 60:02d}:{r % 60:02d}] ")
        linhas.append(s["texto"] + " ")
    return "".join(linhas).strip() + "\n"


def main(argv: list[str]) -> int:
    arg = lambda k, d=None: argv[argv.index(k) + 1] if k in argv else d  # noqa: E731
    caso, vid = arg("--caso"), arg("--video")
    interno = os.environ.get("ODI_INTERNO_DIR")
    if not (caso and vid and interno):
        print("⛔ uso: --caso ID --video ID, com ODI_INTERNO_DIR")
        return 1
    meta = metadados(vid)
    segs, fonte = [], None
    with tempfile.TemporaryDirectory() as t:
        segs, fonte = cdv.legendas(vid, Path(t))
        if not segs and "--apify" in argv:
            r = cdv.apify_legendas([vid]).get(vid)
            if r:
                segs, fonte = r
        if not segs and "--whisper" in argv:
            segs, fonte = cdv.whisper(vid, Path(t))
    pub = ROOT / "data/casos" / caso / "transcricoes.json"
    pub.parent.mkdir(parents=True, exist_ok=True)
    reg = json.loads(pub.read_text(encoding="utf-8")) if pub.exists() else {"videos": {}}
    ent = {**meta, "tentado_em_utc": now_utc(), "fonte": fonte, "segmentos": len(segs),
           "palavras": sum(len(s["texto"].split()) for s in segs), "diagnostico": [e for e in cdv.ERROS if e.split(": ", 1)[-1]][-12:]}
    if segs:
        priv = Path(interno) / "casos" / caso / "transcricoes"
        priv.mkdir(parents=True, exist_ok=True)
        (priv / f"{vid}.json").write_text(json.dumps({"video": meta, "fonte": fonte, "segmentos": segs}, ensure_ascii=False), encoding="utf-8")
        (priv / f"{vid}.txt").write_text(f"{meta.get('titulo')} · {meta.get('canal')} · https://www.youtube.com/watch?v={vid}\nFonte: {fonte}\n\n" + texto_corrido(segs), encoding="utf-8")
        ent.update(situacao="transcrita", privado=f"casos/{caso}/transcricoes/{vid}.txt", fim_s=segs[-1]["fim"])
    else:
        anterior = (reg["videos"].get(vid) or {})
        if anterior.get("situacao") == "transcrita":  # nunca troca uma transcrição boa por uma falha
            ent = {**anterior, "ultima_falha_utc": now_utc(), "ultima_falha_diagnostico": ent["diagnostico"]}
        else:
            ent["situacao"] = "⛔ sem transcrição: o YouTube não entregou legendas nem áudio ao coletor"
    reg["videos"][vid] = ent
    reg["atualizado_em_utc"] = now_utc()
    pub.write_text(json.dumps(reg, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(f"{vid} · {meta.get('titulo')} · {meta.get('duracao_s')} s · {ent.get('situacao')} · {fonte} · {ent['segmentos']} segmentos · {ent['palavras']} palavras")
    for e in ent.get("diagnostico") or []:
        print("diag:", e[:300])
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
