#!/usr/bin/env python3
"""Comentários públicos dos vídeos do Kwai (perfis declarados ao TSE) via Apify, ator natanielsantos/kwai-scraper.

Token SOMENTE por APIFY_TOKEN_3. Teto total autorizado em data/config/kwai_comentarios.json (soma dos manifestos);
o custo de cada execução é o maior entre o informado pela Apify e a estimativa pela tabela de preços do ator.

--teste: 3 vídeos de maior número de comentários × 10 comentários + os 5 vídeos mais recentes de @Lulaoficial
         (para ver se este ator lista a conta oficial), teto de teste.
sem opção: todos os vídeos desde `desde` que ainda não têm comentários coletados, até N comentários por vídeo.

Saída privada (ODI_INTERNO_DIR/kwai/comentarios/): bruto apify_*.jsonl.gz e comentarios.csv.gz (mesmas colunas do YouTube).
Saída pública: data/kwai/comentarios/manifesto-*.json e manifesto_latest.json (contagens e custo; nenhum texto ou autor).
"""
from __future__ import annotations

import csv
import datetime as dt
import gzip
import json
import os
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from collect_comentarios_youtube import CAMPOS  # noqa: E402
from collect_meta_anuncios_apify import custo_run  # noqa: E402
from collect_meta_apify import run_actor  # noqa: E402
from net import now_utc  # noqa: E402

TEXTO = ("text", "content", "comment", "commentText", "body")


def g(x: dict, *ks):
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


def id_video(x: dict) -> str:
    v = g(x, "id", "videoId", "photoId", "video_id")
    if v:
        return str(v)
    m = re.search(r"/video/(\d+)", str(g(x, "url", "videoUrl", "shareUrl") or ""))
    return m.group(1) if m else ""


def lista_comentarios(x: dict) -> list[dict]:
    """O ator devolve os comentários dentro do item do vídeo; o nome do campo não é documentado: procura a lista."""
    for k in ("comments", "commentList", "comment_list", "topComments"):
        if isinstance(x.get(k), list):
            return [c for c in x[k] if isinstance(c, dict)]
    for v in x.values():
        if isinstance(v, list) and v and isinstance(v[0], dict) and any(t in v[0] for t in TEXTO):
            return v
    return []


def e_comentario(x: dict) -> bool:
    """Formato do ator (README, 'Comment Output Example'): um item por comentário, com content e videoId."""
    return "content" in x and "videoId" in x and "caption" not in x


def linhas(x: dict, video: dict, agora: str) -> list[dict]:
    out = []
    if e_comentario(x):
        pai = str(x.get("replyToCommentId") or "")
        return [{"video_id": video["video_id"], "candidate_id": video["candidate_id"], "channel_id": video["perfil"], "ordem": "kwai",
                 "coletado_em": agora, "atualizado_em": "", "comment_id": str(x.get("id") or ""), "parent_id": pai,
                 "tipo": "resposta" if pai else "comentario", "autor_canal": str(x.get("authorId") or x.get("authorUsername") or ""),
                 "autor_nome": str(x.get("authorName") or ""), "texto": " ".join(str(x.get("content") or "").split()),
                 "curtidas": x.get("likedCount") or 0, "respostas": x.get("replyCount") if not pai else "",
                 "publicado_em": quando(x.get("timestamp"))}]
    for c in lista_comentarios(x):
        cid = str(g(c, "id", "commentId", "comment_id") or "")
        base = {"video_id": video["video_id"], "candidate_id": video["candidate_id"], "channel_id": video["perfil"], "ordem": "kwai",
                "coletado_em": agora, "atualizado_em": ""}
        out.append({**base, "comment_id": cid, "parent_id": "", "tipo": "comentario",
                    "autor_canal": str(g(c, "author.id", "authorId", "userId", "user.id", "author.username", "authorUsername") or ""),
                    "autor_nome": str(g(c, "author.name", "authorName", "userName", "user.name", "author.nickname", "nickname") or ""),
                    "texto": " ".join(str(g(c, *TEXTO) or "").split()), "curtidas": g(c, "likeCount", "likes", "diggCount") or 0,
                    "respostas": g(c, "replyCount", "subCommentCount", "replies_count") or "",
                    "publicado_em": quando(g(c, "createTime", "timestamp", "time", "createdAt", "publishedAt"))})
        for r in (c.get("replies") or c.get("subComments") or []):
            if isinstance(r, dict):
                out.append({**base, "comment_id": str(g(r, "id", "commentId") or ""), "parent_id": cid, "tipo": "resposta",
                            "autor_canal": str(g(r, "author.id", "authorId", "userId") or ""),
                            "autor_nome": str(g(r, "author.name", "authorName", "userName", "nickname") or ""),
                            "texto": " ".join(str(g(r, *TEXTO) or "").split()), "curtidas": g(r, "likeCount", "likes") or 0,
                            "respostas": "", "publicado_em": quando(g(r, "createTime", "timestamp", "time", "createdAt"))})
    return out


def gasto_total(pasta: Path) -> float:
    return round(sum(float(json.loads(f.read_text(encoding="utf-8")).get("custo_usd") or 0)
                     for f in pasta.glob("manifesto-*.json")), 4)


def main(argv=None, executar=None) -> int:
    argv = list(argv or [])
    root = Path(".")
    cfg = json.loads((root / "data/config/kwai_comentarios.json").read_text(encoding="utf-8"))
    teste = "--teste" in argv
    pub = root / "data/kwai/comentarios"
    pub.mkdir(parents=True, exist_ok=True)
    agora = now_utc()
    ja = gasto_total(pub)
    resta = round(cfg["teto_total_usd"] - ja, 4)
    teto = min(cfg["teto_teste_usd"], resta) if teste else resta
    man = {"run_started_utc": agora, "ferramenta": f"Apify · {cfg['ator'].replace('~', '/')}", "modo": "teste" if teste else "carga",
           "teto_total_usd": cfg["teto_total_usd"], "gasto_antes_usd": ja, "teto_execucao_usd": teto}

    def fim(status: str, code: int) -> int:
        man["status"] = status
        stamp = agora.replace(":", "").replace("-", "")
        for nome in (f"manifesto-{stamp}.json", "manifesto_latest.json"):
            (pub / nome).write_text(json.dumps(man, ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"comentários Kwai: {status}")
        return code

    token = os.environ.get(cfg["segredo"], "").strip()
    interno = os.environ.get("ODI_INTERNO_DIR")
    if not token and executar is None:
        return fim(f"⛔ {cfg['segredo']} ausente", 1)
    if not interno:
        return fim("⛔ sem repositório privado: texto de comentário não pode ir para o público", 1)
    if teto < 0.01:
        return fim(f"⛔ teto autorizado de US$ {cfg['teto_total_usd']} esgotado (gasto US$ {ja})", 1)
    priv = Path(interno) / "kwai/comentarios"
    priv.mkdir(parents=True, exist_ok=True)
    acervo = priv / "comentarios.csv.gz"
    antigos = list(csv.DictReader(gzip.open(acervo, "rt", encoding="utf-8"), delimiter=";")) if acervo.exists() else []
    feitos = {r["video_id"] for r in antigos}
    feitos |= set(json.loads((priv / "videos_lidos.json").read_text(encoding="utf-8"))) if (priv / "videos_lidos.json").exists() else set()
    videos = [r for r in csv.DictReader(gzip.open(root / "data/kwai/videos.csv.gz", "rt", encoding="utf-8"), delimiter=";")
              if r["publicado_em"] >= cfg["desde"] and int(r["comentarios"] or 0) > 0]
    pendentes = [v for v in videos if v["video_id"] not in feitos]
    pendentes.sort(key=lambda v: -int(v["comentarios"] or 0))
    p = cfg["preco_usd"]
    if teste:
        t = cfg["teste"]
        alvo, por_video, perfis = pendentes[:t["videos"]], t["comentarios_por_video"], t["perfis"]
        max_itens = max(len(alvo), t["videos_por_perfil"])
    else:
        por_video, perfis = cfg["max_comentarios_por_video"], []
        alvo, est = [], p["inicio"]
        for v in pendentes:  # cabe no teto pela tabela de preços (estimativa conservadora)
            c = p["video"] + p["comentario"] * min(por_video, int(v["comentarios"] or 0))
            if est + c > teto * 0.97:
                break
            alvo.append(v)
            est += c
        max_itens = max(1, len(alvo))
    man["videos_alvo"] = len(alvo)
    man["videos_pendentes"] = len(pendentes)
    if not alvo and not perfis:
        return fim("ok · nada pendente", 0)
    por_id = {v["video_id"]: v for v in alvo}
    fmt = cfg.get("url_video") or "{url}"
    payload = {"urls": [fmt.format(video_id=v["video_id"], url=v["url"]) for v in alvo] + perfis, "maxItems": max_itens, "maxCommentsPerVideo": por_video,
               "maxRepliesPerComment": cfg["max_respostas_por_comentario"]}
    executar = executar or (lambda pl, cap: run_actor(token, cfg["ator"], pl, cap))
    try:
        run, itens = executar(payload, teto)
    except Exception as e:  # noqa: BLE001 — o token vai no cabeçalho
        return fim(f"⛔ Apify: {type(e).__name__} {getattr(e, 'code', '')}".strip(), 1)
    itens = itens or []
    with gzip.open(priv / f"apify_{agora[:10]}_{agora[11:13]}{agora[14:16]}{agora[17:19]}.jsonl.gz", "wt", encoding="utf-8") as f:
        for x in itens:
            f.write(json.dumps(x, ensure_ascii=False) + "\n")
    novas, perfil_teste = [], []
    for x in itens:
        vid = str(x.get("videoId")) if e_comentario(x) else id_video(x)
        if vid in por_id:
            novas += linhas(x, por_id[vid], agora)
        elif not e_comentario(x):
            perfil_teste.append({"video_id": vid, "autor": g(x, "author.username", "author.name", "authorName", "username"),
                                 "publicado_em": quando(g(x, "createTime", "timestamp")), "comentarios_no_item": len(lista_comentarios(x))})
    n_coment = sum(1 for r in novas if r["tipo"] == "comentario")
    n_videos = sum(1 for x in itens if not e_comentario(x))
    estimado = round(p["inicio"] + p["video"] * n_videos + p["comentario"] * (len(itens) - n_videos), 4)
    custo = max(custo_run(run) or 0, estimado)
    ids_novos = {r["comment_id"] for r in novas}
    todos = [r for r in antigos if r["comment_id"] not in ids_novos] + novas
    with gzip.open(acervo, "wt", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, CAMPOS, delimiter=";", lineterminator="\n", extrasaction="ignore")
        w.writeheader()
        w.writerows(todos)
    lidos = sorted(feitos | {r["video_id"] for r in novas})  # só conta como lido o vídeo que trouxe comentário
    (priv / "videos_lidos.json").write_text(json.dumps(lidos), encoding="utf-8")
    man.update(run_apify={"id": run.get("id"), "status": run.get("status"), "eventos_cobrados": run.get("chargedEventCounts"),
                          "uso_plataforma_usd": run.get("usageTotalUsd")},
               custo_usd=custo, custo_estimado_tabela_usd=estimado, itens=len(itens), comentarios_novos=n_coment,
               respostas_novas=len(novas) - n_coment, comentarios_no_acervo=len(todos),
               videos_com_comentarios=len({r["video_id"] for r in todos}), itens_fora_da_lista=perfil_teste[:20])
    print("chaves do 1º item: " + ", ".join(sorted(itens[0].keys()))[:900] if itens else "nenhum item")
    lc = next((lista_comentarios(x) for x in itens if lista_comentarios(x)), [])
    if lc:
        print("chaves de um comentário: " + ", ".join(sorted(lc[0].keys()))[:600])
    print(f"{len(itens)} itens · {n_coment} comentários e {len(novas) - n_coment} respostas novos · acervo {len(todos)} · "
          f"custo US$ {custo} (tabela {estimado}; Apify {custo_run(run)}) · teto {teto} · fora da lista: {len(perfil_teste)}")
    return fim("ok" if novas or teste else "⛔ nenhum comentário lido", 0 if novas or teste else 1)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
