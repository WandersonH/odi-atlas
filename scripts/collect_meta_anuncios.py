#!/usr/bin/env python3
"""Biblioteca de Anúncios da Meta (API oficial ads_archive) — anúncios políticos no Brasil que citam cada candidato.

Token SOMENTE pela variável de ambiente META_AD_LIBRARY_TOKEN (segredo do GitHub). Erros não imprimem a URL (contém o token).
Sem token: grava status ⛔ e sai com 1.
Saídas: data/meta/anuncios.json (agregados públicos) e, com ODI_INTERNO_DIR, meta/anuncios/AAAA-MM-DD.jsonl.gz (bruto, privado).
"""
from __future__ import annotations

import gzip
import json
import os
import sys
import urllib.parse
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from net import now_utc, open_url  # noqa: E402

CAMPOS = ["id", "page_id", "page_name", "bylines", "ad_creation_time", "ad_delivery_start_time", "ad_delivery_stop_time",
          "spend", "impressions", "currency", "publisher_platforms", "delivery_by_region", "demographic_distribution",
          "br_total_reach", "ad_snapshot_url", "ad_creative_bodies", "ad_creative_link_titles", "languages"]


def faixa(d: dict | None) -> tuple[int, int | None]:
    d = d or {}
    lo = int(d.get("lower_bound") or 0)
    up = d.get("upper_bound")
    return lo, (int(up) if up not in (None, "") else None)


def soma(faixas: list[tuple[int, int | None]]) -> dict:
    lo = sum(a for a, _ in faixas)
    abertos = sum(1 for _, b in faixas if b is None)
    return {"min": lo, "max": None if abertos else sum(b for _, b in faixas), "faixas_abertas": abertos}


def fase_de(data: str, fases: list[dict]) -> str | None:
    for f in fases:
        if f["de"] <= (data or "")[:10] <= f["ate"]:
            return f["id"]
    return None


def agregar(ads: list[dict], fases: list[dict]) -> dict:
    por_pag = defaultdict(list)
    for a in ads:
        por_pag[(a.get("page_id"), a.get("page_name"))].append(a)
    paginas = []
    for (pid, nome), xs in por_pag.items():
        g = soma([faixa(a.get("spend")) for a in xs])
        paginas.append({"page_id": pid, "pagina": nome, "anuncios": len(xs), "gasto": g,
                        "impressoes": soma([faixa(a.get("impressions")) for a in xs]),
                        "pagadores": sorted({a.get("bylines") for a in xs if a.get("bylines")})[:3]})
    paginas.sort(key=lambda p: (-p["gasto"]["min"], -p["anuncios"]))
    reg = defaultdict(float)
    for a in ads:
        lo, _ = faixa(a.get("spend"))
        for r in a.get("delivery_by_region") or []:
            reg[r.get("region")] += lo * float(r.get("percentage") or 0)
    plat = defaultdict(int)
    for a in ads:
        for p in a.get("publisher_platforms") or []:
            plat[p] += 1
    return {"anuncios": len(ads), "paginas": len(paginas), "gasto": soma([faixa(a.get("spend")) for a in ads]),
            "impressoes": soma([faixa(a.get("impressions")) for a in ads]),
            "moedas": sorted({a.get("currency") for a in ads if a.get("currency")}),
            "plataformas": dict(sorted(plat.items(), key=lambda x: -x[1])),
            "fases": [{"id": f["id"], "rotulo": f["rotulo"], "de": f["de"], "ate": f["ate"],
                       **(lambda xs: {"anuncios": len(xs), "gasto": soma([faixa(a.get("spend")) for a in xs])})(
                           [a for a in ads if fase_de(a.get("ad_delivery_start_time"), [f])])} for f in fases],
            "regioes_gasto_min_estimado": [{"regiao": k, "gasto_min": round(v)} for k, v in sorted(reg.items(), key=lambda x: -x[1])[:27]],
            "top_paginas": paginas[:25]}


def buscar(token: str, cfg: dict, termo: str) -> tuple[list[dict], int]:
    q = {"search_terms": termo, "ad_type": "POLITICAL_AND_ISSUE_ADS", "ad_reached_countries": json.dumps([cfg["pais"]]),
         "ad_active_status": "ALL", "ad_delivery_date_min": cfg["desde"], "fields": ",".join(CAMPOS), "limit": "250",
         "access_token": token}
    url = f"https://graph.facebook.com/{cfg['versao_api']}/ads_archive?" + urllib.parse.urlencode(q)
    out, paginas = [], 0
    while url and paginas < cfg["max_paginas_por_consulta"]:
        with open_url(url, timeout=120) as r:
            d = json.loads(r.read().decode("utf-8"))
        paginas += 1
        out += d.get("data", [])
        url = (d.get("paging") or {}).get("next")
    return out, paginas


def main(argv=None, buscar_fn=None) -> int:
    root = Path(argv[0]) if argv else Path(".")
    cfg = json.loads((root / "data/config/meta_anuncios.json").read_text(encoding="utf-8"))
    fases = json.loads((root / "data/config/trends.json").read_text(encoding="utf-8")).get("fases", [])
    saida = root / "data/meta/anuncios.json"
    saida.parent.mkdir(parents=True, exist_ok=True)
    out = {"schema_version": 1, "coletado_em_utc": now_utc(), "fonte": f"Meta Ad Library API {cfg['versao_api']} · ads_archive",
           "nota": cfg["nota"], "desde": cfg["desde"], "consultas": {}, "erros": {}}
    token = os.environ.get("META_AD_LIBRARY_TOKEN")
    if not token and buscar_fn is None:
        out["status"] = "⛔ falta o segredo META_AD_LIBRARY_TOKEN no GitHub (token da API da Biblioteca de Anúncios da Meta)"
        saida.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
        print(out["status"])
        return 1
    buscar_fn = buscar_fn or (lambda termo: buscar(token, cfg, termo))
    brutos = []
    for c in cfg["consultas"]:
        try:
            ads, pags = buscar_fn(c["termo"])
        except Exception as e:  # noqa: BLE001 — a mensagem pode conter a URL com o token
            corpo = ""
            if hasattr(e, "read"):
                try:
                    corpo = json.loads(e.read().decode("utf-8")).get("error", {}).get("message", "")[:300]
                except Exception:  # noqa: BLE001
                    pass
            out["erros"][c["id"]] = f"{type(e).__name__} {getattr(e, 'code', '')} {corpo}".strip()
            continue
        out["consultas"][c["id"]] = {"candidato": c["candidato"], "termo": c["termo"], "paginas_api": pags, **agregar(ads, fases)}
        brutos += [{"consulta": c["id"], **a} for a in ads]
        print(f"{c['candidato']}: {len(ads)} anúncios · gasto R$ {out['consultas'][c['id']]['gasto']}")
    out["status"] = "ok" if out["consultas"] and not out["erros"] else ("⛔ " + "; ".join(f"{k}: {v}" for k, v in out["erros"].items()))
    saida.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    interno = os.environ.get("ODI_INTERNO_DIR")
    if interno and brutos:
        d = Path(interno) / "meta/anuncios"
        d.mkdir(parents=True, exist_ok=True)
        with gzip.open(d / f"{out['coletado_em_utc'][:10]}.jsonl.gz", "wt", encoding="utf-8") as f:
            for a in brutos:
                f.write(json.dumps(a, ensure_ascii=False) + "\n")
    for k, v in out["erros"].items():
        print(f"⛔ {k}: {v}")
    return 0 if out["status"] == "ok" else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
