#!/usr/bin/env python3
"""Posts públicos dos perfis de X declarados ao TSE (chapas 13 e 22) via Apify (apidojo/tweet-scraper).

Contas: a primeira da lista `segredos` com saldo (data/config/x_posts.json); a conta 1 (principal) não é usada.
Teto total da fonte em x_posts.json (soma dos manifestos); custo = maior entre o informado pela Apify e a tabela.

--teste: 20 posts de @LulaOficial (teto de teste).
sem opção: uma execução por perfil (posts desde `desde`, até N), 3 em paralelo.

Saída pública: data/x/videos.csv.gz (mesmas colunas do TikTok/Kwai/Facebook: video_id = id do post, legenda = texto),
data/x/manifesto-*.json, e seguidores de cada perfil (do próprio post) em data/seguidores/x_latest.csv e x_AAAA-MM-DD.csv
(URL declarada ao TSE, para casar com o card). Bruto no repositório privado (ODI_INTERNO_DIR/x/).
"""
from __future__ import annotations

import csv
import datetime as dt
import gzip
import json
import os
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from collect_kwai_apify import COLS, g, inteiro  # noqa: E402
from collect_meta_anuncios_apify import custo_run  # noqa: E402
from collect_meta_apify import escolher_conta, run_actor  # noqa: E402
from net import now_utc  # noqa: E402


def quando(v) -> str:
    """createdAt do X ('Wed Oct 15 12:00:00 +0000 2026') ou ISO → ISO UTC."""
    s = str(v or "")
    for f in ("%a %b %d %H:%M:%S %z %Y", "%Y-%m-%dT%H:%M:%S.%fZ", "%Y-%m-%dT%H:%M:%SZ"):
        try:
            d = dt.datetime.strptime(s, f)
            d = d if d.tzinfo else d.replace(tzinfo=dt.timezone.utc)
            return d.astimezone(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        except ValueError:
            continue
    return s


def autor(x: dict) -> str:
    return str(g(x, "author.userName", "author.username", "author.screen_name", "user.screen_name", "user.username", "username") or "")


def seguidores_de(x: dict):
    return g(x, "author.followers", "author.followersCount", "author.followers_count", "user.followers_count", "author.public_metrics.followers_count")


def linha(x: dict, pf: dict, agora: str, old: dict) -> dict:
    tid = str(g(x, "id", "id_str", "tweetId") or "")
    rt = inteiro(g(x, "retweetCount", "retweet_count", "public_metrics.retweet_count")) or 0
    qt = inteiro(g(x, "quoteCount", "quote_count", "public_metrics.quote_count")) or 0
    midia = (g(x, "extendedEntities.media") or g(x, "entities.media") or [])
    capa = next((m.get("media_url_https") for m in midia if isinstance(m, dict) and m.get("media_url_https")), "") if isinstance(midia, list) else ""
    return {"candidate_id": pf["candidate_id"], "candidate_name": pf["candidato"], "perfil": pf["handle"], "declarado_por": pf["declarado_por"],
            "video_id": tid, "url": g(x, "url", "twitterUrl") or f"https://x.com/{pf['handle']}/status/{tid}",
            "publicado_em": quando(g(x, "createdAt", "created_at", "date")), "legenda": " ".join(str(g(x, "fullText", "text") or "").split()),
            "duracao_s": "", "visualizacoes": inteiro(g(x, "viewCount", "views", "view_count", "public_metrics.impression_count")),
            "curtidas": inteiro(g(x, "likeCount", "favoriteCount", "favorite_count", "public_metrics.like_count")),
            "comentarios": inteiro(g(x, "replyCount", "reply_count", "public_metrics.reply_count")), "compartilhamentos": rt + qt,
            "primeira_coleta": old.get("primeira_coleta") or agora, "ultima_coleta": agora, "capa_url": capa or old.get("capa_url", "")}


def main(argv=None, executar=None) -> int:
    argv = list(argv or [])
    root = Path(".")
    cfg = json.loads((root / "data/config/x_posts.json").read_text(encoding="utf-8"))
    teste = "--teste" in argv
    pasta = root / "data/x"
    pasta.mkdir(parents=True, exist_ok=True)
    agora = now_utc()
    ja = round(sum(float(json.loads(f.read_text(encoding="utf-8")).get("custo_usd") or 0) for f in pasta.glob("manifesto-*.json")), 4)
    teto = min(cfg["teto_teste_usd"], cfg["teto_total_usd"] - ja) if teste else round(cfg["teto_total_usd"] - ja, 4)
    man = {"run_started_utc": agora, "ferramenta": f"Apify · {cfg['ator'].replace('~', '/')}", "modo": "teste" if teste else "carga",
           "teto_total_usd": cfg["teto_total_usd"], "gasto_antes_usd": ja, "teto_execucao_usd": teto, "perfis": []}

    def fim(status: str, code: int) -> int:
        man["status"] = status
        stamp = agora.replace(":", "").replace("-", "")
        for nome in (f"manifesto-{stamp}.json", "manifesto_latest.json"):
            (pasta / nome).write_text(json.dumps(man, ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"x: {status}")
        return code

    if teto < 0.01:
        return fim(f"⛔ teto de US$ {cfg['teto_total_usd']} esgotado (gasto US$ {ja})", 1)
    nome_conta, token, saldo = escolher_conta(cfg["segredos"], min(teto, 0.5)) if executar is None else ("teste", "x", None)
    man.update(conta=nome_conta, saldo_conta_antes_usd=saldo)
    if not token:
        return fim(f"⛔ nenhuma conta Apify com saldo entre {', '.join(cfg['segredos'])}", 1)
    if saldo is not None:
        teto = min(teto, saldo)
    executar = executar or (lambda pl, cap: run_actor(token, cfg["ator"], pl, cap))
    p = cfg["preco_usd"]
    if teste:
        alvos = [(next(x for x in cfg["perfis"] if x["handle"] == cfg["teste"]["perfil"]), cfg["teste"]["posts"])]
    else:
        alvos, est = [], 0.0
        for pf in cfg["perfis"]:
            n = cfg["posts_por_perfil"]["principal" if pf.get("principal") else "outras"]
            n = min(n, int((teto - est) / p["post"]))
            if n < 10:
                break
            alvos.append((pf, n))
            est += p["post"] * n

    def um(a):
        pf, n = a
        pl = ({"twitterHandles": [pf["handle"]], "maxItems": n, "maxItemsPerTarget": n} if "xquik" in cfg["ator"]
              else {"twitterHandles": [pf["handle"]], "start": cfg["desde"], "maxItems": n, "sort": "Latest"})
        try:
            run, itens = executar(pl, round(p["post"] * n * 1.05 + 0.01, 4))
            return pf, n, run or {}, itens or [], None
        except Exception as e:  # noqa: BLE001 — o token vai no cabeçalho
            return pf, n, {}, [], f"{type(e).__name__} {getattr(e, 'code', '')}".strip()
    with ThreadPoolExecutor(max_workers=3) as ex:
        res = list(ex.map(um, alvos))
    src = pasta / "videos.csv.gz"
    acervo = {r["video_id"]: r for r in csv.DictReader(gzip.open(src, "rt", encoding="utf-8"), delimiter=";")} if src.exists() else {}
    gasto, novos, brutos, seguidores = 0.0, 0, [], {}
    for pf, n, run, itens, erro in res:
        posts = [x for x in itens if g(x, "id", "id_str", "tweetId") and not x.get("noResults") and str(g(x, "type") or "tweet").lower() in ("tweet", "post")]
        brutos += itens
        meus = [x for x in posts if autor(x).lower() == pf["handle"].lower() and not g(x, "isRetweet", "retweeted_status")]  # reposts ficam fora
        custo = max(custo_run(run) or 0, round(p["post"] * len(itens), 4))
        gasto += custo
        for x in meus:
            r = linha(x, pf, agora, acervo.get(str(g(x, "id", "tweetId"))) or {})
            if r["video_id"] and (r["publicado_em"] or "9") >= cfg["desde"]:
                novos += 0 if r["video_id"] in acervo else 1
                acervo[r["video_id"]] = r
        fol = next((inteiro(seguidores_de(x)) for x in posts if autor(x).lower() == pf["handle"].lower() and seguidores_de(x) is not None), None)
        if fol not in (None, ""):
            seguidores[pf["handle"]] = fol
        man["perfis"].append({"perfil": pf["handle"], "candidato": pf["candidato"], "pedido": n, "itens": len(itens), "lidos": len(meus),
                              "erro": erro or next((str(x.get("noResults") or x.get("error"))[:120] for x in itens if x.get("noResults") or x.get("error")), None),
                              "seguidores": fol, "mais_antigo": min((quando(g(x, "createdAt")) for x in meus), default=None),
                              "run": run.get("id"), "custo_usd": custo, "eventos_cobrados": run.get("chargedEventCounts")})
        print(f"@{pf['handle']}: {len(meus)} posts próprios de {len(itens)} itens (pedidos {n}) · seguidores {fol}{' · ' + erro if erro else ''} · US$ {custo}")
    interno = os.environ.get("ODI_INTERNO_DIR")
    if interno and brutos:
        d = Path(interno) / "x"
        d.mkdir(parents=True, exist_ok=True)
        with gzip.open(d / f"apify_{agora.replace(':', '').replace('-', '')}.jsonl.gz", "wt", encoding="utf-8") as f:
            for x in brutos:
                f.write(json.dumps(x, ensure_ascii=False) + "\n")
    with gzip.open(src, "wt", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, COLS, delimiter=";", lineterminator="\n", extrasaction="ignore")
        w.writeheader()
        w.writerows(sorted(acervo.values(), key=lambda r: (r["candidate_id"], r["publicado_em"]), reverse=True))
    if seguidores:
        seg = root / "data/seguidores"
        seg.mkdir(parents=True, exist_ok=True)
        cols = ["candidate_id", "candidate_name", "platform", "url", "followers", "captured_at", "source_url"]
        por = {pf["handle"]: pf for pf in cfg["perfis"]}
        for nome in (f"x_{agora[:10]}.csv", "x_latest.csv"):
            with open(seg / nome, "w", encoding="utf-8", newline="") as f:
                w = csv.DictWriter(f, cols, delimiter=";", lineterminator="\n")
                w.writeheader()
                for h, n in sorted(seguidores.items()):
                    w.writerow({"candidate_id": por[h]["candidate_id"], "candidate_name": por[h]["declarado_por"], "platform": "X / Twitter",
                                "url": por[h]["url_tse"], "followers": n, "captured_at": agora[:10], "source_url": f"https://x.com/{h}"})
    man.update(custo_usd=round(gasto, 4), posts_novos=novos, posts_no_acervo=len(acervo))
    if brutos:
        print("chaves do 1º item: " + ", ".join(sorted(brutos[0].keys()))[:900])
    print(f"{novos} posts novos · acervo {len(acervo)} · custo US$ {round(gasto, 4)} · teto {teto}")
    return fim("ok" if acervo else "⛔ nenhum post lido", 0 if acervo else 1)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
