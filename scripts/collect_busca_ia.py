#!/usr/bin/env python3
"""Busca de conteúdo de IA sobre a eleição no TikTok e no Instagram, para a página "Rótulo de IA nas campanhas".

Pedido do responsável (23/10/2026, 01h16): "preciso de uma busca sobre a página de IA, te dou 10 dólares"; opção "3+4":
TikTok por termos + exemplos citados na reportagem do New York Times (21/10), e Reels do Instagram com conferência do selo de IA.
Configuração e autorização em data/config/busca_ia.json (conta 1, teto total US$ 10).

Etapas (uma por chamada):
  --coletar  Apify, uma execução por busca/hashtag, cada uma limitada ao que sobra do teto (custo real lido depois):
             TikTok apidojo/tiktok-scraper (palavra-chave) e Instagram apify/instagram-hashtag-scraper (feed da hashtag).
  --rotulos  grátis, navegador sem login (Playwright): abre a página dos vídeos do TikTok mais vistos e lê os campos de
             rótulo de IA do próprio TikTok (mesma regra de collect_rotulo_ia.py); no Instagram, abre uma amostra de posts e
             procura o selo ("AI info", "Informações de IA", "AI content"…). Página que pede login fica ⛔, nunca estimada.
  --build    agregados públicos em data/ia/busca.json (sem texto nem nome de quem tem menos de 10 mil seguidores).

Privado: ODI_INTERNO_DIR/ia/busca/ (brutos e itens.json). Público: data/ia/busca.json e manifesto de custo.
"""
from __future__ import annotations

import asyncio
import gzip
import json
import os
import re
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from net import now_utc  # noqa: E402

RAIZ = Path(__file__).resolve().parents[1]
SELO_IG = re.compile(r"\bAI info\b|Informa[cç][oõ]es de IA|\bAI content\b|Conte[uú]do de IA|Made with AI|Criado com IA|Feito com IA", re.I)


def cfg() -> dict:
    return json.loads((RAIZ / "data/config/busca_ia.json").read_text(encoding="utf-8"))


def g(x: dict, *ks):
    for k in ks:
        v = x
        for p in k.split("."):
            v = v.get(p) if isinstance(v, dict) else None
        if v not in (None, ""):
            return v
    return None


def data_iso(v) -> str | None:
    if isinstance(v, (int, float)) or (isinstance(v, str) and v.isdigit()):
        n = int(v)
        n = n // 1000 if n > 10**11 else n
        return datetime.fromtimestamp(n, timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    if isinstance(v, str) and len(v) >= 10:
        return v[:19] + ("Z" if len(v) >= 19 else "")
    return None


def num(v):
    try:
        return int(v)
    except (TypeError, ValueError):
        return None


def norm_tiktok(x: dict, busca: dict) -> dict | None:
    vid = str(g(x, "id", "awemeId", "aweme_id") or "")
    if not vid:
        return None
    autor = g(x, "channel.username", "authorMeta.name", "author.uniqueId", "author.username", "author") or ""
    autor = autor if isinstance(autor, str) else ""
    return {"rede": "TikTok", "id": vid, "busca": busca["q"], "grupo": busca["grupo"], "exemplo_nyt": busca.get("exemplo"),
            "autor": autor, "seguidores": num(g(x, "channel.followers", "authorMeta.fans", "authorStats.followerCount")),
            "verificado": bool(g(x, "channel.verified", "authorMeta.verified")),
            "texto": " ".join(str(g(x, "title", "desc", "text", "description") or "").split())[:300],
            "publicado_em": data_iso(g(x, "uploadedAt", "createTime", "createTimeISO", "uploadedAtFormatted")),
            "visualizacoes": num(g(x, "views", "playCount", "stats.playCount")), "curtidas": num(g(x, "likes", "diggCount", "stats.diggCount")),
            "comentarios": num(g(x, "comments", "commentCount", "stats.commentCount")), "compartilhamentos": num(g(x, "shares", "shareCount", "stats.shareCount")),
            "url": g(x, "postPage", "webVideoUrl", "url") or (f"https://www.tiktok.com/@{autor}/video/{vid}" if autor else None),
            "campos_ia_coletor": {k: v for k, v in x.items() if re.search(r"aigc|ai_?gen|aigenerat|synthetic", k, re.I)}}


def norm_instagram(x: dict, tag: str) -> dict | None:
    code = g(x, "shortCode", "code")
    if not code:
        return None
    return {"rede": "Instagram", "id": str(code), "busca": f"#{tag}", "grupo": "hashtag", "exemplo_nyt": None,
            "autor": g(x, "ownerUsername", "owner.username") or "", "seguidores": num(g(x, "ownerFollowersCount", "owner.followerCount")),
            "verificado": bool(g(x, "ownerVerified", "owner.isVerified")),
            "texto": " ".join(str(g(x, "caption") or "").split())[:300], "publicado_em": data_iso(g(x, "timestamp", "createdAt")),
            "visualizacoes": num(g(x, "videoPlayCount", "videoViewCount")), "curtidas": num(g(x, "likesCount", "likeCount")),
            "comentarios": num(g(x, "commentsCount", "commentCount")), "compartilhamentos": None, "tipo": g(x, "type", "productType"),
            "url": g(x, "url") or f"https://www.instagram.com/p/{code}/", "campos_ia_coletor": {}}


def custo(run: dict | None) -> float:
    return float((run or {}).get("usageTotalUsd") or 0)


def coletar(C: dict, priv: Path, pub: Path, executar) -> dict:
    priv.mkdir(parents=True, exist_ok=True)
    pub.mkdir(parents=True, exist_ok=True)
    mans = [json.loads(f.read_text(encoding="utf-8")) for f in pub.glob("manifesto-*.json")]
    ja = round(sum(float(m.get("custo_usd") or 0) for m in mans if m.get("lote") == C["lote"]), 4)
    feitas = {r["busca"] for m in mans if m.get("lote") == C["lote"] for r in m.get("execucoes", []) if r.get("status") == "SUCCEEDED"}
    agora = now_utc()
    man = {"lote": C["lote"], "run_started_utc": agora, "conta": C["segredo"], "teto_usd": C["teto_usd"], "gasto_antes_usd": ja, "execucoes": []}
    gasto = ja
    T, I = C["tiktok"], C["instagram"]
    pedidos = [("tiktok", b["q"], b, T["ator"], {"keywords": [b["q"]], "maxItems": T["por_busca"]}, T["preco"]["consulta"] + T["preco"]["item"] * T["por_busca"])
               for b in T["buscas"]]
    pedidos += [("instagram", f"#{h}", h, I["ator"], {"hashtags": [h], "resultsType": "posts", "resultsLimit": I["por_hashtag"]}, I["preco"]["item"] * I["por_hashtag"])
                for h in I["hashtags"]]
    for rede, rot, b, ator, entrada, est in pedidos:
        if rot in feitas:
            continue
        sobra = round(C["teto_usd"] - gasto, 4)
        if sobra < 0.1:
            man["execucoes"].append({"busca": rot, "status": f"⛔ não executada: teto de US$ {C['teto_usd']} atingido"})
            continue
        cap = round(min(sobra, max(0.1, est * 1.15)), 4)
        try:
            run, itens = executar(ator, entrada, cap)
        except Exception as e:  # noqa: BLE001 — o token vai no cabeçalho
            man["execucoes"].append({"busca": rot, "rede": rede, "status": f"⛔ {type(e).__name__} {getattr(e, 'code', '')}".strip()})
            continue
        itens = itens or []
        c = max(custo(run), round(est * len(itens) / max(1, entrada.get("maxItems") or entrada.get("resultsLimit")), 4))
        gasto = round(gasto + c, 4)
        with gzip.open(priv / f"bruto_{rede}_{re.sub(r'[^a-z0-9]+', '_', rot.lower())}.jsonl.gz", "wt", encoding="utf-8") as f:
            for x in itens:
                f.write(json.dumps({**x, "_busca": rot}, ensure_ascii=False) + "\n")
        man["execucoes"].append({"busca": rot, "rede": rede, "run": (run or {}).get("id"), "status": (run or {}).get("status"), "itens": len(itens), "custo_usd": c})
        print(f"{rede} {rot}: {len(itens)} itens · US$ {c} · total US$ {gasto}")
    man["custo_usd"] = round(gasto - ja, 4)
    stamp = agora.replace(":", "").replace("-", "")
    for nome in (f"manifesto-{stamp}.json", "manifesto_latest.json"):
        (pub / nome).write_text(json.dumps(man, ensure_ascii=False, indent=1), encoding="utf-8")
    return man


def itens_privados(C: dict, priv: Path) -> list[dict]:
    """Todos os brutos normalizados e sem repetição (o mesmo vídeo achado por buscas diferentes guarda todas as buscas)."""
    T = {b["q"]: b for b in C["tiktok"]["buscas"]}
    por = {}
    for f in sorted(priv.glob("bruto_*.jsonl.gz")):
        for linha in gzip.open(f, "rt", encoding="utf-8"):
            x = json.loads(linha)
            rot = x.get("_busca", "")
            n = norm_tiktok(x, T[rot]) if rot in T else norm_instagram(x, rot.lstrip("#")) if rot.startswith("#") else None
            if not n:
                continue
            k = (n["rede"], n["id"])
            if k in por:
                por[k]["buscas"] = sorted(set(por[k]["buscas"]) | {n["busca"]})
                por[k]["exemplo_nyt"] = por[k]["exemplo_nyt"] or n["exemplo_nyt"]
            else:
                por[k] = {**n, "buscas": [n["busca"]]}
    antigos = {(i["rede"], i["id"]): i for i in json.loads((priv / "itens.json").read_text(encoding="utf-8"))} if (priv / "itens.json").exists() else {}
    for k, v in por.items():  # leitura de rótulo já feita não se perde
        if k in antigos:
            for c in ("rotulo_ia", "campos_ia", "rotulo_lido_em", "rotulo_status"):
                if c in antigos[k]:
                    v[c] = antigos[k][c]
    return list(por.values())


async def ler_rotulos(itens: list[dict], C: dict, limite_tk: int | None = None, limite_ig: int | None = None, paralelas: int = 4) -> None:
    import collect_rotulo_ia as cr
    from playwright.async_api import async_playwright
    lt = C["tiktok"]["rotulo_top"] if limite_tk is None else limite_tk
    li = C["instagram"]["rotulo_amostra"] if limite_ig is None else limite_ig
    tk = sorted([i for i in itens if i["rede"] == "TikTok" and "rotulo_status" not in i and i.get("url")], key=lambda i: -(i["visualizacoes"] or 0))[:lt]
    ig = sorted([i for i in itens if i["rede"] == "Instagram" and "rotulo_status" not in i], key=lambda i: -(i["curtidas"] or 0))[:li]
    async with async_playwright() as p:
        b = await p.chromium.launch(headless=True)
        ctx = await b.new_context(locale="pt-BR", viewport={"width": 1366, "height": 900},
                                  user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36")
        sem = asyncio.Semaphore(paralelas)  # 23/10: 2.200 vídeos em sequência levariam ~3 h; 4 abas ao mesmo tempo

        async def um(i):
            async with sem:
                pg = await ctx.new_page()
                try:
                    await pg.goto(i["url"], wait_until="domcontentloaded", timeout=40000)
                    await pg.wait_for_timeout(3500)
                    if i["rede"] == "TikTok":
                        estado = await pg.evaluate("() => { const s = document.getElementById('__UNIVERSAL_DATA_FOR_REHYDRATION__'); return s ? s.textContent : null; }")
                        it = ((((json.loads(estado) if estado else {}).get("__DEFAULT_SCOPE__") or {}).get("webapp.video-detail") or {}).get("itemInfo") or {}).get("itemStruct")
                        if it:
                            c = cr.campos_ia(it)
                            i.update(campos_ia=c, rotulo_ia=cr.tem_rotulo(c), rotulo_status="lido")
                        else:
                            i["rotulo_status"] = "⛔ página sem dados do vídeo (removido, restrito ou bloqueio)"
                    else:
                        txt = await pg.evaluate("() => document.body ? document.body.innerText : ''")
                        if re.search(r"Log in|Entrar|Sign up|Cadastre-se", txt[:400]) and not re.search(r"likes|curtidas", txt, re.I):
                            i["rotulo_status"] = "⛔ página pediu login"
                        else:
                            i.update(rotulo_ia=bool(SELO_IG.search(txt)), rotulo_status="lido")
                except Exception as e:  # noqa: BLE001
                    i["rotulo_status"] = f"⛔ {type(e).__name__}"
                i["rotulo_lido_em"] = now_utc()
                await pg.close()
        await asyncio.gather(*(um(i) for i in tk + ig))
        await b.close()
    print(f"rótulos: TikTok {sum(1 for i in tk if i.get('rotulo_status') == 'lido')} de {len(tk)} lidos · "
          f"Instagram {sum(1 for i in ig if i.get('rotulo_status') == 'lido')} de {len(ig)} lidos")


def agregar(itens: list[dict], C: dict) -> dict:
    rx = re.compile(C["filtro_politico"], re.I)
    minimo = C["min_seguidores_publico"]
    out = {"schema_version": 1, "gerado_em_utc": now_utc(), "fonte": "Apify (TikTok: apidojo/tiktok-scraper por palavra-chave; Instagram: apify/instagram-hashtag-scraper) "
           "e leitura da página pública de cada post (navegador sem login) para o rótulo de IA", "redes": {}, "nyt": [],
           "min_seguidores_publico": minimo,
           "nota": "Busca, não universo: o que as plataformas devolveram para cada termo ou hashtag. 'Sobre a eleição' = texto cita candidato, "
                   "partido, voto, TSE ou STF (filtro por expressões). O rótulo é o que a plataforma mostra; sem rótulo não quer dizer sem IA. "
                   "Contas com menos de 10 mil seguidores entram só nas contagens."}
    for rede in ("TikTok", "Instagram"):
        r = [i for i in itens if i["rede"] == rede]
        pol = [i for i in r if rx.search(i["texto"] or "")]
        lidos = [i for i in r if i.get("rotulo_status") == "lido"]
        rot = [i for i in lidos if i.get("rotulo_ia")]
        pub = lambda i: (i["seguidores"] or 0) >= minimo  # noqa: E731
        out["redes"][rede] = {
            "posts": len(r), "sobre_a_eleicao": len(pol), "visualizacoes": sum(i["visualizacoes"] or 0 for i in r) or None,
            "rotulo": {"lidos": len(lidos), "com_rotulo": len(rot), "pct": round(100 * len(rot) / len(lidos), 1) if lidos else None,
                       "nao_lidos": Counter(i.get("rotulo_status") for i in r if i.get("rotulo_status") and i["rotulo_status"] != "lido").most_common(4),
                       "campos_vistos": sorted({k.split(".")[-1] for i in lidos for k in (i.get("campos_ia") or {})})[:12]},
            "por_busca": [[b, sum(1 for i in r if b in i["buscas"]), sum(1 for i in r if b in i["buscas"] and i.get("rotulo_ia"))]
                          for b in sorted({b for i in r for b in i["buscas"]})],
            "por_mes": sorted(Counter((i["publicado_em"] or "")[:7] for i in pol if i["publicado_em"]).items())[-6:],
            "contas_pequenas": sum(1 for i in r if not pub(i)),
            "mais_vistos": [{k: i.get(k) for k in ("autor", "seguidores", "verificado", "texto", "publicado_em", "visualizacoes", "curtidas", "url", "rotulo_ia", "rotulo_status", "buscas")}
                            for i in sorted([i for i in pol if pub(i)], key=lambda i: -((i["visualizacoes"] or 0) or (i["curtidas"] or 0)))[:25]]}
    for b in C["tiktok"]["buscas"]:
        if b["grupo"] != "nyt":
            continue
        r = sorted([i for i in itens if b["q"] in i["buscas"]], key=lambda i: -(i["visualizacoes"] or 0))
        top = next((i for i in r if (i["seguidores"] or 0) >= minimo), None)
        out["nyt"].append({"exemplo": b["exemplo"], "busca": b["q"], "achados": len(r), "visualizacoes_somadas": sum(i["visualizacoes"] or 0 for i in r) or None,
                           "com_rotulo": sum(1 for i in r if i.get("rotulo_ia")), "rotulo_lidos": sum(1 for i in r if i.get("rotulo_status") == "lido"),
                           "mais_visto": {k: top.get(k) for k in ("autor", "seguidores", "texto", "visualizacoes", "url", "rotulo_ia", "rotulo_status")} if top else None})
    return out


def main(argv=None, executar=None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    C = cfg()
    interno = os.environ.get("ODI_INTERNO_DIR")
    if not interno:
        print("⛔ sem repositório privado (texto e autor de pessoas comuns só no privado)")
        return 1
    priv, pub = Path(interno) / "ia/busca", Path("data/ia/busca")
    if "--coletar" in argv:
        token = os.environ.get(C["segredo"], "").strip()
        if not (token or executar):
            print(f"⛔ falta {C['segredo']}")
            return 1
        from collect_meta_apify import run_actor
        executar = executar or (lambda ator, pl, cap: run_actor(token, ator, pl, cap))
        man = coletar(C, priv, pub, executar)
        print(f"coleta: {len(man['execucoes'])} execuções · custo desta rodada US$ {man['custo_usd']} · lote US$ {round(man['gasto_antes_usd'] + man['custo_usd'], 4)} de US$ {C['teto_usd']}")
    itens = itens_privados(C, priv)
    if "--rotulos" in argv and itens:
        lim = lambda k: int(argv[argv.index(k) + 1]) if k in argv else None  # noqa: E731
        asyncio.run(ler_rotulos(itens, C, lim("--limite-tiktok"), lim("--limite-instagram")))
    priv.mkdir(parents=True, exist_ok=True)
    (priv / "itens.json").write_text(json.dumps(itens, ensure_ascii=False), encoding="utf-8")
    if "--build" in argv or "--rotulos" in argv or "--coletar" in argv:
        out = agregar(itens, C)
        Path("data/ia").mkdir(parents=True, exist_ok=True)
        Path("data/ia/busca.json").write_text(json.dumps(out, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
        for rede, r in out["redes"].items():
            print(f"{rede}: {r['posts']} posts · sobre a eleição {r['sobre_a_eleicao']} · rótulo lido em {r['rotulo']['lidos']}, com rótulo {r['rotulo']['com_rotulo']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
