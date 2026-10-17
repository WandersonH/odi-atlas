#!/usr/bin/env python3
"""Biblioteca de Anúncios da Meta pela Apify (ator jmlp/meta-ad-library-scraper) — alternativa ao token oficial.

Token SOMENTE por APIFY_TOKEN. Cada execução tem teto de gasto (maxTotalChargeUsd da Apify): --teste usa o teto de teste;
sem a opção, o teto diário. Também respeita o teto mensal somando os manifestos do mês.
Saídas: data/meta/anuncios.json (mesmo formato da coleta oficial; agregados), data/meta/manifesto-AAAA-MM-*.json (custo) e,
com ODI_INTERNO_DIR, meta/anuncios/apify_AAAA-MM-DD.jsonl.gz (bruto, privado).
"""
from __future__ import annotations

import datetime as dt
import gzip
import json
import os
import re
import sys
import urllib.parse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from collect_meta_anuncios import agregar  # noqa: E402
from collect_meta_apify import api, run_actor  # noqa: E402
from net import now_utc  # noqa: E402


def faixa_de(v) -> dict | None:
    """Gasto/alcance em qualquer formato do ator → {'lower_bound','upper_bound'} (strings numéricas), ou None."""
    if v is None or v == "":
        return None
    if isinstance(v, dict):
        lo = v.get("lower_bound", v.get("lowerBound", v.get("min")))
        up = v.get("upper_bound", v.get("upperBound", v.get("max")))
        if lo is None and up is None:
            return None
        return {"lower_bound": str(lo or 0), "upper_bound": "" if up in (None, "") else str(up)}
    if isinstance(v, (int, float)):
        return {"lower_bound": str(int(v)), "upper_bound": str(int(v))}
    s = str(v)
    nums = [int(x.replace(".", "").replace(",", "")) for x in re.findall(r"\d[\d.,]*", s)]
    if not nums:
        return None
    if s.strip().startswith("<"):
        return {"lower_bound": "0", "upper_bound": str(nums[0])}
    if len(nums) == 1:
        return {"lower_bound": str(nums[0]), "upper_bound": "" if ">" in s or "+" in s else str(nums[0])}
    return {"lower_bound": str(nums[0]), "upper_bound": str(nums[1])}


def iso(t) -> str:
    try:
        return dt.datetime.fromtimestamp(int(t), dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    except (TypeError, ValueError):
        return str(t or "")


def normalizar(x: dict) -> dict:
    snap = x.get("snapshot") or {}
    plat = x.get("publisher_platform") or x.get("publisher_platforms") or []
    if isinstance(plat, str):
        plat = [p.strip().lower() for p in plat.split(",") if p.strip()]
    return {"id": str(x.get("ad_archive_id") or x.get("adArchiveID") or x.get("id") or ""),
            "page_id": str(x.get("page_id") or snap.get("page_id") or ""), "page_name": x.get("page_name") or snap.get("page_name") or "",
            "bylines": snap.get("byline") or x.get("byline") or x.get("bylines") or "",
            "ad_delivery_start_time": iso(x.get("start_date") or x.get("startDate")),
            "ad_delivery_stop_time": iso(x.get("end_date") or x.get("endDate")),
            "spend": faixa_de(x.get("spend")), "impressions": faixa_de(x.get("impressions") or x.get("impressions_with_index")),
            "reach": faixa_de(x.get("reach_estimate") or x.get("reach")), "currency": x.get("currency") or "",
            "publisher_platforms": [str(p).lower() for p in plat], "delivery_by_region": x.get("delivery_by_region") or []}


def url_biblioteca(termo: str, pais: str, desde: str) -> str:
    q = {"active_status": "all", "ad_type": "political_and_issue_ads", "country": pais, "q": termo,
         "search_type": "keyword_unordered", "media_type": "all", "start_date[min]": desde}
    return "https://www.facebook.com/ads/library/?" + urllib.parse.urlencode(q)


def custo_run(run: dict) -> float:
    """Custo cobrado: eventos cobrados × preço do evento (plano FREE quando há faixas); senão usageTotalUsd."""
    ev = ((run.get("pricingInfo") or {}).get("pricingPerEvent") or {}).get("actorChargeEvents") or {}
    tot = 0.0
    for nome, n in (run.get("chargedEventCounts") or {}).items():
        e = ev.get(nome) or {}
        preco = e.get("eventPriceUsd")
        if preco is None:
            preco = ((e.get("eventTieredPricingUsd") or {}).get("FREE") or {}).get("tieredEventPriceUsd") or 0
        tot += float(n or 0) * float(preco or 0)
    return round(tot or float(run.get("usageTotalUsd") or 0), 4)


def gasto_mes(pasta: Path) -> float:
    mes = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m")
    tot = 0.0
    for f in pasta.glob(f"manifesto-{mes}-*.json"):
        try:
            tot += float(json.loads(f.read_text(encoding="utf-8")).get("custo_usd") or 0)
        except Exception:  # noqa: BLE001
            pass
    return round(tot, 4)


def main(argv=None, executar=None) -> int:
    argv = list(argv or [])
    root = Path(".")
    cfg = json.loads((root / "data/config/meta_anuncios_apify.json").read_text(encoding="utf-8"))
    teste = "--teste" in argv
    pasta = root / "data/meta"
    pasta.mkdir(parents=True, exist_ok=True)
    fases = json.loads((root / "data/config/trends.json").read_text(encoding="utf-8")).get("fases", [])
    agora = now_utc()
    teto = cfg["teto_teste_usd"] if teste else cfg["teto_diario_usd"]
    ja = gasto_mes(pasta)
    out = {"schema_version": 1, "coletado_em_utc": agora, "fonte": f"Meta · Biblioteca de Anúncios via Apify ({cfg['ator'].replace('~', '/')})",
           "nota": cfg["nota"], "desde": cfg["desde"], "consultas": {}, "erros": {}, "modo": "teste" if teste else "diário",
           "teto_usd": teto, "gasto_mes_antes_usd": ja}
    token = os.environ.get("APIFY_TOKEN", "").strip()
    if not token and executar is None:
        out["status"] = "⛔ APIFY_TOKEN ausente"
    elif ja + teto > cfg["teto_mensal_usd"] + 1e-9:
        out["status"] = f"⛔ teto mensal de US$ {cfg['teto_mensal_usd']} atingido (já gasto US$ {ja})"
    if "status" in out:
        (pasta / "anuncios.json").write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
        print(out["status"])
        return 1
    executar = executar or (lambda payload, cap: run_actor(token, cfg["ator"], payload, cap))
    max_ads = cfg["max_anuncios_por_consulta_teste" if teste else "max_anuncios_por_consulta_diario"]
    payload = {"adLibraryUrls": [url_biblioteca(c["termo"], cfg["pais"], cfg["desde"]) for c in cfg["consultas"]],
               "country": cfg["pais"], "minDate": cfg["desde"], "maxAds": max_ads, "activeStatus": "all"}
    custo, brutos = 0.0, []
    try:
        run, itens = executar(payload, teto)
        custo = custo_run(run)
        out["run_apify"] = {"id": run.get("id"), "status": run.get("status"), "custo_usd": custo}
        brutos = itens or []
    except Exception as e:  # noqa: BLE001 — a mensagem não contém o token (vai no cabeçalho)
        out["erros"]["apify"] = f"{type(e).__name__} {getattr(e, 'code', '')}".strip()
    # cada item volta com a URL/termo de origem em campos diferentes conforme o ator; atribui pelo texto da busca
    por = {c["id"]: [] for c in cfg["consultas"]}
    for x in brutos:
        origem = json.dumps({k: x.get(k) for k in ("adLibraryUrl", "inputUrl", "url", "query", "keyword", "searchTerm")}, ensure_ascii=False).lower()
        alvo = next((c["id"] for c in cfg["consultas"] if urllib.parse.quote(c["termo"]).lower() in origem or c["termo"].lower() in origem), None)
        if alvo is None:  # sem origem no item: atribui por menção no texto do anúncio
            txt = json.dumps(x, ensure_ascii=False).lower()
            alvo = next((c["id"] for c in cfg["consultas"] if c["termo"].lower() in txt), None)
        if alvo:
            por[alvo].append(normalizar(x))
    for c in cfg["consultas"]:
        ads = [a for a in por[c["id"]] if a["id"]]
        ads = list({a["id"]: a for a in ads}.values())
        out["consultas"][c["id"]] = {"candidato": c["candidato"], "termo": c["termo"], "paginas_api": None,
                                     "limite_da_coleta": max_ads, "no_limite": len(ads) >= max_ads, **agregar(ads, fases)}
        print(f"{c['candidato']}: {len(ads)} anúncios{' (limite da coleta atingido)' if len(ads) >= max_ads else ''}")
    ok = any(v["anuncios"] for v in out["consultas"].values())
    out["status"] = "ok" if ok and not out["erros"] else ("⚠️ parcial" if ok else "⛔ " + ("; ".join(f"{k}: {v}" for k, v in out["erros"].items()) or "nenhum anúncio"))
    out["custo_usd"] = custo
    (pasta / "anuncios.json").write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    (pasta / f"manifesto-{agora[:7]}-{agora.replace(':', '').replace('-', '')}.json").write_text(
        json.dumps({"coletado_em_utc": agora, "modo": out["modo"], "teto_usd": teto, "custo_usd": custo, "itens": len(brutos),
                    "run": out.get("run_apify", {}).get("id")}, ensure_ascii=False, indent=1), encoding="utf-8")
    interno = os.environ.get("ODI_INTERNO_DIR")
    if interno and brutos:
        d = Path(interno) / "meta/anuncios"
        d.mkdir(parents=True, exist_ok=True)
        with gzip.open(d / f"apify_{agora[:10]}.jsonl.gz", "wt", encoding="utf-8") as f:
            for x in brutos:
                f.write(json.dumps(x, ensure_ascii=False) + "\n")
    print(f"meta via apify: {out['status']} · {len(brutos)} itens · custo US$ {custo} (teto {teto}) · mês antes US$ {ja}")
    if brutos:
        print("campos do 1º item: " + ", ".join(sorted(brutos[0].keys()))[:900])
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
