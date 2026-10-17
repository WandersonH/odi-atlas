#!/usr/bin/env python3
"""Central de Transparência de Anúncios do Google — anúncios de partidos e candidatos (região Brasil).

Navegador headless (Playwright) sem login: digita cada termo na busca da Central (RPC SearchSuggestions), aceita só
anunciantes do Brasil cujo nome verificado corresponde à lista de config (sem pessoas físicas homônimas), abre a
página de cada anunciante e de cada domínio oficial e lê os anúncios (RPC SearchCreatives), rolando até o fim.
Saída: data/google_ads/transparencia.json (e histórico de anúncios vistos em data/google_ads/anuncios.csv).
"""
from __future__ import annotations

import asyncio
import csv
import datetime as dt
import json
import sys
import unicodedata
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from net import now_utc  # noqa: E402

BASE = "https://adstransparency.google.com"
FORMATO = {1: "texto", 2: "imagem", 3: "vídeo"}
COLS = ["creative_id", "advertiser_id", "anunciante", "dominio", "formato", "primeira_exibicao", "ultima_exibicao", "origem", "visto_em"]


def norm(s: str) -> str:
    return " ".join(unicodedata.normalize("NFKD", s or "").encode("ascii", "ignore").decode().lower().split())


def ts(x) -> str | None:
    try:
        return dt.datetime.fromtimestamp(int(x["1"]), dt.timezone.utc).strftime("%Y-%m-%d")
    except (KeyError, TypeError, ValueError):
        return None


def parse_criativos(d: dict, origem: str) -> list[dict]:
    out = []
    for c in d.get("1", []) or []:
        if not isinstance(c, dict) or not c.get("2"):
            continue
        out.append({"creative_id": c["2"], "advertiser_id": c.get("1", ""), "anunciante": c.get("12", ""),
                    "dominio": c.get("14", ""), "formato": FORMATO.get(c.get("4"), str(c.get("4", ""))),
                    "primeira_exibicao": ts(c.get("6")), "ultima_exibicao": ts(c.get("7")), "origem": origem,
                    "url": f"{BASE}/advertiser/{c.get('1', '')}/creative/{c['2']}?region=BR"})
    return out


def aceitar(sug: dict, aceitos: list[str]) -> bool:
    nome = norm(sug.get("nome", ""))
    return sug.get("pais") == "BR" and any(a in nome for a in aceitos)


async def coletar(cfg: dict) -> tuple[dict, list[dict], list[str]]:
    from playwright.async_api import async_playwright
    anunciantes, criativos, erros = {}, {}, []
    async with async_playwright() as p:
        b = await p.chromium.launch(headless=True)
        ctx = await b.new_context(locale="pt-BR", viewport={"width": 1366, "height": 900},
                                  user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0 Safari/537.36")
        # 1) busca por nome
        for termo in cfg["buscas"]:
            pg = await ctx.new_page()
            sugs = []

            async def r1(r, sugs=sugs):
                if "SearchService/SearchSuggestions" in r.url:
                    try:
                        for it in (await r.json()).get("1", []):
                            a = it.get("1")
                            if a:
                                sugs.append({"nome": a.get("1", ""), "id": a.get("2", ""), "pais": a.get("3", "")})
                    except Exception:  # noqa: BLE001
                        pass
            pg.on("response", r1)
            try:
                await pg.goto(f"{BASE}/?region={cfg['regiao']}", wait_until="domcontentloaded", timeout=60000)
                await pg.wait_for_timeout(4000)
                caixa = pg.locator("input").first
                await caixa.click()
                await caixa.type(termo, delay=80)
                await pg.wait_for_timeout(4500)
            except Exception as e:  # noqa: BLE001
                erros.append(f"busca '{termo}': {type(e).__name__}")
            for s in sugs:
                if aceitar(s, cfg["anunciantes_aceitos"]):
                    anunciantes.setdefault(s["id"], {"advertiser_id": s["id"], "nome": s["nome"], "encontrado_por": termo})
            await pg.close()
        # 2) página de cada anunciante e de cada domínio
        alvos = [(f"{BASE}/advertiser/{a}?region={cfg['regiao']}", f"anunciante:{a}") for a in anunciantes] + \
                [(f"{BASE}/?region={cfg['regiao']}&domain={d}", f"dominio:{d}") for d in cfg["dominios"]]
        for url, origem in alvos:
            pg = await ctx.new_page()
            lidos = []

            async def r2(r, lidos=lidos, origem=origem):
                if "SearchService/SearchCreatives" in r.url:
                    try:
                        lidos.extend(parse_criativos(await r.json(), origem))
                    except Exception:  # noqa: BLE001
                        pass
            pg.on("response", r2)
            try:
                await pg.goto(url, wait_until="domcontentloaded", timeout=60000)
                await pg.wait_for_timeout(7000)
                antes = -1
                for _ in range(40):  # rola até parar de carregar
                    if len(lidos) == antes:
                        break
                    antes = len(lidos)
                    await pg.mouse.wheel(0, 6000)
                    await pg.wait_for_timeout(2500)
            except Exception as e:  # noqa: BLE001
                erros.append(f"{origem}: {type(e).__name__}")
            for c in lidos:
                criativos.setdefault(c["creative_id"], c)
                if c["advertiser_id"] and c["advertiser_id"] not in anunciantes and origem.startswith("dominio:"):
                    anunciantes[c["advertiser_id"]] = {"advertiser_id": c["advertiser_id"], "nome": c["anunciante"], "encontrado_por": origem}
            await pg.close()
        await b.close()
    return anunciantes, list(criativos.values()), erros


def resumir(anunciantes: dict, criativos: list[dict], cfg: dict) -> list[dict]:
    out = []
    for a in anunciantes.values():
        cs = [c for c in criativos if c["advertiser_id"] == a["advertiser_id"]]
        noperiodo = [c for c in cs if (c["ultima_exibicao"] or "") >= cfg["inicio_periodo_eleitoral"]]
        na_campanha = [c for c in cs if (c["ultima_exibicao"] or "") >= cfg["inicio_campanha"]]
        fmt = {}
        for c in cs:
            fmt[c["formato"]] = fmt.get(c["formato"], 0) + 1
        out.append({**a, "anuncios": len(cs), "formatos": fmt,
                    "primeira_exibicao": min((c["primeira_exibicao"] for c in cs if c["primeira_exibicao"]), default=None),
                    "ultima_exibicao": max((c["ultima_exibicao"] for c in cs if c["ultima_exibicao"]), default=None),
                    "exibidos_desde_inicio_periodo": len(noperiodo), "exibidos_na_campanha": len(na_campanha),
                    "url": f"{BASE}/advertiser/{a['advertiser_id']}?region=BR"})
    return sorted(out, key=lambda x: (-x["exibidos_na_campanha"], -x["anuncios"], x["nome"]))


def main(argv=None, coletar_fn=None) -> int:
    root = Path(argv[0]) if argv else Path(".")
    cfg = json.loads((root / "data/config/google_transparencia.json").read_text(encoding="utf-8"))
    agora = now_utc()
    try:
        anunciantes, criativos, erros = asyncio.run(coletar(cfg)) if coletar_fn is None else coletar_fn(cfg)
    except Exception as e:  # noqa: BLE001
        anunciantes, criativos, erros = {}, [], [f"navegador: {type(e).__name__} {e}"[:200]]
    pasta = root / "data/google_ads"
    pasta.mkdir(parents=True, exist_ok=True)
    resumo = resumir(anunciantes, criativos, cfg)
    camp = sorted((c for c in criativos if (c["ultima_exibicao"] or "") >= cfg["inicio_campanha"]),
                  key=lambda c: c["ultima_exibicao"] or "", reverse=True)
    status = "ok" if (anunciantes or criativos) and not erros else ("⚠️ parcial: " + "; ".join(erros) if anunciantes or criativos else "⛔ " + ("; ".join(erros) or "nenhum anunciante encontrado"))
    out = {"schema_version": 1, "coletado_em_utc": agora, "fonte": "Google · Central de Transparência de Anúncios (navegador sem login)",
           "nota": cfg["nota"], "status": status, "anunciantes": resumo, "total_anuncios": len(criativos),
           "anuncios_exibidos_na_campanha": camp, "erros": erros}
    (pasta / "transparencia.json").write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    hist = pasta / "anuncios.csv"
    vistos = {}
    if hist.exists():
        vistos = {r["creative_id"]: r for r in csv.DictReader(open(hist, encoding="utf-8"), delimiter=";")}
    for c in criativos:
        vistos[c["creative_id"]] = {**vistos.get(c["creative_id"], {}), **{k: c.get(k, "") for k in COLS if k != "visto_em"}, "visto_em": agora}
    with open(hist, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, COLS, delimiter=";", lineterminator="\n", extrasaction="ignore")
        w.writeheader()
        w.writerows(sorted(vistos.values(), key=lambda r: (r["advertiser_id"], r["creative_id"])))
    for a in resumo:
        print(f"{a['nome']} ({a['advertiser_id']}): {a['anuncios']} anúncios · última exibição {a['ultima_exibicao']} · na campanha {a['exibidos_na_campanha']}")
    print(f"google transparência: {status} · {len(resumo)} anunciantes · {len(criativos)} anúncios · {len(camp)} exibidos desde {cfg['inicio_campanha']}")
    return 0 if anunciantes or criativos else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
