#!/usr/bin/env python3
"""Diagnóstico (não grava dados): o que as bibliotecas de anúncios entregam a um navegador sem login?

Meta: Biblioteca de Anúncios (anúncios sobre temas sociais, eleições ou política, Brasil) e relatório de gastos.
Google: Central de Transparência de Anúncios (busca de anunciante, região BR).
Registra só status, URLs internas chamadas, tamanhos e contagens — sem conteúdo de anúncio de terceiros.
"""
import asyncio, json, re

META = "https://www.facebook.com/ads/library/?active_status=all&ad_type=political_and_issue_ads&country=BR&media_type=all&search_type=keyword_unordered&q="
ALVOS = [("meta_busca", META + "Lula", ("graphql", "async/search_ads", "ads/library")),
         ("meta_busca", META + "Fl%C3%A1vio%20Bolsonaro", ("graphql", "async/search_ads", "ads/library")),
         ("meta_relatorio", "https://www.facebook.com/ads/library/report/?source=nav-header&country=BR", ("report", "graphql")),
         ("google_busca", "https://adstransparency.google.com/?region=BR&query=Partido%20Liberal", ("rpc",)),
         ("google_busca", "https://adstransparency.google.com/?region=BR&query=Partido%20dos%20Trabalhadores", ("rpc",)),
         ("google_politico", "https://adstransparency.google.com/political?region=BR", ("rpc",))]


async def main():
    from playwright.async_api import async_playwright
    async with async_playwright() as p:
        b = await p.chromium.launch(headless=True)
        ctx = await b.new_context(locale="pt-BR", viewport={"width": 1366, "height": 900},
                                  user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0 Safari/537.36")
        for tipo, url, padroes in ALVOS:
            pg = await ctx.new_page()
            achados = []

            async def resp(r, achados=achados, padroes=padroes):
                u = r.url
                if any(x in u for x in padroes) and r.request.resource_type in ("xhr", "fetch"):
                    try:
                        corpo = await r.text()
                    except Exception:
                        corpo = ""
                    achados.append({"st": r.status, "u": re.sub(r"\?.*", "", u)[-70:], "bytes": len(corpo),
                                    "ad_archive_id": corpo.count("ad_archive_id"), "spend": corpo.count("spend"),
                                    "creative": corpo.count("CR"), "login": "login" in corpo[:3000].lower()})
            pg.on("response", resp)
            try:
                await pg.goto(url, wait_until="domcontentloaded", timeout=60000)
                await pg.wait_for_timeout(9000)
                for _ in range(2):
                    await pg.mouse.wheel(0, 3000); await pg.wait_for_timeout(3000)
                titulo = (await pg.title())[:60]
                txt = await pg.inner_text("body")
                resumo = {"login_na_pagina": bool(re.search(r"(Entrar|Log in|Faça login)", txt[:4000])),
                          "resultados": re.findall(r"~?\s?[\d\.]+\s(?:resultados|results)", txt)[:3],
                          "trechos": [l.strip()[:80] for l in txt.splitlines() if re.search(r"(Valor gasto|Amount spent|Impress|Veiculação|Anúncios|ads|anunciante|Advertiser)", l)][:6],
                          "chars": len(txt)}
            except Exception as e:
                titulo, resumo = f"erro {type(e).__name__}", {}
            print(json.dumps({"tipo": tipo, "url": url.split(".com")[1][:80], "titulo": titulo, **resumo,
                              "respostas": len(achados), "amostra": achados[:6]}, ensure_ascii=False))
            await pg.close()
        await b.close()

asyncio.run(main())
