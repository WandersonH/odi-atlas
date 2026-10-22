#!/usr/bin/env python3
"""Comentários públicos dos posts do Facebook das páginas declaradas ao TSE via Apify (dami_studio/facebook-comments-scraper).

Contas: a primeira de `segredos` com saldo (data/config/facebook_comentarios.json); a conta 1 (principal) não é usada.
Teto total da fonte (soma dos manifestos); custo = maior entre o informado pela Apify e a tabela de preços.

--teste: 2 posts × 10 comentários.
--diario: conta 1 (APIFY_TOKEN, autorizado em 22/10/2026), posts desde ontem ainda sem comentários no acervo, até
          cfg["diario"]["comentarios_por_post"] por post; teto por dia e por mês em cfg["diario"]; sem consulta de saldo.
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
    diario = "--diario" in argv
    pub = root / "data/facebook/comentarios"
    pub.mkdir(parents=True, exist_ok=True)
    agora = now_utc()
    mans = [json.loads(f.read_text(encoding="utf-8")) for f in pub.glob("manifesto-*.json")]
    desde = cfg["desde"]
    if diario:
        import datetime as dt
        D = cfg["diario"]
        desde = (dt.datetime.now(dt.timezone(dt.timedelta(hours=-3))) - dt.timedelta(days=1)).date().isoformat()
        ja = round(sum(float(m.get("custo_usd") or 0) for m in mans if m.get("modo") == "diário" and (m.get("run_started_utc") or "")[:7] == agora[:7]), 4)
        teto = round(min(D["teto_dia_usd"], D["teto_mes_usd"] - ja), 4)
    else:
        ja = round(sum(float(m.get("custo_usd") or 0) for m in mans if m.get("modo") != "diário"), 4)
        resta = round(cfg["teto_total_usd"] - ja, 4)
        teto = min(cfg["teto_teste_usd"], resta) if teste else resta
    man = {"run_started_utc": agora, "ferramenta": f"Apify · {cfg['ator'].replace('~', '/')}", "modo": "diário" if diario else "teste" if teste else "carga",
           "teto_total_usd": cfg["diario"]["teto_mes_usd"] if diario else cfg["teto_total_usd"], "gasto_antes_usd": ja, "teto_execucao_usd": teto,
           "desde": desde, "runs": []}

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
    if diario:  # conta 1 autorizada; sem consulta de saldo e sem troca de conta
        nome_conta, saldo = cfg["diario"]["segredo"], None
        token = "x" if executar is not None else os.environ.get(nome_conta, "").strip()
    else:
        nome_conta, token, saldo = escolher_conta(cfg["segredos"], min(teto, 0.2)) if executar is None else ("teste", "x", None)
    man.update(conta=nome_conta, saldo_conta_antes_usd=saldo)
    if not token:
        return fim(f"⛔ nenhuma conta Apify com saldo entre {', '.join(cfg['segredos'])}", 1)
    # o teto da fonte vale para a soma das contas: quando uma esgota, o coletor passa para a próxima
    conta = {"nome": nome_conta, "token": token, "esgotadas": []}

    def executar_real(pl, cap):
        """Troca de conta quando a atual bate o limite do mês (HTTP 403 'hard limit')."""
        while True:
            try:
                return run_actor(conta["token"], cfg["ator"], pl, cap)
            except Exception as e:  # noqa: BLE001
                if getattr(e, "code", None) != 403 or diario:
                    raise
                conta["esgotadas"].append(conta["nome"])
                resto = [x for x in cfg["segredos"] if x not in conta["esgotadas"]]
                n2, t2, _s2 = escolher_conta(resto, cap) if resto else ("", "", None)
                if not t2:
                    raise
                print(f"conta {conta['nome']} sem saldo no mês; seguindo com {n2}")
                conta.update(nome=n2, token=t2)
    executar = executar or executar_real
    priv = Path(interno) / "facebook/comentarios"
    priv.mkdir(parents=True, exist_ok=True)
    acervo = priv / "comentarios.csv.gz"
    antigos = list(csv.DictReader(gzip.open(acervo, "rt", encoding="utf-8"), delimiter=";")) if acervo.exists() else []
    ja_por_post = {}
    for r in antigos:
        ja_por_post[r["video_id"]] = ja_por_post.get(r["video_id"], 0) + 1
    posts = [r for r in csv.DictReader(gzip.open(root / "data/facebook/videos.csv.gz", "rt", encoding="utf-8"), delimiter=";")
             if r["publicado_em"][:10] >= desde and int(r["comentarios"] or 0) > 0 and r["url"]]
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
    if diario:
        pv = cfg["diario"]["comentarios_por_post"]
        novos_posts = [v for v in posts if not ja_por_post.get(v["video_id"])]
        novos_posts.sort(key=lambda v: -int(v["comentarios"] or 0))
        pendentes = novos_posts
        lotes = [(novos_posts[i:i + cfg["posts_por_execucao"]], pv) for i in range(0, len(novos_posts), cfg["posts_por_execucao"])]
    elif teste:
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
        while diario and alvo and gasto + est * 1.2 + 0.01 > teto:
            alvo = alvo[:-1]  # tira o post com menos comentários até caber
            est = sum(p["comentario"] * min(pv, int(v["comentarios"] or 0)) for v in alvo)
        if not alvo or gasto + est > teto * 0.97:
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
    man.update(contas_esgotadas=conta["esgotadas"], conta_final=conta["nome"])
    man.update(custo_usd=round(gasto, 4), comentarios_novos=len(novas), comentarios_no_acervo=len(todos), comentarios_por_candidato=por_cand,
               videos_com_comentarios=len({r["video_id"] for r in todos}), posts_pendentes=len(pendentes))
    print(f"{len(novas)} comentários novos · acervo {len(todos)} {por_cand} · custo US$ {round(gasto, 4)} · teto {teto}")
    return fim("ok" if novas else "⛔ nenhum comentário lido", 0 if novas else 1)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
