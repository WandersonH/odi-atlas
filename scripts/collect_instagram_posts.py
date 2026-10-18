#!/usr/bin/env python3
"""Posts públicos dos perfis de Instagram declarados ao TSE pelas chapas 13 e 22 (presidente e vice), desde 20/07/2026.

Autorização (18/10/2026, 02h24): teto de US$ 5, numa das contas novas (APIFY_TOKEN_8; a conta 1 não é usada).
Atores em ordem de preço (loja Apify, plano gratuito, consulta de 18/10): o coletor usa o primeiro de `atores` em
data/config/instagram_posts.json; `--ator dono~nome` força outro (para o teste comparativo).

--teste: 10 posts de @lulaoficial (teto de teste).
sem opção: uma execução por perfil, posts desde `desde`, até N (perfis principais têm cota maior), 4 em paralelo.

Saída pública: data/instagram/videos.csv.gz (mesmas colunas de TikTok/Kwai/Facebook/X: video_id = shortcode,
legenda = texto; visualizações só em vídeos/reels), data/instagram/manifesto-*.json. Bruto no repositório privado.
"""
from __future__ import annotations

import csv
import gzip
import json
import os
import re
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from collect_kwai_apify import COLS, g, inteiro, quando  # noqa: E402
from collect_meta_anuncios_apify import custo_run  # noqa: E402
from collect_meta_apify import escolher_conta, ig_username, run_actor  # noqa: E402
from net import now_utc  # noqa: E402

COLS_IG = COLS + ["tipo"]
IDS = {"13": ("280002542548", "Lula"), "22": ("280002551544", "Flávio Bolsonaro")}
PRINCIPAIS = {"lulaoficial", "flaviobolsonaro"}


def perfis(root: Path, excluir: set[str]) -> list[dict]:
    out, vistos = [], set()
    for r in csv.DictReader(gzip.open(root / "data/tse/redes_sociais_candidatos_2026.csv.gz", "rt", encoding="utf-8"), delimiter=";"):
        if r.get("PLATAFORMA") != "instagram" or r.get("NR_CANDIDATO") not in IDS or r.get("DS_CARGO", "").upper() not in ("PRESIDENTE", "VICE-PRESIDENTE"):
            continue
        u = ig_username(r["DS_URL"])
        if not u or u in vistos or u in excluir:
            continue
        vistos.add(u)
        cid, nome = IDS[r["NR_CANDIDATO"]]
        out.append({"perfil": u, "url_tse": r["DS_URL"].strip(), "candidate_id": cid, "candidato": nome,
                    "declarado_por": r.get("NM_URNA_CANDIDATO", ""), "principal": u in PRINCIPAIS})
    return sorted(out, key=lambda p: (not p["principal"], p["candidato"] != "Lula", p["perfil"]))


def entrada(ator: str, perfil: str, n: int, desde: str) -> dict:
    if ator.startswith("esdrasdw~"):
        return {"directUrls": [perfil], "resultsType": "posts", "resultsLimit": n, "onlyPostsNewerThan": desde}
    if ator.startswith("apidojo~"):
        return {"startUrls": [f"https://www.instagram.com/{perfil}/"], "maxItems": n, "until": desde}
    if ator.startswith("apify~instagram-post-scraper"):
        return {"username": [perfil], "resultsLimit": n, "onlyPostsNewerThan": desde}
    return {"directUrls": [f"https://www.instagram.com/{perfil}/"], "resultsType": "posts", "resultsLimit": n, "onlyPostsNewerThan": desde}


def linha(x: dict, pf: dict, agora: str, old: dict) -> dict:
    sc = str(g(x, "shortCode", "shortcode", "code") or "")
    url = g(x, "url", "postUrl") or (f"https://www.instagram.com/p/{sc}/" if sc else "")
    tipo = str(g(x, "type", "productType", "media_type") or "")
    views = inteiro(g(x, "videoPlayCount", "videoViewCount", "playCount", "viewCount", "video_view_count"))
    likes = inteiro(g(x, "likesCount", "likeCount", "like_count"))
    return {"candidate_id": pf["candidate_id"], "candidate_name": pf["candidato"], "perfil": pf["perfil"], "declarado_por": pf["declarado_por"],
            "video_id": sc or str(g(x, "id", "pk") or ""), "url": url, "publicado_em": quando(g(x, "timestamp", "takenAt", "taken_at", "createdAt")),
            "legenda": " ".join(str(g(x, "caption", "caption.text", "text", "title") or "").split()),
            "duracao_s": inteiro(g(x, "videoDuration", "video_duration")) or "", "visualizacoes": views,
            "curtidas": likes if likes is not None and likes >= 0 else None, "comentarios": inteiro(g(x, "commentsCount", "commentCount", "comment_count")),
            "compartilhamentos": inteiro(g(x, "reshareCount", "sharesCount")), "primeira_coleta": old.get("primeira_coleta") or agora,
            "ultima_coleta": agora, "capa_url": g(x, "displayUrl", "thumbnailUrl", "imageUrl", "image_versions2.candidates.0.url") or old.get("capa_url", ""),
            "tipo": "vídeo" if views is not None or re.search(r"video|reel|clip", tipo, re.I) else "post"}


def main(argv=None, executar=None) -> int:
    argv = list(argv or [])
    root = Path(".")
    cfg = json.loads((root / "data/config/instagram_posts.json").read_text(encoding="utf-8"))
    teste = "--teste" in argv
    ator = argv[argv.index("--ator") + 1] if "--ator" in argv else cfg["atores"][0]["ator"]
    preco = next((a for a in cfg["atores"] if a["ator"] == ator), cfg["atores"][0])
    pasta = root / "data/instagram"
    pasta.mkdir(parents=True, exist_ok=True)
    agora = now_utc()
    ja = round(sum(float(json.loads(f.read_text(encoding="utf-8")).get("custo_usd") or 0) for f in pasta.glob("manifesto-*.json")), 4)
    resta = round(cfg["teto_total_usd"] - ja, 4)
    teto = min(cfg["teto_teste_usd"], resta) if teste else resta
    man = {"run_started_utc": agora, "ferramenta": f"Apify · {ator.replace('~', '/')}", "modo": "teste" if teste else "carga",
           "teto_total_usd": cfg["teto_total_usd"], "gasto_antes_usd": ja, "teto_execucao_usd": teto, "perfis": []}

    def fim(status: str, code: int) -> int:
        man["status"] = status
        stamp = agora.replace(":", "").replace("-", "")
        for nome in (f"manifesto-{stamp}.json", "manifesto_latest.json"):
            (pasta / nome).write_text(json.dumps(man, ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"instagram: {status}")
        return code

    if teto < 0.01:
        return fim(f"⛔ teto autorizado de US$ {cfg['teto_total_usd']} esgotado (gasto US$ {ja})", 1)
    nome_conta, token, saldo = escolher_conta(cfg["segredos"], min(teto, 0.05)) if executar is None else ("teste", "x", None)
    man.update(conta=nome_conta, saldo_conta_antes_usd=saldo)
    if not token:
        return fim(f"⛔ conta Apify sem saldo ({', '.join(cfg['segredos'])})", 1)
    if saldo is not None:
        teto = min(teto, saldo)
    executar = executar or (lambda pl, cap: run_actor(token, ator, pl, cap))
    excluir = set(cfg.get("perfis_inexistentes") or [])
    todos = perfis(root, excluir)
    p_item, p_run = preco["item"], preco.get("inicio", 0.0)
    if teste:
        alvos = [(next(p for p in todos if p["perfil"] == cfg["teste"]["perfil"]), cfg["teste"]["posts"])]
    else:
        alvos, est = [], 0.0
        for pf in todos:
            n = cfg["posts_por_perfil"]["principal" if pf["principal"] else "outros"]
            c = p_run + p_item * n
            if est + c > teto * 0.95:
                break
            alvos.append((pf, n))
            est += c
    man["perfis_planejados"] = len(alvos)
    man["perfis_fora_do_teto"] = [p["perfil"] for p in todos if p["perfil"] not in {a[0]["perfil"] for a in alvos}]

    def um(a):
        pf, n = a
        try:
            run, itens = executar(entrada(ator, pf["perfil"], n, cfg["desde"]), max(0.1, round(p_run + p_item * n * 1.3 + 0.005, 4)))
            return pf, n, run or {}, itens or [], None
        except Exception as e:  # noqa: BLE001 — o token vai no cabeçalho
            corpo = ""
            try:
                corpo = e.read().decode("utf-8", "replace")[:300]
            except Exception:  # noqa: BLE001
                pass
            return pf, n, {}, [], f"{type(e).__name__} {getattr(e, 'code', '')} {corpo}".strip()
    with ThreadPoolExecutor(max_workers=4) as ex:
        res = list(ex.map(um, alvos))
    src = pasta / "videos.csv.gz"
    acervo = {r["video_id"]: r for r in csv.DictReader(gzip.open(src, "rt", encoding="utf-8"), delimiter=";")} if src.exists() else {}
    gasto, novos, brutos = 0.0, 0, []
    for pf, n, run, itens, erro in res:
        posts = [x for x in itens if g(x, "shortCode", "shortcode", "code", "id") and not x.get("error") and not x.get("demo")]
        brutos += itens
        custo = 0.0 if erro and not run else max(custo_run(run) or 0, round(p_run + p_item * len(itens), 5))
        gasto += custo
        lidos = 0
        for x in posts:
            r = linha(x, pf, agora, acervo.get(str(g(x, "shortCode", "shortcode", "code") or "")) or {})
            if r["video_id"] and (r["publicado_em"] or "9") >= cfg["desde"]:
                novos += 0 if r["video_id"] in acervo else 1
                acervo[r["video_id"]] = r
                lidos += 1
        man["perfis"].append({"perfil": pf["perfil"], "candidato": pf["candidato"], "declarado_por": pf["declarado_por"], "pedido": n,
                              "itens": len(itens), "lidos_no_periodo": lidos,
                              "erro": erro or next((str(x.get("error") or x.get("errorDescription"))[:200] for x in itens if x.get("error")), None),
                              "mais_antigo": min((quando(g(x, "timestamp", "takenAt")) for x in posts), default=None),
                              "run": run.get("id"), "custo_usd": custo})
        print(f"@{pf['perfil']}: {lidos} posts no período ({len(itens)} itens, pedido {n}){' · ' + erro if erro else ''}")
    interno = os.environ.get("ODI_INTERNO_DIR")
    if interno and brutos:
        d = Path(interno) / "instagram"
        d.mkdir(parents=True, exist_ok=True)
        with gzip.open(d / f"apify_{agora.replace(':', '').replace('-', '')}.jsonl.gz", "wt", encoding="utf-8") as f:
            for x in brutos:
                f.write(json.dumps(x, ensure_ascii=False) + "\n")
    with gzip.open(src, "wt", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, COLS_IG, delimiter=";", lineterminator="\n", extrasaction="ignore")
        w.writeheader()
        w.writerows(sorted(acervo.values(), key=lambda r: (r["candidate_id"], r["publicado_em"]), reverse=True))
    man.update(custo_usd=round(gasto, 4), posts_novos=novos, posts_no_acervo=len(acervo),
               campos_vazios={k: sum(1 for r in acervo.values() if r.get(k) in (None, "")) for k in ("legenda", "publicado_em", "curtidas", "comentarios", "visualizacoes", "capa_url")})
    if brutos:
        print("chaves do 1º item: " + ", ".join(sorted(brutos[0].keys()))[:900])
    print(f"{novos} posts novos · acervo {len(acervo)} · campos vazios {man['campos_vazios']}")
    return fim("ok" if acervo else "⛔ nenhum post lido", 0 if acervo else 1)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
