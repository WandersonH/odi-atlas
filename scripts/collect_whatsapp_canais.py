#!/usr/bin/env python3
"""Seguidores dos canais de WhatsApp declarados ao TSE (presidente e vice), pela página pública do canal (sem login).

A página https://whatsapp.com/channel/<id> mostra o nome do canal e "N seguidores/followers" nas metatags.
Só dados públicos do canal (nome e contagem); nenhuma mensagem, nenhum dado de pessoa.
Saída: data/seguidores/whatsapp_latest.csv e whatsapp_AAAA-MM-DD.csv (mesmas colunas dos demais) e
data/seguidores/whatsapp_manifesto_latest.json (o que foi pedido e o que a página devolveu).
"""
from __future__ import annotations

import csv
import gzip
import html
import json
import re
import sys
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from net import now_utc  # noqa: E402

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0 Safari/537.36"
COLS = ["candidate_id", "candidate_name", "platform", "url", "followers", "captured_at", "source_url"]
MULT = {"": 1, "mil": 1_000, "k": 1_000, "mi": 1_000_000, "m": 1_000_000, "milhão": 1_000_000, "milhões": 1_000_000, "mil milhões": 1_000_000_000}


def canais(root: Path) -> list[dict]:
    out = []
    for r in csv.DictReader(gzip.open(root / "data/tse/redes_sociais_candidatos_2026.csv.gz", "rt", encoding="utf-8"), delimiter=";"):
        if r.get("PLATAFORMA") != "whatsapp" or r.get("DS_CARGO", "").upper() not in ("PRESIDENTE", "VICE-PRESIDENTE"):
            continue
        m = re.search(r"whatsapp\.com/channel/([A-Za-z0-9]+)", r["DS_URL"], re.I)
        out.append({"candidate_id": r["SQ_CANDIDATO"], "declarado_por": r.get("NM_URNA_CANDIDATO", ""), "url_tse": r["DS_URL"].strip(),
                    "canal": m.group(1) if m else None})
    return out


def numero(txt: str) -> int | None:
    """'1,2 mi seguidores', '1.2M followers', '35.401 seguidores', '12K followers' -> inteiro."""
    t = html.unescape(txt)
    m = re.search(r"([\d][\d.,  ]*)\s*(mil milhões|milhões|milhão|mil|mi|[kKmM])?\s*(?:seguidores|followers)", t)
    if not m:
        return None
    n, suf = m.group(1).strip().replace(" ", "").replace(" ", ""), (m.group(2) or "").lower()
    if suf:
        n = n.replace(",", ".")
        if n.count(".") > 1:
            n = n.replace(".", "")
        return int(round(float(n) * MULT[suf]))
    return int(re.sub(r"[.,]", "", n))


def ler_pagina(url: str) -> tuple[int, str]:
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept-Language": "pt-BR,pt;q=0.9,en;q=0.8"})
    with urllib.request.urlopen(req, timeout=30) as r:  # noqa: S310 — URL fixa do whatsapp.com
        return r.status, r.read().decode("utf-8", "replace")


def extrair(pag: str) -> dict:
    meta = {}
    for prop in ("og:title", "og:description", "description"):
        m = re.search(rf'<meta[^>]+(?:property|name)="{prop}"[^>]+content="([^"]*)"', pag) or \
            re.search(rf'<meta[^>]+content="([^"]*)"[^>]+(?:property|name)="{prop}"', pag)
        if m:
            meta[prop] = html.unescape(m.group(1))
    corpo = re.sub(r"<[^>]+>", " ", pag)
    n = next((numero(v) for v in [meta.get("og:description", ""), meta.get("description", ""), corpo] if numero(v) is not None), None)
    return {"nome": meta.get("og:title"), "descricao": (meta.get("og:description") or "")[:160], "seguidores": n}


def main(argv=None, baixar=None) -> int:
    root = Path(".")
    agora = now_utc()
    baixar = baixar or ler_pagina
    man = {"run_started_utc": agora, "fonte": "página pública do canal (whatsapp.com/channel), sem login", "canais": []}
    linhas = []
    for c in canais(root):
        reg = {"declarado_por": c["declarado_por"], "url_tse": c["url_tse"], "canal": c["canal"]}
        if not c["canal"]:
            reg["erro"] = "endereço declarado não é de canal (link de grupo/conversa): não coletado"
        else:
            # o id do canal diferencia maiúsculas; o TSE às vezes grava tudo em maiúsculas — tenta como veio
            try:
                st, pag = baixar(f"https://whatsapp.com/channel/{c['canal']}")
                reg.update(http=st, **extrair(pag))
            except Exception as e:  # noqa: BLE001
                reg["erro"] = f"{type(e).__name__} {getattr(e, 'code', '')}".strip()
        man["canais"].append(reg)
        print(f"{c['declarado_por']} · {c['url_tse']}: {reg.get('seguidores') if reg.get('seguidores') is not None else '⛔ ' + (reg.get('erro') or 'sem número na página')} · {reg.get('nome') or ''}")
        if reg.get("seguidores") is not None:
            linhas.append({"candidate_id": c["candidate_id"], "candidate_name": c["declarado_por"], "platform": "WhatsApp", "url": c["url_tse"],
                           "followers": reg["seguidores"], "captured_at": agora[:10], "source_url": f"https://whatsapp.com/channel/{c['canal']}"})
    seg = root / "data/seguidores"
    seg.mkdir(parents=True, exist_ok=True)
    if linhas:
        for nome in (f"whatsapp_{agora[:10]}.csv", "whatsapp_latest.csv"):
            with open(seg / nome, "w", encoding="utf-8", newline="") as f:
                w = csv.DictWriter(f, COLS, delimiter=";", lineterminator="\n")
                w.writeheader()
                w.writerows(linhas)
    man["status"] = f"ok · {len(linhas)} de {len(man['canais'])} endereços com número" if linhas else "⛔ nenhum número lido"
    (seg / "whatsapp_manifesto_latest.json").write_text(json.dumps(man, ensure_ascii=False, indent=1), encoding="utf-8")
    print(man["status"])
    return 0 if linhas else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
