"""Rótulo de IA nas campanhas: o que as plataformas marcam como conteúdo sintético/gerado por IA (grátis).

1. YouTube (Data API, chave YOUTUBE_API_KEY): videos.list part=status — campo `status.containsSyntheticMedia`, a declaração
   do próprio canal de que o vídeo tem conteúdo alterado ou sintético. Vídeos: os dos canais das candidaturas
   (data/youtube/videos_latest.csv.gz) e os vídeos sobre o debate (data/debate/youtube_videos.json).
2. TikTok (página pública do perfil, Playwright, sem login): guarda de cada vídeo qualquer campo cujo nome indique
   rótulo de IA (AIGC, aigc, aiGenerated…) — o TikTok não documenta esses campos; o manifesto lista o que apareceu.
   Perfis: os declarados ao TSE pelas chapas presidenciais (os mesmos do collect_tiktok.py).
3. Instagram: ⛔ nenhuma das ferramentas usadas devolve o rótulo "Informações de IA" (verificado em 19/10 nos ~16,6 mil
   posts já coletados, 15 campos por post). Fica registrado como lacuna.

Saída pública: data/ia/rotulo_coleta.json (vídeos de contas públicas de campanha e canais, só metadados).
Uso: python scripts/collect_rotulo_ia.py [--sem-tiktok] [--rolagens 15]
"""
from __future__ import annotations

import asyncio
import csv
import gzip
import json
import os
import re
import sys
import urllib.error
import urllib.parse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from net import get_json, now_utc  # noqa: E402

API = "https://www.googleapis.com/youtube/v3/videos"
CAMPO_IA = re.compile(r"aigc|ai_?generat|aigenerat|ai_?label|synthetic|ia_?gerad|created_?by_?ai|madewithai|is_?ai\b", re.I)
ERROS: list[str] = []


def campos_ia(o, caminho: str = "") -> dict:
    """Todos os campos (em qualquer nível) cujo nome sugere rótulo de IA → {caminho: valor curto}."""
    out = {}
    if isinstance(o, dict):
        for k, v in o.items():
            c = f"{caminho}.{k}" if caminho else k
            if CAMPO_IA.search(k):
                out[c] = v if isinstance(v, (bool, int, float)) or v is None else str(v)[:120]
            if isinstance(v, (dict, list)):
                out.update(campos_ia(v, c))
    elif isinstance(o, list):
        for v in o[:5]:
            out.update(campos_ia(v, caminho + "[]"))
    return out


def tem_rotulo(campos: dict) -> bool:
    """Rótulo ativo: algum campo de IA com valor verdadeiro, número > 0 ou texto não vazio."""
    for v in campos.values():
        if v is True or (isinstance(v, (int, float)) and not isinstance(v, bool) and v > 0) or (isinstance(v, str) and v.strip() not in ("", "0", "false", "False")):
            return True
    return False


def youtube_alvos(root: Path) -> list[dict]:
    cfg = json.loads((root / "data/config/temas_youtube.json").read_text(encoding="utf-8"))
    out = []
    for r in csv.DictReader(gzip.open(root / "data/youtube/videos_latest.csv.gz", "rt", encoding="utf-8"), delimiter=";"):
        if r["candidate_id"] in cfg["candidatos"]:
            out.append({"id": r["video_id"], "origem": "canal da candidatura", "candidato": r["candidate_name"] or cfg["candidatos"][r["candidate_id"]]["nome"],
                        "canal": r["canal"], "titulo": r["titulo"], "publicado_em": r["publicado_em"]})
    deb = root / "data/debate/youtube_videos.json"
    if deb.exists():
        for v in json.loads(deb.read_text(encoding="utf-8"))["videos"]:
            out.append({"id": v["id"], "origem": "vídeo sobre o debate", "candidato": v.get("campanha"), "canal": v["canal"],
                        "titulo": v["titulo"], "publicado_em": v["publicado_em"]})
    vistos, uniq = set(), []
    for a in out:
        if a["id"] not in vistos:
            vistos.add(a["id"])
            uniq.append(a)
    return uniq


def youtube(key: str, alvos: list[dict]) -> list[dict]:
    por = {a["id"]: a for a in alvos}
    ids = list(por)
    for i in range(0, len(ids), 50):
        try:
            d = get_json(API + "?" + urllib.parse.urlencode({"part": "status", "id": ",".join(ids[i:i + 50]), "key": key}), timeout=60)
        except urllib.error.HTTPError as e:
            ERROS.append(f"youtube videos.list: HTTP {e.code}")
            if e.code == 403:
                break
            continue
        except Exception as e:  # noqa: BLE001 — a mensagem pode ter a URL com a chave
            ERROS.append(f"youtube videos.list: {type(e).__name__}")
            continue
        for it in d.get("items", []):
            st = it.get("status") or {}
            por[it["id"]]["campo_presente"] = "containsSyntheticMedia" in st
            por[it["id"]]["sintetico_declarado"] = st.get("containsSyntheticMedia")
    return [a for a in por.values() if "campo_presente" in a]


async def tiktok(perfis: list[dict], rolagens: int) -> tuple[list[dict], dict]:
    from playwright.async_api import async_playwright
    out, resumo = [], {}
    async with async_playwright() as p:
        b = await p.chromium.launch(headless=True)
        ctx = await b.new_context(locale="pt-BR", viewport={"width": 1366, "height": 900},
                                  user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36")
        for a in perfis:
            pg, itens, respostas = await ctx.new_page(), [], []

            async def resp(r, itens=itens, respostas=respostas):
                if "/api/post/item_list" in r.url or "/api/creator/item_list" in r.url:
                    respostas.append(r.status)
                    try:
                        itens.extend((await r.json()).get("itemList") or [])
                    except Exception:  # noqa: BLE001
                        pass
            pg.on("response", resp)
            erro = None
            try:
                await pg.goto(f"https://www.tiktok.com/@{a['perfil']}", wait_until="domcontentloaded", timeout=45000)
                await pg.wait_for_timeout(6000)
                # a primeira página de vídeos vem embutida no HTML (estado inicial); lê de lá também
                try:
                    estado = await pg.evaluate("() => { const s = document.getElementById('__UNIVERSAL_DATA_FOR_REHYDRATION__'); return s ? s.textContent : null; }")
                    if estado:
                        d = json.loads(estado)
                        ilm = (((d.get("__DEFAULT_SCOPE__") or {}).get("webapp.user-detail") or {}).get("itemList")) or []
                        itens.extend(ilm)
                except Exception:  # noqa: BLE001
                    pass
                parado = 0
                for _ in range(rolagens):
                    antes = len(itens)
                    await pg.mouse.wheel(0, 4000)
                    await pg.wait_for_timeout(2500)
                    parado = parado + 1 if len(itens) == antes else 0
                    if parado >= 3:
                        break
            except Exception as e:  # noqa: BLE001
                erro = type(e).__name__
            await pg.close()
            vistos, nomes = set(), set()
            for it in itens:
                if not it.get("id") or it["id"] in vistos:
                    continue
                vistos.add(it["id"])
                c = campos_ia(it)
                nomes |= set(c)
                ts = it.get("createTime")
                out.append({"id": str(it["id"]), "perfil": a["perfil"], "candidato": a["candidate_name"],
                            "publicado_em": (__import__("datetime").datetime.fromtimestamp(int(ts), __import__("datetime").timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ") if str(ts or "").isdigit() else None),
                            "legenda": " ".join((it.get("desc") or "").split())[:200], "url": f"https://www.tiktok.com/@{a['perfil']}/video/{it['id']}",
                            "campos_ia": c, "rotulo_ia": tem_rotulo(c),
                            "visualizacoes": (it.get("stats") or {}).get("playCount")})
            resumo[a["perfil"]] = {"candidato": a["candidate_name"], "respostas_api": len(respostas), "videos": len(vistos),
                                   "campos_ia_vistos": sorted(nomes), "erro": erro}
            print(f"tiktok @{a['perfil']}: {len(vistos)} vídeos · campos de IA vistos {sorted(nomes)[:6]} {erro or ''}")
        await b.close()
    return out, resumo


def main(argv=None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    root = Path(".")
    key = os.environ.get("YOUTUBE_API_KEY", "").strip()
    out = {"coletado_em_utc": now_utc(), "youtube": None, "tiktok": None,
           "instagram": "⛔ não coletado: as ferramentas usadas no Atlas não devolvem o rótulo 'Informações de IA' "
                        "(verificado em 19/10/2026 em ~16,6 mil posts já coletados; 15 campos por post, nenhum de IA)"}
    if key:
        alvos = youtube_alvos(root)
        vs = youtube(key, alvos)
        out["youtube"] = {"pedidos": len(alvos), "lidos": len(vs), "videos": vs}
        print(f"youtube: {len(vs)} de {len(alvos)} vídeos lidos · campo presente em {sum(v['campo_presente'] for v in vs)} · "
              f"declarados sintéticos {sum(bool(v['sintetico_declarado']) for v in vs)}")
    else:
        ERROS.append("youtube: falta YOUTUBE_API_KEY")
    if "--sem-tiktok" not in argv:
        import collect_tiktok as ct
        perfis = [a for a in ct.alvos(root)]
        rol = int(argv[argv.index("--rolagens") + 1]) if "--rolagens" in argv else 15
        try:
            vids, resumo = asyncio.run(tiktok(perfis, rol))
            out["tiktok"] = {"perfis": resumo, "videos": vids}
        except Exception as e:  # noqa: BLE001
            ERROS.append(f"tiktok: {type(e).__name__}: {str(e)[:200]}")
    out["erros"] = ERROS
    Path("data/ia").mkdir(parents=True, exist_ok=True)
    Path("data/ia/rotulo_coleta.json").write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"erros: {ERROS[:4]}")
    return 0 if (out["youtube"] or out["tiktok"]) else 1


if __name__ == "__main__":
    raise SystemExit(main())
