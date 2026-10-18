#!/usr/bin/env python3
"""Publicações das demais chapas do 1º turno (todas menos 13 e 22), titular e vice, desde 20/07/2026.

Pedido do usuário (18/10/2026): "colete todos dados de rede dos candidatos do 1º turno e vices"; teto de US$ 6 nas contas
dos outros pesquisadores (a conta 1 não é usada). O YouTube já cobre todas as chapas (collect_youtube.py, API oficial).

Perfis: os declarados ao TSE (data/tse/redes_sociais_candidatos_2026.csv.gz), cargos PRESIDENTE e VICE-PRESIDENTE. O vice conta
para a chapa do titular (candidate_id = SQ do titular). Endereços que o TSE classificou como "site_ou_outro" só entram quando
dizem a rede explicitamente ("Tik Tok - @x", "X - @x", kwai-video.com/u/@x); um "@nome" solto não é atribuído a rede nenhuma.

Redes e ferramentas:
- tiktok: yt-dlp (grátis), mesma leitura do coletor das chapas 13 e 22;
- instagram: Apify esdrasdw/instagram-content-scraper (+ leitura de reels para visualizações), conta 8 primeiro;
- facebook: Apify apify/facebook-posts-scraper;
- x: Apify xquik/x-tweet-scraper (busca "from:perfil since:20/07 -filter:retweets");
- kwai: Apify unfenced-group/kwai-scraper.
Cada rede paga tem teto próprio (data/config/primeiro_turno.json); o número de posts por perfil sai do teto, igual para todos
os perfis da rede. Cada rede usa uma conta diferente das já usadas nesta execução.

--rede R (repetível): só essas redes. --teste: 1 perfil por rede, 10 posts.
Saída pública: data/primeiro_turno/<rede>/videos.csv.gz (mesmas colunas dos acervos das chapas 13 e 22) e manifestos.
Bruto no repositório privado (ODI_INTERNO_DIR/primeiro_turno/<rede>/).
"""
from __future__ import annotations

import csv
import gzip
import html
import json
import os
import re
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import collect_facebook_posts as cfb  # noqa: E402
import collect_instagram_posts as cig  # noqa: E402
import collect_x_posts as cx  # noqa: E402
from collect_kwai_apify import COLS, g, inteiro, quando  # noqa: E402
from collect_meta_anuncios_apify import custo_run  # noqa: E402
from collect_meta_apify import escolher_conta, fb_url, ig_username, run_actor  # noqa: E402
from net import now_utc  # noqa: E402

FORA = {"13", "22"}  # já cobertas pelos coletores próprios
REDES = ("tiktok", "instagram", "facebook", "x", "kwai")
COLS_OUT = COLS + ["reacoes", "tipo"]


def _x(url: str) -> str | None:
    m = re.search(r"(?:x|twitter)\.com/@?([A-Za-z0-9_]{1,15})", url, re.I)
    return m.group(1) if m and m.group(1).lower() not in ("share", "intent", "home", "i") else None


def _kwai(url: str) -> str | None:
    m = re.search(r"kwai(?:-video)?\.com/(?:u/)?@([A-Za-z0-9._]+)", url, re.I)
    return m.group(1) if m else None


def _tiktok(url: str) -> str | None:
    m = re.search(r"tiktok\.com/@([A-Za-z0-9._]{2,30})", url, re.I)
    return m.group(1).lower() if m else None


def explicito(url: str) -> tuple[str, str] | None:
    """Endereço do tipo "Tik Tok - @x" ou "X - @x" (o TSE classificou como site_ou_outro)."""
    m = re.match(r"\s*(tik\s*tok|x|twitter|kwai)\s*-\s*@([A-Za-z0-9._]+)\s*$", url, re.I)
    if not m:
        return None
    rede = {"tiktok": "tiktok", "x": "x", "twitter": "x", "kwai": "kwai"}[re.sub(r"\s", "", m.group(1).lower())]
    return rede, m.group(2).lower() if rede == "tiktok" else m.group(2)


def perfil_de(plat: str, url: str) -> tuple[str, str] | None:
    """(rede, identificador) de um endereço declarado ao TSE; None se não der para saber."""
    if plat == "instagram":
        u = ig_username(url)
        return ("instagram", u) if u else None
    if plat == "facebook":
        u = fb_url(url)
        return ("facebook", u) if u and "/share/" not in u.lower() else None  # link de compartilhamento não é página
    if plat == "x":
        u = _x(url)
        return ("x", u) if u else None
    if plat == "tiktok":
        u = _tiktok(url)
        return ("tiktok", u) if u else None
    if plat == "kwai":
        u = _kwai(url)
        return ("kwai", u.lower()) if u else None
    if plat == "site_ou_outro":
        e = explicito(url)
        if e:
            return e
        u = _kwai(url)
        return ("kwai", u.lower()) if u else None
    return None


def alvos(root: Path) -> list[dict]:
    linhas = [r for r in csv.DictReader(gzip.open(root / "data/tse/redes_sociais_candidatos_2026.csv.gz", "rt", encoding="utf-8"), delimiter=";")
              if r.get("DS_CARGO", "").upper() in ("PRESIDENTE", "VICE-PRESIDENTE") and r.get("NR_CANDIDATO") not in FORA]
    urna = json.loads((root / "data/elections.json").read_text(encoding="utf-8"))["candidates"]["2026"]
    titular = {}
    for r in linhas:  # titular = quem estava na urna com o número (a chapa 28 trocou de titular e não foi às urnas)
        if r["DS_CARGO"].upper() == "PRESIDENTE" and (r["NR_CANDIDATO"] not in titular or r.get("NM_URNA_CANDIDATO") == urna.get(r["NR_CANDIDATO"])):
            titular[r["NR_CANDIDATO"]] = (r["SQ_CANDIDATO"], r.get("NM_URNA_CANDIDATO", "").title())
    out, vistos = [], set()
    for r in sorted(linhas, key=lambda r: (r["NR_CANDIDATO"], r["DS_CARGO"] != "PRESIDENTE", r["DS_URL"])):
        p = perfil_de(r.get("PLATAFORMA", ""), r.get("DS_URL", ""))
        if not p or (p[0], p[1].lower()) in vistos:
            continue
        vistos.add((p[0], p[1].lower()))
        if r["NR_CANDIDATO"] not in urna:  # chapa que não foi às urnas no 1º turno (28: troca de titular)
            continue
        cid, nome = titular[r["NR_CANDIDATO"]]
        out.append({"rede": p[0], "perfil": p[1], "handle": p[1], "url": p[1] if p[0] == "facebook" else "", "url_tse": r["DS_URL"].strip(),
                    "numero": r["NR_CANDIDATO"], "candidate_id": cid, "candidato": nome, "declarado_por": r.get("NM_URNA_CANDIDATO", ""),
                    "cargo": r["DS_CARGO"].title(), "na_urna": r["NR_CANDIDATO"] in urna})
    return out


def por_perfil(teto: float, n_perfis: int, item: float, inicio: float, leituras: int, maximo: int) -> int:
    """Posts por perfil que cabem no teto (mesmo número para todos os perfis da rede)."""
    if n_perfis == 0 or item <= 0:
        return 0
    n = int((teto * 0.95 - inicio * n_perfis * leituras) / (item * n_perfis * leituras))
    return max(0, min(n, maximo))


def linha_kwai(x: dict, pf: dict, agora: str, old: dict) -> dict:
    vid = str(g(x, "videoId", "video_id", "photoId", "id"))
    h = pf["perfil"]
    return {"candidate_id": pf["candidate_id"], "candidate_name": pf["candidato"], "perfil": h, "declarado_por": pf["declarado_por"],
            "video_id": vid, "url": g(x, "url", "videoUrl", "shareUrl") or f"https://www.kwai.com/@{h}/video/{vid}",
            "publicado_em": quando(g(x, "uploadTime", "createTime", "timestamp", "publishedAt", "postedAt", "created_at")),
            "legenda": " ".join(html.unescape(str(g(x, "caption", "description", "title") or "")).split()),
            "duracao_s": inteiro(g(x, "duration", "durationSeconds", "videoDuration")),
            "visualizacoes": inteiro(g(x, "viewCount", "views", "playCount", "stats.views")),
            "curtidas": inteiro(g(x, "likeCount", "likes", "stats.likes")), "comentarios": inteiro(g(x, "commentCount", "comments", "stats.comments")),
            "compartilhamentos": inteiro(g(x, "shareCount", "shares", "stats.shares")), "primeira_coleta": old.get("primeira_coleta") or agora,
            "ultima_coleta": agora, "capa_url": g(x, "coverUrl", "firstFrameUrl", "thumbnail", "cover") or old.get("capa_url", ""), "tipo": "vídeo"}


def entrada(rede: str, ator: str, pf: dict, n: int, desde: str) -> list[dict]:
    """Uma ou duas leituras (Instagram: posts + reels para visualizações)."""
    if rede == "instagram":
        return [x for x in (cig.entrada(ator, pf["perfil"], n, desde), cig.reels(ator, pf["perfil"], n, desde)) if x]
    if rede == "facebook":
        return [{"startUrls": [{"url": pf["perfil"]}], "resultsLimit": n, "onlyPostsNewerThan": desde}]
    if rede == "x":
        return [{"searchTerms": [f"from:{pf['perfil']} since:{desde} -filter:retweets"], "maxItems": n, "queryType": "Latest"}]
    if rede == "kwai":
        return [{"profileHandles": [pf["perfil"]], "includeProfileVideos": True, "postedAfter": desde, "maxItems": n, "onlyNewVideos": False}]
    raise ValueError(rede)


def converter(rede: str, itens: list[dict], extra: list[dict], pf: dict, agora: str, acervo: dict) -> list[dict]:
    out = []
    if rede == "instagram":
        plays = {str(v.get("shortCode")): v for v in extra if v.get("shortCode")}
        for x in itens:
            if not g(x, "shortCode", "shortcode", "code", "id") or x.get("error") or x.get("demo"):
                continue
            v = plays.get(str(x.get("shortCode")))
            if v:
                x = {**x, "videoPlayCount": v.get("videoPlayCount"), "videoDuration": x.get("videoDuration") or v.get("videoDuration"), "_reel": True}
            sc = str(g(x, "shortCode", "shortcode", "code") or "")
            out.append(cig.linha(x, pf, agora, acervo.get(sc) or {}))
    elif rede == "facebook":
        for x in itens:
            if g(x, "postId", "id") and not x.get("error"):
                out.append(cfb.linha(x, pf, agora, acervo.get(str(g(x, "postId", "id"))) or {}))
    elif rede == "x":
        for x in itens:
            if not g(x, "id", "id_str", "tweetId") or x.get("noResults") or str(g(x, "type") or "tweet").lower() not in ("tweet", "post", "reply", "quote"):
                continue
            if cx.autor(x).lower() != pf["perfil"].lower() or g(x, "isRetweet", "retweeted_status"):
                continue
            r = cx.linha(x, pf, agora, acervo.get(str(g(x, "id", "tweetId"))) or {})
            out.append({**r, "tipo": "post"})
    elif rede == "kwai":
        for x in itens:
            if str(g(x, "type", "recordType", "kind") or "video").lower() in ("profile", "user", "creator"):
                continue
            vid = g(x, "videoId", "video_id", "photoId", "id")
            if vid:
                out.append(linha_kwai(x, pf, agora, acervo.get(str(vid)) or {}))
    return out


def ler(p: Path) -> dict:
    return {r["video_id"]: r for r in csv.DictReader(gzip.open(p, "rt", encoding="utf-8"), delimiter=";")} if p.exists() else {}


def gravar(p: Path, acervo: dict):
    p.parent.mkdir(parents=True, exist_ok=True)
    with gzip.open(p, "wt", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, COLS_OUT, delimiter=";", lineterminator="\n", extrasaction="ignore")
        w.writeheader()
        w.writerows(sorted(acervo.values(), key=lambda r: (r["candidate_id"], r["publicado_em"]), reverse=True))


def tiktok(root: Path, perfis: list[dict], desde: str, teste: bool, agora: str) -> dict:
    import collect_tiktok as ct
    pasta = root / "data/primeiro_turno/tiktok"
    acervo = ler(pasta / "videos.csv.gz")
    man = {"rede": "tiktok", "ferramenta": "yt-dlp (grátis)", "perfis": []}
    for pf in perfis[:1] if teste else perfis:
        a = {"candidate_id": pf["candidate_id"], "candidate_name": pf["candidato"], "perfil": pf["perfil"], "declarado_por": pf["declarado_por"]}
        reg = {"perfil": pf["perfil"], "candidato": pf["candidato"], "declarado_por": pf["declarado_por"], "status": None, "lidos": 0}
        for t in range(1, ct.TENTATIVAS + 1):
            try:
                ents, parcial = ct.listar(pf["perfil"], 10 if teste else ct.LIMITE_POR_PERFIL, desde)
                rows = [r for r in (ct.linha(a, e, agora) for e in ents) if r and r["publicado_em"] >= desde]
                for r in rows:
                    r["primeira_coleta"] = (acervo.get(r["video_id"]) or {}).get("primeira_coleta") or agora
                    r["tipo"] = "vídeo"
                    acervo[r["video_id"]] = r
                reg.update(status="ok", lidos=len(rows), aviso=f"lista interrompida ({parcial})" if parcial else None)
                break
            except Exception as e:  # noqa: BLE001
                reg["status"] = "sem vídeos públicos" if "does not have any videos" in str(e) else f"⛔ {type(e).__name__}: {str(e)[:160]}"
                if reg["status"] == "sem vídeos públicos":
                    break
                time.sleep(ct.ESPERA_S * t)
        man["perfis"].append(reg)
        print(f"tiktok @{pf['perfil']}: {reg['status']} · {reg['lidos']} vídeos desde {desde}")
        time.sleep(3)
    gravar(pasta / "videos.csv.gz", acervo)
    man.update(custo_usd=0.0, posts_no_acervo=len(acervo), status="ok" if any(p["status"] == "ok" for p in man["perfis"]) else "⛔ nenhum perfil lido")
    return man


def paga(root: Path, rede: str, cfg: dict, perfis: list[dict], teste: bool, agora: str, usadas: set, executar=None) -> dict:
    rc = cfg["redes"][rede]
    pasta = root / "data/primeiro_turno" / rede
    pasta.mkdir(parents=True, exist_ok=True)
    ja = round(sum(float(json.loads(f.read_text(encoding="utf-8")).get("custo_usd") or 0) for f in pasta.glob("manifesto-*.json")), 4)
    teto = round(min(rc["teto_usd"] - ja, cfg["teto_teste_usd"]) if teste else rc["teto_usd"] - ja, 4)
    man = {"rede": rede, "ferramenta": f"Apify · {rc['ator'].replace('~', '/')}", "teto_usd": rc["teto_usd"], "gasto_antes_usd": ja,
           "teto_execucao_usd": teto, "perfis": []}
    if teto < 0.02:
        return {**man, "custo_usd": 0.0, "status": f"⛔ teto da rede esgotado (US$ {rc['teto_usd']})"}
    if executar is None:
        segredos = [s for s in (rc.get("segredos") or cfg["segredos"]) if s not in usadas]
        nome, token, saldo = escolher_conta(segredos, min(teto, 1.0))
        if not token:
            return {**man, "custo_usd": 0.0, "status": "⛔ nenhuma conta dos outros pesquisadores com saldo"}
        usadas.add(nome)
        if saldo is not None:
            teto = min(teto, round(saldo - 0.02, 4))
        man.update(conta=nome)
        executar = lambda pl, cap: run_actor(token, rc["ator"], pl, cap)  # noqa: E731
    alvo = perfis[:1] if teste else perfis
    leituras = 2 if rede == "instagram" else 1
    n = 10 if teste else por_perfil(teto, len(alvo), rc["item"], rc.get("inicio", 0.0), leituras, rc["maximo_por_perfil"])
    man["posts_pedidos_por_perfil"] = n
    if n < 5:
        return {**man, "custo_usd": 0.0, "status": "⛔ teto não cabe nem 5 posts por perfil"}

    def um(pf):
        pls, res, custo = entrada(rede, rc["ator"], pf, n, cfg["desde"]), [], 0.0
        cap = max(0.1, round(rc.get("inicio", 0.0) + rc["item"] * n * 1.3 + 0.005, 4))
        try:
            for pl in pls:
                run, itens = executar(pl, cap)
                res.append(itens or [])
                custo += max(custo_run(run or {}) or 0, round(rc.get("inicio", 0.0) + rc["item"] * len(itens or []), 5))
                if not itens:
                    break
            return pf, res, custo, (run or {}).get("id"), None
        except Exception as e:  # noqa: BLE001 — o token vai no cabeçalho
            return pf, res, custo, None, f"{type(e).__name__} {getattr(e, 'code', '')}".strip()
    with ThreadPoolExecutor(max_workers=3) as ex:
        resultados = list(ex.map(um, alvo))
    acervo = ler(pasta / "videos.csv.gz")
    gasto, brutos = 0.0, []
    for pf, res, custo, run_id, erro in resultados:
        itens, extra = (res[0] if res else []), (res[1] if len(res) > 1 else [])
        brutos += itens + extra
        gasto += custo
        rows = [r for r in converter(rede, itens, extra, pf, agora, acervo) if r["video_id"] and (r["publicado_em"] or "9") >= cfg["desde"]]
        for r in rows:
            acervo[r["video_id"]] = r
        man["perfis"].append({"perfil": pf["perfil"], "candidato": pf["candidato"], "declarado_por": pf["declarado_por"], "itens": len(itens),
                              "lidos_no_periodo": len(rows), "no_limite": len(itens) >= n, "run": run_id, "custo_usd": round(custo, 5),
                              "erro": erro or next((str(g(x, "error", "errorDescription", "noResults"))[:160] for x in itens if g(x, "error", "errorDescription", "noResults")), None),
                              "mais_antigo": min((r["publicado_em"] for r in rows if r["publicado_em"]), default=None)})
        print(f"{rede} {pf['perfil']}: {len(rows)} posts desde {cfg['desde']} ({len(itens)} itens, pedido {n}){' · ' + erro if erro else ''}")
    interno = os.environ.get("ODI_INTERNO_DIR")
    if interno and brutos:
        d = Path(interno) / "primeiro_turno" / rede
        d.mkdir(parents=True, exist_ok=True)
        with gzip.open(d / f"apify_{agora.replace(':', '').replace('-', '')}.jsonl.gz", "wt", encoding="utf-8") as f:
            for x in brutos:
                f.write(json.dumps(x, ensure_ascii=False) + "\n")
    gravar(pasta / "videos.csv.gz", acervo)
    man.update(custo_usd=round(gasto, 4), posts_no_acervo=len(acervo), status="ok" if acervo else "⛔ nenhum post lido")
    return man


def main(argv=None, executar=None) -> int:
    argv = list(argv or [])
    root = Path(".")
    cfg = json.loads((root / "data/config/primeiro_turno.json").read_text(encoding="utf-8"))
    teste = "--teste" in argv
    redes = [argv[i + 1] for i, a in enumerate(argv) if a == "--rede"] or list(REDES)
    agora = now_utc()
    todos = alvos(root)
    usadas: set[str] = set()
    resumo = {}
    for rede in redes:
        perfis = [p for p in todos if p["rede"] == rede]
        try:
            man = tiktok(root, perfis, cfg["desde"], teste, agora) if rede == "tiktok" else paga(root, rede, cfg, perfis, teste, agora, usadas, executar)
        except Exception as e:  # noqa: BLE001 — uma rede com problema não derruba as outras
            man = {"rede": rede, "custo_usd": 0.0, "status": f"⛔ {type(e).__name__}: {str(e)[:200]}"}
        man.update(run_started_utc=agora, modo="teste" if teste else "carga", perfis_declarados=len(perfis))
        pasta = root / "data/primeiro_turno" / rede
        pasta.mkdir(parents=True, exist_ok=True)
        stamp = agora.replace(":", "").replace("-", "")
        for nome in (f"manifesto-{stamp}.json", "manifesto_latest.json"):
            (pasta / nome).write_text(json.dumps(man, ensure_ascii=False, indent=1), encoding="utf-8")
        resumo[rede] = man["status"]
        print(f"{rede}: {man['status']} · acervo {man.get('posts_no_acervo')}")
    (root / "data/primeiro_turno/perfis.json").write_text(json.dumps({"gerado_em_utc": agora, "perfis": todos}, ensure_ascii=False, indent=1), encoding="utf-8")
    return 0 if any(s == "ok" for s in resumo.values()) else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
