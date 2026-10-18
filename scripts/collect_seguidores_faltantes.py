#!/usr/bin/env python3
"""Seguidores dos perfis declarados ao TSE (chapas 13 e 22) que ficaram sem número nas coletas principais.

Por que existem: o ator de TikTok (apidojo) devolve `noResults` para perfis com poucos vídeos; no X o número vem dos posts
e perfis sem post desde 20/07 ficam sem número; no Instagram o ator principal às vezes devolve item vazio.
Aqui cada perfil faltante é consultado direto no perfil, tentando atores alternativos em ordem (o primeiro que
devolver número vale). Contas Apify 3 a 7 (a conta 1 não é usada). Teto mínimo por execução (US$ 0,10, exigência da Apify).

Saída: data/seguidores/complemento_latest.csv (mesmas colunas dos demais; linhas antigas de perfis não reconsultados
são mantidas com a data original) e data/seguidores/complemento_manifesto_latest.json (o que foi tentado e o resultado).
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
from collect_meta_apify import escolher_conta, run_actor  # noqa: E402
from net import now_utc  # noqa: E402

SEGREDOS = ["APIFY_TOKEN_3", "APIFY_TOKEN_4", "APIFY_TOKEN_5", "APIFY_TOKEN_6", "APIFY_TOKEN_7"]
IDS = {"13": "280002542548", "22": "280002551544"}
ROTULO = {"tiktok": "TikTok", "x": "X / Twitter", "instagram": "Instagram"}
PADRAO = {"tiktok": r"tiktok\.com/@?([A-Za-z0-9._]+)", "x": r"(?:x|twitter)\.com/@?([A-Za-z0-9_]+)",
          "instagram": r"instagram\.com/([A-Za-z0-9._]+)"}
# (ator, função que monta a entrada). Ordem = preferência.
ATORES = {
    "tiktok": [("clockworks~tiktok-profile-scraper", lambda u: {"profiles": [u], "resultsPerPage": 1, "shouldDownloadVideos": False}),
               ("clockworks~tiktok-scraper", lambda u: {"profiles": [u], "resultsPerPage": 1, "shouldDownloadVideos": False})],
    "x": [("apidojo~twitter-user-scraper", lambda u: {"twitterHandles": [u], "maxItems": 1, "getFollowers": False, "getFollowing": False})],
    "instagram": [("apify~instagram-profile-scraper", lambda u: {"usernames": [u]}),
                  ("apify~instagram-scraper", lambda u: {"directUrls": [f"https://www.instagram.com/{u}/"], "resultsType": "details", "resultsLimit": 1})],
}
ARQS = ("latest.csv", "youtube_latest.csv", "kwai_latest.csv", "x_latest.csv", "tiktok_latest.csv")
COLS = ["candidate_id", "candidate_name", "platform", "url", "followers", "captured_at", "source_url"]


def usuario(plat: str, url: str) -> str | None:
    m = re.search(PADRAO[plat], url, re.I)
    if not m:
        return None
    u = m.group(1).lower()
    return None if u in ("p", "reel", "explore", "intent", "share", "home") else u


def seguidores(x: dict):
    return g(x, "authorMeta.fans", "followersCount", "followers_count", "followers", "fans", "user.followerCount",
             "author.followerCount", "authorStats.followerCount", "stats.followerCount", "public_metrics.followers_count",
             "legacy.followers_count")


def faltantes(root: Path) -> list[dict]:
    """Perfis TikTok/X/Instagram das chapas 13 e 22 cujo usuário não aparece com número em nenhum CSV de seguidores."""
    com_numero = set()
    seg = root / "data/seguidores"
    for arq in ARQS:
        p = seg / arq
        if not p.exists():
            continue
        for r in csv.DictReader(open(p, encoding="utf-8"), delimiter=";"):
            if str(r.get("followers") or "").strip():
                for plat in PADRAO:
                    for campo in ("url", "source_url"):
                        u = usuario(plat, r.get(campo) or "")
                        if u:
                            com_numero.add((plat, u))
    out, vistos = [], set()
    for x in json.loads((root / "data/tse/redes_presidencia_2026.json").read_text(encoding="utf-8")):
        if x["plataforma"] not in PADRAO or x["nr"] not in IDS:
            continue
        u = usuario(x["plataforma"], x["url"])
        if not u or (x["plataforma"], u) in com_numero or (x["plataforma"], u) in vistos:
            continue
        vistos.add((x["plataforma"], u))
        out.append({"plataforma": x["plataforma"], "usuario": u, "url_tse": x["url"], "candidate_id": IDS[x["nr"]], "declarado_por": x["urna"]})
    return out


def main(argv=None, executar=None) -> int:
    root = Path(".")
    agora = now_utc()
    seg = root / "data/seguidores"
    seg.mkdir(parents=True, exist_ok=True)
    al = faltantes(root)
    man = {"run_started_utc": agora, "perfis": [], "faltantes": len(al)}

    def fim(status: str, code: int) -> int:
        man["status"] = status
        (seg / "complemento_manifesto_latest.json").write_text(json.dumps(man, ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"seguidores faltantes: {status}")
        return code

    if not al:
        return fim("ok · nenhum perfil faltante", 0)
    nome, token, saldo = escolher_conta(SEGREDOS, 0.15) if executar is None else ("teste", "x", None)
    man.update(conta=nome)
    if not token:
        return fim("⛔ nenhuma conta Apify com saldo (3 a 7)", 1)
    executar = executar or (lambda ator, pl: run_actor(token, ator, pl, 0.1))

    def um(a):
        tentativas = []
        for ator, entrada in ATORES[a["plataforma"]]:
            try:
                run, itens = executar(ator, entrada(a["usuario"]))
            except Exception as e:  # noqa: BLE001 — o token vai no cabeçalho, não na mensagem
                tentativas.append({"ator": ator.replace("~", "/"), "erro": f"{type(e).__name__} {getattr(e, 'code', '')}".strip()})
                continue
            itens = itens or []
            n = next((inteiro(seguidores(x)) for x in itens if seguidores(x) is not None), None)
            tentativas.append({"ator": ator.replace("~", "/"), "run": (run or {}).get("id"), "itens": len(itens), "seguidores": n,
                               "chaves": sorted(itens[0].keys())[:25] if itens and n is None else None,
                               "erro_ator": str(g(itens[0], "errorDescription", "error", "message") or "")[:200] if itens and n is None else None})
            if n is not None:
                return a, n, ator, tentativas
        return a, None, None, tentativas

    with ThreadPoolExecutor(max_workers=4) as ex:
        res = list(ex.map(um, al))
    antigos = {}
    p = seg / "complemento_latest.csv"
    if p.exists():
        antigos = {(r["platform"], r["url"].lower()): r for r in csv.DictReader(open(p, encoding="utf-8"), delimiter=";")}
    novos = 0
    for a, n, ator, tent in res:
        man["perfis"].append({"plataforma": a["plataforma"], "usuario": a["usuario"], "seguidores": n, "tentativas": tent})
        print(f"{a['plataforma']} @{a['usuario']}: {n if n is not None else '⛔ sem número'}")
        if n is not None:
            novos += 1
            r = {"candidate_id": a["candidate_id"], "candidate_name": a["declarado_por"], "platform": ROTULO[a["plataforma"]],
                 "url": a["url_tse"], "followers": n, "captured_at": agora[:10],
                 "source_url": {"tiktok": "https://www.tiktok.com/@", "x": "https://x.com/", "instagram": "https://www.instagram.com/"}[a["plataforma"]] + a["usuario"]}
            antigos[(r["platform"], r["url"].lower())] = r
    with open(p, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, COLS, delimiter=";", lineterminator="\n", extrasaction="ignore")
        w.writeheader()
        w.writerows(antigos.values())
    sem = [f"{x['plataforma']} @{x['usuario']}" for x in man["perfis"] if x["seguidores"] is None]
    man["sem_numero"] = sem
    return fim(f"ok · {novos} de {len(al)} perfis com número" + (f" · ⛔ sem número: {', '.join(sem)}" if sem else ""), 0 if novos else 1)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
