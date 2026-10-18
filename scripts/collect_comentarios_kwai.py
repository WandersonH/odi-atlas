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


def video_do_comentario(x: dict) -> str:
    v = g(x, "videoId", "video_id", "photoId", "video.id")
    if v:
        return str(v)
    m = re.search(r"/video/(\d+)", str(g(x, "videoUrl", "video_url", "inputUrl", "sourceUrl", "url") or ""))
    return m.group(1) if m else ""


def e_comentario(x: dict) -> bool:
    """Um item por comentário (formato dos atores de comentários): tem texto e aponta um vídeo; não é o próprio vídeo."""
    return any(k in x for k in TEXTO) and "caption" not in x and "viewCount" not in x and bool(video_do_comentario(x))


def linhas(x: dict, video: dict, agora: str) -> list[dict]:
    out = []
    if e_comentario(x):
        pai = str(g(x, "replyToCommentId", "parentId", "parentCommentId", "replyTo.id") or "")
        return [{"video_id": video["video_id"], "candidate_id": video["candidate_id"], "channel_id": video["perfil"], "ordem": "kwai",
                 "coletado_em": agora, "atualizado_em": "", "comment_id": str(g(x, "commentId", "comment_id", "id") or ""), "parent_id": pai,
                 "tipo": "resposta" if pai else "comentario",
                 "autor_canal": str(g(x, "authorId", "author.id", "userId", "user.id", "authorUsername", "author.username") or ""),
                 "autor_nome": str(g(x, "authorName", "author.name", "author.nickname", "userName", "user.name", "nickname") or ""),
                 "texto": " ".join(str(g(x, *TEXTO) or "").split()),
                 "curtidas": g(x, "likedCount", "likeCount", "likes", "diggCount") or 0,
                 "respostas": g(x, "replyCount", "subCommentCount") if not pai else "",
                 "publicado_em": quando(g(x, "timestamp", "createTime", "createdAt", "time", "publishedAt"))}]
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
    executar = executar or (lambda ator, pl, cap: run_actor(token, ator, pl, cap))
    man["runs"] = []
    gasto = 0.0

    def rodar(ator: str, payload: dict, cap: float):
        run, itens = executar(ator, payload, round(cap, 4))
        itens = itens or []
        with gzip.open(priv / f"apify_{now_utc().replace(':', '').replace('-', '')}_{len(man['runs'])}.jsonl.gz", "wt", encoding="utf-8") as f:
            for x in itens:
                f.write(json.dumps(x, ensure_ascii=False) + "\n")
        return run, itens

    if "--videos-lula" in argv:  # vídeos de @Lulaoficial pelo ator que os lista (o dos vídeos não lista)
        vl = cfg["videos_lula"]
        cap = min(vl["teto_usd"], teto)
        try:
            run, itens = rodar(vl["ator"], {"urls": [vl["perfil"]], "maxItems": vl["max_videos"], "maxCommentsPerVideo": 0}, cap)
        except Exception as e:  # noqa: BLE001
            return fim(f"⛔ Apify: {type(e).__name__} {getattr(e, 'code', '')}".strip(), 1)
        vs = [x for x in itens if not e_comentario(x) and str(g(x, "authorMeta.username") or "").lower() == vl["handle"].lower()]
        custo = max(custo_run(run) or 0, round(0.00005 + 0.002 * len(itens), 4))
        n = juntar_videos(root, vs, vl["handle"], agora)
        man.update(custo_usd=custo, runs=[{"id": run.get("id"), "itens": len(itens), "custo_usd": custo}], videos_lula_lidos=len(vs), videos_novos_no_acervo=n,
                   videos_lula_desde=min((quando(g(x, "createTime")) for x in vs), default=None))
        print(f"vídeos de @{vl['handle']}: {len(vs)} lidos ({n} novos no acervo) · mais antigo {man['videos_lula_desde']} · custo US$ {custo}")
        return fim("ok" if vs else "⛔ nenhum vídeo lido", 0 if vs else 1)

    if teste:
        t = cfg["teste"]
        lotes = [(pendentes[:t["videos"]], t["comentarios_por_video"])]
    else:  # cota igual por candidato, dividida entre os vídeos do período
        lotes = []
        for cid in sorted({v["candidate_id"] for v in videos}):
            todos_c = [v for v in videos if v["candidate_id"] == cid]
            pv = max(cfg["min_comentarios_por_video"], min(cfg["max_comentarios_por_video"], cfg["cota_comentarios_por_candidato"] // max(1, len(todos_c))))
            lotes.append(([v for v in pendentes if v["candidate_id"] == cid], pv))
    novas, alvo_total = [], 0
    fmt = cfg.get("url_video") or "{url}"
    for alvo_c, por_video in lotes:
        alvo, est = [], p["inicio"]
        for v in alvo_c:  # cabe no que resta do teto pela tabela de preços (estimativa conservadora)
            c = p["video"] + p["comentario"] * min(por_video, int(v["comentarios"] or 0))
            if gasto + est + c > teto * 0.97:
                break
            alvo.append(v)
            est += c
        if not alvo:
            continue
        alvo_total += len(alvo)
        # O ator só lê o 1º vídeo de cada execução nesta conta (carga de 17/10: 68 e 71 vídeos pedidos, 1 lido em cada):
        # uma execução por vídeo (início = US$ 0,00005), 4 em paralelo.
        from concurrent.futures import ThreadPoolExecutor

        def um(v):
            pl = {"videoUrls": [fmt.format(video_id=v["video_id"], url=v["url"])], "maxCommentsPerVideo": por_video,
                  "includeReplies": cfg["max_respostas_por_comentario"] > 0, "maxRepliesPerComment": cfg["max_respostas_por_comentario"]}
            cap = p["inicio"] + p["comentario"] * por_video * 1.2 + 0.001
            try:
                return v, *executar(cfg["ator"], pl, round(cap, 4)), None
            except Exception as e:  # noqa: BLE001 — o token vai no cabeçalho
                return v, {}, [], f"{type(e).__name__} {getattr(e, 'code', '')}".strip()
        with ThreadPoolExecutor(max_workers=cfg.get("execucoes_paralelas", 4)) as ex:
            resultados = list(ex.map(um, alvo))
        brutos, lote_c, lote_custo, erros = [], 0, 0.0, 0
        for v, run, itens, erro in resultados:
            if erro:
                erros += 1
                continue
            itens = itens or []
            brutos += itens
            lin = [l for x in itens if e_comentario(x) and video_do_comentario(x) == v["video_id"] for l in linhas(x, v, agora)]
            n_c = sum(1 for x in itens if e_comentario(x))
            custo = max(custo_run(run) or 0, round(p["inicio"] + p["comentario"] * n_c, 5))
            lote_custo += custo
            lote_c += len(lin)
            novas += lin
        gasto += lote_custo
        with gzip.open(priv / f"apify_{now_utc().replace(':', '').replace('-', '')}_{len(man['runs'])}.jsonl.gz", "wt", encoding="utf-8") as f:
            for x in brutos:
                f.write(json.dumps(x, ensure_ascii=False) + "\n")
        from collections import Counter
        st = Counter(str((run or {}).get("status")) + ("" if itens else " vazio") for _, run, itens, _ in resultados)
        man["runs"].append({"execucoes": len(alvo), "erros": erros, "por_video": por_video, "comentarios": lote_c, "custo_usd": round(lote_custo, 4),
                            "status_execucoes": dict(st), "exemplo_vazio": next((r.get("id") for _, r, i, _ in resultados if not i and r), None)})
        print(f"status das execuções: {dict(st)}")
        print(f"lote: {len(alvo)} vídeos × até {por_video} (uma execução por vídeo) · {lote_c} comentários · {erros} erros · US$ {round(lote_custo, 4)}")
    man["videos_alvo"] = alvo_total
    man["videos_pendentes"] = len(pendentes)
    if not alvo_total:
        return fim("ok · nada pendente", 0)
    ids_novos = {r["comment_id"] for r in novas}
    todos = [r for r in antigos if r["comment_id"] not in ids_novos] + novas
    with gzip.open(acervo, "wt", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, CAMPOS, delimiter=";", lineterminator="\n", extrasaction="ignore")
        w.writeheader()
        w.writerows(todos)
    lidos = sorted(feitos | {r["video_id"] for r in novas})  # só conta como lido o vídeo que trouxe comentário
    (priv / "videos_lidos.json").write_text(json.dumps(lidos), encoding="utf-8")
    n_coment = sum(1 for r in novas if r["tipo"] == "comentario")
    por_cand = {}
    for r in todos:
        por_cand[r["candidate_id"]] = por_cand.get(r["candidate_id"], 0) + 1
    man.update(custo_usd=round(gasto, 4), comentarios_novos=n_coment, respostas_novas=len(novas) - n_coment, comentarios_no_acervo=len(todos),
               comentarios_por_candidato=por_cand, videos_com_comentarios=len({r["video_id"] for r in todos}))
    print(f"{n_coment} comentários e {len(novas) - n_coment} respostas novos · acervo {len(todos)} {por_cand} · custo US$ {round(gasto, 4)} · teto {teto}")
    return fim("ok" if novas else "⛔ nenhum comentário lido", 0 if novas else 1)


def juntar_videos(root: Path, vs: list[dict], handle: str, agora: str) -> int:
    """Vídeos lidos pelo ator natanielsantos entram no acervo do Kwai (mesmas colunas do collect_kwai_apify)."""
    import collect_kwai_apify as ck
    cfgk = json.loads((root / "data/config/kwai.json").read_text(encoding="utf-8"))
    perfil = next(p for p in cfgk["perfis"] if p["handle"] == handle)
    src = root / "data/kwai/videos.csv.gz"
    acervo = {r["video_id"]: r for r in csv.DictReader(gzip.open(src, "rt", encoding="utf-8"), delimiter=";")} if src.exists() else {}
    novos = 0
    for x in vs:
        vid = str(x["id"])
        old = acervo.get(vid, {})
        novos += 0 if old else 1
        acervo[vid] = {"candidate_id": perfil["candidate_id"], "candidate_name": perfil["candidato"], "perfil": handle,
                       "declarado_por": perfil["declarado_por"], "video_id": vid, "url": x.get("url") or f"https://www.kwai.com/@{handle}/video/{vid}",
                       "publicado_em": quando(x.get("createTime")), "legenda": " ".join(str(x.get("caption") or "").split()),
                       "duracao_s": ck.inteiro(x.get("duration")), "visualizacoes": ck.inteiro(x.get("viewCount")),
                       "curtidas": ck.inteiro(x.get("likeCount")), "comentarios": ck.inteiro(x.get("commentCount")),
                       "compartilhamentos": ck.inteiro(x.get("shareCount")), "primeira_coleta": old.get("primeira_coleta") or agora,
                       "ultima_coleta": agora, "capa_url": x.get("thumb") or old.get("capa_url", "")}
    with gzip.open(src, "wt", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, ck.COLS, delimiter=";", lineterminator="\n")
        w.writeheader()
        w.writerows(sorted(acervo.values(), key=lambda r: (r["candidate_id"], r["publicado_em"]), reverse=True))
    return novos

if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
