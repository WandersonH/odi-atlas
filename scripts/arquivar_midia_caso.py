#!/usr/bin/env python3
"""Guarda no repositório privado a mídia de um post de caso (vídeo, capa, áudio) a partir dos links do CDN que a coleta já
registrou (ODI_INTERNO_DIR/casos/<id>/apify/*.json → items[].videoUrl/displayUrl/audioUrl). Não faz nova coleta paga.

Pedido do responsável (23/10/2026, 17h15): "tu não baixou o post das camisetas, agora ele saiu do ar". Os links assinados do
Instagram valem alguns dias (parâmetro oe); o CDN pode continuar servindo depois de o post sair do ar. Cada arquivo fica com
sha256, tamanho, link de origem e horário em casos/<id>/midia/manifesto.json.
"""
from __future__ import annotations

import hashlib
import json
import os
import sys
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from net import now_utc  # noqa: E402

CAMPOS = {"videoUrl": "video.mp4", "displayUrl": "capa.jpg", "audioUrl": "audio.mp4"}
UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36"


def links(pasta: Path) -> list[tuple[str, str, str]]:
    out = []
    for f in sorted((pasta / "apify").glob("*.json")):
        try:
            d = json.loads(f.read_text(encoding="utf-8"))
        except ValueError:
            continue
        for it in (d.get("items") or []) if isinstance(d, dict) else []:
            for k, nome in CAMPOS.items():
                if it.get(k):
                    out.append((nome, it[k], f.name))
            for i, img in enumerate(it.get("images") or []):
                out.append((f"imagem_{i + 1}.jpg", img, f.name))
    return out


def main(argv=None) -> int:
    argv = sys.argv[1:] if argv is None else list(argv)
    caso = argv[argv.index("--caso") + 1] if "--caso" in argv else None
    interno = os.environ.get("ODI_INTERNO_DIR")
    if not (caso and interno):
        print("⛔ informe --caso e ODI_INTERNO_DIR")
        return 1
    pasta = Path(interno) / "casos" / caso
    dest = pasta / "midia"
    dest.mkdir(parents=True, exist_ok=True)
    man = {"caso": caso, "baixado_em_utc": now_utc(), "arquivos": []}
    vistos = set()
    for nome, url, origem in links(pasta):
        if nome in vistos:
            continue
        reg = {"arquivo": nome, "origem_coleta": origem, "url": url}
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": UA}), timeout=60) as r:
                dados = r.read()
            if len(dados) < 1000:
                raise ValueError(f"resposta pequena demais ({len(dados)} bytes)")
            (dest / nome).write_bytes(dados)
            reg.update(status="ok", bytes=len(dados), sha256=hashlib.sha256(dados).hexdigest())
            vistos.add(nome)
        except Exception as e:  # noqa: BLE001
            reg.update(status=f"⛔ {type(e).__name__}: {str(e)[:150]}")
        man["arquivos"].append(reg)
        print(f"{nome}: {reg['status']}{' · ' + str(reg.get('bytes')) + ' bytes' if reg.get('bytes') else ''}")
    (dest / "manifesto.json").write_text(json.dumps(man, ensure_ascii=False, indent=1), encoding="utf-8")
    ok = sum(1 for a in man["arquivos"] if a["status"] == "ok")
    print(f"caso {caso}: {ok} arquivo(s) guardado(s) no privado")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
