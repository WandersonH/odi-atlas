#!/usr/bin/env python3
"""Variação de seguidores entre a coleta mais recente e a anterior, por conta (página "Quem acompanha").

Entradas: data/seguidores/coleta_AAAA-MM-DD.csv (Instagram/Facebook, Apify) e data/seguidores/youtube_AAAA-MM-DD.csv
(YouTube Data API) — um arquivo por dia de coleta. Chave da conta: candidate_id + endereço normalizado, igual ao da página.
Compara o último dia com o dia de coleta imediatamente anterior (normalmente ontem; se a coleta de ontem falhou, o último
dia disponível — a saída diz qual). Saída: data/seguidores/variacao.json
"""
from __future__ import annotations

import csv
import json
import re
import sys
from pathlib import Path
from urllib.parse import unquote, urlparse

sys.path.insert(0, str(Path(__file__).resolve().parent))
from net import now_utc  # noqa: E402


def chave_url(raw: str) -> str:
    """Mesma normalização de bnUrlForMatch na página: host sem www | caminho decodificado, sem barra final, minúsculo."""
    s = (raw or "").strip()
    try:
        u = urlparse(s if re.match(r"^[a-z][a-z0-9+.-]*://", s, re.I) else "https://" + s)
        host = (u.hostname or "").lower().removeprefix("www.")
        return host + "|" + unquote(u.path).rstrip("/").lower()
    except ValueError:
        return s.split("?")[0].rstrip("/").lower()


def series(pasta: Path) -> dict[str, dict[str, int]]:
    out: dict[str, dict[str, int]] = {}
    for p in sorted(pasta.glob("*.csv")):
        m = re.fullmatch(r"(?:coleta|youtube|kwai|x|tiktok)_(\d{4}-\d{2}-\d{2})\.csv", p.name)
        if not m:
            continue
        for r in csv.DictReader(open(p, encoding="utf-8"), delimiter=";"):
            try:
                n = int(float(r.get("followers") or ""))
            except ValueError:
                continue
            if r.get("candidate_id") and r.get("url"):
                out.setdefault(f"{r['candidate_id']}|{chave_url(r['url'])}", {})[m.group(1)] = n
    return out


def variacoes(ser: dict[str, dict[str, int]]) -> dict[str, dict]:
    out = {}
    for k, s in ser.items():
        datas = sorted(s)
        if len(datas) < 2:
            continue
        d1, d0 = datas[-1], datas[-2]
        a, b = s[d1], s[d0]
        out[k] = {"atual": a, "data_atual": d1, "anterior": b, "data_anterior": d0, "diferenca": a - b,
                  "variacao_pct": round((a - b) / b * 100, 2) if b > 0 else None}
    return out


def main(argv=None) -> int:
    root = Path(argv[0]) if argv else Path(".")
    pasta = root / "data/seguidores"
    v = variacoes(series(pasta))
    out = {"schema_version": 1, "gerado_em_utc": now_utc(),
           "metodo": "Variação = (coleta mais recente − coleta anterior) ÷ coleta anterior. A anterior é o dia de coleta imediatamente anterior (normalmente ontem); a data comparada aparece em cada conta. Contagens arredondadas pela plataforma (ex.: 90 mil) podem mostrar 0% mesmo com variação real.",
           "itens": v}
    (pasta / "variacao.json").write_text(json.dumps(out, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(f"variação de seguidores: {len(v)} contas com duas coletas")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
