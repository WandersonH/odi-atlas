#!/usr/bin/env python3
"""Diagnóstico (não grava dados): Central de Transparência de Anúncios do Google, região Brasil.
Digita o nome do anunciante na busca da própria página e registra as respostas RPC (SearchSuggestions, SearchCreatives):
status, tamanho e o começo do corpo (para entender o formato). Só nomes de anunciantes públicos e IDs de anúncios."""
import asyncio, json, re

TERMOS = ["Partido Liberal", "Partido dos Trabalhadores", "Flávio Bolsonaro", "Lula"]


async def main():
    from playwright.async_api import async_playwright
    async with async_playwright() as p:
        b = await p.chromium.launch(headless=True)
        ctx = await b.new_context(locale="pt-BR", viewport={"width": 1366, "height": 900},
                                  user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0 Safari/537.36")
        for url in ["https://adstransparency.google.com/advertiser/AR13313535647001083905?region=BR",
                    "https://adstransparency.google.com/?region=BR&domain=partidoliberal.org.br",
                    "https://adstransparency.google.com/?region=BR&domain=pt.org.br"]:
            pg = await ctx.new_page(); achados = []
            async def resp2(r, achados=achados):
                if "/anji/_/rpc/" in r.url and "Duns" not in r.url:
                    try: corpo = await r.text()
                    except Exception: corpo = ""
                    achados.append({"rpc": r.url.split("/rpc/")[1].split("?")[0], "st": r.status, "bytes": len(corpo), "ini": corpo[:1500]})
            pg.on("response", resp2)
            try:
                await pg.goto(url, wait_until="domcontentloaded", timeout=60000); await pg.wait_for_timeout(9000)
                txt = (await pg.inner_text("body"))[:600]
            except Exception as e:
                txt = f"erro {type(e).__name__}"
            print(json.dumps({"url": url[30:], "texto": txt.replace("\n", " | "), "rpcs": achados[:3]}, ensure_ascii=False))
            await pg.close()
        for termo in []:
            pg = await ctx.new_page()
            achados = []

            async def resp(r, achados=achados):
                if "/anji/_/rpc/" in r.url:
                    try:
                        corpo = await r.text()
                    except Exception:
                        corpo = ""
                    achados.append({"rpc": r.url.split("/rpc/")[1].split("?")[0], "st": r.status, "bytes": len(corpo), "ini": corpo[:700]})
            pg.on("response", resp)
            try:
                await pg.goto("https://adstransparency.google.com/?region=BR", wait_until="domcontentloaded", timeout=60000)
                await pg.wait_for_timeout(5000)
                caixa = pg.locator("input").first
                await caixa.click()
                await caixa.type(termo, delay=80)
                await pg.wait_for_timeout(4000)
                opcoes = await pg.locator("[role=option], material-select-item, .suggestion").all_inner_texts()
                await caixa.press("Enter")
                await pg.wait_for_timeout(7000)
                url = pg.url
            except Exception as e:
                opcoes, url = [f"erro {type(e).__name__}"], ""
            print(json.dumps({"termo": termo, "url_final": url[:160], "sugestoes": [o[:80] for o in opcoes[:8]],
                              "rpcs": [{k: v for k, v in a.items()} for a in achados if a["rpc"] != "TfaarAdvertiserService/GetAdvertiserDunsMapping"][:4]},
                             ensure_ascii=False))
            await pg.close()
        await b.close()

asyncio.run(main())
