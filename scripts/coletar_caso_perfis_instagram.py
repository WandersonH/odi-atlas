#!/usr/bin/env python3
"""Coleta, para um caso, os posts recentes de perfis do Instagram e uma amostra dos comentários desses posts (conta 1, teto obrigatório).

Pedido do responsável (27/10/2026, 01h58): caso 010, "adicione o instagram" à coleta de brasileiros nos perfis de Donald Trump e
Marco Rubio; teto escolhido: US$ 2,50. Duas execuções, cada uma limitada pelo que sobra do teto:
  1. apify/instagram-scraper (directUrls dos perfis, resultsType posts, onlyPostsNewerThan): os posts do período (US$ 0,0026 cada);
  2. datadoping/instagram-comments-and-replies-scraper: comentários de todos os posts numa execução, a mesma quantidade por post,
     ordem "popular" (US$ 1,40 por mil, custo real dos casos 008 e 009). O ator não filtra idioma: o português é separado na análise.
Os resultados são lidos em páginas (a leitura de uma vez deu IncompleteRead nos casos 008 e 009).
Saída só no privado: ODI_INTERNO_DIR/casos/<caso>/instagram/<run>.json e manifesto.json. Público: data/casos/<caso>/instagram_coleta.json
(contagens, sem texto nem autor).
Uso: python scripts/coletar_caso_perfis_instagram.py --caso 010 --perfis realdonaldtrump,marcorubio,secrubio --desde 2026-10-24 --teto 2.5
"""
from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from collect_meta_apify import api  # noqa: E402
from importar_apify_runs import paginas  # noqa: E402
from net import now_utc  # noqa: E402

PRECO_POST = 0.0026
PRECO_COMENTARIO = 1.40 / 1000
MIN_CAP = 0.10


def arg(argv, k, d=None):
    return argv[argv.index(k) + 1] if k in argv else d


def rodar(token: str, ator: str, entrada: dict, cap: float, chamar=api, espera=time.sleep) -> tuple[dict, list]:
    run = chamar("POST", f"/acts/{ator}/runs?waitForFinish=60&maxTotalChargeUsd={cap}", token, entrada)["data"]
    while run.get("status") in ("READY", "RUNNING"):
        espera(20)
        run = chamar("GET", f"/actor-runs/{run['id']}?waitForFinish=60", token)["data"]
    return run, paginas(chamar, token, run["defaultDatasetId"])


def custo(run: dict) -> float:
    return float(run.get("usageTotalUsd") or 0)


def coletar(caso: str, perfis: list[str], desde: str, teto: float, priv: Path, executar) -> dict:
    priv.mkdir(parents=True, exist_ok=True)
    man = {"caso": caso, "inicio_utc": now_utc(), "perfis": perfis, "desde": desde, "teto_usd": teto, "runs": [], "erros": []}
    gasto = 0.0

    def gravar(ator, entrada, run, itens):
        reg = {"run_id": run.get("id"), "ator": ator, "status": run.get("status"), "inicio_utc": run.get("startedAt"),
               "fim_utc": run.get("finishedAt"), "custo_usd": custo(run), "itens": len(itens)}
        (priv / f"{run.get('id')}.json").write_text(json.dumps({**reg, "input": entrada, "items": itens}, ensure_ascii=False), encoding="utf-8")
        man["runs"].append(reg)

    e1 = {"directUrls": [f"https://www.instagram.com/{p}/" for p in perfis], "resultsType": "posts", "resultsLimit": 15,
          "onlyPostsNewerThan": desde, "addParentData": False}
    cap1 = round(min(max(MIN_CAP, PRECO_POST * 15 * len(perfis) * 1.3), teto), 2)
    try:
        run, posts = executar("apify~instagram-scraper", e1, cap1)
        gasto += max(custo(run), PRECO_POST * len(posts))
        gravar("apify/instagram-scraper", e1, run, posts)
    except Exception as e:  # noqa: BLE001 — a mensagem da API não contém o token
        man["erros"].append(f"posts: {type(e).__name__} {getattr(e, 'code', '')}".strip())
        posts = []
    posts = [p for p in posts if p.get("url") and (p.get("timestamp") or "") >= desde]
    man["posts"] = [{"perfil": p.get("ownerUsername"), "url": p.get("url"), "publicado_utc": p.get("timestamp"), "tipo": p.get("type"),
                     "curtidas": p.get("likesCount"), "comentarios": p.get("commentsCount"), "legenda": (p.get("caption") or "")[:300]} for p in posts]
    sobra = teto - gasto - 0.01
    n_total = int(sobra / PRECO_COMENTARIO)
    if posts and n_total >= 50 and sobra >= MIN_CAP:
        por_post = max(20, n_total // len(posts))
        e2 = {"code_or_id_or_url": [p["url"] for p in posts], "sort_by": "popular", "max_comments": por_post, "scrape_replies": False, "max_replies": 20}
        man["comentarios_pedidos_por_post"] = por_post
        try:
            run, coms = executar("datadoping~instagram-comments-and-replies-scraper", e2, round(sobra, 2))
            gasto += max(custo(run), 0.0)
            gravar("datadoping/instagram-comments-and-replies-scraper", e2, run, coms)
        except Exception as e:  # noqa: BLE001
            man["erros"].append(f"comentários: {type(e).__name__} {getattr(e, 'code', '')}".strip())
    man.update(fim_utc=now_utc(), gasto_usd=round(gasto, 4), dentro_do_teto=gasto <= teto + 1e-9)
    (priv / "manifesto.json").write_text(json.dumps(man, ensure_ascii=False, indent=1), encoding="utf-8")
    return man


def main(argv=None, executar=None) -> int:
    argv = sys.argv[1:] if argv is None else list(argv)
    caso, teto, desde = arg(argv, "--caso"), arg(argv, "--teto"), arg(argv, "--desde")
    perfis = [p.strip().lstrip("@") for p in (arg(argv, "--perfis") or "").split(",") if p.strip()]
    interno = os.environ.get("ODI_INTERNO_DIR")
    token = os.environ.get("APIFY_TOKEN", "").strip()
    if not (caso and teto and desde and perfis and interno and (token or executar)):
        print("⛔ faltam --caso, --perfis, --desde, --teto, ODI_INTERNO_DIR ou APIFY_TOKEN (o teto é obrigatório)")
        return 1
    executar = executar or (lambda ator, pl, cap: rodar(token, ator, pl, cap))
    man = coletar(caso, perfis, desde, float(teto), Path(interno) / f"casos/{caso}/instagram", executar)
    pub = Path("data/casos") / caso
    pub.mkdir(parents=True, exist_ok=True)
    resumo = {k: man.get(k) for k in ("caso", "inicio_utc", "fim_utc", "perfis", "desde", "comentarios_pedidos_por_post", "erros")}
    resumo["runs"] = [{k: r[k] for k in ("run_id", "ator", "status", "itens")} for r in man["runs"]]
    resumo["posts"] = [{k: p[k] for k in ("perfil", "url", "publicado_utc", "tipo", "curtidas", "comentarios")} for p in man.get("posts", [])]
    (pub / "instagram_coleta.json").write_text(json.dumps(resumo, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"caso {caso} Instagram: {len(man.get('posts', []))} posts · itens por execução {[r['itens'] for r in man['runs']]} · "
          f"dentro do teto: {man['dentro_do_teto']} · erros {man['erros']}")
    return 0 if man["runs"] else 1


if __name__ == "__main__":
    sys.exit(main())
