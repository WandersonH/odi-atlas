#!/usr/bin/env python3
"""Vídeos de apoio (e de crítica) no TikTok por hashtag — de quaisquer contas, não só das campanhas. Gratuito, sem login.

Abre https://www.tiktok.com/tag/<hashtag> num Chromium headless (Playwright), rola a página e guarda as respostas
/api/challenge/item_list que a própria página pede (teste D1.2: ~30 vídeos por rolagem, sem login).
Saída:
  privado (ODI_INTERNO_DIR/tiktok/hashtags/videos_todos.csv.gz) ou temporário: todas as contas;
  data/tiktok/hashtags/videos.csv.gz: só contas com min_seguidores_publico+ (contas pequenas = pessoas comuns, LGPD);
  data/tiktok/hashtags/manifesto_latest.json: contagens por hashtag, incluindo as contas pequenas (só números).
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
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from net import now_utc  # noqa: E402

COLS = ["video_id", "conta", "nome_conta", "seguidores", "verificada", "publicado_em", "legenda", "hashtags", "visualizacoes",
        "curtidas", "comentarios", "compartilhamentos", "hashtag_coletada", "lado_hashtag", "url", "coletado_em"]


def linha(it: dict, tag: str, lado: str, agora: str) -> dict | None:
    a, st, ast = it.get("author") or {}, it.get("stats") or {}, it.get("authorStats") or {}
    if not it.get("id") or not a.get("uniqueId"):
        return None
    ts = it.get("createTime")
    try:
        pub = dt.datetime.fromtimestamp(int(ts), dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    except (TypeError, ValueError):
        pub = ""
    tags = sorted({(c.get("title") or "").lower() for c in it.get("challenges") or [] if c.get("title")})
    return {"video_id": str(it["id"]), "conta": a["uniqueId"], "nome_conta": a.get("nickname", ""),
            "seguidores": ast.get("followerCount", ""), "verificada": int(bool(a.get("verified"))), "publicado_em": pub,
            "legenda": (it.get("desc") or "").replace("\n", " ").replace("\r", " "), "hashtags": "|".join(tags),
            "visualizacoes": st.get("playCount", ""), "curtidas": st.get("diggCount", ""), "comentarios": st.get("commentCount", ""),
            "compartilhamentos": st.get("shareCount", ""), "hashtag_coletada": tag, "lado_hashtag": lado,
            "url": f"https://www.tiktok.com/@{a['uniqueId']}/video/{it['id']}", "coletado_em": agora}


async def coletar(cfg: dict, agora: str) -> tuple[list[dict], dict]:
    from playwright.async_api import async_playwright
    out, resumo = [], {}
    async with async_playwright() as p:
        b = await p.chromium.launch(headless=True)
        ctx = await b.new_context(locale="pt-BR", viewport={"width": 1366, "height": 900},
                                  user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36")
        alvos = [(lado, tag, f"https://www.tiktok.com/tag/{tag}") for lado, tags in cfg["hashtags"].items() for tag in tags]
        # busca por frase (como a caixa de busca do site); sem login o TikTok pode limitar ou exigir entrada — o resumo registra
        alvos += [("busca", q, "https://www.tiktok.com/search/video?" + __import__("urllib.parse").parse.urlencode({"q": q})) for q in cfg.get("buscas", [])]
        for lado, tag, endereco in alvos:
            if True:
                pg, itens, respostas = await ctx.new_page(), [], []

                async def resp(r, itens=itens, respostas=respostas):
                    if "/api/challenge/item_list" in r.url or "/api/search/" in r.url:
                        respostas.append(r.status)
                        try:
                            d = await r.json()
                            itens.extend(d.get("itemList") or d.get("item_list") or [])
                            itens.extend(x["item"] for x in d.get("data") or [] if isinstance(x, dict) and isinstance(x.get("item"), dict))
                        except Exception:  # noqa: BLE001
                            pass
                pg.on("response", resp)
                erro = None
                try:
                    await pg.goto(endereco, wait_until="domcontentloaded", timeout=45000)
                    await pg.wait_for_timeout(5000)
                    parado = 0
                    for _ in range(cfg["rolagens_por_hashtag"]):
                        antes = len(itens)
                        await pg.mouse.wheel(0, 4000)
                        await pg.wait_for_timeout(2200)
                        parado = parado + 1 if len(itens) == antes else 0
                        if parado >= 3:
                            break
                except Exception as e:  # noqa: BLE001
                    erro = type(e).__name__
                await pg.close()
                ls = [l for it in itens if (l := linha(it, tag, lado, agora))]
                out += ls
                resumo[tag] = {"lado": lado, "respostas_api": len(respostas), "videos": len(ls),
                               "contas": len({l["conta"] for l in ls}), "erro": erro}
                print(f"{'#' if lado != 'busca' else 'busca: '}{tag}: {len(ls)} vídeos de {resumo[tag]['contas']} contas ({len(respostas)} respostas) {erro or ''}")
        await b.close()
    return out, resumo


# ---- modo pago (02/11/2026): a página pública da hashtag não entrega vídeos desde 30/10; o responsável autorizou a conta 1 ----
def dia_mes(hoje: dt.date) -> int:
    """Dias que faltam no mês, contando hoje."""
    prox = (hoje.replace(day=28) + dt.timedelta(days=4)).replace(day=1)
    return (prox - hoje).days


def gasto_mes(p: Path, mes: str) -> float:
    if not p.exists():
        return 0.0
    return round(sum(float(r["custo_usd"] or 0) for r in csv.DictReader(open(p, encoding="utf-8"), delimiter=";") if r["data"][:7] == mes), 4)


def plano_pago(pg: dict, n_tags: int, gasto: float, hoje: dt.date) -> tuple[float, int]:
    """Teto de hoje (o que sobra do mês dividido pelos dias que faltam) e vídeos por hashtag que cabem nele."""
    teto = round(max(0.0, pg["teto_mensal_usd"] - gasto) / dia_mes(hoje), 4)
    n = int((teto * 0.95 - n_tags * pg["usd_por_busca"]) / (n_tags * pg["usd_por_item"])) if n_tags else 0
    return teto, max(0, min(pg["itens_por_hashtag"], n))


def linha_paga(x: dict, tag: str, lado: str, agora: str) -> dict | None:
    from collect_casos import norm
    r = norm("tiktok", x, tag, agora)
    if not r or not r["conta"]:
        return None
    ht = x.get("hashtags") or []
    tags = sorted({(h.get("name") or h.get("title") or "") if isinstance(h, dict) else str(h) for h in ht} - {""}) if isinstance(ht, list) else []
    if not tags:
        tags = sorted({w[1:].lower() for w in r["texto"].split() if w.startswith("#") and len(w) > 1})
    return {"video_id": r["item_id"], "conta": r["conta"], "nome_conta": r["nome_conta"], "seguidores": r["seguidores"] if r["seguidores"] is not None else "",
            "verificada": r["verificada"], "publicado_em": r["publicado_em"], "legenda": r["texto"], "hashtags": "|".join(t.lower() for t in tags),
            "visualizacoes": r["visualizacoes"] if r["visualizacoes"] is not None else "", "curtidas": r["curtidas"] if r["curtidas"] is not None else "",
            "comentarios": r["comentarios"] if r["comentarios"] is not None else "", "compartilhamentos": r["compartilhamentos"] if r["compartilhamentos"] is not None else "",
            "hashtag_coletada": tag, "lado_hashtag": lado, "url": r["url"], "coletado_em": agora}


def coletar_pago(cfg: dict, agora: str, token: str, gastos: Path, executar=None) -> tuple[list[dict], dict, dict]:
    pg = cfg["pago"]
    hoje = dt.date.fromisoformat(agora[:10])
    alvos = [(lado, tag) for lado, tags in cfg["hashtags"].items() for tag in tags]
    gasto = gasto_mes(gastos, agora[:7])
    teto, n = plano_pago(pg, len(alvos), gasto, hoje)
    info = {"ator": pg["ator"], "conta": pg["segredo"], "teto_mensal_usd": pg["teto_mensal_usd"], "gasto_mes_antes_usd": gasto,
            "teto_hoje_usd": teto, "videos_pedidos_por_hashtag": n, "dateRange": pg["dateRange"], "sortType": "DATE_POSTED"}
    if n < 5:
        return [], {}, {**info, "custo_usd": 0.0, "status": "⛔ teto do mês esgotado (não cabem 5 vídeos por hashtag)"}
    if executar is None:
        from collect_meta_apify import run_actor
        executar = lambda ator, pl, cap: run_actor(token, ator, pl, cap)  # noqa: E731
    from collect_meta_anuncios_apify import custo_run
    out, resumo, custo = [], {}, 0.0
    cap = round(pg["usd_por_busca"] + pg["usd_por_item"] * n * 1.3 + 0.01, 4)
    for lado, tag in alvos:
        erro, itens, run = None, [], {}
        try:
            run, itens = executar(pg["ator"], {"keywords": [f"#{tag}"], "maxItems": n, "dateRange": pg["dateRange"], "sortType": "DATE_POSTED"}, cap)
            itens = itens or []
        except Exception as e:  # noqa: BLE001 — o token vai no cabeçalho, não na mensagem
            erro = f"{type(e).__name__} {getattr(e, 'code', '')}".strip()
        c = max(custo_run(run or {}) or 0, round(pg["usd_por_busca"] + pg["usd_por_item"] * len(itens), 5)) if not erro else 0.0
        custo += c
        ls = [l for x in itens if (l := linha_paga(x, tag, lado, agora))]
        out += ls
        resumo[tag] = {"lado": lado, "itens_do_ator": len(itens), "videos": len(ls), "contas": len({l["conta"] for l in ls}),
                       "mais_antigo": min((l["publicado_em"] for l in ls if l["publicado_em"]), default=None), "run": (run or {}).get("id"), "erro": erro}
        print(f"#{tag}: {len(ls)} vídeos de {resumo[tag]['contas']} contas (pedido {n}){' · ' + erro if erro else ''}")
    return out, resumo, {**info, "custo_usd": round(custo, 4), "status": "ok" if out else "⛔ nenhum vídeo lido"}


def ler(p: Path) -> list[dict]:
    return list(csv.DictReader(gzip.open(p, "rt", encoding="utf-8"), delimiter=";")) if p.exists() else []


def gravar(p: Path, rows: list[dict]):
    p.parent.mkdir(parents=True, exist_ok=True)
    with gzip.open(p, "wt", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, COLS, delimiter=";", lineterminator="\n")
        w.writeheader()
        w.writerows(rows)


def mesclar(antigos: list[dict], novos: list[dict]) -> list[dict]:
    """Um registro por vídeo; métricas da leitura mais nova; hashtags coletadas acumulam."""
    por = {r["video_id"]: r for r in antigos}
    for r in novos:
        a = por.get(r["video_id"])
        if a:
            r = {**r, "hashtag_coletada": "|".join(sorted(set(a["hashtag_coletada"].split("|")) | {r["hashtag_coletada"]})),
                 "lado_hashtag": "|".join(sorted(set(a["lado_hashtag"].split("|")) | {r["lado_hashtag"]}))}
        por[r["video_id"]] = r
    return sorted(por.values(), key=lambda r: (r["publicado_em"], r["video_id"]), reverse=True)


def main(argv=None) -> int:
    root = Path(".")
    cfg = json.loads((root / "data/config/tiktok_hashtags.json").read_text(encoding="utf-8"))
    agora = now_utc()
    d = os.environ.get("ODI_INTERNO_DIR")
    priv = Path(d) / "tiktok/hashtags" if d else Path(os.environ.get("RUNNER_TEMP") or tempfile.gettempdir()) / "odi_tiktok_hashtags"
    pg = cfg.get("pago") or {}
    token = os.environ.get(pg.get("segredo", ""), "").strip() if pg.get("ativo") else ""
    pago = None
    if pg.get("ativo") and token and d:
        # o gasto do mês fica no privado; sem o privado não há como respeitar o teto mensal, então não roda pago
        novos, resumo, pago = coletar_pago(cfg, agora, token, priv / "gastos.csv")
        priv.mkdir(parents=True, exist_ok=True)
        novo_arq = not (priv / "gastos.csv").exists()
        with open(priv / "gastos.csv", "a", encoding="utf-8", newline="") as fh:
            w = csv.writer(fh, delimiter=";")
            if novo_arq:
                w.writerow(["data", "ator", "custo_usd", "videos"])
            w.writerow([agora, pg["ator"], pago["custo_usd"], len(novos)])
    else:
        if pg.get("ativo"):
            print("⚠️ modo pago ativo, mas sem token ou sem repositório privado: página pública (grátis)")
        novos, resumo = asyncio.run(coletar(cfg, agora))
    novos = [r for r in novos if r["publicado_em"][:10] >= cfg["desde"]]
    todos = mesclar(ler(priv / "videos_todos.csv.gz"), novos)
    gravar(priv / "videos_todos.csv.gz", todos)
    pub = root / "data/tiktok/hashtags"
    grandes = lambda r: str(r["seguidores"]).isdigit() and int(r["seguidores"]) >= cfg["min_seguidores_publico"]  # noqa: E731
    publico = mesclar(ler(pub / "videos.csv.gz"), [r for r in novos if grandes(r)])
    gravar(pub / "videos.csv.gz", publico)
    contas = {r["conta"]: r for r in todos}
    man = {"schema_version": 1, "run_started_utc": agora, "modo": "interno" if d else "efemero",
           "fonte": ("busca do TikTok por #hashtag via Apify (apidojo/tiktok-scraper), filtro de data do TikTok "
                     f"{pago['dateRange']}; {pago['videos_pedidos_por_hashtag']} vídeos pedidos por hashtag") if pago else
                    "páginas públicas de hashtag do TikTok, navegador headless sem login",
           "universo": "⛔ desconhecido: o TikTok não informa quantos vídeos cada hashtag tem no período",
           "hashtags": resumo, "videos_desta_coleta": len(novos), "videos_acumulados": len(todos),
           "contas_acumuladas": len(contas), "contas_com_10mil_ou_mais": sum(1 for r in contas.values() if grandes(r)),
           "videos_publicos_acumulados": len(publico),
           "status": "ok" if novos else "⛔ nenhum vídeo lido"}
    (pub / "manifesto_latest.json").write_text(json.dumps(man, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"hashtags: {len(novos)} vídeos nesta coleta ({len(todos)} acumulados, {len(contas)} contas, "
          f"{man['contas_com_10mil_ou_mais']} com 10 mil+); público: {len(publico)} vídeos")
    return 0 if novos else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
