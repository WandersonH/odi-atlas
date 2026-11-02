#!/usr/bin/env python3
"""Diagnóstico da coleta grátis do TikTok (02/11/2026): desde 30/10 as páginas de hashtag devolvem 0 vídeos.
Abre uma página de hashtag e uma de busca e registra, sem guardar conteúdo: status e tamanho de cada resposta /api/,
chaves do JSON, título da página, se há bloco de dados embutido (__UNIVERSAL_DATA_FOR_REHYDRATION__) e quantos links /video/ há
na página. Uso: python scripts/diag_tiktok.py [hashtag] [busca]"""
import asyncio
import json
import re
import sys


async def main(tag, q):
    from playwright.async_api import async_playwright
    async with async_playwright() as p:
        for ua_nome, ua in (("chrome124", "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"),
                            ("padrao", None)):
            b = await p.chromium.launch(headless=True)
            ctx = await b.new_context(locale="pt-BR", viewport={"width": 1366, "height": 900}, **({"user_agent": ua} if ua else {}))
            for url in (f"https://www.tiktok.com/tag/{tag}", "https://www.tiktok.com/search/video?q=" + q):
                pg = await ctx.new_page()
                log = []

                async def resp(r, log=log):
                    if "/api/" in r.url:
                        try:
                            body = await r.body()
                            try:
                                d = json.loads(body)
                                info = f"chaves={list(d)[:8]} statusCode={d.get('statusCode', d.get('status_code'))} itens={len(d.get('itemList') or d.get('item_list') or d.get('data') or [])}"
                            except Exception:  # noqa: BLE001
                                info = f"não-JSON {body[:60]!r}"
                            log.append(f"{r.status} {len(body)}B {r.url.split('?')[0][-45:]} {info}")
                        except Exception as e:  # noqa: BLE001
                            log.append(f"{r.status} {r.url.split('?')[0][-45:]} sem corpo {type(e).__name__}")
                pg.on("response", resp)
                try:
                    await pg.goto(url, wait_until="domcontentloaded", timeout=45000)
                    await pg.wait_for_timeout(6000)
                    for _ in range(3):
                        await pg.mouse.wheel(0, 4000)
                        await pg.wait_for_timeout(2500)
                    html = await pg.content()
                    tit = await pg.title()
                    m = re.search(r'<script id="__UNIVERSAL_DATA_FOR_REHYDRATION__"[^>]*>(.*?)</script>', html, re.S)
                    uni = ""
                    if m:
                        try:
                            ds = json.loads(m.group(1)).get("__DEFAULT_SCOPE__", {})
                            uni = f"escopos={list(ds)[:10]}"
                        except Exception:  # noqa: BLE001
                            uni = "presente, não lido"
                    vids = len(set(re.findall(r'/@[\w.]+/video/(\d+)', html)))
                    captcha = "captcha" in html.lower() or "verify" in tit.lower()
                    print(f"[{ua_nome}] {url[:60]} | título={tit[:60]!r} | links /video/={vids} | rehydration={uni or 'ausente'} | captcha?={captcha} | html={len(html)}B")
                except Exception as e:  # noqa: BLE001
                    print(f"[{ua_nome}] {url[:60]} | erro {type(e).__name__}")
                for l in log[:12]:
                    print("    ", l)
                await pg.close()
            await b.close()


asyncio.run(main(*(sys.argv[1:3] if len(sys.argv) > 2 else ("lula", "Lula"))))
