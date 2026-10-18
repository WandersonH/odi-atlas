#!/usr/bin/env python3
"""Seguidores dos perfis de TikTok declarados ao TSE (chapas 13 e 22) via Apify (apidojo/tiktok-profile-scraper, US$ 0,0003/item).

Uma execução por perfil, 1 item (o post mais recente traz os números do perfil). Contas 3 a 7 (a conta 1 não é usada).
Saída: data/seguidores/tiktok_latest.csv e tiktok_AAAA-MM-DD.csv (URL declarada ao TSE, para casar com o card),
data/seguidores/tiktok_manifesto_latest.json.
"""
from __future__ import annotations

import csv
import json
import re
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from collect_kwai_apify import g, inteiro  # noqa: E402
from collect_meta_anuncios_apify import custo_run  # noqa: E402
from collect_meta_apify import escolher_conta, run_actor  # noqa: E402
from net import now_utc  # noqa: E402

ATOR = "apidojo~tiktok-profile-scraper"
SEGREDOS = ["APIFY_TOKEN_3", "APIFY_TOKEN_4", "APIFY_TOKEN_5", "APIFY_TOKEN_6", "APIFY_TOKEN_7"] + [f"APIFY_TOKEN_{i}" for i in range(8, 16)]
IDS = {"13": "280002542548", "22": "280002551544"}


def alvos(root: Path) -> list[dict]:
    out, vistos = [], set()
    for x in json.loads((root / "data/tse/redes_presidencia_2026.json").read_text(encoding="utf-8")):
        if x["plataforma"] != "tiktok" or x["nr"] not in IDS:
            continue
        m = re.search(r"tiktok\.com/@?([A-Za-z0-9._]+)", x["url"], re.I)
        if not m:
            continue
        u = m.group(1).lower()
        if u in vistos:
            continue
        vistos.add(u)
        out.append({"usuario": u, "url_tse": x["url"], "candidate_id": IDS[x["nr"]], "declarado_por": x["urna"]})
    return out


def seguidores(x: dict):
    return g(x, "authorMeta.fans", "channel.followers", "author.followerCount", "authorStats.followerCount", "user.followerCount",
             "author.stats.followerCount", "followers", "fans")


def main(argv=None, executar=None) -> int:
    root = Path(".")
    agora = now_utc()
    al = alvos(root)
    man = {"run_started_utc": agora, "ferramenta": f"Apify · {ATOR.replace('~', '/')}", "perfis": []}
    nome, token, saldo = escolher_conta(SEGREDOS, 0.05) if executar is None else ("teste", "x", None)
    man.update(conta=nome, saldo_conta_antes_usd=saldo)
    seg = root / "data/seguidores"
    seg.mkdir(parents=True, exist_ok=True)
    if not token:
        man["status"] = "⛔ nenhuma conta Apify com saldo (3 a 7)"
        (seg / "tiktok_manifesto_latest.json").write_text(json.dumps(man, ensure_ascii=False, indent=1), encoding="utf-8")
        print(man["status"])
        return 1
    executar = executar or (lambda pl, cap: run_actor(token, ATOR, pl, cap))

    def um(a):
        try:
            return a, *executar({"usernames": [a["usuario"]], "maxItems": 1}, 0.01), None
        except Exception as e:  # noqa: BLE001 — o token vai no cabeçalho
            return a, {}, [], f"{type(e).__name__} {getattr(e, 'code', '')}".strip()
    with ThreadPoolExecutor(max_workers=4) as ex:
        res = list(ex.map(um, al))
    linhas, custo = [], 0.0
    for a, run, itens, erro in res:
        itens = itens or []
        n = next((inteiro(seguidores(x)) for x in itens if seguidores(x) is not None), None)
        custo += max(custo_run(run or {}) or 0, 0.0003 * len(itens))
        man["perfis"].append({"usuario": a["usuario"], "seguidores": n, "itens": len(itens), "erro": erro,
                              "chaves": sorted(itens[0].keys())[:30] if itens and n is None else None})
        print(f"@{a['usuario']}: {n if n is not None else '⛔ sem número'}{' · ' + erro if erro else ''}")
        if n not in (None, ""):
            linhas.append({"candidate_id": a["candidate_id"], "candidate_name": a["declarado_por"], "platform": "TikTok", "url": a["url_tse"],
                           "followers": n, "captured_at": agora[:10], "source_url": f"https://www.tiktok.com/@{a['usuario']}"})
    if linhas:
        cols = ["candidate_id", "candidate_name", "platform", "url", "followers", "captured_at", "source_url"]
        for nomearq in (f"tiktok_{agora[:10]}.csv", "tiktok_latest.csv"):
            with open(seg / nomearq, "w", encoding="utf-8", newline="") as f:
                w = csv.DictWriter(f, cols, delimiter=";", lineterminator="\n")
                w.writeheader()
                w.writerows(linhas)
    man.update(custo_usd=round(custo, 4), status="ok" if linhas else "⛔ nenhum número lido")
    (seg / "tiktok_manifesto_latest.json").write_text(json.dumps(man, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"TikTok seguidores: {len(linhas)} de {len(al)} perfis · US$ {round(custo, 4)}")
    return 0 if linhas else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
