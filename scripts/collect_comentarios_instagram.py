#!/usr/bin/env python3
"""Comentários públicos dos posts do Instagram das campanhas (perfis principais: @lulaoficial e @flaviobolsonaro), via Apify.

Pedido do responsável (23/10/2026, 01h31): "não temos uma página de comentários do Instagram"; autorizado às 01h36
(data/config/instagram_comentarios.json): conta 1, ator datadoping/instagram-comments-and-replies-scraper (o mesmo dos casos
007 e 008), ordem "popular", sem respostas.

--carga  (uma vez): cota igual por candidato (3.000) nos posts desde 16/08, entre 5 e 50 por post, começando pelos posts com
         mais comentários; execuções de até 40 posts, cada uma limitada ao que sobra do teto do lote (US$ 8,50).
--diario : posts publicados desde ontem (Brasília) ainda sem comentários no acervo, 30 por post, teto do dia e do mês.

Entrada: data/instagram/conteudo.json (acervo de posts). Saída privada: ODI_INTERNO_DIR/instagram/comentarios/comentarios.csv.gz
(mesmas colunas do YouTube) e brutos. Pública: data/instagram/comentarios/manifesto-*.json (contagens e custo, sem texto).
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
from net import now_utc  # noqa: E402

CODIGO = re.compile(r"instagram\.com/(?:[\w.]+/)?(?:p|reel|reels|tv)/([\w-]+)")


def custo(run: dict | None) -> float:
    return float((run or {}).get("usageTotalUsd") or 0)


def linha(x: dict, post: dict, cid: str, agora: str) -> dict | None:
    if x.get("content_type") == "caption" or x.get("is_created_by_media_owner") and x.get("content_type") == "caption":
        return None
    texto = " ".join(str(x.get("text") or "").split())
    cid_c = str(x.get("comment_id") or x.get("id") or "")
    if not texto or not cid_c:
        return None
    u = x.get("user") if isinstance(x.get("user"), dict) else {}
    pai = str(x.get("parent_comment_id") or x.get("replied_to_comment_id") or "")
    return {"comment_id": cid_c, "parent_id": pai, "tipo": "resposta" if pai else "comentario", "video_id": post["video_id"], "candidate_id": cid,
            "channel_id": post["perfil"], "ordem": "popular", "autor_canal": str(x.get("user_id") or u.get("id") or ""),
            "autor_nome": x.get("username") or u.get("username") or "", "texto": texto, "curtidas": x.get("like_count") or 0,
            "respostas": x.get("child_comment_count") or 0, "publicado_em": x.get("created_at_utc") or "", "atualizado_em": "", "coletado_em": agora}


def desdobrar(itens: list[dict]) -> list[dict]:
    """Itens do ator mais as respostas que vêm dentro de cada comentário (prévia grátis em preview_child_comments, ou
    listas de respostas quando o ator as entrega aninhadas). A resposta herda o input_url do comentário."""
    out = []
    for x in itens:
        out.append(x)
        for k in ("preview_child_comments", "replies", "child_comments"):
            for r in x.get(k) or []:
                if isinstance(r, dict):
                    out.append({**r, "input_url": x.get("input_url"), "parent_comment_id": r.get("parent_comment_id") or x.get("comment_id") or x.get("id")})
    return out


def main(argv=None, executar=None) -> int:
    argv = sys.argv[1:] if argv is None else list(argv)
    root = Path(".")
    C = json.loads((root / "data/config/instagram_comentarios.json").read_text(encoding="utf-8"))
    diario = "--diario" in argv
    respostas = "--respostas" in argv
    if not diario and not respostas and "--carga" not in argv:
        print("⛔ informe --carga, --diario ou --respostas")
        return 1
    agora = now_utc()
    pub = root / "data/instagram/comentarios"
    pub.mkdir(parents=True, exist_ok=True)
    mans = [json.loads(f.read_text(encoding="utf-8")) for f in pub.glob("manifesto-*.json")]
    if diario:
        D = C["diario"]
        ja = round(sum(float(m.get("custo_usd") or 0) for m in mans if m.get("modo") == "diário" and (m.get("run_started_utc") or "")[:7] == agora[:7]), 4)
        teto = round(min(D["teto_dia_usd"], D["teto_mes_usd"] - ja), 4)
    else:
        D = C["respostas"] if respostas else C["carga"]
        ja = round(sum(float(m.get("custo_usd") or 0) for m in mans if m.get("lote") == D["lote"]), 4)
        teto = round(D["teto_usd"] - ja, 4)
    modo = "diário" if diario else "respostas" if respostas else "carga"
    man = {"run_started_utc": agora, "modo": modo, "lote": None if diario else D["lote"], "conta": C["segredo"],
           "ferramenta": "Apify · " + C["ator"].replace("~", "/"), "gasto_antes_usd": ja, "teto_execucao_usd": teto, "execucoes": []}

    def fim(status: str, code: int) -> int:
        man["status"] = status
        stamp = agora.replace(":", "").replace("-", "")
        for nome in (f"manifesto-{stamp}.json", "manifesto_latest.json"):
            (pub / nome).write_text(json.dumps(man, ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"comentários Instagram: {status}")
        return code

    interno = os.environ.get("ODI_INTERNO_DIR")
    token = os.environ.get(C["segredo"], "").strip()
    if not interno:
        return fim("⛔ sem repositório privado: texto de comentário não pode ir para o público", 1)
    if not (token or executar):
        return fim(f"⛔ falta {C['segredo']}", 1)
    if teto < 0.1:
        return fim(f"⛔ teto esgotado (gasto US$ {ja})", 1)
    priv = Path(interno) / "instagram/comentarios"
    priv.mkdir(parents=True, exist_ok=True)
    acervo = priv / "comentarios.csv.gz"
    antigos = list(csv.DictReader(gzip.open(acervo, "rt", encoding="utf-8"), delimiter=";")) if acervo.exists() else []
    feitos = {r["video_id"] for r in antigos}
    conteudo = json.loads((root / "data/instagram/conteudo.json").read_text(encoding="utf-8"))
    posts = {}
    for cid, c in conteudo["candidatos"].items():
        for v in c["videos"]:
            if C["perfis"].get(v["perfil"]) == cid and (v.get("publicado_em") or "") >= C["desde"] and (v.get("comentarios") or 0) > 0:
                posts[v["video_id"]] = {**v, "candidate_id": cid}
    if diario:
        ontem = (dt.datetime.now(dt.timezone(dt.timedelta(hours=-3))) - dt.timedelta(days=1)).date().isoformat()
        alvo = [(p, D["por_post"]) for p in posts.values() if p["video_id"] not in feitos and p["publicado_em"][:10] >= ontem]
    else:
        alvo = []
        for cid in ([] if respostas else sorted(set(C["perfis"].values()))):
            ps = sorted([p for p in posts.values() if p["candidate_id"] == cid and p["video_id"] not in feitos], key=lambda p: -(p.get("comentarios") or 0))
            n = max(D["min_por_post"], min(D["max_por_post"], D["cota_por_candidato"] // max(1, len(ps))))
            k = max(1, D["cota_por_candidato"] // n)
            alvo += [(p, n) for p in ps[:k]]
    if respostas:  # posts com mais respostas no acervo bruto (child_comment_count dos comentários já lidos)
        soma = {}
        for f in priv.glob("apify_*.jsonl.gz"):
            for l in gzip.open(f, "rt", encoding="utf-8"):
                x = json.loads(l)
                m = CODIGO.search(str(x.get("input_url") or ""))
                if m and x.get("content_type") != "caption":
                    soma[m.group(1)] = soma.get(m.group(1), 0) + int(x.get("child_comment_count") or 0)
        ja_resp = {r["parent_id"] for r in antigos if r.get("tipo") == "resposta"}
        ordem = sorted((v for v in posts if soma.get(v)), key=lambda v: -soma[v])
        alvo = [(posts[v], D["comentarios_por_post"]) for v in ordem[:D["posts"]]]
        man["respostas_ja_no_acervo"] = len(ja_resp)
    man["posts_alvo"] = len(alvo)
    if not alvo:
        return fim("ok · nada pendente", 0)
    from collect_meta_apify import run_actor
    executar = executar or (lambda ator, pl, cap: run_actor(token, ator, pl, cap))
    gasto, novas = 0.0, []
    if respostas:  # grátis: prévias de respostas que já vieram nos brutos anteriores (preview_child_comments)
        for f in sorted(priv.glob("apify_*.jsonl.gz")):
            for l in gzip.open(f, "rt", encoding="utf-8"):
                x = json.loads(l)
                for y in desdobrar([x])[1:]:
                    m = CODIGO.search(str(y.get("input_url") or ""))
                    p = posts.get(m.group(1)) if m else None
                    r = linha(y, p, p["candidate_id"], agora) if p else None
                    if r and r["tipo"] == "resposta":
                        novas.append(r)
        man["respostas_previas_gratis"] = len(novas)
        print(f"prévias de respostas já nos brutos (grátis): {len(novas)}")
    lotes = {}
    for p, n in alvo:  # mesmo limite por post numa execução
        lotes.setdefault(n, []).append(p)
    for n, ps in lotes.items():
        for i in range(0, len(ps), D["posts_por_execucao"]):
            grupo = ps[i:i + D["posts_por_execucao"]]
            sobra = round(teto - gasto, 4)
            por_item = n * (1 + (D["respostas_por_comentario"] if respostas else 0))  # comentário + respostas
            caber = int(sobra / C["preco_comentario_usd"] / 1.05 / por_item)
            if caber < 1 or sobra < 0.1:
                man["execucoes"].append({"posts": len(grupo), "status": f"⛔ não executada: teto de US$ {teto} atingido"})
                continue
            grupo = grupo[:caber]
            cap = round(min(sobra, max(0.1, C["preco_comentario_usd"] * por_item * len(grupo) * 1.05)), 4)
            pl = {"code_or_id_or_url": [p["url"] for p in grupo], "sort_by": "popular", "max_comments": n, "scrape_replies": respostas,
                  "max_replies": D["respostas_por_comentario"] if respostas else 20}
            try:
                run, itens = executar(C["ator"], pl, cap)
            except Exception as e:  # noqa: BLE001 — o token vai no cabeçalho
                man["execucoes"].append({"posts": len(grupo), "status": f"⛔ {type(e).__name__} {getattr(e, 'code', '')}".strip()})
                continue
            itens = itens or []
            por_codigo = {p["video_id"]: p for p in grupo}
            lin = []
            for x in desdobrar(itens):
                m = CODIGO.search(str(x.get("input_url") or ""))
                p = por_codigo.get(m.group(1)) if m else None
                r = linha(x, p, p["candidate_id"], agora) if p else None
                if r:
                    lin.append(r)
            c = max(custo(run), round(C["preco_comentario_usd"] * len(lin), 4))
            gasto = round(gasto + c, 4)
            novas += lin
            with gzip.open(priv / f"apify_{now_utc().replace(':', '').replace('-', '')}_{len(man['execucoes'])}.jsonl.gz", "wt", encoding="utf-8") as f:
                for x in itens:
                    f.write(json.dumps(x, ensure_ascii=False) + "\n")
            man["execucoes"].append({"run": (run or {}).get("id"), "status": (run or {}).get("status"), "posts": len(grupo), "por_post": n,
                                     "itens": len(itens), "comentarios": len(lin), "respostas": sum(1 for r in lin if r["tipo"] == "resposta"), "custo_usd": c})
            print(f"execução: {len(grupo)} posts × até {n} · {len(lin)} comentários · US$ {c} · total US$ {gasto}")
    novas = list({r["comment_id"]: r for r in novas}.values())  # prévia grátis e coleta paga podem trazer a mesma resposta
    ids = {r["comment_id"] for r in novas}
    todos = [r for r in antigos if r["comment_id"] not in ids] + novas
    with gzip.open(acervo, "wt", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, CAMPOS, delimiter=";", lineterminator="\n", extrasaction="ignore")
        w.writeheader()
        w.writerows(todos)
    por_cand = {}
    for r in todos:
        por_cand[r["candidate_id"]] = por_cand.get(r["candidate_id"], 0) + 1
    man.update(custo_usd=round(gasto, 4), comentarios_novos=len(novas), respostas_no_acervo=sum(1 for r in todos if r.get("tipo") == "resposta"), comentarios_no_acervo=len(todos), comentarios_por_candidato=por_cand,
               posts_com_comentarios=len({r["video_id"] for r in todos}))
    print(f"{len(novas)} comentários novos · acervo {len(todos)} {por_cand} · custo US$ {round(gasto, 4)} (teto {teto})")
    return fim("ok" if novas else "⛔ nenhum comentário lido", 0 if novas else 1)


if __name__ == "__main__":
    raise SystemExit(main())
