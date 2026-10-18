#!/usr/bin/env python3
"""Respostas públicas aos perfis principais de Lula e Flávio no X, via Apify (xquik/x-tweet-scraper), desde 20/07/2026.

Para a análise de "pontes entre públicos": quem responde aos dois candidatos e em que tom. Amostra, não censo:
o teto autorizado (US$ 5, 18/10/2026) cobre ~3% das respostas informadas pelos posts. Por isso a amostra é igual
por candidato e por dia: uma busca `to:<perfil> since:<dia> until:<dia+1> filter:replies`, até N respostas por dia.
Viés conhecido: a busca "Latest" traz as respostas mais recentes de cada dia (fim do dia pesa mais).

Contas: as de `segredos` em data/config/x_respostas.json (a conta 1 não é usada); troca de conta quando o saldo acaba.
Teto: soma dos manifestos (custo = maior entre o informado pela Apify e a tabela de preço).

--teste: 1 dia, 20 respostas por candidato (mostra as chaves do item para conferir o mapeamento).
--por-post: 2ª estratégia (18/10): a busca por dia devolveu mediana de 19 respostas/dia nas datas antigas; aqui, as
respostas de cada post (`conversation_id:<id>`), os N posts com mais respostas de cada semana, mesmo N por candidato.

Saída privada (ODI_INTERNO_DIR/x/respostas/): respostas.csv.gz (mesmas colunas dos comentários do YouTube:
video_id = post respondido, autor_canal = id do autor) e o bruto.
Saída pública: data/x/respostas/manifesto-*.json (contagens; nenhum texto nem autor).
"""
from __future__ import annotations

import csv
import datetime as dt
import gzip
import json
import os
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from collect_comentarios_youtube import CAMPOS  # noqa: E402
from collect_kwai_apify import g, inteiro  # noqa: E402
from collect_meta_anuncios_apify import custo_run  # noqa: E402
from collect_meta_apify import escolher_conta, run_actor  # noqa: E402
from collect_x_posts import quando  # noqa: E402
from net import now_utc  # noqa: E402


def linha(x: dict, perfil: dict, agora: str) -> dict | None:
    tid = str(g(x, "id", "id_str", "tweetId") or "")
    if not tid:
        return None
    pai = str(g(x, "inReplyToId", "inReplyToStatusId", "in_reply_to_status_id_str", "inReplyToTweetId") or "")
    conv = str(g(x, "conversationId", "conversation_id_str") or "")
    return {"comment_id": tid, "parent_id": pai, "tipo": "resposta_x", "video_id": conv or pai,
            "candidate_id": perfil["candidate_id"], "channel_id": perfil["handle"],
            # resposta direta ao candidato ou a outra pessoa dentro da conversa do post do candidato
            "ordem": "direta" if str(g(x, "inReplyToUsername") or "").lower() == perfil["handle"].lower() else "na_conversa",
            "autor_canal": str(g(x, "author.id", "author.userId", "user.id_str", "user.id") or ""),
            "autor_nome": str(g(x, "author.userName", "author.username", "user.screen_name") or ""),
            "texto": " ".join(str(g(x, "text", "fullText", "full_text") or "").split()),
            "curtidas": inteiro(g(x, "likeCount", "favorite_count")) or 0, "respostas": inteiro(g(x, "replyCount", "reply_count")) or 0,
            "publicado_em": quando(g(x, "createdAt", "created_at")), "atualizado_em": "", "coletado_em": agora}


def dias(desde: str, ate: str) -> list[str]:
    d0, d1 = dt.date.fromisoformat(desde), dt.date.fromisoformat(ate)
    return [(d0 + dt.timedelta(i)).isoformat() for i in range((d1 - d0).days + 1)]


def main(argv=None, executar=None, contas=None) -> int:
    argv = list(argv or [])
    root = Path(".")
    cfg = json.loads((root / "data/config/x_respostas.json").read_text(encoding="utf-8"))
    teste = "--teste" in argv
    pub = root / "data/x/respostas"
    pub.mkdir(parents=True, exist_ok=True)
    agora = now_utc()
    ja = round(sum(float(json.loads(f.read_text(encoding="utf-8")).get("custo_usd") or 0) for f in pub.glob("manifesto-*.json")), 4)
    resta = round(cfg["teto_total_usd"] - ja, 4)
    teto = min(cfg["teto_teste_usd"], resta) if teste else resta
    preco = cfg["preco_usd"]["post"]
    man = {"run_started_utc": agora, "ferramenta": f"Apify · {cfg['ator'].replace('~', '/')}", "modo": "teste" if teste else "carga",
           "teto_total_usd": cfg["teto_total_usd"], "gasto_antes_usd": ja, "teto_execucao_usd": teto, "buscas": []}

    def fim(status: str, code: int) -> int:
        man["status"] = status
        stamp = agora.replace(":", "").replace("-", "")
        for nome in (f"manifesto-{stamp}.json", "manifesto_latest.json"):
            (pub / nome).write_text(json.dumps(man, ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"respostas X: {status}")
        return code

    interno = os.environ.get("ODI_INTERNO_DIR")
    if not interno:
        return fim("⛔ sem repositório privado: texto de resposta não pode ir para o público", 1)
    if teto < 0.005:
        return fim(f"⛔ teto de US$ {cfg['teto_total_usd']} esgotado", 1)
    priv = Path(interno) / "x/respostas"
    priv.mkdir(parents=True, exist_ok=True)
    acervo = priv / "respostas.csv.gz"
    antigos = list(csv.DictReader(gzip.open(acervo, "rt", encoding="utf-8"), delimiter=";")) if acervo.exists() else []
    feitos = {(r["channel_id"], r["publicado_em"][:10]) for r in antigos}  # (perfil, dia) já com respostas
    ate = (dt.date.fromisoformat(agora[:10]) - dt.timedelta(days=1)).isoformat()
    lista_dias = dias(cfg["desde"], ate)
    por_post = "--por-post" in argv
    if por_post:
        # 2ª estratégia: respostas de cada post (conversation_id), os posts com mais respostas de cada semana, mesmo número por candidato
        ja_post = {r["video_id"] for r in antigos if r.get("ordem") in ("direta", "na_conversa") and r.get("tipo") == "resposta_x_post"}
        posts = [r for r in csv.DictReader(gzip.open(root / "data/x/videos.csv.gz", "rt", encoding="utf-8"), delimiter=";")
                 if r["publicado_em"][:10] >= cfg["desde"] and int(float(r["comentarios"] or 0)) > 0]
        escolhidos = []
        k = cfg["por_post"]["teste_posts"] if teste else cfg["por_post"]["posts_por_semana"]
        for p in cfg["perfis"]:
            meus = [r for r in posts if r["perfil"].lower() == p["handle"].lower() and r["video_id"] not in ja_post]
            sem = {}
            for r in meus:
                d = dt.date.fromisoformat(r["publicado_em"][:10])
                sem.setdefault((d - dt.timedelta(days=d.weekday())).isoformat(), []).append(r)
            for lst in sem.values():
                escolhidos += [(p, r) for r in sorted(lst, key=lambda r: -int(float(r["comentarios"] or 0)))[:k]]
        if teste:  # 1 post por candidato (o com mais respostas da semana mais recente)
            escolhidos = [next(e for e in reversed(escolhidos) if e[0] is p) for p in cfg["perfis"] if any(e[0] is p for e in escolhidos)]
        n = cfg["por_post"]["teste_por_post"] if teste else max(10, min(cfg["por_post"]["max_por_post"], int(teto * 0.95 / preco / max(1, len(escolhidos)))))
        tarefas = [(p, r["publicado_em"][:10], min(n, int(float(r["comentarios"])) + 5), r["video_id"]) for p, r in escolhidos]
    elif teste:
        tarefas = [(p, cfg["teste"]["dia"], cfg["teste"]["por_dia"]) for p in cfg["perfis"]]
    else:
        pend = [(p, d) for d in lista_dias for p in cfg["perfis"] if (p["handle"], d) not in feitos]
        n = max(10, min(cfg["max_por_dia"], int(teto * 0.95 / preco / max(1, len(pend)))))
        tarefas = [(p, d, n) for p, d in pend]
    man.update(estrategia="por post (conversation_id)" if por_post else "por dia (to:perfil)", dias_no_periodo=len(lista_dias),
               buscas_planejadas=len(tarefas), por_busca=max((t[2] for t in tarefas), default=0))
    print(f"{len(tarefas)} buscas planejadas, até {man['por_busca']} respostas cada · teto US$ {teto}")
    gasto, novas, brutos = 0.0, [], []
    lote = cfg.get("buscas_por_lote", 16)
    for i in range(0, len(tarefas), lote):
        parte = tarefas[i:i + lote]
        est = round(sum(t[2] for t in parte) * preco * 1.1 + 0.02, 4)
        if gasto + est > teto:
            man["parou"] = f"teto: gasto US$ {round(gasto, 4)} + estimativa do lote US$ {est} > US$ {teto}"
            print(man["parou"])
            break
        if executar is None:
            nome, token, saldo = (contas or escolher_conta)(cfg["segredos"], est)
            if not token:
                man["parou"] = "nenhuma conta Apify com saldo"
                print(man["parou"])
                break
            exe = (lambda tok: (lambda pl, cap: run_actor(tok, cfg["ator"], pl, cap)))(token)
        else:
            nome, exe = "teste", executar

        def um(t, exe=exe, nome=nome):
            p, d, n = t[:3]
            if len(t) > 3:
                pl = {"searchTerms": [f"conversation_id:{t[3]}"], "maxItems": n, "queryType": "Latest"}
            else:
                d2 = (dt.date.fromisoformat(d) + dt.timedelta(days=1)).isoformat()
                pl = {"searchTerms": [f"to:{p['handle']} since:{d} until:{d2} filter:replies"], "maxItems": n, "queryType": "Latest"}
            try:
                run, itens = exe(pl, round(n * preco * 1.2 + 0.01, 4))
                return t, nome, run or {}, itens or [], None
            except Exception as e:  # noqa: BLE001 — o token vai no cabeçalho
                return t, nome, {}, [], f"{type(e).__name__} {getattr(e, 'code', '')}".strip()
        with ThreadPoolExecutor(max_workers=4) as ex:
            res = list(ex.map(um, parte))
        for t, conta, run, itens, erro in res:
            p, d, n = t[:3]
            brutos += itens
            lin = [r for r in (linha(x, p, agora) for x in itens) if r and r["texto"] and str(r["comment_id"]) != (t[3] if len(t) > 3 else "")]
            if len(t) > 3:
                for r in lin:
                    r["tipo"] = "resposta_x_post"
            custo = 0.0 if erro else max(custo_run(run) or 0, round(preco * len(itens), 5))
            gasto += custo
            novas += lin
            man["buscas"].append({"perfil": p["handle"], "dia": d, "post": t[3] if len(t) > 3 else None, "pedido": n, "itens": len(itens), "respostas": len(lin), "conta": conta,
                                  "run": run.get("id"), "custo_usd": custo, "erro": erro})
            if teste and itens:
                print("chaves do 1º item: " + ", ".join(sorted(itens[0].keys()))[:700])
                print("autor: " + ", ".join(sorted((itens[0].get("author") or {}).keys()))[:400])
        print(f"lote {i // lote + 1}: {sum(len(r[3]) for r in res)} itens · gasto acumulado US$ {round(gasto, 4)}")
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
    por = {}
    for r in todos:
        por[r["candidate_id"]] = por.get(r["candidate_id"], 0) + 1
    man.update(custo_usd=round(gasto, 4), respostas_novas=len(novas), respostas_no_acervo=len(todos), respostas_por_candidato=por,
               autores_distintos=len({r["autor_canal"] for r in todos if r["autor_canal"]}),
               sem_autor=sum(1 for r in todos if not r["autor_canal"]), sem_post_respondido=sum(1 for r in todos if not r["video_id"]))
    print(f"{len(novas)} respostas novas · acervo {len(todos)} {por} · custo US$ {round(gasto, 4)}")
    return fim("ok" if novas else "⛔ nenhuma resposta lida", 0 if novas else 1)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
