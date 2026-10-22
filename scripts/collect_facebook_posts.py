#!/usr/bin/env python3
"""Posts públicos das páginas de Facebook declaradas ao TSE (chapas 13 e 22) via Apify (apify/facebook-posts-scraper).

Token SOMENTE por APIFY_TOKEN_2. Teto total autorizado em data/config/facebook_posts.json (soma dos manifestos);
custo de cada execução = maior entre o informado pela Apify e a estimativa pela tabela de preços do plano gratuito.

--teste: 10 posts de facebook.com/lula (teto de teste).
--diario: conta 1 (APIFY_TOKEN), posts desde o dia anterior, teto por dia e por mês em cfg["diario"] (autorizado em 22/10/2026);
          não consulta saldo da conta.
sem opção: uma execução por página (posts desde `desde`, até N por página), 3 em paralelo.

Saída pública: data/facebook/videos.csv.gz (mesmas colunas do acervo do TikTok/Kwai: video_id = id do post,
legenda = texto, visualizações quando o Facebook informa), data/facebook/manifesto-*.json e manifesto_latest.json.
Bruto no repositório privado (ODI_INTERNO_DIR/facebook/), quando houver.
"""
from __future__ import annotations

import csv
import gzip
import json
import os
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from collect_kwai_apify import COLS, g, inteiro, quando  # noqa: E402
from collect_meta_anuncios_apify import custo_run  # noqa: E402
from collect_meta_apify import escolher_conta, run_actor, saldo_conta  # noqa: E402
from net import now_utc  # noqa: E402

COLS_FB = COLS + ["reacoes", "tipo"]


def linha(x: dict, pag: dict, agora: str, old: dict) -> dict:
    pid = str(g(x, "postId", "id", "post_id") or "")
    reacoes = inteiro(g(x, "likes", "reactionsCount", "topReactionsCount", "reactions"))
    midia = x.get("media") if isinstance(x.get("media"), list) else []
    capa = g(x, "thumbnail", "full_picture", "image") or next((g(m, "thumbnail", "photo_image.uri", "image.uri") for m in midia if isinstance(m, dict)), "")
    return {"candidate_id": pag["candidate_id"], "candidate_name": pag["candidato"], "perfil": pag["perfil"], "declarado_por": pag["declarado_por"],
            "video_id": pid, "url": g(x, "url", "postUrl", "facebookUrl") or "", "publicado_em": quando(g(x, "time", "timestamp", "date", "createdAt")),
            "legenda": " ".join(str(g(x, "text", "message", "postText") or "").split()),
            "duracao_s": "", "visualizacoes": inteiro(g(x, "viewsCount", "videoViewCount", "views")),
            "curtidas": reacoes, "comentarios": inteiro(g(x, "comments", "commentsCount")), "compartilhamentos": inteiro(g(x, "shares", "sharesCount")),
            "primeira_coleta": old.get("primeira_coleta") or agora, "ultima_coleta": agora, "capa_url": capa or old.get("capa_url", ""),
            "reacoes": reacoes, "tipo": "vídeo" if g(x, "viewsCount", "videoViewCount") is not None or g(x, "isVideo") else "post"}


def main(argv=None, executar=None) -> int:
    argv = list(argv or [])
    root = Path(".")
    cfg = json.loads((root / "data/config/facebook_posts.json").read_text(encoding="utf-8"))
    teste = "--teste" in argv
    lacuna = "--lacuna" in argv  # uma vez: cfg["lacuna"] (conta 1, desde fixo, teto próprio)
    diario = "--diario" in argv or lacuna
    pre = "--pre" in argv  # só a pré-campanha (de `desde` até `pre_ate`), sem repetir os posts já coletados da campanha
    pasta = root / "data/facebook"
    pasta.mkdir(parents=True, exist_ok=True)
    agora = now_utc()
    mans = [json.loads(f.read_text(encoding="utf-8")) for f in pasta.glob("manifesto-*.json")]
    desde = cfg["desde"]
    if diario:
        import datetime as dt
        D = cfg["diario"]
        if lacuna:
            L = cfg["lacuna"]
            desde = L["desde"]
            ja = round(sum(float(m.get("custo_usd") or 0) for m in mans if m.get("modo") == "lacuna" and m.get("desde") == desde), 4)
            teto = round(L["teto_usd"] - ja, 4)
        else:
            ontem = (dt.datetime.now(dt.timezone(dt.timedelta(hours=-3))) - dt.timedelta(days=1)).date().isoformat()
            desde = ontem
            ja = round(sum(float(m.get("custo_usd") or 0) for m in mans if m.get("modo") == "diário" and (m.get("run_started_utc") or "")[:7] == agora[:7]), 4)
            teto = round(min(D["teto_dia_usd"], D["teto_mes_usd"] - ja), 4)
    else:
        ja = round(sum(float(m.get("custo_usd") or 0) for m in mans if m.get("modo") not in ("diário", "lacuna")), 4)
        resta = round(cfg["teto_total_usd"] - ja, 4)
        teto = min(cfg["teto_teste_usd"], resta) if teste else resta
    man = {"run_started_utc": agora, "ferramenta": f"Apify · {cfg['ator'].replace('~', '/')}",
           "modo": "lacuna" if lacuna else "diário" if diario else "teste" if teste else "pré-campanha" if pre else "carga",
           "teto_total_usd": cfg["lacuna"]["teto_usd"] if lacuna else cfg["diario"]["teto_mes_usd"] if diario else cfg["teto_total_usd"], "gasto_antes_usd": ja, "teto_execucao_usd": teto,
           "desde": desde, "paginas": []}

    def fim(status: str, code: int) -> int:
        man["status"] = status
        stamp = agora.replace(":", "").replace("-", "")
        for nome in (f"manifesto-{stamp}.json", "manifesto_latest.json"):
            (pasta / nome).write_text(json.dumps(man, ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"facebook: {status}")
        return code

    segredos = cfg.get("segredos") or [cfg["segredo"]]
    if diario:  # conta 1 autorizada; sem consulta de saldo
        nome_conta, token, saldo = cfg["diario"]["segredo"], os.environ.get(cfg["diario"]["segredo"], "").strip(), None
        if executar is not None:
            token = "x"
    else:
        nome_conta, token, saldo = escolher_conta(segredos, 0.1) if executar is None else ("teste", "x", None)
    man["conta"] = nome_conta
    if not token and executar is None:
        return fim(f"⛔ nenhuma conta Apify disponível ({nome_conta if diario else ', '.join(segredos)})", 1)
    if teto < 0.01:
        return fim(f"⛔ teto autorizado esgotado (gasto US$ {ja}, teto US$ {man['teto_total_usd']})", 1)
    if executar is None and not diario:
        man["saldo_conta_antes_usd"] = saldo
        if saldo is not None:
            teto = min(teto, saldo)
            if teto < 0.05:
                return fim(f"⛔ saldo da conta Apify esgotado (US$ {saldo})", 1)
    executar = executar or (lambda pl, cap: run_actor(token, cfg["ator"], pl, cap))
    p = cfg["preco_usd"]
    if teste:
        alvos = [(next(x for x in cfg["paginas"] if x["url"] == cfg["teste"]["pagina"]), cfg["teste"]["posts"])]
    else:
        alvos, est = [], 0.0
        cota = cfg["lacuna"]["posts_por_pagina"] if lacuna else cfg["diario"]["posts_por_pagina"] if diario else cfg["posts_por_pagina_pre"] if pre else cfg["posts_por_pagina"]
        for pg in cfg["paginas"]:
            n = cota["principal" if pg.get("principal") else "outras"]
            if not n:
                continue
            if diario:
                alvos.append((pg, n))
                continue
            c = p["inicio"] + p["post"] * n
            if est + c > teto:
                n = int((teto - est - p["inicio"]) / p["post"])
                if n < 5:
                    break
                c = p["inicio"] + p["post"] * n
            alvos.append((pg, n))
            est += c

    def um(a):
        pg, n = a
        pl = {"startUrls": [{"url": pg["url"]}], "resultsLimit": n, "onlyPostsNewerThan": desde}
        try:
            run, itens = executar(pl, round(p["inicio"] + p["post"] * n * 1.05 + 0.002, 4))
            return pg, n, run or {}, itens or [], None
        except Exception as e:  # noqa: BLE001 — o token vai no cabeçalho
            return pg, n, {}, [], f"{type(e).__name__} {getattr(e, 'code', '')}".strip()
    if diario:
        # uma página por vez: o teto de cada página é o que sobra do dia, pelo custo real das anteriores
        res, sobra = [], teto
        for pg, n in sorted(alvos, key=lambda a: not a[0].get("principal")):
            n = min(n, int((sobra - p["inicio"]) / p["post"] / 1.05))
            if n < 1:
                res.append((pg, 0, {}, [], f"teto {'da lacuna' if lacuna else 'do dia'} de US$ {teto} atingido (não executado)"))
                continue
            r = um((pg, n))
            res.append(r)
            sobra -= max(custo_run(r[2]) or 0, round((p["inicio"] if r[2] else 0) + p["post"] * len(r[3]), 4))
    else:
        with ThreadPoolExecutor(max_workers=3) as ex:
            res = list(ex.map(um, alvos))
    interno = os.environ.get("ODI_INTERNO_DIR")
    src = pasta / "videos.csv.gz"
    acervo = {r["video_id"]: r for r in csv.DictReader(gzip.open(src, "rt", encoding="utf-8"), delimiter=";")} if src.exists() else {}
    gasto, novos, brutos = 0.0, 0, []
    for pg, n, run, itens, erro in res:
        posts = [x for x in itens if g(x, "postId", "id") and not x.get("error")]
        brutos += itens
        custo = max(custo_run(run) or 0, round((p["inicio"] if run else 0) + p["post"] * len(posts), 4))
        gasto += custo
        for x in posts:
            r = linha(x, pg, agora, acervo.get(str(g(x, "postId", "id"))) or {})
            if r["video_id"] and (r["publicado_em"] or "9") >= cfg["desde"]:
                novos += 0 if r["video_id"] in acervo else 1
                acervo[r["video_id"]] = r
        man["paginas"].append({"perfil": pg["perfil"], "url": pg["url"], "candidato": pg["candidato"], "pedido": n, "lidos": len(posts),
                               "erro": erro or next((str(x.get("error"))[:200] for x in itens if x.get("error")), None),
                               "mais_antigo": min((quando(g(x, "time", "timestamp")) for x in posts), default=None),
                               "run": run.get("id"), "custo_usd": custo, "eventos_cobrados": run.get("chargedEventCounts")})
        print(f"{pg['perfil']}: {len(posts)} posts de {n} pedidos{' · ' + erro if erro else ''} · US$ {custo}")
    if interno and brutos:
        d = Path(interno) / "facebook"
        d.mkdir(parents=True, exist_ok=True)
        with gzip.open(d / f"apify_{agora.replace(':', '').replace('-', '')}.jsonl.gz", "wt", encoding="utf-8") as f:
            for x in brutos:
                f.write(json.dumps(x, ensure_ascii=False) + "\n")
    with gzip.open(src, "wt", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, COLS_FB, delimiter=";", lineterminator="\n", extrasaction="ignore")
        w.writeheader()
        w.writerows(sorted(acervo.values(), key=lambda r: (r["candidate_id"], r["publicado_em"]), reverse=True))
    man.update(custo_usd=round(gasto, 4), posts_novos=novos, posts_no_acervo=len(acervo))
    if brutos:
        print("chaves do 1º item: " + ", ".join(sorted(brutos[0].keys()))[:900])
    print(f"{novos} posts novos · acervo {len(acervo)} · custo US$ {round(gasto, 4)} · teto {teto}")
    return fim("ok" if acervo else "⛔ nenhum post lido", 0 if acervo else 1)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
