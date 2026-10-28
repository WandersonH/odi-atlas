#!/usr/bin/env python3
"""Totais que as próprias plataformas informam para os termos de um caso (universo informado, regra 9 do CLAUDE.md).

Pedido do responsável (28/10/2026, 01h29): "não consegue só o número geral pra termos o tamanho de amostra?".
Só há número oficial para hashtags (e uma estimativa do YouTube para buscas); frases no X e no Facebook não têm total publicado.
  - Instagram: página da hashtag (apify/instagram-scraper, resultsType "details") → postsCount (todos os tempos, não só o período);
    conta 1, teto US$ 0,10 (custo de tabela ~US$ 0,0026 por hashtag).
  - TikTok: página pública da hashtag (Playwright, sem login, grátis) → videoCount e viewCount do desafio (todos os tempos).
  - YouTube: search.list desde o início do caso → pageInfo.totalResults (estimativa arredondada que o próprio YouTube informa).
  - X e Facebook: ⛔ não informam total.
Público: data/casos/<caso>/contagens_plataforma.json.
Uso: python scripts/contagens_plataforma.py --caso 014 [--sem-instagram] [--sem-tiktok] [--sem-youtube]
"""
from __future__ import annotations

import asyncio
import json
import os
import re
import sys
import urllib.parse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from net import get_json, now_utc  # noqa: E402


def instagram(tags: list[str], token: str, executar=None) -> list[dict]:
    from collect_meta_apify import run_actor
    executar = executar or (lambda a, p, c: run_actor(token, a, p, c))
    pl = {"directUrls": [f"https://www.instagram.com/explore/tags/{t}/" for t in tags], "resultsType": "details", "resultsLimit": 1}
    try:
        run, itens = executar("apify~instagram-scraper", pl, 0.10)
    except Exception as e:  # noqa: BLE001
        return [{"hashtag": t, "erro": type(e).__name__} for t in tags]
    por = {}
    for x in itens or []:
        nome = str(x.get("name") or x.get("hashtag") or "").lstrip("#").lower() or re.sub(r".*/tags/([^/]+)/?.*", r"\1", str(x.get("url") or x.get("inputUrl") or "")).lower()
        por[nome] = x
    out = []
    for t in tags:
        x = por.get(t.lower(), {})
        n = x.get("postsCount") or x.get("mediaCount") or x.get("posts_count")
        out.append({"hashtag": t, "total_posts": int(n) if str(n or "").isdigit() else None, "fonte": "Instagram, página da hashtag (postsCount)",
                    "run": (run or {}).get("id"), "erro": x.get("error") if x else "sem item"})
    return out


async def _tiktok(tags: list[str]) -> list[dict]:
    from playwright.async_api import async_playwright
    out = []
    async with async_playwright() as p:
        b = await p.chromium.launch()
        pg = await b.new_page(locale="pt-BR")
        for t in tags:
            reg = {"hashtag": t, "total_videos": None, "total_visualizacoes": None, "fonte": "TikTok, página pública da hashtag (challengeInfo.stats)"}
            try:
                await pg.goto(f"https://www.tiktok.com/tag/{urllib.parse.quote(t)}", wait_until="domcontentloaded", timeout=45000)
                await pg.wait_for_timeout(2500)
                txt = await pg.evaluate("() => (document.getElementById('__UNIVERSAL_DATA_FOR_REHYDRATION__')||{}).textContent || ''")
                d = json.loads(txt) if txt else {}
                ch = ((d.get("__DEFAULT_SCOPE__") or {}).get("webapp.challenge-detail") or {}).get("challengeInfo") or {}
                st = ch.get("statsV2") or ch.get("stats") or {}
                reg["total_videos"] = int(st["videoCount"]) if str(st.get("videoCount", "")).isdigit() else None
                reg["total_visualizacoes"] = int(st["viewCount"]) if str(st.get("viewCount", "")).isdigit() else None
                if reg["total_videos"] is None:
                    reg["erro"] = "página sem dados do desafio (hashtag inexistente ou bloqueio)"
            except Exception as e:  # noqa: BLE001
                reg["erro"] = type(e).__name__
            out.append(reg)
        await b.close()
    return out


def youtube(buscas: list[str], desde: str, key: str) -> list[dict]:
    out = []
    for q in buscas:
        reg = {"busca": q, "total_estimado": None, "fonte": "YouTube Data API, search.list pageInfo.totalResults (estimativa do YouTube, arredondada)"}
        try:
            d = get_json("https://www.googleapis.com/youtube/v3/search?" + urllib.parse.urlencode(
                {"part": "id", "q": q, "type": "video", "maxResults": 1, "publishedAfter": desde + "T00:00:00Z", "regionCode": "BR", "key": key}), timeout=60)
            reg["total_estimado"] = (d.get("pageInfo") or {}).get("totalResults")
        except Exception as e:  # noqa: BLE001 — a mensagem pode conter a chave
            reg["erro"] = type(e).__name__
        out.append(reg)
    return out


def main(argv=None) -> int:
    argv = sys.argv[1:] if argv is None else list(argv)
    caso = argv[argv.index("--caso") + 1] if "--caso" in argv else "014"
    cfg = next(c for c in json.loads(Path("data/config/casos.json").read_text(encoding="utf-8"))["casos"] if c["id"] == caso)
    tags = list(dict.fromkeys(cfg.get("hashtags", []) + [t for k, v in cfg.items() if k.startswith("hashtags_instagram") for t in v]))
    out = {"caso": caso, "gerado_em_utc": now_utc(), "pedido": "Responsável em 28/10/2026, 01h29: \"não consegue só o número geral pra termos o tamanho de amostra?\"",
           "aviso": "Totais de hashtag são de TODOS OS TEMPOS (a plataforma não informa por período) e só valem para quem usou a hashtag; frases não têm total publicado. "
                    "O YouTube informa uma estimativa arredondada. X e Facebook não informam total.",
           "x": {"total": None, "fonte": "⛔ o X não informa total de publicações por termo sem a API paga"},
           "facebook": {"total": None, "fonte": "⛔ o Facebook não informa total de publicações por termo ou hashtag"}}
    if "--sem-instagram" not in argv:
        tok = os.environ.get("APIFY_TOKEN", "").strip()
        out["instagram"] = instagram(tags, tok) if tok else [{"hashtag": t, "erro": "APIFY_TOKEN ausente"} for t in tags]
    if "--sem-tiktok" not in argv:
        out["tiktok"] = asyncio.run(_tiktok(tags))
    if "--sem-youtube" not in argv and os.environ.get("YOUTUBE_API_KEY"):
        out["youtube"] = youtube(cfg.get("buscas_tiktok", [])[:8], cfg["desde"], os.environ["YOUTUBE_API_KEY"])
    dest = Path("data/casos") / caso
    dest.mkdir(parents=True, exist_ok=True)
    (dest / "contagens_plataforma.json").write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"caso {caso} contagens: instagram {[(x['hashtag'], x.get('total_posts')) for x in out.get('instagram', [])]} · "
          f"tiktok {[(x['hashtag'], x.get('total_videos')) for x in out.get('tiktok', [])]} · youtube {[(x['busca'], x.get('total_estimado')) for x in out.get('youtube', [])]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
