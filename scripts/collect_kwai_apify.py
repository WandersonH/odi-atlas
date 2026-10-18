#!/usr/bin/env python3
"""Kwai das chapas 13 e 22 via Apify (ator unfenced-group/kwai-scraper), com teto de gasto. Token SOMENTE por APIFY_TOKEN_2.

--historico: acervo completo (sem data inicial, reentrega vídeos já vistos para obter a capa), teto_historico_usd.
--teste: carga inicial (vídeos desde 16/08, até max_videos_por_perfil_teste por perfil, teto de teste).
sem opção: diário, só vídeos novos (onlyNewVideos), teto diário. Respeita o teto mensal somando data/kwai/manifesto-*.json.
Saídas: data/kwai/videos.csv.gz (mesmo formato do TikTok), data/kwai/perfis.csv (seguidores etc. por dia),
data/kwai/manifesto_latest.json e manifesto-AAAA-MM-*.json (custo). Bruto em ODI_INTERNO_DIR/kwai/ (privado), quando houver.
"""
from __future__ import annotations

import csv
import datetime as dt
import gzip
import html
import json
import os
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from collect_meta_anuncios_apify import custo_run  # noqa: E402
from collect_meta_apify import escolher_conta, run_actor, saldo_conta  # noqa: E402
from net import now_utc  # noqa: E402

COLS = ["candidate_id", "candidate_name", "perfil", "declarado_por", "video_id", "url", "publicado_em", "legenda", "duracao_s",
        "visualizacoes", "curtidas", "comentarios", "compartilhamentos", "primeira_coleta", "ultima_coleta", "capa_url"]
PCOLS = ["data", "perfil", "candidate_id", "seguidores", "curtidas_total", "videos_total", "nome"]


def g(x: dict, *ks):
    """Primeiro campo presente (aceita caminho com ponto)."""
    for k in ks:
        v = x
        for p in k.split("."):
            v = v.get(p) if isinstance(v, dict) else None
        if v not in (None, ""):
            return v
    return None


def quando(v) -> str:
    if v in (None, ""):
        return ""
    try:
        f = float(v)
        if f > 1e12:
            f /= 1000
        return dt.datetime.fromtimestamp(f, dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    except (TypeError, ValueError):
        s = str(v)
        return s[:19] + "Z" if len(s) >= 19 and s[10] == "T" else s


def inteiro(v):
    try:
        return int(float(str(v).replace(",", "")))
    except (TypeError, ValueError):
        return ""


def e_video(x: dict) -> bool:
    return bool(g(x, "videoId", "video_id", "photoId", "id")) and (g(x, "caption", "description", "viewCount", "views", "playCount") is not None) \
        and str(g(x, "type", "recordType", "kind") or "video").lower() not in ("profile", "user", "creator")


def handle_de(x: dict) -> str:
    m = re.search(r"/@([^/?#]+)/video/", str(x.get("url") or ""))
    if m:  # o nome de usuário do Kwai diferencia maiúsculas: comparar como veio
        return m.group(1)
    h = g(x, "sourceProfile", "authorHandle", "author.handle", "author.username", "creator.handle", "handle", "username", "userName", "author.kwaiId", "kwaiId") or ""
    return str(h).lstrip("@")


def main(argv=None, executar=None) -> int:
    argv = list(argv or [])
    root = Path(".")
    cfg = json.loads((root / "data/config/kwai.json").read_text(encoding="utf-8"))
    historico = "--historico" in argv
    teste = "--teste" in argv or historico
    pasta = root / "data/kwai"
    pasta.mkdir(parents=True, exist_ok=True)
    agora = now_utc()
    teto = cfg["teto_historico_usd"] if historico else cfg["teto_teste_usd"] if teste else cfg["teto_diario_usd"]
    mes = agora[:7]
    ja = round(sum(float(json.loads(f.read_text(encoding="utf-8")).get("custo_usd") or 0) for f in pasta.glob(f"manifesto-{mes}-*.json")), 4)
    man = {"run_started_utc": agora, "ferramenta": f"Apify · {cfg['ator'].replace('~', '/')}", "modo": "histórico" if historico else "teste" if teste else "diário",
           "teto_usd": teto, "gasto_mes_antes_usd": ja, "perfis": [], "fora": cfg.get("fora")}
    segredos = cfg.get("segredos") or [cfg.get("segredo", "APIFY_TOKEN_2")]
    nome_conta, token, saldo = escolher_conta(segredos, teto) if executar is None else ("teste", "x", None)
    man["conta"] = nome_conta
    if not token and executar is None:
        man["status"] = f"⛔ nenhuma conta Apify com saldo para o teto (US$ {teto}) entre {', '.join(segredos)}"
    elif ja + teto > cfg["teto_mensal_usd"] + 1e-9:
        man["status"] = f"⛔ teto mensal de US$ {cfg['teto_mensal_usd']} atingido (já gasto US$ {ja})"
    if "status" not in man and executar is None:
        man["saldo_conta_antes_usd"] = saldo
        if saldo is not None and saldo < teto:
            man["status"] = f"⛔ saldo da conta Apify (US$ {saldo}) menor que o teto desta execução (US$ {teto})"
    if "status" in man:
        (pasta / "manifesto_latest.json").write_text(json.dumps(man, ensure_ascii=False, indent=1), encoding="utf-8")
        print(man["status"])
        return 1
    executar = executar or (lambda payload, cap: run_actor(token, cfg["ator"], payload, cap))
    por_handle = {p["handle"]: p for p in cfg["perfis"]}
    desde = cfg.get("desde_carga_historica", cfg["desde"]) if teste else cfg["desde"]
    maximo = cfg["max_videos_por_perfil_historico" if historico else "max_videos_por_perfil_teste" if teste else "max_videos_por_perfil_diario"]
    payload = {"profileHandles": list(por_handle), "includeProfileVideos": True, **({"postedAfter": desde} if desde else {}),
               "maxItems": maximo, "onlyNewVideos": not historico}
    try:
        run, itens = executar(payload, teto)
    except Exception as e:  # noqa: BLE001 — o token vai no cabeçalho
        man["status"] = f"⛔ Apify: {type(e).__name__} {getattr(e, 'code', '')}".strip()
        (pasta / "manifesto_latest.json").write_text(json.dumps(man, ensure_ascii=False, indent=1), encoding="utf-8")
        print(man["status"])
        return 1
    itens = itens or []
    custo = custo_run(run)
    man.update(run_apify={"id": run.get("id"), "status": run.get("status"), "eventos_cobrados": run.get("chargedEventCounts"),
                          "uso_plataforma_usd": run.get("usageTotalUsd"), "teto_usd": (run.get("options") or {}).get("maxTotalChargeUsd")},
               custo_usd=custo, itens=len(itens))
    interno = os.environ.get("ODI_INTERNO_DIR")
    if interno and itens:
        d = Path(interno) / "kwai"
        d.mkdir(parents=True, exist_ok=True)
        with gzip.open(d / f"apify_{agora[:10]}_{agora[11:13]}{agora[14:16]}{agora[17:19]}.jsonl.gz", "wt", encoding="utf-8") as f:
            for x in itens:
                f.write(json.dumps(x, ensure_ascii=False) + "\n")
    # reprocessa também os brutos anteriores (o ator não reentrega vídeos já entregues: onlyNewVideos)
    if interno:
        anteriores = []
        for f in sorted((Path(interno) / "kwai").glob("apify_*.jsonl.gz")):
            anteriores += [json.loads(l) for l in gzip.open(f, "rt", encoding="utf-8")]
        ids = {str(g(x, "videoId", "video_id", "photoId", "id")) for x in itens}
        itens = [x for x in anteriores if str(g(x, "videoId", "video_id", "photoId", "id")) not in ids or not e_video(x)] + itens
    # vídeos
    src = pasta / "videos.csv.gz"
    acervo = {}
    if src.exists():
        acervo = {r["video_id"]: r for r in csv.DictReader(gzip.open(src, "rt", encoding="utf-8"), delimiter=";")}
    novos, perfis_vistos = 0, {}
    for x in itens:
        h = handle_de(x)
        if not e_video(x):
            pedido = str(x.get("url") or "").rstrip("/").split("/@")[-1]
            if pedido in por_handle:
                perfis_vistos[pedido] = {**x, "_handle_resolvido": str(x.get("handle") or "")}
            continue
        p = por_handle.get(h)
        if not p:
            continue
        vid = str(g(x, "videoId", "video_id", "photoId", "id"))
        old = acervo.get(vid, {})
        acervo[vid] = {"candidate_id": p["candidate_id"], "candidate_name": p["candidato"], "perfil": h, "declarado_por": p["declarado_por"],
                       "video_id": vid, "url": g(x, "url", "videoUrl", "shareUrl") or f"https://www.kwai.com/@{h}/video/{vid}",
                       "publicado_em": quando(g(x, "uploadTime", "createTime", "timestamp", "publishedAt", "postedAt", "created_at")),
                       "legenda": " ".join(html.unescape(str(g(x, "caption", "description", "title") or "")).split()),
                       "duracao_s": inteiro(g(x, "duration", "durationSeconds", "videoDuration")),
                       "visualizacoes": inteiro(g(x, "viewCount", "views", "playCount", "stats.views")),
                       "curtidas": inteiro(g(x, "likeCount", "likes", "stats.likes")),
                       "comentarios": inteiro(g(x, "commentCount", "comments", "stats.comments")),
                       "compartilhamentos": inteiro(g(x, "shareCount", "shares", "stats.shares")),
                       "primeira_coleta": old.get("primeira_coleta") or agora, "ultima_coleta": agora,
                       "capa_url": g(x, "coverUrl", "firstFrameUrl", "thumbnail", "cover") or old.get("capa_url", "")}
        novos += 0 if old else 1
    with gzip.open(src, "wt", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, COLS, delimiter=";", lineterminator="\n")
        w.writeheader()
        w.writerows(sorted(acervo.values(), key=lambda r: (r["candidate_id"], r["publicado_em"]), reverse=True))
    # perfis (seguidores por dia)
    pp = pasta / "perfis.csv"
    linhas = list(csv.DictReader(open(pp, encoding="utf-8"), delimiter=";")) if pp.exists() else []
    linhas = [r for r in linhas if not (r["data"] == agora[:10] and r["perfil"] in perfis_vistos)]
    for h, x in perfis_vistos.items():
        linhas.append({"data": agora[:10], "perfil": h, "candidate_id": por_handle[h]["candidate_id"],
                       "seguidores": inteiro(g(x, "followers", "followerCount", "fans", "stats.followers")),
                       "curtidas_total": inteiro(g(x, "totalLikes", "likes", "likeCount", "stats.likes")),
                       "videos_total": inteiro(g(x, "videoCount", "videos", "photoCount", "stats.videos")),
                       "nome": g(x, "displayName", "name", "nickname") or ""})
    with open(pp, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, PCOLS, delimiter=";", lineterminator="\n")
        w.writeheader()
        w.writerows(sorted(linhas, key=lambda r: (r["data"], r["perfil"])))
    # seguidores para a página "Quem acompanha" (mesmo formato de latest.csv; URL declarada ao TSE para casar com o card)
    seg = root / "data/seguidores"
    seg.mkdir(parents=True, exist_ok=True)
    hoje_linhas = [r for r in linhas if r["data"] == agora[:10] and r["seguidores"] != ""]
    if hoje_linhas:
        cols = ["candidate_id", "candidate_name", "platform", "url", "followers", "captured_at", "source_url"]
        for nome in (f"kwai_{agora[:10]}.csv", "kwai_latest.csv"):
            with open(seg / nome, "w", encoding="utf-8", newline="") as f:
                w = csv.DictWriter(f, cols, delimiter=";", lineterminator="\n")
                w.writeheader()
                for r in hoje_linhas:
                    p = por_handle[r["perfil"]]
                    w.writerow({"candidate_id": p["candidate_id"], "candidate_name": p["declarado_por"], "platform": "Kwai", "url": p["url_tse"],
                                "followers": r["seguidores"], "captured_at": agora[:10], "source_url": f"https://www.kwai.com/@{r['perfil']}"})
    for h, p in por_handle.items():
        n = sum(1 for r in acervo.values() if r["perfil"] == h)
        pv = perfis_vistos.get(h)
        man["perfis"].append({"perfil": h, "candidato": p["candidato"], "url": f"https://www.kwai.com/@{h}", "url_tse": p["url_tse"],
                              "lido_nesta_execucao": bool(pv) or any(handle_de(x) == h for x in itens), "videos_no_acervo": n,
                              "seguidores": inteiro(g(pv, "followers", "followerCount", "fans", "stats.followers")) if pv else None,
                              "nome_exibido": (pv or {}).get("displayName"), "videos_no_perfil": inteiro((pv or {}).get("videoCount")) if pv else None,
                              "handle_resolvido": (pv or {}).get("_handle_resolvido")})
    man["videos_novos"] = novos
    man["status"] = "ok" if acervo else "⛔ nenhum vídeo lido"
    for nome in (f"manifesto-{mes}-{agora.replace(':', '').replace('-', '')}.json", "manifesto_latest.json"):
        (pasta / nome).write_text(json.dumps(man, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"kwai: {man['status']} · {len(itens)} itens · {novos} vídeos novos · acervo {len(acervo)} · custo US$ {custo} (teto {teto})")
    if itens:
        print("chaves do 1º item: " + ", ".join(sorted(itens[0].keys()))[:900])
        v = next((x for x in itens if e_video(x)), None)
        if v:
            print("chaves de um vídeo: " + ", ".join(sorted(v.keys()))[:900])
    return 0 if acervo else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
