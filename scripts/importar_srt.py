"""Importa uma legenda .srt do debate (arquivo enviado pelo usuário) para a transcrição privada.

Grava ODI_INTERNO_DIR/debate/transcricao.json no mesmo formato do collect_debate_video.py e guarda o .srt original
ao lado (debate/<nome>.srt). O texto integral fica só no privado; o público recebe só análises e trechos curtos.
Uso: ODI_INTERNO_DIR=… python scripts/importar_srt.py arquivo.srt "descrição da fonte" ["título do vídeo"]
"""
from __future__ import annotations

import json
import os
import re
import shutil
import sys
from pathlib import Path


def tempo(x: str) -> float:
    h, m, s = x.strip().replace(",", ".").split(":")
    return int(h) * 3600 + int(m) * 60 + float(s)


def ler_srt(texto: str) -> list[dict]:
    out = []
    for bloco in re.split(r"\n\s*\n", texto.replace("\r\n", "\n").strip()):
        linhas = bloco.strip().split("\n")
        i = next((k for k, l in enumerate(linhas) if "-->" in l), None)
        if i is None:
            continue
        a, z = linhas[i].split("-->")
        t = " ".join(" ".join(linhas[i + 1:]).split())
        if t:
            out.append({"ini": round(tempo(a), 2), "fim": round(tempo(z), 2), "texto": t})
    return out


def main(argv=None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    arq, fonte = Path(argv[0]), argv[1]
    titulo = argv[2] if len(argv) > 2 else None
    interno = os.environ.get("ODI_INTERNO_DIR")
    if not interno:
        print("⛔ defina ODI_INTERNO_DIR (repositório privado)")
        return 1
    segs = ler_srt(arq.read_text(encoding="utf-8-sig"))
    d = Path(interno) / "debate"
    d.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(arq, d / "integra_legenda_youtube_auto.srt")
    video = {"id": None, "titulo": titulo, "arquivo": "debate/integra_legenda_youtube_auto.srt", "duracao_s": segs[-1]["fim"] if segs else None}
    (d / "transcricao.json").write_text(json.dumps({"video": video, "fonte": fonte, "segmentos": segs}, ensure_ascii=False), encoding="utf-8")
    print(f"{len(segs)} trechos · {sum(len(s['texto'].split()) for s in segs)} palavras · {segs[-1]['fim'] / 60:.1f} min")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
