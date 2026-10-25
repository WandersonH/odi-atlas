#!/usr/bin/env python3
"""Comentários públicos dos vídeos do TikTok das campanhas (todos os perfis do acervo: declarados ao TSE e o do vice indicado
pelo responsável), via Apify, ator clockworks/tiktok-comments-scraper, sem respostas.

Pedido do responsável (23/10/2026, 11h40): "não temos a página de comentários do TikTok"; autorizado às 11h43 ("a com diario"):
data/config/tiktok_comentarios.json (conta 1).

--carga  (uma vez): cota igual por candidato (3.000) nos vídeos desde 16/08, entre 5 e 50 por vídeo, começando pelos vídeos com
         mais comentários; execuções de até 40 vídeos, cada uma limitada ao que sobra do teto do lote (US$ 3,50). Se a 1ª execução
         não trouxer nenhum comentário reconhecido, as demais não rodam (entrada ou formato errado não gasta o teto).
--diario : vídeos publicados desde ontem (Brasília) ainda sem comentários no acervo, 30 por vídeo, teto do dia e do mês.

Entrada: data/tiktok/conteudo.json. Saída privada: ODI_INTERNO_DIR/tiktok/comentarios/comentarios.csv.gz (mesmas colunas do
YouTube) e brutos. Pública: data/tiktok/comentarios/manifesto-*.json (contagens e custo, sem texto).
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
from reposicao import janela  # noqa: E402
from net import now_utc  # noqa: E402

CODIGO = re.compile(r"/video/(\d+)")


def custo(run: dict | None) -> float:
    return float((run or {}).get("usageTotalUsd") or 0)


def linha(x: dict, post: dict, cid: str, agora: str) -> dict | None:
    texto = " ".join(str(x.get("text") or "").split())
    cid_c = str(x.get("cid") or x.get("id") or "")
    if not texto or not cid_c:
        return None
    return {"comment_id": cid_c, "parent_id": str(x.get("repliesToId") or ""), "tipo": "resposta" if x.get("repliesToId") else "comentario",
            "video_id": post["video_id"], "candidate_id": cid, "channel_id": post["perfil"], "ordem": "padrão",
            "autor_canal": str(x.get("uid") or ""), "autor_nome": x.get("uniqueId") or "", "texto": texto,
            "curtidas": x.get("diggCount") or 0, "respostas": x.get("replyCommentTotal") or 0,
            "publicado_em": x.get("createTimeISO") or "", "atualizado_em": "", "coletado_em": agora}


def main(argv=None, executar=None) -> int:
    argv = sys.argv[1:] if argv is None else list(argv)
    root = Path(".")
    C = json.loads((root / "data/config/tiktok_comentarios.json").read_text(encoding="utf-8"))
    diario = "--diario" in argv
    reforco = "--reforco" in argv  # 23/10/2026: o resto do teto da carga em 50 comentários nos vídeos mais comentados (15 por candidato)
    if not diario and "--carga" not in argv and not reforco:
        print("⛔ informe --carga, --reforco ou --diario")
        return 1
    agora = now_utc()
    pub = root / "data/tiktok/comentarios"
    pub.mkdir(parents=True, exist_ok=True)
    mans = [json.loads(f.read_text(encoding="utf-8")) for f in pub.glob("manifesto-*.json")]
    if diario:
        D = C["diario"]
        ja = round(sum(float(m.get("custo_usd") or 0) for m in mans if m.get("modo") == "diário" and (m.get("run_started_utc") or "")[:7] == agora[:7]), 4)
        _, mult = janela((dt.datetime.now(dt.timezone(dt.timedelta(hours=-3))) - dt.timedelta(days=1)).date().isoformat())
        teto = round(min(D["teto_dia_usd"] * mult, D["teto_mes_usd"] - ja), 4)
    else:
        D = C["carga"]
        ja = round(sum(float(m.get("custo_usd") or 0) for m in mans if m.get("lote") == D["lote"]), 4)
        teto = round(D["teto_usd"] - ja, 4)
    man = {"run_started_utc": agora, "modo": "diário" if diario else "reforço" if reforco else "carga", "lote": None if diario else D["lote"], "conta": C["segredo"],
           "ferramenta": "Apify · " + C["ator"].replace("~", "/"), "gasto_antes_usd": ja, "teto_execucao_usd": teto, "execucoes": []}

    def fim(status: str, code: int) -> int:
        man["status"] = status
        stamp = agora.replace(":", "").replace("-", "")
        for nome in (f"manifesto-{stamp}.json", "manifesto_latest.json"):
            (pub / nome).write_text(json.dumps(man, ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"comentários TikTok: {status}")
        return code

    interno = os.environ.get("ODI_INTERNO_DIR")
    token = os.environ.get(C["segredo"], "").strip()
    if not interno:
        return fim("⛔ sem repositório privado: texto de comentário não pode ir para o público", 1)
    if not (token or executar):
        return fim(f"⛔ falta {C['segredo']}", 1)
    if teto < 0.1:
        return fim(f"⛔ teto esgotado (gasto US$ {ja})", 1)
    priv = Path(interno) / "tiktok/comentarios"
    priv.mkdir(parents=True, exist_ok=True)
    acervo = priv / "comentarios.csv.gz"
    antigos = list(csv.DictReader(gzip.open(acervo, "rt", encoding="utf-8"), delimiter=";")) if acervo.exists() else []
    feitos = {r["video_id"] for r in antigos}
    conteudo = json.loads((root / "data/tiktok/conteudo.json").read_text(encoding="utf-8"))
    posts = {}
    for cid, c in conteudo["candidatos"].items():
        for v in c["videos"]:
            if (v.get("publicado_em") or "") >= C["desde"] and (v.get("comentarios") or 0) > 0:
                posts[v["video_id"]] = {**v, "candidate_id": cid}
    if diario:
        ontem, _ = janela((dt.datetime.now(dt.timezone(dt.timedelta(hours=-3))) - dt.timedelta(days=1)).date().isoformat())
        alvo = [(p, D["por_video"]) for p in posts.values() if p["video_id"] not in feitos and p["publicado_em"][:10] >= ontem]
    elif reforco:  # mesmo lote e teto da carga; vídeos já lidos entram de novo (comentários repetidos contam uma vez, por id)
        alvo = []
        for cid in sorted(conteudo["candidatos"]):
            ps = sorted([p for p in posts.values() if p["candidate_id"] == cid], key=lambda p: -(p.get("comentarios") or 0))
            alvo += [(p, D["max_por_video"]) for p in ps[:D.get("reforco_videos_por_candidato", 15)]]
    else:
        alvo = []
        for cid in sorted(conteudo["candidatos"]):
            ps = sorted([p for p in posts.values() if p["candidate_id"] == cid and p["video_id"] not in feitos], key=lambda p: -(p.get("comentarios") or 0))
            n = max(D["min_por_video"], min(D["max_por_video"], D["cota_por_candidato"] // max(1, len(ps))))
            k = max(1, D["cota_por_candidato"] // n)
            alvo += [(p, n) for p in ps[:k]]
    man["videos_alvo"] = len(alvo)
    if not alvo:
        return fim("ok · nada pendente", 0)
    from collect_meta_apify import run_actor
    executar = executar or (lambda ator, pl, cap: run_actor(token, ator, pl, cap))
    gasto, novas = 0.0, []
    lotes = {}
    for p, n in alvo:  # mesmo limite por post numa execução
        lotes.setdefault(n, []).append(p)
    for n, ps in lotes.items():
        for i in range(0, len(ps), D["videos_por_execucao"]):
            grupo = ps[i:i + D["videos_por_execucao"]]
            sobra = round(teto - gasto, 4)
            caber = int(sobra / C["preco_comentario_usd"] / 1.05 / n)
            if caber < 1 or sobra < 0.1:
                man["execucoes"].append({"posts": len(grupo), "status": f"⛔ não executada: teto de US$ {teto} atingido"})
                continue
            grupo = grupo[:caber]
            cap = round(min(sobra, max(0.1, C["preco_comentario_usd"] * n * len(grupo) * 1.05)), 4)
            pl = {"postURLs": [p["url"] for p in grupo], "commentsPerPost": n, "maxRepliesPerComment": 0}
            try:
                run, itens = executar(C["ator"], pl, cap)
            except Exception as e:  # noqa: BLE001 — o token vai no cabeçalho
                man["execucoes"].append({"posts": len(grupo), "status": f"⛔ {type(e).__name__} {getattr(e, 'code', '')}".strip()})
                continue
            itens = itens or []
            por_codigo = {p["video_id"]: p for p in grupo}
            lin = []
            for x in itens:
                m = CODIGO.search(str(x.get("videoWebUrl") or x.get("submittedVideoUrl") or x.get("input") or ""))
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
                                     "itens": len(itens), "comentarios": len(lin), "custo_usd": c})
            print(f"execução: {len(grupo)} posts × até {n} · {len(lin)} comentários · US$ {c} · total US$ {gasto}")
            if not lin and len(man["execucoes"]) == 1:  # entrada ou formato errado: não gasta o resto do teto
                man["chaves_do_1o_item"] = sorted(itens[0].keys())[:40] if itens else []
                return_status = "⛔ 1ª execução sem comentários reconhecidos; as demais não rodaram"
                print(return_status, man["chaves_do_1o_item"])
                man.update(custo_usd=round(gasto, 4))
                return fim(return_status, 1)
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
               videos_com_comentarios=len({r["video_id"] for r in todos}))
    print(f"{len(novas)} comentários novos · acervo {len(todos)} {por_cand} · custo US$ {round(gasto, 4)} (teto {teto})")
    return fim("ok" if novas else "⛔ nenhum comentário lido", 0 if novas else 1)


if __name__ == "__main__":
    raise SystemExit(main())
