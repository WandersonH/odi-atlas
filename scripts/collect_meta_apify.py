#!/usr/bin/env python3
"""Seguidores de perfis Instagram/Facebook declarados ao TSE, via atores oficiais da Apify.

- Lê as URLs de data/tse/redes_sociais_candidatos_<ANO>.csv.gz (coleta do TSE), filtrando cargos.
- Token SOMENTE pela variável de ambiente APIFY_TOKEN (segredo do GitHub). Nunca é gravado nem impresso.
- Orçamento: antes de rodar, soma o custo das execuções do mês (registrado nos manifestos) e não
  roda se o teto mensal for ultrapassado; cada ator roda com maxTotalChargeUsd = teto por execução.
- Saída: data/seguidores/latest.csv no formato do caderno 02
  (candidate_id;candidate_name;platform;url;followers;captured_at;source_url), histórico datado e
  manifesto com custo real (usageTotalUsd) de cada execução.
- Perfil sem número na resposta fica sem número (não vira zero).
"""
from __future__ import annotations

import csv
import datetime as dt
import gzip
import json
import os
import re
import sys
import urllib.parse
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from net import with_scheme, now_utc  # noqa: E402

API = "https://api.apify.com/v2"
PLAT_LABEL = {"instagram": "Instagram", "facebook": "Facebook"}


def api(method: str, path: str, token: str, body=None, timeout=360):
    req = urllib.request.Request(f"{API}{path}", method=method,
                                 data=None if body is None else json.dumps(body).encode(),
                                 headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read() or b"null")


def saldo_conta(token: str) -> float | None:
    """Saldo real do mês na conta Apify (limite − uso), pela API de limites. None se não der para ler.
    O custo informado em cada execução pode vir zerado; o saldo da conta é a referência para não estourar o limite."""
    try:
        lim = (api("GET", "/users/me/limits", token, timeout=60) or {}).get("data", {})
        uso, teto = (lim.get("current") or {}).get("monthlyUsageUsd"), (lim.get("limits") or {}).get("maxMonthlyUsageUsd")
        return round(teto - uso, 4) if isinstance(uso, (int, float)) and isinstance(teto, (int, float)) else None
    except Exception:  # noqa: BLE001 — a mensagem não contém o token
        return None


def ig_username(url: str) -> str | None:
    u = url.strip()
    p = urllib.parse.urlparse(u if "://" in u else "https://" + u)
    parts = [x for x in p.path.split("/") if x]
    if not parts or parts[0].lower() in ("p", "reel", "reels", "stories", "explore", "tv"):
        return None
    name = parts[0].lstrip("@").lower()
    return name if re.fullmatch(r"[a-z0-9._]{1,30}", name) else None


def fb_url(url: str) -> str | None:
    u = url.strip()
    p = urllib.parse.urlparse(u if "://" in u else "https://" + u)
    if not p.hostname or "facebook.com" not in p.hostname.lower() and "fb.com" not in p.hostname.lower():
        return None
    path = p.path.rstrip("/")
    if not path or path in ("/",):
        return None
    q = "?" + p.query if "profile.php" in path and p.query else ""
    return "https://www.facebook.com" + path + q


def load_targets(root: Path, cfg: dict, year: str = "2026"):
    src = root / "data" / "tse" / f"redes_sociais_candidatos_{year}.csv.gz"
    alvo = {c.upper() for c in cfg["cargos"]}
    out = []
    for r in csv.DictReader(gzip.open(src, "rt", encoding="utf-8"), delimiter=";"):
        if r.get("DS_CARGO", "").upper() not in alvo or r.get("PLATAFORMA") not in cfg["plataformas"]:
            continue
        key = ig_username(r["DS_URL"]) if r["PLATAFORMA"] == "instagram" else fb_url(r["DS_URL"])
        out.append({"candidate_id": r["SQ_CANDIDATO"], "candidate_name": r.get("NM_URNA_CANDIDATO", ""),
                    "platform": r["PLATAFORMA"], "url": r["DS_URL"].strip(), "key": key})
    return out


def spent_this_month(root: Path) -> float:
    mes = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m")
    total = 0.0
    for f in (root / "data" / "seguidores").glob(f"manifesto-{mes}-*.json"):
        try:
            total += float(json.loads(f.read_text(encoding="utf-8")).get("custo_total_usd") or 0)
        except Exception:
            pass
    return round(total, 4)


def first_number(item: dict, keys: list[str]):
    for k in keys:
        v = item.get(k)
        if isinstance(v, (int, float)) and v >= 0:
            return int(v), k
    return None, None


def run_actor(token: str, actor: str, payload: dict, cap: float):
    run = api("POST", f"/acts/{actor}/runs?waitForFinish=300&maxTotalChargeUsd={cap}", token, payload)["data"]
    while run.get("status") in ("READY", "RUNNING"):
        run = api("GET", f"/actor-runs/{run['id']}?waitForFinish=300", token)["data"]
    items = api("GET", f"/datasets/{run['defaultDatasetId']}/items?clean=true&format=json", token) or []
    return run, items


def main(argv=None) -> int:
    root = Path(argv[0]) if argv else Path(".")
    cfg = json.loads((root / "data/config/seguidores_meta.json").read_text(encoding="utf-8"))
    started = now_utc()
    stamp = started.replace(":", "").replace("-", "")
    man = {"schema_version": 1, "stage": "seguidores-meta", "run_started_utc": started, "config": cfg,
           "execucoes": [], "blocked": [], "warnings": []}
    token = os.environ.get("APIFY_TOKEN", "").strip()
    outdir = root / "data" / "seguidores"
    outdir.mkdir(parents=True, exist_ok=True)

    def finish(code: int) -> int:
        man["custo_total_usd"] = round(sum(e.get("custo_usd") or 0 for e in man["execucoes"]), 4)
        man["run_finished_utc"] = now_utc()
        man["status"] = "bloqueado" if man["blocked"] else "ok"
        txt = json.dumps(man, ensure_ascii=False, indent=1)
        (outdir / f"manifesto-{started[:7]}-{stamp}.json").write_text(txt, encoding="utf-8")
        (outdir / "manifesto_latest.json").write_text(txt, encoding="utf-8")
        print(json.dumps({k: man[k] for k in ("status", "blocked", "warnings", "custo_total_usd")}, ensure_ascii=False))
        return code

    if not token:
        man["blocked"].append("APIFY_TOKEN ausente (cadastre o segredo no GitHub)")
        return finish(1)
    gasto = spent_this_month(root)
    man["gasto_mes_antes_usd"] = gasto
    if gasto + cfg["teto_por_execucao_usd"] > cfg["teto_mensal_usd"]:
        man["blocked"].append(f"teto mensal: já gastos US$ {gasto:.2f} de US$ {cfg['teto_mensal_usd']:.2f}")
        return finish(1)

    targets = load_targets(root, cfg)
    man["alvos"] = {p: sum(1 for t in targets if t["platform"] == p) for p in cfg["plataformas"]}
    man["alvos_sem_chave"] = [t["url"] for t in targets if not t["key"]]
    rows, cap_each = [], round(cfg["teto_por_execucao_usd"] / max(1, len(cfg["plataformas"])), 2)
    raw_dir = outdir / "bruto" / started[:10]
    raw_dir.mkdir(parents=True, exist_ok=True)

    for plat in cfg["plataformas"]:
        tg = [t for t in targets if t["platform"] == plat and t["key"]]
        keys = sorted({t["key"] for t in tg})
        if not keys:
            continue
        ex = {"plataforma": plat, "ator": cfg["atores"][plat], "perfis_pedidos": len(keys), "teto_usd": cap_each}
        man["execucoes"].append(ex)
        try:
            payload = ({"usernames": keys} if plat == "instagram"
                       else {"startUrls": [{"url": k} for k in keys]})
            run, items = run_actor(token, cfg["atores"][plat], payload, cap_each)
            ex.update(run_id=run.get("id"), status_apify=run.get("status"),
                      custo_usd=run.get("usageTotalUsd"), itens=len(items))
            found = {}
            for it in items:
                if plat == "instagram":
                    k = str(it.get("username") or "").lower()
                    n, campo = first_number(it, ["followersCount", "followers"])
                    src = it.get("url") or f"https://www.instagram.com/{k}/"
                else:
                    k = fb_url(str(it.get("facebookUrl") or it.get("pageUrl") or it.get("url") or "")) or ""
                    n, campo = first_number(it, ["followers", "followersCount", "likes"])
                    src = it.get("pageUrl") or it.get("facebookUrl") or it.get("url") or ""
                found[k.lower()] = {"followers": n, "campo": campo, "source_url": src}
            # guarda só campos mínimos (perfil público de candidatura), sem posts nem comentários
            (raw_dir / f"{plat}.json").write_text(json.dumps(
                [{"chave": k, **v} for k, v in sorted(found.items())], ensure_ascii=False, indent=1), encoding="utf-8")
            ok = 0
            for t in tg:
                f = found.get(t["key"].lower())
                if f and f["followers"] is not None:
                    ok += 1
                    rows.append([t["candidate_id"], t["candidate_name"], PLAT_LABEL[plat], with_scheme(t["url"]), f["followers"],
                                 started[:10], f["source_url"] or t["url"]])
            ex["perfis_com_numero"] = ok
            if ok == 0:
                man["blocked"].append(f"{plat}: nenhum perfil retornou número de seguidores")
        except Exception as e:
            ex["erro"] = f"{type(e).__name__}: {e}"
            man["blocked"].append(f"{plat}: {ex['erro']}")

    if rows:
        header = ["candidate_id", "candidate_name", "platform", "url", "followers", "captured_at", "source_url"]
        for name in (f"coleta_{started[:10]}.csv", "latest.csv"):
            with open(outdir / name, "w", encoding="utf-8", newline="") as f:
                w = csv.writer(f, delimiter=";", lineterminator="\n")
                w.writerow(header)
                w.writerows(rows)
    man["linhas_csv"] = len(rows)
    return finish(1 if man["blocked"] else 0)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
