#!/usr/bin/env python3
"""Diagnóstico (não grava dados): o TikTok entrega comentários e vídeos de hashtag a um navegador sem login?

Abre, num Chromium headless (Playwright), páginas públicas e registra as respostas JSON que a própria página pede:
  - vídeo de campanha → /api/comment/list (comentários);
  - página de hashtag → /api/challenge/item_list (vídeos de quaisquer contas com a hashtag);
  - busca → /api/search/... (pode exigir login).
Imprime só contagens e chaves, sem texto de comentário nem nome de usuário.
"""
import asyncio, json, sys

ALVOS = [("comentarios", "https://www.tiktok.com/@lulaoficial/video/7696698384177958164", "/api/comment/list"),
         ("comentarios", "https://www.tiktok.com/@flaviobolsonaro/video/7697046838171471125", "/api/comment/list"),
         ("hashtag", "https://www.tiktok.com/tag/flaviobolsonaro", "/api/challenge/item_list"),
         ("hashtag", "https://www.tiktok.com/tag/lula13", "/api/challenge/item_list"),
         ("busca", "https://www.tiktok.com/search/video?q=vote%2022%20flavio", "/api/search/")]


async def main():
    from playwright.async_api import async_playwright
    async with async_playwright() as p:
        b = await p.chromium.launch(headless=True)
        ctx = await b.new_context(locale="pt-BR", user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36",
                                  viewport={"width": 1366, "height": 900})
        for tipo, url, padrao in ALVOS:
            pg = await ctx.new_page()
            achados = []

            async def resp(r, achados=achados, padrao=padrao):
                if padrao in r.url:
                    try:
                        d = await r.json()
                    except Exception:
                        achados.append({"status": r.status, "json": False}); return
                    itens = d.get("comments") or d.get("itemList") or d.get("data") or []
                    achados.append({"status": r.status, "itens": len(itens) if isinstance(itens, list) else "?", "chaves": sorted(d)[:10],
                                    "contas_distintas": len({(i.get("author") or {}).get("uniqueId") for i in itens if isinstance(i, dict) and i.get("author")}) if isinstance(itens, list) else None})
            pg.on("response", resp)
            try:
                await pg.goto(url, wait_until="domcontentloaded", timeout=45000)
                await pg.wait_for_timeout(6000)
                for _ in range(3):
                    await pg.mouse.wheel(0, 2500); await pg.wait_for_timeout(2500)
                titulo = (await pg.title())[:60]
            except Exception as e:
                titulo = f"erro {type(e).__name__}"
            print(json.dumps({"tipo": tipo, "url": url.split("tiktok.com")[1][:60], "titulo": titulo, "respostas": achados[:5]}, ensure_ascii=False))
            await pg.close()
        await b.close()

asyncio.run(main())
