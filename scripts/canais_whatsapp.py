#!/usr/bin/env python3
"""Seguidores de canais públicos do WhatsApp, lidos na página pública de cada canal (whatsapp.com/channel/<código>).

Pedido do responsável (02/11/2026, 01h38, caso 026 "janonismo"): "acompanhar o crescimento de grupos que surgiram em alguns
países" a partir do "Exército de Lula" de André Janones.
- Universo: o número de seguidores é o que o próprio WhatsApp mostra na página pública do canal (é o total da plataforma, não
  amostra). O WhatsApp pode arredondar (ex.: "161K"): o texto exibido é guardado tal como veio, ao lado do número lido.
- Canais: lista em data/config/casos.json → caso → "canais_whatsapp" (nome, país, link, fonte do link). Só canais públicos.
- Cada execução acrescenta uma leitura por canal em data/casos/<caso>/canais_whatsapp.json (nunca apaga leituras anteriores).
  Falha de leitura vira ⛔ com o motivo, nunca número.
- Leituras publicadas pela imprensa ficam separadas ("segundo_a_imprensa"), com veículo e data, e não se misturam às do Atlas.
Uso: python scripts/canais_whatsapp.py --caso 026
"""
from __future__ import annotations

import datetime as dt
import html
import json
import re
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
UA = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0 Safari/537.36"
MULT = {"": 1, "k": 1_000, "mil": 1_000, "m": 1_000_000, "mi": 1_000_000, "mio": 1_000_000, "b": 1_000_000_000}
RX_SEG = re.compile(r"([\d][\d.,\s  ]*)\s*(k|mil|mi|mio|m|b)?\.?\s*(?:followers|seguidores|abonnés|abonn[eé]s|follower)",
                    re.I)


def numero(txt: str) -> int | None:
    """'161K' → 161000; '1,2 mi' → 1200000; '44.926' → 44926; '10 740 000' → 10740000."""
    m = RX_SEG.search(txt or "")
    if not m:
        return None
    n, suf = m.group(1).strip(), (m.group(2) or "").lower()
    n = re.sub(r"[\s  ]", "", n)
    if suf:
        n = n.replace(",", ".")
        if n.count(".") > 1:
            n = n.replace(".", "")
        try:
            return int(round(float(n) * MULT[suf]))
        except ValueError:
            return None
    digitos = re.sub(r"[.,]", "", n)
    return int(digitos) if digitos.isdigit() else None


def ler_pagina(url: str) -> dict:
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept-Language": "en-US,en;q=0.8"})
    with urllib.request.urlopen(req, timeout=40) as r:
        corpo = r.read().decode("utf-8", errors="replace")
        status = r.status
    meta = {m.group(1).lower(): html.unescape(m.group(2)) for m in
            re.finditer(r'<meta[^>]+(?:property|name)="([^"]+)"[^>]+content="([^"]*)"', corpo)}
    texto = html.unescape(re.sub(r"<[^>]+>", " ", corpo))
    alvo = " ".join(filter(None, [meta.get("og:description"), meta.get("description"), texto]))
    m = RX_SEG.search(alvo)
    return {"http": status, "titulo": meta.get("og:title"), "seguidores_texto": m.group(0).strip() if m else None,
            "seguidores": numero(m.group(0)) if m else None}


def main(argv: list[str]) -> int:
    caso = argv[argv.index("--caso") + 1] if "--caso" in argv else "026"
    cfg = next(c for c in json.loads((ROOT / "data/config/casos.json").read_text(encoding="utf-8"))["casos"] if c["id"] == caso)
    canais = cfg.get("canais_whatsapp") or []
    arq = ROOT / f"data/casos/{caso}/canais_whatsapp.json"
    arq.parent.mkdir(parents=True, exist_ok=True)
    dados = json.loads(arq.read_text(encoding="utf-8")) if arq.exists() else {"leituras": []}
    agora = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    dados.update({"metodo": " ".join(__doc__.split("Uso:")[0].split()), "canais": canais,
                  "segundo_a_imprensa": cfg.get("canais_whatsapp_imprensa") or [], "pendentes": cfg.get("canais_whatsapp_pendentes") or [],
                  "atualizado_em_utc": agora})
    # 02/11/2026: canais que o painel WhatsApp do Atlas já lia (data/whatsapp, desde 15/10) trazem a série anterior,
    # com a fonte; o painel guarda o texto que a página mostrava ("10 mi seguidores")
    hist = {}
    for nome_arq in ("seguidores.csv", "seguidores_horario.csv"):
        p = ROOT / "data/whatsapp" / nome_arq
        if p.exists():
            import csv
            for r in csv.DictReader(open(p, encoding="utf-8"), delimiter=";"):
                hist.setdefault(r["canal_id"], {})[r.get("coletado_em_utc") or r["data"]] = {
                    "lido_em_utc": r.get("coletado_em_utc") or (r["data"] + "T12:00:00Z"), "seguidores": int(r["seguidores"]) if r["seguidores"].isdigit() else None,
                    "seguidores_texto": r.get("texto_original"), "fonte": f"painel WhatsApp do Atlas (data/whatsapp/{nome_arq})"}
    dados["historico_painel"] = {c["nome"]: sorted(hist[c["link"].rstrip("/").rsplit("/", 1)[-1]].values(), key=lambda x: x["lido_em_utc"])
                                 for c in canais if c["link"].rstrip("/").rsplit("/", 1)[-1] in hist}
    falhas = 0
    for c in canais:
        reg = {"lido_em_utc": agora, "canal": c["nome"], "link": c["link"]}
        try:
            reg.update(ler_pagina(c["link"]))
            if reg.get("seguidores") is None:
                reg["situacao"] = "⛔ a página não mostrou o número de seguidores"
                falhas += 1
        except Exception as e:  # noqa: BLE001
            reg["situacao"] = f"⛔ falha ao ler: {type(e).__name__} {getattr(e, 'code', '')}".strip()
            falhas += 1
        dados["leituras"].append(reg)
        print(c["nome"], "→", reg.get("seguidores_texto") or reg.get("situacao"))
    arq.write_text(json.dumps(dados, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(f"{len(canais) - falhas}/{len(canais)} canais lidos")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
