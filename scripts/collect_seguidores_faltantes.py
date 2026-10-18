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
import gzip
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
ROTULO = {"tiktok": "TikTok", "x": "X / Twitter", "instagram": "Instagram", "facebook": "Facebook"}
PADRAO = {"tiktok": r"tiktok\.com/@?([A-Za-z0-9._]+)", "x": r"(?:x|twitter)\.com/@?([A-Za-z0-9_]+)",
          "instagram": r"instagram\.com/([A-Za-z0-9._]+)", "facebook": r"facebook\.com/([A-Za-z0-9.]+)"}
# (ator, função que monta a entrada). Ordem = preferência.
ATORES = {
    "tiktok": [("clockworks~tiktok-profile-scraper", lambda u: {"profiles": [u], "resultsPerPage": 1, "shouldDownloadVideos": False}),
               ("clockworks~tiktok-scraper", lambda u: {"profiles": [u], "resultsPerPage": 1, "shouldDownloadVideos": False})],
    "x": [("apidojo~twitter-user-scraper", lambda u: {"twitterHandles": [u], "maxItems": 1, "getFollowers": False, "getFollowing": False})],
    "instagram": [("apify~instagram-profile-scraper", lambda u: {"usernames": [u]}),
                  ("apify~instagram-scraper", lambda u: {"directUrls": [f"https://www.instagram.com/{u}/"], "resultsType": "details", "resultsLimit": 1})],
    "facebook": [("apify~facebook-pages-scraper", lambda u: {"startUrls": [{"url": f"https://www.facebook.com/{u}"}]})],
}
ARQS = ("latest.csv", "youtube_latest.csv", "kwai_latest.csv", "x_latest.csv", "tiktok_latest.csv")
COLS = ["candidate_id", "candidate_name", "platform", "url", "followers", "captured_at", "source_url"]


def usuario(plat: str, url: str) -> str | None:
    m = re.search(PADRAO[plat], url, re.I)
    if not m:
        return None
    u = m.group(1).lower()
    return None if u in ("p", "reel", "explore", "intent", "share", "home", "profile.php", "people", "groups") else u


def seguidores(x: dict):
    return g(x, "authorMeta.fans", "followersCount", "followers_count", "followers", "fans", "user.followerCount",
             "author.followerCount", "authorStats.followerCount", "stats.followerCount", "public_metrics.followers_count",
             "legacy.followers_count")


def alvos_tse(root: Path) -> list[dict]:
    """Todos os perfis TikTok/X/Instagram/Facebook declarados por candidatos a presidente e vice (id de cada pessoa)."""
    src = root / "data/tse/redes_sociais_candidatos_2026.csv.gz"
    out, vistos = [], set()
    for r in csv.DictReader(gzip.open(src, "rt", encoding="utf-8"), delimiter=";"):
        plat = r.get("PLATAFORMA")
        if r.get("DS_CARGO", "").upper() not in ("PRESIDENTE", "VICE-PRESIDENTE") or plat not in PADRAO:
            continue
        u = usuario(plat, r["DS_URL"])
        if not u or (r["SQ_CANDIDATO"], plat, u) in vistos:
            continue
        vistos.add((r["SQ_CANDIDATO"], plat, u))
        out.append({"plataforma": plat, "usuario": u, "url_tse": r["DS_URL"].strip(), "candidate_id": r["SQ_CANDIDATO"],
                    "declarado_por": r.get("NM_URNA_CANDIDATO", "")})
    return out


def ja_coletados(root: Path) -> tuple[set, dict]:
    """(id, rede, usuário) que já têm número, e o número mais recente por (rede, usuário) em qualquer CSV principal."""
    tem, num = set(), {}
    for arq in ARQS:
        p = root / "data/seguidores" / arq
        if not p.exists():
            continue
        for r in csv.DictReader(open(p, encoding="utf-8"), delimiter=";"):
            if not str(r.get("followers") or "").strip():
                continue
            for plat in PADRAO:
                if ROTULO[plat] != r.get("platform") and not (plat == "x" and "twitter" in (r.get("platform") or "").lower()):
                    continue
                for campo in ("url", "source_url"):
                    u = usuario(plat, r.get(campo) or "")
                    if u:
                        tem.add((r["candidate_id"], plat, u))
                        if (plat, u) not in num or (r.get("captured_at") or "") > (num[(plat, u)].get("captured_at") or ""):
                            num[(plat, u)] = dict(r, _arq=arq)
    return tem, num


def faltantes(root: Path) -> list[dict]:
    """Perfis declarados (por pessoa) sem número em nenhum CSV principal."""
    tem, _ = ja_coletados(root)
    return [a for a in alvos_tse(root) if (a["candidate_id"], a["plataforma"], a["usuario"]) not in tem]


def main(argv=None, executar=None) -> int:
    root = Path(".")
    agora = now_utc()
    seg = root / "data/seguidores"
    seg.mkdir(parents=True, exist_ok=True)
    _, num = ja_coletados(root)
    al = faltantes(root)
    # Mesmo perfil já coletado sob outro candidato (ex.: perfil do vice gravado com o id do titular): reaproveita, sem nova consulta.
    reaproveitar = [a for a in al if (a["plataforma"], a["usuario"]) in num]
    consultar = {}
    for a in al:
        if (a["plataforma"], a["usuario"]) not in num:
            consultar.setdefault((a["plataforma"], a["usuario"]), []).append(a)
    man = {"run_started_utc": agora, "perfis": [], "faltantes": len(al), "reaproveitados": len(reaproveitar), "consultados": len(consultar)}

    def fim(status: str, code: int) -> int:
        man["status"] = status
        (seg / "complemento_manifesto_latest.json").write_text(json.dumps(man, ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"seguidores faltantes: {status}")
        return code

    linhas = {}
    for a in reaproveitar:
        r0 = num[(a["plataforma"], a["usuario"])]
        linhas[(a["candidate_id"], a["url_tse"].lower())] = {"candidate_id": a["candidate_id"], "candidate_name": a["declarado_por"],
                                                            "platform": ROTULO[a["plataforma"]], "url": a["url_tse"], "followers": r0["followers"],
                                                            "captured_at": r0.get("captured_at"), "source_url": r0.get("source_url") or r0.get("url")}
    res = []
    if consultar:
        nome, token, _saldo = escolher_conta(SEGREDOS, 0.15) if executar is None else ("teste", "x", None)
        man.update(conta=nome)
        if not token:
            return fim("⛔ nenhuma conta Apify com saldo (3 a 7)", 1)
        executar = executar or (lambda ator, pl: run_actor(token, ator, pl, 0.1))

        def um(chave):
            plat, u = chave
            tentativas = []
            for ator, entrada in ATORES[plat]:
                try:
                    run, itens = executar(ator, entrada(u))
                except Exception as e:  # noqa: BLE001 — o token vai no cabeçalho, não na mensagem
                    tentativas.append({"ator": ator.replace("~", "/"), "erro": f"{type(e).__name__} {getattr(e, 'code', '')}".strip()})
                    continue
                itens = itens or []
                if any("demo" in x for x in itens):  # plano gratuito do ator devolve item de demonstração, não o perfil
                    tentativas.append({"ator": ator.replace("~", "/"), "run": (run or {}).get("id"), "itens": len(itens), "seguidores": None,
                                       "erro_ator": "item de demonstração do plano gratuito (descartado)"})
                    continue
                n = next((inteiro(seguidores(x)) for x in itens if seguidores(x) is not None), None)
                tentativas.append({"ator": ator.replace("~", "/"), "run": (run or {}).get("id"), "itens": len(itens), "seguidores": n,
                                   "chaves": sorted(itens[0].keys())[:25] if itens and n is None else None,
                                   "erro_ator": str(g(itens[0], "errorDescription", "error", "message") or "")[:200] if itens and n is None else None})
                if n is not None:
                    return chave, n, tentativas
            return chave, None, tentativas

        with ThreadPoolExecutor(max_workers=4) as ex:
            res = list(ex.map(um, list(consultar)))
    base = {"tiktok": "https://www.tiktok.com/@", "x": "https://x.com/", "instagram": "https://www.instagram.com/", "facebook": "https://www.facebook.com/"}
    novos = 0
    for (plat, u), n, tent in res:
        donos = consultar[(plat, u)]
        man["perfis"].append({"plataforma": plat, "usuario": u, "candidatos": sorted({a["declarado_por"] for a in donos}), "seguidores": n, "tentativas": tent})
        print(f"{plat} @{u}: {n if n is not None else '⛔ sem número'}")
        if n is None:
            continue
        novos += 1
        for a in donos:
            linhas[(a["candidate_id"], a["url_tse"].lower())] = {"candidate_id": a["candidate_id"], "candidate_name": a["declarado_por"],
                                                                "platform": ROTULO[plat], "url": a["url_tse"], "followers": n,
                                                                "captured_at": agora[:10], "source_url": base[plat] + u}
    with open(seg / "complemento_latest.csv", "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, COLS, delimiter=";", lineterminator="\n", extrasaction="ignore")
        w.writeheader()
        w.writerows(linhas.values())
    sem = [f"{x['plataforma']} @{x['usuario']}" for x in man["perfis"] if x["seguidores"] is None]
    man["sem_numero"] = sem
    status = f"ok · {len(reaproveitar)} cards preenchidos com número já coletado · {novos} de {len(consultar)} perfis consultados com número"
    return fim(status + (f" · ⛔ sem número: {', '.join(sem)}" if sem else ""), 0 if (novos or reaproveitar or not al) else 1)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
