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
    novos, resumo = asyncio.run(coletar(cfg, agora))
    novos = [r for r in novos if r["publicado_em"][:10] >= cfg["desde"]]
    d = os.environ.get("ODI_INTERNO_DIR")
    priv = Path(d) / "tiktok/hashtags" if d else Path(os.environ.get("RUNNER_TEMP") or tempfile.gettempdir()) / "odi_tiktok_hashtags"
    todos = mesclar(ler(priv / "videos_todos.csv.gz"), novos)
    gravar(priv / "videos_todos.csv.gz", todos)
    pub = root / "data/tiktok/hashtags"
    grandes = lambda r: str(r["seguidores"]).isdigit() and int(r["seguidores"]) >= cfg["min_seguidores_publico"]  # noqa: E731
    publico = mesclar(ler(pub / "videos.csv.gz"), [r for r in novos if grandes(r)])
    gravar(pub / "videos.csv.gz", publico)
    contas = {r["conta"]: r for r in todos}
    man = {"schema_version": 1, "run_started_utc": agora, "modo": "interno" if d else "efemero",
           "fonte": "páginas públicas de hashtag do TikTok, navegador headless sem login",
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
