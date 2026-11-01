#!/usr/bin/env python3
"""Transcrição da fala do vídeo de um post de caso, com marcação de tempo (grátis, no runner do GitHub).

Pedido do responsável (01/11/2026, 17h23, caso 024): "quero a transcrição desse vídeo do Flávio, como fizemos no caso do Nikolas
no Nordeste". No caso 009 as falas vieram das legendas queimadas no vídeo (o Instagram tinha silenciado o áudio); aqui o áudio existe,
então a transcrição é automática: faster-whisper (modelo "medium", português, CPU, filtro de voz), sem edição do texto.
A coleta paga já feita (apify/instagram-reel-scraper) não trouxe transcrição: a etapa paga cobre até ~6 min e a live tem ~17 min.

Entrada: ODI_INTERNO_DIR/casos/<caso>/midia/video.mp4 (baixado por arquivar_midia_caso.py a partir do link do CDN registrado na coleta).
Saída privada: casos/<caso>/midia/audio.m4a (o vídeo inteiro passa de 100 MB e não vai para o git), transcricao.srt e transcricao.json.
Saída pública: data/casos/<caso>/transcricao.json — o autor é figura pública (perfil com milhões de seguidores); trechos com tempo,
modelo, revisão, duração, idioma detectado e aviso de que é transcrição automática (pode errar nomes e palavras).
Uso: python scripts/transcrever_midia_caso.py --caso 024 [--modelo medium]
"""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from net import now_utc  # noqa: E402


def hms(s: float) -> str:
    s = int(round(s))
    return f"{s // 3600}:{s % 3600 // 60:02d}:{s % 60:02d}" if s >= 3600 else f"{s // 60}:{s % 60:02d}"


def srt_t(s: float) -> str:
    ms = int(round(s * 1000))
    return f"{ms // 3600000:02d}:{ms % 3600000 // 60000:02d}:{ms % 60000 // 1000:02d},{ms % 1000:03d}"


def main(argv=None) -> int:
    argv = sys.argv[1:] if argv is None else list(argv)
    caso = argv[argv.index("--caso") + 1]
    modelo = argv[argv.index("--modelo") + 1] if "--modelo" in argv else "medium"
    interno = os.environ.get("ODI_INTERNO_DIR")
    if not interno:
        print("⛔ ODI_INTERNO_DIR ausente")
        return 1
    m = Path(interno) / "casos" / caso / "midia"
    video = m / "video.mp4"
    if not video.exists():
        print("⛔ vídeo não encontrado (rode arquivar_midia_caso.py antes)")
        return 1
    audio = m / "audio.m4a"
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(video), "-vn", "-ac", "1", "-c:a", "aac", "-b:a", "64k", str(audio)], check=True)
    from faster_whisper import WhisperModel
    import faster_whisper
    wm = WhisperModel(modelo, device="cpu", compute_type="int8", cpu_threads=os.cpu_count() or 2)
    # áudio decodificado pelo ffmpeg (16 kHz, mono, float32): evita o PyAV, cuja versão nova recusa um parâmetro do faster-whisper 1.1.1 (01/11/2026)
    import numpy as np
    pcm = subprocess.run(["ffmpeg", "-loglevel", "error", "-i", str(audio), "-f", "f32le", "-ac", "1", "-ar", "16000", "-"], check=True, capture_output=True).stdout
    segs, info = wm.transcribe(np.frombuffer(pcm, dtype=np.float32), language="pt", vad_filter=True, beam_size=5, condition_on_previous_text=True)
    trechos = [{"inicio": round(s.start, 2), "fim": round(s.end, 2), "tempo": hms(s.start), "texto": s.text.strip()} for s in segs]
    with open(m / "transcricao.srt", "w", encoding="utf-8") as f:
        for i, t in enumerate(trechos, 1):
            f.write(f"{i}\n{srt_t(t['inicio'])} --> {srt_t(t['fim'])}\n{t['texto']}\n\n")
    out = {"caso": caso, "gerado_em_utc": now_utc(), "modelo": f"faster-whisper {faster_whisper.__version__}, modelo {modelo} (int8, CPU), português, filtro de voz",
           "duracao_s": round(info.duration, 1), "duracao": hms(info.duration), "fala_s": round(sum(t["fim"] - t["inicio"] for t in trechos), 1),
           "audio_sha256": hashlib.sha256(audio.read_bytes()).hexdigest(), "video_sha256": hashlib.sha256(video.read_bytes()).hexdigest(),
           "palavras": sum(len(t["texto"].split()) for t in trechos), "trechos": trechos,
           "aviso": "Transcrição automática, sem edição: pode errar nomes próprios, números e palavras ditas rápido. Para citar, confira no vídeo pelo tempo indicado."}
    (m / "transcricao.json").write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    pub = Path("data/casos") / caso
    pub.mkdir(parents=True, exist_ok=True)
    (pub / "transcricao.json").write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"caso {caso}: transcrição de {out['duracao']} ({out['palavras']} palavras, {len(trechos)} trechos) com {out['modelo']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
