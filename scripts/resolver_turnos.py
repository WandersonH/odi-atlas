"""Converte a codificação manual dos turnos (privado: debate/turnos_codificacao.tsv) em data/config/debate_turnos.json.

Cada linha do TSV: tempo aproximado (s) · orador · âncora opcional (começo da fala). Com âncora, o turno começa no
trecho da legenda onde a âncora aparece (procurada a partir de ~40 s antes do tempo informado). O público recebe só
tempos e oradores; as âncoras (texto da transmissão) ficam no privado.
Uso: ODI_INTERNO_DIR=… python scripts/resolver_turnos.py
"""
from __future__ import annotations

import json
import os
import re
import sys
import unicodedata
from pathlib import Path

ORADORES = {"lula", "flavio", "mediacao", "intervalo", "indefinido"}


def norm(s: str) -> str:
    s = "".join(c for c in unicodedata.normalize("NFD", s.lower()) if unicodedata.category(c) != "Mn")
    return re.sub(r"[^a-z0-9 ]+", " ", s)


def ler_tsv(texto: str) -> list[tuple[float, str, str | None]]:
    out = []
    for l in texto.splitlines():
        if not l.strip() or l.startswith("#"):
            continue
        p = l.split("\t")
        out.append((float(p[0]), p[1].strip(), p[2].strip() if len(p) > 2 and p[2].strip() else None))
    return out


def resolver(linhas, segs) -> tuple[dict, list[str]]:
    # texto corrido normalizado com o índice do trecho de cada posição
    pos, partes, total = [], [], 0
    for i, s in enumerate(segs):
        t = " " + " ".join(norm(s["texto"]).split())
        partes.append(t)
        pos.append(total)
        total += len(t)
    corrido = "".join(partes)
    turnos, erros = {}, []
    for t, orador, ancora in linhas:
        if orador not in ORADORES:
            erros.append(f"{t}: orador desconhecido {orador}")
            continue
        ini = t
        if ancora:
            a = " " + " ".join(norm(ancora).split())
            k0 = next((i for i, s in enumerate(segs) if s["ini"] >= t - 40), 0)
            j = corrido.find(a, pos[k0])
            if j < 0 or segs[max(i for i, p in enumerate(pos) if p <= j)]["ini"] > t + 120:
                erros.append(f"{t}: âncora não encontrada ({ancora[:30]})")
                continue
            ini = segs[max(i for i, p in enumerate(pos) if p <= j)]["ini"]
        turnos[f"{ini:.2f}"] = orador
    return dict(sorted(turnos.items(), key=lambda kv: float(kv[0]))), erros


def main() -> int:
    interno = Path(os.environ["ODI_INTERNO_DIR"])
    segs = json.loads((interno / "debate/transcricao.json").read_text(encoding="utf-8"))["segmentos"]
    linhas = ler_tsv((interno / "debate/turnos_codificacao.tsv").read_text(encoding="utf-8"))
    turnos, erros = resolver(linhas, segs)
    for e in erros:
        print("⛔", e)
    out = {"metodo": "codificação manual dos turnos sobre a legenda automática da íntegra; assistida por IA (Claude) em 19/10/2026; não validada por pessoa da equipe",
           "unidade": "trecho da legenda (2 a 5 s); uma fala que começa no meio de um trecho entra a partir desse trecho",
           "turnos": turnos}
    Path("data/config/debate_turnos.json").write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"{len(turnos)} turnos · {len(erros)} erros")
    return 1 if erros else 0


if __name__ == "__main__":
    raise SystemExit(main())
