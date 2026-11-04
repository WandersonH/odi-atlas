#!/usr/bin/env python3
"""Transcrição de debate publicada em PDF com o nome de quem fala (ex.: Poder360, debate da Globo de 23/10/2026).

Pedido do responsável (04/11/2026, 00h06): "transcrição debate", com o link do PDF do Poder360.
Entrada (privado): o PDF baixado por `baixar-privado.yml` (ex.: ODI_INTERNO_DIR/debate/globo/transcricao_poder360_23out2026.pdf).
- Texto extraído com `pdftotext` (poppler); cabeçalho, rodapé e número de página do Poder360 são retirados.
- Quem fala: o rótulo em maiúsculas da própria transcrição ("CÉSAR TRALLI:", "FLÁVIO BOLSONARO:",
  "LUIZ INÁCIO LULA DA SILVA:" ou "LULA:"). Não é atribuição automática: vem do texto publicado.
- Blocos: começa um novo bloco a cada fala da mediação com "Estamos de volta" (volta do intervalo).
- O PDF não traz horário das falas: "ini"/"fim" são a posição em palavras desde o início, não segundos ("sem_tempo").
Saída (privado): ODI_INTERNO_DIR/debate/<debate>/transcricao.json no formato de collect_debate_video.py, com "orador" e "bloco".
Uso: ODI_INTERNO_DIR=... python scripts/importar_transcricao_pdf.py --debate globo --pdf debate/globo/transcricao_poder360_23out2026.pdf \
        --fonte "..." --url "..."
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from pathlib import Path

ROTULOS = {"LUIZ INÁCIO LULA DA SILVA": "lula", "LULA": "lula", "FLÁVIO BOLSONARO": "flavio", "CÉSAR TRALLI": "mediacao"}
RX_ROTULO = re.compile(r"^(" + "|".join(sorted(map(re.escape, ROTULOS), key=len, reverse=True)) + r"):\s*")
RX_LIXO = re.compile(r"^(\d{1,3}|Poder360 – www\.poder360\.com\.br|\[transcrição – .*\])$")


def linhas_pdf(pdf: Path) -> list[str]:
    txt = subprocess.run(["pdftotext", str(pdf), "-"], check=True, capture_output=True, text=True).stdout
    return [l.strip() for l in txt.replace("\f", "\n").splitlines() if l.strip() and not RX_LIXO.match(l.strip())]


def falas(linhas: list[str]) -> list[dict]:
    out, bloco = [], 1
    for l in linhas:
        if l == "[INTERVALO]":
            continue
        m = RX_ROTULO.match(l)
        if m:
            orador = ROTULOS[m.group(1)]
            resto = l[m.end():]
            if orador == "mediacao" and "Estamos de volta" in resto[:120]:
                bloco += 1
            out.append({"orador": orador, "rotulo": m.group(1), "bloco": bloco, "texto": resto})
        elif out:
            out[-1]["texto"] += " " + l
        else:
            out.append({"orador": "mediacao", "rotulo": None, "bloco": bloco, "texto": l})
    pos = 0
    for f in out:
        f["texto"] = re.sub(r"\s+", " ", f["texto"]).strip()
        n = len(f["texto"].split())
        f["ini"], f["fim"] = pos, pos + n
        pos += n
    return out


def main(argv: list[str]) -> int:
    interno = os.environ.get("ODI_INTERNO_DIR")
    if not interno:
        print("⛔ ODI_INTERNO_DIR não definido")
        return 1
    arg = lambda k, d=None: argv[argv.index(k) + 1] if k in argv else d  # noqa: E731
    debate, pdf = arg("--debate", "globo"), Path(interno) / arg("--pdf")
    segs = falas(linhas_pdf(pdf))
    destino = Path(interno) / "debate" / debate / "transcricao.json"
    tr = {"video": {"id": None, "titulo": arg("--titulo"), "arquivo": str(pdf.relative_to(interno)), "url": arg("--url")},
          "fonte": arg("--fonte"), "sem_tempo": True, "unidade_posicao": "palavras desde o início da transcrição",
          "segmentos": segs}
    destino.write_text(json.dumps(tr, ensure_ascii=False), encoding="utf-8")
    por = {}
    for s in segs:
        por.setdefault(s["orador"], [0, 0])
        por[s["orador"]][0] += 1
        por[s["orador"]][1] += s["fim"] - s["ini"]
    print(f"{debate}: {len(segs)} falas · blocos {max(s['bloco'] for s in segs)} · falas/palavras por orador {por}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
