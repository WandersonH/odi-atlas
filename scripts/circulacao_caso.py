#!/usr/bin/env python3
"""Leitura diária da circulação de posts do Instagram de um caso (reproduções, curtidas, comentários, compartilhamentos).

Pedido do responsável (26/10/2026, 02h11): "quero uma comparação de circulação" entre o reel de Nikolas Ferreira
(DeuEvFlRfuH, caso 009) e o carrossel DeujIRxGDYZ (produção da Makinoff). Autorizado: teto de US$ 3,50 para o carrossel,
incluindo uma leitura por dia dos dois posts por 7 dias. A leitura diária tem teto próprio em data/config/circulacao_caso.json.

- Reel: apify/instagram-reel-scraper com includeSharesCount (US$ 0,0023 + 0,001 de início + 0,006 pelo número de compartilhamentos).
- Post comum ou carrossel: apify/instagram-scraper (directUrls, details; US$ 0,0026), sem número de compartilhamentos.
- Para sozinho depois da data final ou quando o gasto acumulado chegaria ao teto. Conta 1 (APIFY_TOKEN).
- Ponto zero: as leituras já feitas pela coleta do caso (ODI_INTERNO_DIR/casos/<pasta>/apify/*.json), sem nova execução.
Saída pública: data/casos/<caso>/circulacao.json (só números; nome do autor só com 10 mil+ seguidores; sem custo).
Saída privada: ODI_INTERNO_DIR/casos/<caso>/circulacao_estado.json (leituras, runs e gasto).
Uso: python scripts/circulacao_caso.py --caso 009 [--sem-coleta]
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from collect_meta_apify import run_actor  # noqa: E402
from net import now_utc  # noqa: E402

CAP = 0.10          # maxTotalChargeUsd por execução (mínimo aceito pelo Apify); o custo real é lido depois
CUSTO_PREVISTO = {"reel": 0.0093, "post": 0.0036}
MIN_PUBLICO = 10000


def arg(argv, k, d=None):
    return argv[argv.index(k) + 1] if k in argv else d


def codigo(url: str) -> str:
    partes = [p for p in url.split("?")[0].split("/") if p]
    for i, p in enumerate(partes):
        if p in ("reel", "p", "reels") and i + 1 < len(partes):
            return partes[i + 1]
    return partes[-1]


def numeros(it: dict) -> dict:
    return {"reproducoes": it.get("videoPlayCount") or it.get("videoViewCount"), "curtidas": it.get("likesCount"),
            "comentarios": it.get("commentsCount"), "compartilhamentos": it.get("sharesCount")}


def ponto_zero(interno: Path, post: dict) -> list[dict]:
    out = []
    for f in sorted((interno / "casos" / post["pasta"] / "apify").glob("*.json")):
        if f.name.startswith("manifesto"):
            continue
        try:
            d = json.loads(f.read_text(encoding="utf-8"))
        except ValueError:
            continue
        for it in d.get("items") or []:
            if it.get("shortCode") == codigo(post["url"]) and it.get("likesCount") is not None:
                out.append({"lido_em_utc": (d.get("fim_utc") or d.get("inicio_utc") or "")[:19] + "Z", "run": d.get("run_id"),
                            "origem": "coleta do caso", "publicado_em_utc": it.get("timestamp"), "autor": it.get("ownerUsername"),
                            "tipo": it.get("type"), **numeros(it)})
    return out


def ler(token: str, post: dict, executar=run_actor) -> tuple[dict | None, float, str | None]:
    if post["ator"] == "reel":
        ator, pl = "apify~instagram-reel-scraper", {"username": [post["url"]], "includeSharesCount": True,
                                                     "includeTranscript": False, "includeDownloadedVideo": False}
    else:
        ator, pl = "apify~instagram-scraper", {"directUrls": [post["url"]], "resultsType": "details", "resultsLimit": 1, "addParentData": False}
    try:
        run, itens = executar(token, ator, pl, CAP)
    except Exception as e:  # noqa: BLE001 — a mensagem da API não contém o token
        return None, 0.0, f"{ator}: {type(e).__name__} {getattr(e, 'code', '')}".strip()
    custo = float(run.get("usageTotalUsd") or 0)
    it = next((x for x in itens if x.get("shortCode") == codigo(post["url"]) or x.get("likesCount") is not None), None)
    if not it:
        return None, max(custo, CUSTO_PREVISTO[post["ator"]]), f"{ator}: nenhum item (o post pode ter saído do ar)"
    return ({"lido_em_utc": now_utc(), "run": run.get("id"), "origem": "leitura diária", "publicado_em_utc": it.get("timestamp"),
             "autor": it.get("ownerUsername"), "tipo": it.get("type"), **numeros(it)}, max(custo, CUSTO_PREVISTO[post["ator"]]), None)


def seguidores(interno: Path, pasta: str) -> int | None:
    f = interno / "casos" / pasta / "perfil_instagram.json"
    try:
        return int(json.loads(f.read_text(encoding="utf-8")).get("seguidores") or 0)
    except (OSError, ValueError, TypeError):
        return None


def main(argv=None, executar=run_actor, root: Path = Path(".")) -> int:
    argv = sys.argv[1:] if argv is None else list(argv)
    caso = arg(argv, "--caso")
    cfg = json.loads((root / "data/config/circulacao_caso.json").read_text(encoding="utf-8"))[caso]
    interno = Path(os.environ.get("ODI_INTERNO_DIR", ""))
    token = os.environ.get("APIFY_TOKEN", "").strip()
    if not (caso and os.environ.get("ODI_INTERNO_DIR")):
        print("⛔ informe --caso e ODI_INTERNO_DIR")
        return 1
    arq = interno / "casos" / caso / "circulacao_estado.json"
    arq.parent.mkdir(parents=True, exist_ok=True)
    est = json.loads(arq.read_text(encoding="utf-8")) if arq.exists() else {"gasto_usd": 0.0, "leituras": {}, "erros": []}
    hoje = now_utc()[:10]
    for post in cfg["posts"]:
        cod = codigo(post["url"])
        ls = est["leituras"].setdefault(cod, [])
        vistos = {x.get("run") for x in ls}
        ls.extend(x for x in ponto_zero(interno, post) if x["run"] not in vistos)
        ls.sort(key=lambda x: x["lido_em_utc"])
    coletar = "--sem-coleta" not in argv and hoje <= cfg["ate"] and (token or executar is not run_actor)
    if coletar:
        for post in cfg["posts"]:
            cod = codigo(post["url"])
            if any(x["lido_em_utc"][:10] == hoje and x["origem"] == "leitura diária" for x in est["leituras"][cod]):
                continue  # uma leitura por dia
            if est["gasto_usd"] + CAP > cfg["teto_usd"]:
                est["erros"].append(f"{now_utc()} {cod}: teto da leitura diária atingido (US$ {cfg['teto_usd']})")
                continue
            reg, custo, erro = ler(token, post, executar)
            est["gasto_usd"] = round(est["gasto_usd"] + custo, 4)
            if reg:
                est["leituras"][cod].append(reg)
            if erro:
                est["erros"].append(f"{now_utc()} {cod}: {erro}")
    arq.write_text(json.dumps(est, ensure_ascii=False, indent=1), encoding="utf-8")
    pub = {"caso": caso, "atualizado_em_utc": now_utc(), "ate": cfg["ate"], "nota": cfg.get("nota", ""), "posts": []}
    for post in cfg["posts"]:
        cod = codigo(post["url"])
        ls = est["leituras"][cod]
        seg = seguidores(interno, post["pasta"])
        autor = next((x["autor"] for x in ls if x.get("autor")), None)
        pub["posts"].append({"codigo": cod, "url": post["url"], "rotulo": post["rotulo"], "tipo": next((x["tipo"] for x in ls if x.get("tipo")), None),
                             "publicado_em_utc": next((x["publicado_em_utc"] for x in ls if x.get("publicado_em_utc")), None),
                             "autor": autor if (seg or 0) >= MIN_PUBLICO else None, "seguidores_autor": seg,
                             "tem_compartilhamentos": post["ator"] == "reel",
                             # carrossel: o leitor de reels devolveu sharesCount 0 para um post com 230 mil curtidas (26/10/2026);
                             # número não confiável, então o compartilhamento só vale para reel
                             "serie": [{k: (x.get(k) if (k != "compartilhamentos" or post["ator"] == "reel") else None)
                                        for k in ("lido_em_utc", "origem", "reproducoes", "curtidas", "comentarios", "compartilhamentos")} for x in ls]})
    dest = root / "data/casos" / caso / "circulacao.json"
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(pub, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"circulação {caso}: " + " · ".join(f"{p['codigo']} {len(p['serie'])} leituras" for p in pub["posts"])
          + f" · coleta {'feita' if coletar else 'não feita'} · erros novos {len([e for e in est['erros'] if e.startswith(hoje)])}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
