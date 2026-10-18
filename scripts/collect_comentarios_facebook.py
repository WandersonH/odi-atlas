#!/usr/bin/env python3
"""Comentários públicos dos posts do Facebook das páginas declaradas ao TSE via Apify (dami_studio/facebook-comments-scraper).

Contas: a primeira de `segredos` com saldo (data/config/facebook_comentarios.json); a conta 1 (principal) não é usada.
Teto total da fonte (soma dos manifestos); custo = maior entre o informado pela Apify e a tabela de preços.

--teste: 2 posts × 10 comentários.
sem opção: cota igual por candidato dividida entre os posts do período (desde `desde`), até 100 posts por execução.

Saída privada (ODI_INTERNO_DIR/facebook/comentarios/): bruto e comentarios.csv.gz (mesmas colunas do YouTube).
Saída pública: data/facebook/comentarios/manifesto-*.json (contagens e custo; nenhum texto ou autor).
"""
from __future__ import annotations

import csv
import gzip
import json
import os
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from collect_comentarios_youtube import CAMPOS  # noqa: E402
from collect_kwai_apify import g, quando  # noqa: E402
from collect_meta_anuncios_apify import custo_run  # noqa: E402
from collect_meta_apify import escolher_conta, run_actor  # noqa: E402
from net import now_utc  # noqa: E402


def chave_post(url: str) -> str:
    """Identificador estável do post a partir da URL (o ator devolve a URL pedida em inputUrl)."""
    return re.sub(r"[?#].*$", "", str(url or "")).rstrip("/").lower()


def linha(x: dict, post: dict, agora: str) -> dict:
    pai = str(g(x, "replyToCommentId", "parentId") or "")
    return {"comment_id": str(g(x, "commentId", "id") or ""), "parent_id": pai, "tipo": "resposta" if pai else "comentario",
            "video_id": post["video_id"], "candidate_id": post["candidate_id"], "channel_id": post["perfil"], "ordem": "facebook",
            "autor_canal": str(g(x, "profileId", "author.id") or ""), "autor_nome": str(g(x, "profileName", "author.name") or ""),
            "texto": " ".join(str(g(x, "text", "content") or "").split()), "curtidas": g(x, "likesCount", "likeCount") or 0,
            "respostas": g(x, "commentsCount", "replyCount") if not pai else "", "publicado_em": quando(g(x, "date", "timestamp", "createdAt")),
            "atualizado_em": "", "coletado_em": agora}


def main(argv=None, executar=None) -> int:
    argv = list(argv or [])
    root = Path(".")
    cfg = json.loads((root / "data/config/facebook_comentarios.json").read_text(encoding="utf-8"))
    teste = "--teste" in argv
    pub = root / "data/facebook/comentarios"
    pub.mkdir(parents=True, exist_ok=True)
    agora = now_utc()
    ja = round(sum(float(json.loads(f.read_text(encoding="utf-8")).get("custo_usd") or 0) for f in pub.glob("manifesto-*.json")), 4)
    resta = round(cfg["teto_total_usd"] - ja, 4)
    teto = min(cfg["teto_teste_usd"], resta) if teste else resta
    man = {"run_started_utc": agora, "ferramenta": f"Apify · {cfg['ator'].replace('~', '/')}", "modo": "teste" if teste else "carga",
           "teto_total_usd": cfg["teto_total_usd"], "gasto_antes_usd": ja, "teto_execucao_usd": teto, "runs": []}

    def fim(status: str, code: int) -> int:
        man["status"] = status
        stamp = agora.replace(":", "").replace("-", "")
        for nome in (f"manifesto-{stamp}.json", "manifesto_latest.json"):
            (pub / nome).write_text(json.dumps(man, ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"comentários Facebook: {status}")
        return code

    interno = os.environ.get("ODI_INTERNO_DIR")
    if not interno:
        return fim("⛔ sem repositório privado: texto de comentário não pode ir para o público", 1)
    if teto < 0.005:
        return fim(f"⛔ teto de US$ {cfg['teto_total_usd']} esgotado (gasto US$ {ja})", 1)
    nome_conta, token, saldo = escolher_conta(cfg["segredos"], min(teto, 0.2)) if executar is None else ("teste", "x", None)
    man.update(conta=nome_conta, saldo_conta_antes_usd=saldo)
    if not token:
        return fim(f"⛔ nenhuma conta Apify com saldo entre {', '.join(cfg['segredos'])}", 1)
    if saldo is not None:
        teto = min(teto, saldo)
    executar = executar or (lambda pl, cap: run_actor(token, cfg["ator"], pl, cap))
    priv = Path(interno) / "facebook/comentarios"
    priv.mkdir(parents=True, exist_ok=True)
    acervo = priv / "comentarios.csv.gz"
    antigos = list(csv.DictReader(gzip.open(acervo, "rt", encoding="utf-8"), delimiter=";")) if acervo.exists() else []
    ja_por_post = {}
    for r in antigos:
        ja_por_post[r["video_id"]] = ja_por_post.get(r["video_id"], 0) + 1
    posts = [r for r in csv.DictReader(gzip.open(root / "data/facebook/videos.csv.gz", "rt", encoding="utf-8"), delimiter=";")
             if r["publicado_em"][:10] >= cfg["desde"] and int(r["comentarios"] or 0) > 0 and r["url"]]
    alvo_post = {}
    for cid in {v["candidate_id"] for v in posts}:
        n_c = sum(1 for v in posts if v["candidate_id"] == cid)
        pv_c = max(cfg["min_comentarios_por_post"], min(cfg["max_comentarios_por_post"], cfg["cota_comentarios_por_candidato"] // max(1, n_c)))
        for v in posts:
            if v["candidate_id"] == cid:
                alvo_post[v["video_id"]] = min(pv_c, int(v["comentarios"] or 0))
    # pendente: post sem coleta ou com menos de 80% da meta atual (a meta sobe quando o teto aumenta; repetidos são descartados)
    pendentes = sorted((v for v in posts if ja_por_post.get(v["video_id"], 0) < 0.8 * alvo_post[v["video_id"]]),
                       key=lambda v: -int(v["comentarios"] or 0))
    p = cfg["preco_usd"]
    if teste:
        lotes = [(pendentes[:cfg["teste"]["posts"]], cfg["teste"]["comentarios_por_post"])]
    else:
        lotes = []
        for cid in sorted({v["candidate_id"] for v in posts}):
            n_c = sum(1 for v in posts if v["candidate_id"] == cid)
            pv = max(cfg["min_comentarios_por_post"], min(cfg["max_comentarios_por_post"], cfg["cota_comentarios_por_candidato"] // max(1, n_c)))
            meus = [v for v in pendentes if v["candidate_id"] == cid]
            for i in range(0, len(meus), cfg["posts_por_execucao"]):
                lotes.append((meus[i:i + cfg["posts_por_execucao"]], pv))
    novas, gasto, brutos = [], 0.0, []
    for alvo, pv in lotes:
        est = sum(p["comentario"] * min(pv, int(v["comentarios"] or 0)) for v in alvo)
        if gasto + est > teto * 0.97:
            continue
        por_url = {chave_post(v["url"]): v for v in alvo}
        pl = {"startUrls": [{"url": v["url"]} for v in alvo], "resultsLimit": pv}
        try:
            run, itens = executar(pl, round(min(teto - gasto, est * 1.2 + 0.01), 4))
        except Exception as e:  # noqa: BLE001 — o token vai no cabeçalho
            corpo = ""
            try:
                corpo = e.read().decode("utf-8", "replace")[:300]  # resposta da Apify (não contém o token)
            except Exception:  # noqa: BLE001
                pass
            man["runs"].append({"erro": f"{type(e).__name__} {getattr(e, 'code', '')} {corpo}".strip()})
            print(f"erro na execução: {type(e).__name__} {getattr(e, 'code', '')} {corpo}")
            continue
        itens = itens or []
        brutos += itens
        lin = [linha(x, por_url[chave_post(x.get("inputUrl"))], agora) for x in itens
               if chave_post(x.get("inputUrl")) in por_url and g(x, "text", "content") is not None]
        custo = max(custo_run(run) or 0, round(p["comentario"] * len(lin), 4))
        gasto += custo
        novas += lin
        man["runs"].append({"id": (run or {}).get("id"), "status": (run or {}).get("status"), "posts": len(alvo), "por_post": pv, "itens": len(itens),
                            "comentarios": len(lin), "custo_usd": custo, "eventos_cobrados": (run or {}).get("chargedEventCounts")})
        print(f"lote: {len(alvo)} posts × até {pv} · {len(itens)} itens · {len(lin)} comentários · US$ {custo}")
        if itens and not lin:
            print("1º item (só chaves e tipos): " + json.dumps({k: type(v).__name__ for k, v in itens[0].items()})[:600])
    if brutos:
        with gzip.open(priv / f"apify_{agora.replace(':', '').replace('-', '')}.jsonl.gz", "wt", encoding="utf-8") as f:
            for x in brutos:
                f.write(json.dumps(x, ensure_ascii=False) + "\n")
    ids = {r["comment_id"] for r in novas}
    todos = [r for r in antigos if r["comment_id"] not in ids] + novas
    with gzip.open(acervo, "wt", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, CAMPOS, delimiter=";", lineterminator="\n", extrasaction="ignore")
        w.writeheader()
        w.writerows(todos)
    por_cand = {}
    for r in todos:
        por_cand[r["candidate_id"]] = por_cand.get(r["candidate_id"], 0) + 1
    man.update(custo_usd=round(gasto, 4), comentarios_novos=len(novas), comentarios_no_acervo=len(todos), comentarios_por_candidato=por_cand,
               videos_com_comentarios=len({r["video_id"] for r in todos}), posts_pendentes=len(pendentes))
    print(f"{len(novas)} comentários novos · acervo {len(todos)} {por_cand} · custo US$ {round(gasto, 4)} · teto {teto}")
    return fim("ok" if novas else "⛔ nenhum comentário lido", 0 if novas else 1)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
