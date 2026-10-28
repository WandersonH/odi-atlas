#!/usr/bin/env python3
"""Casos e análises: tudo o que foi publicado com as hashtags, menções e termos de cada caso, em cada rede.

Configuração: data/config/casos.json (um bloco por caso: termos, janela, teto por rede). Só casos com `coletar: true`.
Redes e ferramentas:
- tiktok: página pública da hashtag num navegador sem login (Playwright; grátis), mesma leitura do coletor de hashtags;
- x: Apify xquik/x-tweet-scraper, busca do próprio X (hashtags, menções, "from:" do perfil do caso);
- instagram: Apify apidojo/instagram-hashtag-scraper (página da hashtag) e esdrasdw/instagram-content-scraper (perfil do caso);
- facebook: Apify scrapeforge/facebook-search-posts (busca de posts);
- kwai: Apify unfenced-group/kwai-scraper (feed da hashtag).
Contas dos outros pesquisadores (a conta 1 não é usada). Teto por rede e por caso, somado pelos manifestos.

Privacidade: publicações de qualquer pessoa. O arquivo completo (com contas e textos) vai SÓ para o repositório privado
(ODI_INTERNO_DIR/casos/<id>/itens.csv.gz); sem o privado, fica num temporário e só os agregados são gerados.

--caso ID (padrão: todos os ativos) · --rede R (repetível) · --teste (1 termo por rede, 10 itens) ·
--complemento (só as buscas de `complementos_x`: a busca do X devolve os mais recentes primeiro e, no limite, corta o começo).
Saída pública: data/casos/<id>/manifesto-*.json. Os agregados da página saem de build_casos.py.
"""
from __future__ import annotations

import asyncio
import csv
import datetime as dt
import gzip
import json
import os
import sys
import tempfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from collect_kwai_apify import g, inteiro, quando  # noqa: E402
from collect_meta_anuncios_apify import custo_run  # noqa: E402
from collect_meta_apify import escolher_conta, run_actor  # noqa: E402
from net import now_utc  # noqa: E402

REDES = ("tiktok", "x", "instagram", "facebook", "kwai", "google")
COLS = ["rede", "item_id", "conta", "nome_conta", "seguidores", "verificada", "publicado_em", "texto", "visualizacoes", "curtidas",
        "comentarios", "compartilhamentos", "termo", "url", "capa_url", "coletado_em"]
ATOR = {"x": "xquik~x-tweet-scraper", "instagram": "apify~instagram-hashtag-scraper", "instagram_palavra": "apidojo~instagram-hashtag-scraper",
        "tiktok_apify": "novi~multiple-tiktok-hashtag-scraper", "instagram_perfil": "esdrasdw~instagram-content-scraper",
        "facebook": "scrapeforge~facebook-search-posts", "kwai": "unfenced-group~kwai-scraper", "tiktok_busca": "apidojo~tiktok-scraper"}


def iso(v) -> str:
    """Datas em formatos variados (ISO, epoch em s ou ms, data do X) → ISO UTC."""
    if v in (None, ""):
        return ""
    s = str(v)
    if s.isdigit():
        n = int(s)
        n = n // 1000 if n > 10**11 else n
        return dt.datetime.fromtimestamp(n, dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    for f in ("%a %b %d %H:%M:%S %z %Y",):
        try:
            return dt.datetime.strptime(s, f).astimezone(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        except ValueError:
            pass
    return quando(s)


def norm(rede: str, x: dict, termo: str, agora: str) -> dict | None:
    """Item bruto de qualquer ator → linha comum. None para itens sem id (perfil, erro, demonstração)."""
    if x.get("demo") or x.get("error") or x.get("noResults"):
        return None
    if rede == "x":
        iid = g(x, "id", "id_str", "tweetId")
        conta = g(x, "author.userName", "author.username", "user.screen_name")
        return iid and {"rede": rede, "item_id": str(iid), "conta": conta or "", "nome_conta": g(x, "author.name", "user.name") or "",
                        "seguidores": inteiro(g(x, "author.followers", "author.followersCount", "user.followers_count")),
                        "verificada": int(bool(g(x, "author.isBlueVerified", "author.isVerified", "author.verified"))),
                        "publicado_em": iso(g(x, "createdAt", "created_at")), "texto": " ".join(str(g(x, "fullText", "text") or "").split()),
                        "visualizacoes": inteiro(g(x, "viewCount", "views")), "curtidas": inteiro(g(x, "likeCount", "favoriteCount")),
                        "comentarios": inteiro(g(x, "replyCount")), "compartilhamentos": (inteiro(g(x, "retweetCount")) or 0) + (inteiro(g(x, "quoteCount")) or 0),
                        "termo": termo, "url": g(x, "url", "twitterUrl") or (f"https://x.com/{conta}/status/{iid}" if conta else ""),
                        "capa_url": "", "coletado_em": agora}
    if rede == "tiktok":
        iid = g(x, "id", "aweme_id", "video_id", "videoId")
        conta = g(x, "author.uniqueId", "author.unique_id", "authorMeta.name", "author.username", "author")
        conta = conta if isinstance(conta, str) else ""
        return iid and {"rede": rede, "item_id": str(iid), "conta": conta, "nome_conta": g(x, "author.nickname", "authorMeta.nickName") or "",
                        "seguidores": inteiro(g(x, "authorStats.followerCount", "author.follower_count", "authorMeta.fans", "author.followerCount")),
                        "verificada": int(bool(g(x, "author.verified", "authorMeta.verified"))),
                        "publicado_em": iso(g(x, "createTime", "create_time", "createTimeISO", "timestamp")),
                        "texto": " ".join(str(g(x, "desc", "text", "description") or "").split()),
                        "visualizacoes": inteiro(g(x, "stats.playCount", "statistics.play_count", "playCount")),
                        "curtidas": inteiro(g(x, "stats.diggCount", "statistics.digg_count", "diggCount")),
                        "comentarios": inteiro(g(x, "stats.commentCount", "statistics.comment_count", "commentCount")),
                        "compartilhamentos": inteiro(g(x, "stats.shareCount", "statistics.share_count", "shareCount")), "termo": termo,
                        "url": g(x, "webVideoUrl", "share_url", "url") or (f"https://www.tiktok.com/@{conta}/video/{iid}" if conta else ""),
                        "capa_url": "", "coletado_em": agora}
    if rede == "instagram":
        iid = g(x, "code", "shortCode", "shortcode", "id")
        conta = g(x, "owner.username", "ownerUsername", "user.username", "username")
        return iid and {"rede": rede, "item_id": str(iid), "conta": conta or "", "nome_conta": g(x, "owner.fullName", "ownerFullName", "owner.full_name") or "",
                        "seguidores": inteiro(g(x, "owner.followerCount", "owner.followersCount", "owner.follower_count")),
                        "verificada": int(bool(g(x, "owner.isVerified", "owner.is_verified"))),
                        "publicado_em": iso(g(x, "createdAt", "timestamp", "takenAt", "taken_at")),
                        "texto": " ".join(str(g(x, "caption", "caption.text", "text") or "").split()),
                        "visualizacoes": inteiro(g(x, "video.playCount", "videoPlayCount", "playCount", "viewCount")),
                        "curtidas": inteiro(g(x, "likeCount", "likesCount")), "comentarios": inteiro(g(x, "commentCount", "commentsCount")),
                        "compartilhamentos": inteiro(g(x, "shareCount", "reshareCount")), "termo": termo,
                        "url": g(x, "url") or f"https://www.instagram.com/p/{iid}/", "capa_url": g(x, "image.url", "displayUrl", "thumbnailUrl") or "",
                        "coletado_em": agora}
    if rede == "facebook":
        iid = g(x, "post_id", "postId", "id")
        return iid and {"rede": rede, "item_id": str(iid), "conta": g(x, "author.name", "author_name", "user.name", "pageName") or "",
                        "nome_conta": g(x, "author.name", "author_name", "user.name") or "", "seguidores": inteiro(g(x, "author.followers", "page_followers")),
                        "verificada": int(bool(g(x, "author.verified", "author.is_verified"))), "publicado_em": iso(g(x, "timestamp", "time", "date", "created_time", "creation_time")),
                        "texto": " ".join(str(g(x, "message", "text", "post_text") or "").split()), "visualizacoes": inteiro(g(x, "video_view_count", "views")),
                        "curtidas": inteiro(g(x, "reactions_count", "reactions.total", "likes", "reactionsCount")),
                        "comentarios": inteiro(g(x, "comments_count", "commentsCount", "comments")), "compartilhamentos": inteiro(g(x, "reshare_count", "shares_count", "shares")),
                        "termo": termo, "url": g(x, "url", "post_url", "link") or "", "capa_url": g(x, "image.uri", "image", "thumbnail") or "", "coletado_em": agora}
    if rede == "kwai":
        if str(g(x, "type", "recordType", "kind") or "video").lower() in ("profile", "user", "creator"):
            return None
        iid = g(x, "videoId", "video_id", "photoId", "id")
        conta = g(x, "authorHandle", "author.handle", "author.username", "creator.handle", "handle", "username")
        return iid and {"rede": rede, "item_id": str(iid), "conta": conta or "", "nome_conta": g(x, "authorName", "author.name", "creator.name") or "",
                        "seguidores": inteiro(g(x, "authorFollowers", "author.followers", "author.followerCount", "creator.followers")),
                        "verificada": int(bool(g(x, "author.verified", "creator.verified"))),
                        "publicado_em": iso(g(x, "uploadTime", "createTime", "timestamp", "publishedAt", "postedAt")),
                        "texto": " ".join(str(g(x, "caption", "description", "title") or "").split()),
                        "visualizacoes": inteiro(g(x, "viewCount", "views", "playCount", "stats.views")), "curtidas": inteiro(g(x, "likeCount", "likes", "stats.likes")),
                        "comentarios": inteiro(g(x, "commentCount", "comments", "stats.comments")), "compartilhamentos": inteiro(g(x, "shareCount", "shares", "stats.shares")),
                        "termo": termo, "url": g(x, "url", "videoUrl", "shareUrl") or "", "capa_url": g(x, "coverUrl", "thumbnail", "cover") or "", "coletado_em": agora}
    raise ValueError(rede)


def pedidos(rede: str, caso: dict, n: int) -> list[tuple[str, str, dict]]:
    """[(termo, ator, entrada)] de uma rede para o caso."""
    d, tags = caso["desde"], caso.get("hashtags", [])
    out = []
    if caso.get("_so_frases"):
        # 28/10/2026 (caso 014): buscas por frase no Facebook e no Kwai e hashtags extras no Instagram, sem repetir as hashtags já coletadas
        if rede == "instagram":
            return [(f"#{t}", ATOR["instagram"], {"hashtags": [t], "resultsType": "posts", "resultsLimit": n}) for t in caso.get("hashtags_instagram", [])]
        if rede == "facebook":
            return [(q, ATOR["facebook"], {"query": q, "search_type": "posts", "max_results": n, "start_date": d, "recent_posts": False}) for q in caso.get("buscas_facebook", [])]
        if rede == "kwai":
            return [(q, ATOR["kwai"], {"searchTerms": [q], "expandSearchWithHashtag": False, "maxItems": n, "postedAfter": d}) for q in caso.get("buscas_kwai", [])]
        return []
    if rede == "x" and caso.get("_so_complemento"):
        return [(c["termo"], ATOR["x"], {"searchTerms": [c["busca"]], "maxItems": n, "queryType": "Latest"}) for c in caso.get("complementos_x", [])]
    if rede == "x":
        for t in tags:
            out.append((f"#{t}", ATOR["x"], {"searchTerms": [f"#{t} since:{d}"], "maxItems": n, "queryType": "Latest"}))
        for m in caso.get("mencoes_x", []):
            out.append((f"@{m}", ATOR["x"], {"searchTerms": [f"(@{m} OR from:{m}) since:{d}"], "maxItems": n, "queryType": "Latest"}))
    elif rede == "instagram":
        for t in tags:
            # "startUrls" com a página da hashtag devolveu 0 itens no teste de 18/10 (run 39131491525); a busca por palavra-chave é a entrada documentada
            # apidojo (palavra-chave) devolveu só 10 por hashtag na carga de 18/10 (run 39132035304); apify/instagram-hashtag-scraper lê o feed da hashtag
            out.append((f"#{t}", ATOR["instagram"], {"hashtags": [t], "resultsType": "posts", "resultsLimit": n}))
        for p in caso.get("perfis_instagram", []):
            out.append((f"@{p}", ATOR["instagram_perfil"], {"directUrls": [p], "resultsType": "posts", "resultsLimit": n, "onlyPostsNewerThan": d}))
    elif rede == "facebook":
        for t in tags:
            # com recent_posts=True a busca devolveu 5 por hashtag (runs de 18/10); sem ele, a busca geral do período
            out.append((f"#{t}", ATOR["facebook"], {"query": f"#{t}", "search_type": "posts", "max_results": n, "start_date": d, "recent_posts": False}))
    elif rede == "kwai":
        for t in tags:
            # o feed da hashtag não trouxe nada desde 16/10 (run 39132035304); busca por palavra completada com o feed da hashtag
            out.append((f"#{t}", ATOR["kwai"], {"searchTerms": [t], "expandSearchWithHashtag": True, "maxItems": n, "postedAfter": d}))
    elif rede == "tiktok":
        for q in caso.get("buscas_tiktok", []):  # busca por frase (como a caixa de busca do TikTok)
            out.append((q, ATOR["tiktok_busca"], {"keywords": [q], "maxItems": n}))
        for t in tags:
            out.append((f"#{t}", ATOR["tiktok_apify"], {"hashtags": [t], "region": "BR", "limit": n}))
    return out


def preco(rede: str, ator: str, cfg: dict) -> tuple[float, float]:
    p = cfg["precos_usd"][ator]
    return p.get("item", 0.0), p.get("consulta", 0.0)


def tiktok(caso: dict, teste: bool, agora: str) -> tuple[list[dict], dict]:
    import collect_tiktok_hashtags as th
    sub = {"hashtags": {"caso": caso.get("hashtags", [])[:1] if teste else caso.get("hashtags", [])}, "rolagens_por_hashtag": 2 if teste else caso.get("rolagens_tiktok", 25),
           "buscas": caso.get("buscas_tiktok", [])[:1] if teste else caso.get("buscas_tiktok", [])}
    brutos, resumo = asyncio.run(th.coletar(sub, agora))
    rows = [{"rede": "tiktok", "item_id": r["video_id"], "conta": r["conta"], "nome_conta": r["nome_conta"], "seguidores": r["seguidores"],
             "verificada": r["verificada"], "publicado_em": r["publicado_em"], "texto": r["legenda"], "visualizacoes": r["visualizacoes"],
             "curtidas": r["curtidas"], "comentarios": r["comentarios"], "compartilhamentos": r["compartilhamentos"],
             "termo": r["hashtag_coletada"] if r["lado_hashtag"] == "busca" else f"#{r['hashtag_coletada']}",
             "url": r["url"], "capa_url": "", "coletado_em": agora} for r in brutos]
    return rows, {"rede": "tiktok", "ferramenta": "página pública da hashtag (Playwright, sem login; grátis)", "termos": resumo, "custo_usd": 0.0}


def google(caso: dict, agora: str, pasta: Path) -> dict:
    """Google Trends (série por hora dos últimos 7 dias) e Google Notícias (títulos desde o início do caso). Grátis; público."""
    import urllib.parse
    from collect_google_busca import RSS, parse_rss
    from collect_trends import Trends
    from net import open_url, read_body
    from build_conteudo import norm as bc_norm
    man = {"rede": "google", "ferramenta": "Google Trends (endereços da própria página) e RSS do Google Notícias", "custo_usd": 0.0}
    out = {"coletado_em": agora, "trends": None, "noticias": []}
    termos = caso.get("termos_trends") or []
    if termos:
        try:
            t = Trends(pause=4)
            ws = {w["id"]: w for w in t.explore(termos[:5], "now 7-d", "BR")}
            ts = t.widget("multiline", ws["TIMESERIES"])
            pts = [{"t": dt.datetime.fromtimestamp(int(p["time"]), dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                    "v": dict(zip(termos, p.get("value") or []))} for p in ts["default"]["timelineData"]]
            out["trends"] = {"termos": termos, "janela": "now 7-d", "pontos": pts,
                             "aviso": "0 a 100, relativo ao pico dentro desta consulta; palavras soltas (não tópicos) são ambíguas"}
            man["trends_pontos"] = len(pts)
        except Exception as e:  # noqa: BLE001
            man["trends_erro"] = f"{type(e).__name__}: {str(e)[:200]}"
    for q in caso.get("termos_noticias") or []:
        try:
            busca = q + " after:" + caso["desde"]
            url = RSS + "?" + urllib.parse.urlencode({"q": busca, "hl": "pt-BR", "gl": "BR", "ceid": "BR:pt-419"})
            with open_url(url, timeout=40) as r:
                its = parse_rss(read_body(r))
            filtro = [bc_norm(x) for x in caso.get("filtro_titulo_noticias") or []]
            out["noticias"] += [{**{k: i.get(k) for k in ("titulo", "link", "veiculo", "dominio", "data_publicacao")}, "termo": q} for i in its
                                if (i.get("data_publicacao") or "") >= caso["desde"] and (not filtro or any(f in bc_norm(i.get("titulo") or "") for f in filtro))]
        except Exception as e:  # noqa: BLE001
            man.setdefault("noticias_erros", []).append(f"{q}: {type(e).__name__}")
    vistos, uniq = set(), []
    for n in sorted(out["noticias"], key=lambda n: n.get("data_publicacao") or ""):
        if n["link"] not in vistos:
            vistos.add(n["link"])
            uniq.append(n)
    out["noticias"] = uniq
    (pasta / "google.json").write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    man.update(noticias=len(uniq), status="ok" if (out["trends"] or uniq) else "⛔ nada lido")
    return man


def paga(rede: str, caso: dict, cfg: dict, pasta: Path, teste: bool, agora: str, usadas: set, executar=None) -> tuple[list[dict], dict]:
    ja = round(sum(float(m.get("custo_usd") or 0) for f in pasta.glob("manifesto-*.json")
                   for m in [json.loads(f.read_text(encoding="utf-8"))] for m in m.get("redes", []) if m.get("rede") == rede), 4)
    teto = round(min(caso["teto_usd"][rede] - ja, cfg["teto_teste_usd"]) if teste else caso["teto_usd"][rede] - ja, 4)
    man = {"rede": rede, "teto_usd": caso["teto_usd"][rede], "gasto_antes_usd": ja, "teto_execucao_usd": teto, "termos": []}
    if teto < 0.02:
        return [], {**man, "custo_usd": 0.0, "status": "⛔ teto da rede esgotado"}
    if executar is None and caso.get("segredo"):
        # conta exclusiva do caso: usa o token direto, sem consultar saldo ou plano (o teto vai em cada execução)
        token = os.environ.get(caso["segredo"], "").strip()
        if not token:
            return [], {**man, "custo_usd": 0.0, "status": f"⛔ segredo {caso['segredo']} ausente no GitHub"}
        man["conta"] = caso["segredo"]
        executar = lambda ator, pl, cap: run_actor(token, ator, pl, cap)  # noqa: E731
    if executar is None:
        # prefere conta ainda não usada nesta execução; se nenhuma tiver saldo, reaproveita uma já usada
        lista = cfg.get("segredos_por_rede", {}).get(rede) or cfg["segredos"]
        nome, token, saldo = escolher_conta([s for s in lista if s not in usadas], min(teto, 0.5))
        if not token:
            nome, token, saldo = escolher_conta(list(lista), min(teto, 0.5))
        if not token:
            return [], {**man, "custo_usd": 0.0, "status": "⛔ nenhuma conta dos outros pesquisadores com saldo"}
        usadas.add(nome)
        man["conta"] = nome
        if saldo is not None:
            teto = min(teto, round(saldo - 0.02, 4))
        executar = lambda ator, pl, cap: run_actor(token, ator, pl, cap)  # noqa: E731
    lista = pedidos(rede, caso, 1)
    if teste:
        lista = lista[:1]
    if not lista:
        return [], {**man, "custo_usd": 0.0, "status": "sem termos para esta rede"}
    # mesmo número de itens por termo, dentro do teto
    custo_fixo = sum(preco(rede, a, cfg)[1] for _, a, _ in lista)
    unit = sum(preco(rede, a, cfg)[0] for _, a, _ in lista)
    n = 10 if teste else max(0, min(caso.get("maximo_por_termo", 2000), int((teto * 0.95 - custo_fixo) / unit) if unit else 0))
    if n < 5:
        return [], {**man, "custo_usd": 0.0, "status": "⛔ teto não cabe nem 5 itens por termo"}
    man["itens_pedidos_por_termo"] = n
    lista = pedidos(rede, caso, n)[:1] if teste else pedidos(rede, caso, n)

    def um(p):
        termo, ator, pl = p
        it_p, q_p = preco(rede, ator, cfg)
        try:
            run, itens = executar(ator, pl, max(0.1, round(q_p + it_p * n * 1.3 + 0.01, 4)))
            itens = itens or []
            return termo, ator, itens, max(custo_run(run or {}) or 0, round(q_p + it_p * len(itens), 5)), (run or {}).get("id"), None
        except Exception as e:  # noqa: BLE001 — o token vai no cabeçalho
            corpo = ""
            try:
                corpo = e.read().decode("utf-8", "replace")[:240]  # mensagem da Apify (não contém o token)
            except Exception:  # noqa: BLE001
                pass
            return termo, ator, [], 0.0, None, f"{type(e).__name__} {getattr(e, 'code', '')} {corpo}".strip()
    with ThreadPoolExecutor(max_workers=3) as ex:
        res = list(ex.map(um, lista))
    rows, gasto, brutos = [], 0.0, []
    for termo, ator, itens, custo, run_id, erro in res:
        brutos += [{**x, "_termo": termo} for x in itens]
        gasto += custo
        ls = [r for r in (norm(rede, x, termo, agora) for x in itens) if r]
        no_periodo = [r for r in ls if (r["publicado_em"] or "9") >= caso["desde"]]
        rows += no_periodo
        man["termos"].append({"termo": termo, "ator": ator.replace("~", "/"), "itens": len(itens), "lidos": len(ls), "no_periodo": len(no_periodo),
                              "no_limite": len(itens) >= n, "run": run_id, "custo_usd": round(custo, 5), "erro": erro,
                              "chaves_1o_item": sorted(itens[0].keys())[:40] if itens else None,
                              "mais_antigo": min((r["publicado_em"] for r in no_periodo if r["publicado_em"]), default=None)})
        print(f"{rede} {termo}: {len(no_periodo)} no período ({len(itens)} itens, pedido {n}){' · ' + erro if erro else ''}")
    man.update(custo_usd=round(gasto, 4), status="ok" if rows else "⛔ nada no período", _brutos=brutos)
    return rows, man


def main(argv=None, executar=None) -> int:
    argv = list(argv or [])
    root = Path(".")
    cfg = json.loads((root / "data/config/casos.json").read_text(encoding="utf-8"))
    teste = "--teste" in argv
    so = [argv[i + 1] for i, a in enumerate(argv) if a == "--caso"]
    redes = [argv[i + 1] for i, a in enumerate(argv) if a == "--rede"] or list(REDES)
    agora = now_utc()
    interno = os.environ.get("ODI_INTERNO_DIR")
    usadas: set[str] = set()
    ok = False
    for caso in cfg["casos"]:
        if not caso.get("coletar") or (so and caso["id"] not in so):
            continue
        if "--complemento" in argv:  # só as buscas complementares do X (ex.: o começo do caso, que a busca "mais recentes" cortou)
            caso = {**caso, "_so_complemento": True}
        if "--frases" in argv:  # só frases (Facebook, Kwai) e hashtags extras do Instagram (28/10/2026)
            caso = {**caso, "_so_frases": True}
        pasta = root / "data/casos" / caso["id"]
        pasta.mkdir(parents=True, exist_ok=True)
        priv = (Path(interno) if interno else Path(os.environ.get("RUNNER_TEMP") or tempfile.gettempdir()) / "odi_casos") / "casos" / caso["id"]
        priv.mkdir(parents=True, exist_ok=True)
        man = {"caso": caso["id"], "titulo": caso["titulo"], "run_started_utc": agora, "modo": "teste" if teste else "carga",
               "privado": bool(interno), "desde": caso["desde"], "redes": []}
        novos = []
        for rede in redes:
            try:
                if rede == "google":
                    rows, m = [], google(caso, agora, pasta)
                elif rede == "tiktok" and caso.get("teto_usd", {}).get("tiktok"):
                    rows, m = paga(rede, caso, cfg, pasta, teste, agora, usadas, executar)
                elif rede == "tiktok":
                    rows, m = tiktok(caso, teste, agora)
                    m["status"] = "ok" if rows else "⛔ nenhum vídeo lido"
                    rows = [r for r in rows if (r["publicado_em"] or "9") >= caso["desde"]]
                else:
                    rows, m = paga(rede, caso, cfg, pasta, teste, agora, usadas, executar)
            except Exception as e:  # noqa: BLE001 — uma rede com problema não derruba as outras
                rows, m = [], {"rede": rede, "custo_usd": 0.0, "status": f"⛔ {type(e).__name__}: {str(e)[:200]}"}
            brutos = m.pop("_brutos", [])
            if brutos:
                with gzip.open(priv / f"bruto_{rede}_{agora.replace(':', '').replace('-', '')}.jsonl.gz", "wt", encoding="utf-8") as f:
                    for x in brutos:
                        f.write(json.dumps(x, ensure_ascii=False) + "\n")
            m["itens_no_periodo"] = len(rows)
            man["redes"].append(m)
            novos += rows
        arq = priv / "itens.csv.gz"
        por = {(r["rede"], r["item_id"]): r for r in csv.DictReader(gzip.open(arq, "rt", encoding="utf-8"), delimiter=";")} if arq.exists() else {}
        for r in novos:
            k = (r["rede"], r["item_id"])
            if k in por:  # métricas da leitura mais nova; termos acumulam
                r = {**r, "termo": "|".join(sorted(set(por[k]["termo"].split("|")) | set(r["termo"].split("|"))))}
            por[k] = r
        with gzip.open(arq, "wt", encoding="utf-8", newline="") as f:
            w = csv.DictWriter(f, COLS, delimiter=";", lineterminator="\n", extrasaction="ignore")
            w.writeheader()
            w.writerows(sorted(por.values(), key=lambda r: r["publicado_em"]))
        man.update(itens_acumulados=len(por), custo_usd=round(sum(float(m.get("custo_usd") or 0) for m in man["redes"]), 4))
        stamp = agora.replace(":", "").replace("-", "")
        for nome in (f"manifesto-{stamp}.json", "manifesto_latest.json"):
            (pasta / nome).write_text(json.dumps(man, ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"caso {caso['id']}: {len(novos)} itens nesta coleta · {len(por)} acumulados")
        ok = ok or bool(novos)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
