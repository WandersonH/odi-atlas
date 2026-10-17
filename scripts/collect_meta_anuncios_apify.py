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
    mult = {"K": 1_000, "M": 1_000_000, "B": 1_000_000_000, "MIL": 1_000, "MI": 1_000_000}

    def num(tok: str, suf: str) -> int:
        suf = suf.upper()
        if suf in mult:  # "1.5K" → 1500 (ponto decimal); "1,5 mil" → 1500
            return int(round(float(tok.replace(",", ".")) * mult[suf]))
        return int(tok.replace(".", "").replace(",", ""))
    nums = [num(t, u) for t, u in re.findall(r"(\d[\d.,]*)\s*(K|M|B|mil|mi)?\b", s, re.I)]
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
            "spend": faixa_de(x.get("spend")),
            "impressions": faixa_de((x.get("impressions_with_index") or {}).get("impressions_text") if isinstance(x.get("impressions_with_index"), dict) else x.get("impressions")),
            "reach": faixa_de(x.get("reach_estimate") or x.get("reach")), "currency": x.get("currency") or "",
            "publisher_platforms": [str(p).lower() for p in plat], "delivery_by_region": x.get("delivery_by_region") or []}


COLS = ["id", "consulta", "page_id", "page_name", "bylines", "ad_delivery_start_time", "ad_delivery_stop_time", "gasto_min", "gasto_max",
        "impressoes_min", "impressoes_max", "alcance_min", "alcance_max", "plataformas", "visto_em"]


def linha(a: dict, consulta: str, agora: str) -> dict:
    g, i, r = a.get("spend") or {}, a.get("impressions") or {}, a.get("reach") or {}
    return {"id": a["id"], "consulta": consulta, "page_id": a["page_id"], "page_name": a["page_name"], "bylines": a["bylines"],
            "ad_delivery_start_time": a["ad_delivery_start_time"], "ad_delivery_stop_time": a["ad_delivery_stop_time"],
            "gasto_min": g.get("lower_bound", ""), "gasto_max": g.get("upper_bound", ""), "impressoes_min": i.get("lower_bound", ""),
            "impressoes_max": i.get("upper_bound", ""), "alcance_min": r.get("lower_bound", ""), "alcance_max": r.get("upper_bound", ""),
            "plataformas": ",".join(a["publisher_platforms"]), "visto_em": agora}


def de_linha(r: dict) -> dict:
    f = lambda lo, up: {"lower_bound": r[lo] or "0", "upper_bound": r[up]} if (r[lo] or r[up]) else None  # noqa: E731
    return {"id": r["id"], "page_id": r["page_id"], "page_name": r["page_name"], "bylines": r["bylines"],
            "ad_delivery_start_time": r["ad_delivery_start_time"], "ad_delivery_stop_time": r["ad_delivery_stop_time"],
            "spend": f("gasto_min", "gasto_max"), "impressions": f("impressoes_min", "impressoes_max"),
            "currency": "BRL", "publisher_platforms": [p for p in r["plataformas"].split(",") if p], "delivery_by_region": []}


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
    # teste: anúncios com exibição desde o início do período; diário: com exibição desde ontem (os maiores primeiro)
    janela = cfg["desde"] if teste else (dt.date.fromisoformat(agora[:10]) - dt.timedelta(days=1)).isoformat()
    custo, brutos, runs = 0.0, [], []
    novos = {}
    cap = round(teto / len(cfg["consultas"]), 4)
    for c in cfg["consultas"]:  # uma execução por consulta: a origem de cada anúncio fica certa
        payload = {"adLibraryUrls": [url_biblioteca(c["termo"], cfg["pais"], janela)], "country": cfg["pais"],
                   "minDate": janela, "maxAds": max_ads, "activeStatus": "all"}
        try:
            run, itens = executar(payload, cap)
            custo += custo_run(run)
            runs.append({"consulta": c["id"], "id": run.get("id"), "status": run.get("status"), "custo_usd": custo_run(run), "itens": len(itens or [])})
            for x in itens or []:
                brutos.append({"_consulta": c["id"], **x})
                a_ = normalizar(x)
                if a_["id"]:
                    novos[(c["id"], a_["id"])] = linha(a_, c["id"], agora)
        except Exception as e:  # noqa: BLE001 — o token vai no cabeçalho, não na mensagem
            out["erros"][c["id"]] = f"{type(e).__name__} {getattr(e, 'code', '')}".strip()
    out["runs_apify"] = runs
    # acumulado público (sem texto dos anúncios): última leitura de cada anúncio por consulta
    hist = pasta / "anuncios_apify.csv"
    acum = {}
    if hist.exists():
        import csv as _csv
        acum = {(r["consulta"], r["id"]): r for r in _csv.DictReader(open(hist, encoding="utf-8"), delimiter=";")}
    acum.update(novos)
    import csv as _csv
    with open(hist, "w", encoding="utf-8", newline="") as f:
        w = _csv.DictWriter(f, COLS, delimiter=";", lineterminator="\n")
        w.writeheader()
        w.writerows(sorted(acum.values(), key=lambda r: (r["consulta"], r["id"])))
    for c in cfg["consultas"]:
        ads = [de_linha(r) for (q, _), r in acum.items() if q == c["id"]]
        hoje = sum(1 for (q, _) in novos if q == c["id"])
        out["consultas"][c["id"]] = {"candidato": c["candidato"], "termo": c["termo"], "paginas_api": None, "lidos_nesta_execucao": hoje,
                                     "limite_da_coleta": max_ads, "no_limite": hoje >= max_ads, **agregar(ads, fases)}
        print(f"{c['candidato']}: {hoje} lidos nesta execução{' (limite atingido)' if hoje >= max_ads else ''}; {len(ads)} no acumulado")
    ok = any(v["anuncios"] for v in out["consultas"].values())
    out["janela_desta_execucao"] = janela
    out["status"] = "ok" if ok and not out["erros"] else ("⚠️ parcial" if ok else "⛔ " + ("; ".join(f"{k}: {v}" for k, v in out["erros"].items()) or "nenhum anúncio"))
    out["custo_usd"] = custo
    (pasta / "anuncios.json").write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    (pasta / f"manifesto-{agora[:7]}-{agora.replace(':', '').replace('-', '')}.json").write_text(
        json.dumps({"coletado_em_utc": agora, "modo": out["modo"], "teto_usd": teto, "custo_usd": custo, "itens": len(brutos),
                    "runs": runs}, ensure_ascii=False, indent=1), encoding="utf-8")
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
