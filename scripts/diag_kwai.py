#!/usr/bin/env python3
"""Diagnóstico (não grava dados): o Kwai entrega perfil e vídeos a um navegador sem login? (versão 2026, Playwright)

Para cada perfil declarado ao TSE: abre a página, rola, registra as respostas JSON que a própria página pede (URL interna,
chaves, nº de itens) e o estado embutido no HTML (__NEXT_DATA__ / __INITIAL_STATE__ / window.__*), e tenta achar
seguidores, nº de vídeos, legendas, datas, visualizações e curtidas. Imprime só contagens, chaves e números públicos dos perfis.
"""
import asyncio, json, re

PERFIS = [("22 Flávio Bolsonaro", "https://www.kwai.com/@FLAVIOBOLSONARO"),
          ("13 Lula", "https://k.kwai.com/u/@lulaoficial/XGXCOK66"),
          ("13 Lula · Pode Espalhar", "https://www.kwai.com/u/@podeespalhar/Cu4CfgOx"),
          ("22 Alfredo Gaspar", "https://s.kw.ai/u/ECB8-VMN"),
          ("55 Ronaldo Caiado", "https://www.kwai.com/@RONALDOCAIADO")]
CHAVES = ("fans", "follower", "photo_count", "photoCount", "feeds", "caption", "viewCount", "view_count", "likeCount", "like_count",
          "commentCount", "comment_count", "timestamp", "createTime", "playCount")


def resumo_json(d, prof=0):
    """Chaves de interesse encontradas no JSON (só o primeiro valor de cada, sem textos longos)."""
    achados = {}
    def walk(x, depth=0):
        if depth > 8 or len(achados) >= 14:
            return
        if isinstance(x, dict):
            for k, v in x.items():
                if any(c.lower() in k.lower() for c in CHAVES) and k not in achados and not isinstance(v, (dict, list)):
                    achados[k] = (str(v)[:60])
                walk(v, depth + 1)
        elif isinstance(x, list):
            for v in x[:3]:
                walk(v, depth + 1)
    walk(d)
    return achados


def listas(d):
    """Maior lista de objetos no JSON (provável lista de vídeos) e seu tamanho."""
    best = (None, 0)
    def walk(x, path="", depth=0):
        nonlocal best
        if depth > 8:
            return
        if isinstance(x, list) and x and isinstance(x[0], dict):
            if len(x) > best[1]:
                best = (path, len(x))
        if isinstance(x, dict):
            for k, v in x.items():
                walk(v, f"{path}.{k}", depth + 1)
        elif isinstance(x, list):
            for v in x[:2]:
                walk(v, path + "[]", depth + 1)
    walk(d)
    return best


async def main():
    from playwright.async_api import async_playwright
    async with async_playwright() as p:
        b = await p.chromium.launch(headless=True)
        ctx = await b.new_context(locale="pt-BR", viewport={"width": 1366, "height": 900},
                                  user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0 Safari/537.36")
        for nome, url in PERFIS:
            pg = await ctx.new_page()
            resps = []

            async def on_resp(r, resps=resps):
                if r.request.resource_type in ("xhr", "fetch") and "kwai" in r.url:
                    try:
                        d = await r.json()
                    except Exception:
                        return
                    resps.append({"u": re.sub(r"\?.*", "", r.url)[-80:], "st": r.status, "chaves": sorted(d)[:8] if isinstance(d, dict) else type(d).__name__,
                                  "lista": listas(d), "campos": resumo_json(d)})
            pg.on("response", on_resp)
            try:
                await pg.goto(url, wait_until="domcontentloaded", timeout=60000)
                await pg.wait_for_timeout(7000)
                for _ in range(4):
                    await pg.mouse.wheel(0, 3000); await pg.wait_for_timeout(2500)
                final = pg.url
                html = await pg.content()
                txt = await pg.inner_text("body")
                estado = {}
                for m in re.finditer(r'<script[^>]*id="__NEXT_DATA__"[^>]*>(.*?)</script>', html, re.S):
                    try:
                        dd = json.loads(m.group(1)); estado["__NEXT_DATA__"] = {"campos": resumo_json(dd), "lista": listas(dd)}
                    except Exception:
                        estado["__NEXT_DATA__"] = "não-JSON"
                for m in re.finditer(r"window\.(__[A-Z_]+__)\s*=\s*(\{.*?\});?\s*</script>", html, re.S):
                    try:
                        dd = json.loads(m.group(2)); estado[m.group(1)] = {"campos": resumo_json(dd), "lista": listas(dd)}
                    except Exception:
                        estado[m.group(1)] = f"{len(m.group(2))} chars (não-JSON)"
                n_videos_dom = await pg.locator("video, [class*=video], [class*=feed] img").count()
                login = bool(re.search(r"(Entrar|Log in|Faça login|Iniciar sessão|download the app|Baixe o app)", txt[:3000], re.I))
                nums = re.findall(r"([\d.,]+\s*(?:mil|mi|K|M)?)\s*(Seguidores|Followers|Curtidas|Likes|Vídeos|Videos)", txt, re.I)[:6]
            except Exception as e:
                final, estado, n_videos_dom, login, nums, txt = f"erro {type(e).__name__}", {}, 0, None, [], ""
            print(json.dumps({"perfil": nome, "url_final": final[:110], "login_ou_app": login, "numeros_na_pagina": nums,
                              "elementos_video_dom": n_videos_dom, "estado_embutido": estado, "chars_texto": len(txt),
                              "respostas_json": resps[:6]}, ensure_ascii=False))
            await pg.close()
        await b.close()

asyncio.run(main())
