#!/usr/bin/env python3
"""Coleta NOVA de um post do Instagram para um caso (conta 1 do Apify, teto total obrigatório e autorizado a cada vez).

Pedido do responsável (22/10/2026, 18h48): caso 008, reel sobre camisas do PT em Piracicaba; autorizou teto de US$ 3,00.

Três execuções em sequência, cada uma limitada pelo que sobra do teto (maxTotalChargeUsd do Apify, valor real lido depois):
  1. apify/instagram-reel-scraper — números do post (reproduções, curtidas, comentários, compartilhamentos, autor);
  2. datadoping/instagram-comments-and-replies-scraper — comentários (ordem "popular"), até --comentarios, sem respostas;
     o limite é reduzido para caber no teto (preço de tabela US$ 1,40 por mil, conferido no custo real do caso 007);
  3. apify/instagram-profile-scraper — seguidores do autor (regra de nome: 10 mil+), se ainda couber no teto.
Cada execução é gravada como as importadas (scripts/importar_apify_runs.py), para o build_caso_instagram.py ler igual.

Saída privada: ODI_INTERNO_DIR/casos/<caso>/apify/<run_id>.json, manifesto_coleta.json e perfil_instagram.json.
Saída pública: nenhuma direta (o build do caso agrega).
Uso: python scripts/coletar_caso_instagram.py --caso 008 --url https://www.instagram.com/reel/<código>/ --teto 3.0 [--comentarios 2000] [--transcricao]
"""
from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from collect_meta_apify import run_actor  # noqa: E402
from net import now_utc  # noqa: E402

PRECO_COMENTARIO = 1.40 / 1000
RESERVA_PERFIL = 0.10   # mínimo de maxTotalChargeUsd aceito pelo Apify; o custo real do perfil no caso 007 foi 0
MIN_CAP = 0.10
CAP_TRANSCRICAO = 0.30


def arg(argv, k, d=None):
    return argv[argv.index(k) + 1] if k in argv else d


def custo(run: dict | None) -> float:
    return float((run or {}).get("usageTotalUsd") or 0)


def coletar(caso: str, url: str, teto: float, maximo: int, priv: Path, executar, transcricao: bool = False) -> dict:
    priv.mkdir(parents=True, exist_ok=True)
    gasto, regs, erros = 0.0, [], []
    # nova tentativa no mesmo caso: execuções já gravadas contam no teto e não se repetem (o custo informado logo após o fim
    # pode vir zerado; conta-se pelo menos o preço de tabela do que veio)
    feitos = {}
    for f in sorted(priv.glob("*.json")):
        if f.name.startswith("manifesto"):
            continue
        d = json.loads(f.read_text(encoding="utf-8"))
        piso = 0.01 if "reel-scraper" in d.get("ator", "") else len(d.get("items") or []) * PRECO_COMENTARIO
        gasto += max(float(d.get("custo_usd") or 0), piso)
        feitos[d.get("ator", "").split(" ")[0]] = d
        regs.append({k: d.get(k) for k in ("run_id", "ator", "status", "inicio_utc", "fim_utc", "origem", "custo_usd", "itens")} | {"reaproveitado": True})

    def tentar(ator, entrada, cap):
        try:
            return executar(ator, entrada, cap)
        except Exception as e:  # noqa: BLE001 — a mensagem da API do Apify não contém o token
            corpo = ""
            if hasattr(e, "read"):
                try:
                    corpo = e.read().decode("utf-8", "replace")[:300]
                except Exception:  # noqa: BLE001
                    pass
            erros.append(f"{ator}: {type(e).__name__} {getattr(e, 'code', '')} {corpo or str(e)[:200]}".strip())
            return None, []

    def gravar(ator: str, entrada: dict, run: dict, itens: list) -> None:
        reg = {"run_id": run.get("id"), "ator": ator, "status": run.get("status"), "inicio_utc": run.get("startedAt"),
               "fim_utc": run.get("finishedAt"), "origem": "API (coleta nova do Atlas)", "custo_usd": custo(run), "entrada": "ok", "itens": len(itens)}
        (priv / f"{run.get('id')}.json").write_text(json.dumps({**reg, "run": run, "input": entrada, "items": itens}, ensure_ascii=False), encoding="utf-8")
        regs.append(reg)

    # 1. o post
    if "apify/instagram-reel-scraper" in feitos:
        itens = feitos["apify/instagram-reel-scraper"].get("items") or []
    else:
        # transcrição (caso 009, autorizada em 26/10/2026): US$ 0,041 por minuto iniciado; o teto da etapa cobre até ~6 min
        e1 = {"username": [url], "includeSharesCount": True, "includeTranscript": transcricao, "includeDownloadedVideo": False}
        run, itens = tentar("apify~instagram-reel-scraper", e1, min(CAP_TRANSCRICAO if transcricao else MIN_CAP, teto))
        if run:
            gasto += custo(run)
            gravar("apify/instagram-reel-scraper · Instagram Reel Scraper", e1, run, itens)
    autor = next((x.get("ownerUsername") for x in itens if x.get("ownerUsername")), None)
    # 2. comentários, cabendo no teto (reserva o perfil)
    sobra = teto - gasto - RESERVA_PERFIL
    n = min(maximo, int(sobra / PRECO_COMENTARIO))
    if n >= 50 and sobra >= MIN_CAP and "datadoping/instagram-comments-and-replies-scraper" not in feitos:
        # mesma entrada do caso 007 (max_replies 20 com scrape_replies falso: o ator não aceita 0)
        e2 = {"code_or_id_or_url": [url], "sort_by": "popular", "max_comments": n, "scrape_replies": False, "max_replies": 20}
        run, itens = tentar("datadoping~instagram-comments-and-replies-scraper", e2, round(sobra, 2))
        if run:
            gasto += custo(run)
            gravar("datadoping/instagram-comments-and-replies-scraper · Instagram Comments", e2, run, itens)
    # 3. seguidores do autor
    perfil = None
    if autor and teto - gasto >= MIN_CAP:
        e3 = {"usernames": [autor]}
        run, itens = tentar("apify~instagram-profile-scraper", e3, round(min(MIN_CAP, teto - gasto), 2))
        run = run or {}
        gasto += custo(run)
        x = next((i for i in itens if i.get("username") or i.get("followersCount") is not None), {})
        perfil = {"usuario": x.get("username") or autor, "seguidores": x.get("followersCount"), "verificado": x.get("verified"), "nome": x.get("fullName"),
                  "privado": x.get("private"), "lido_em_utc": now_utc(), "run": run.get("id"), "custo_usd": custo(run), "ator": "apify/instagram-profile-scraper"}
        (priv.parent / "perfil_instagram.json").write_text(json.dumps(perfil, ensure_ascii=False, indent=1), encoding="utf-8")
        regs.append({"run_id": run.get("id"), "ator": perfil["ator"], "status": run.get("status"), "inicio_utc": run.get("startedAt"),
                     "custo_usd": custo(run), "itens": len(itens), "arquivo": "perfil_instagram.json"})
    man = {"caso": caso, "coletado_em_utc": now_utc(), "url": url, "teto_usd": teto, "gasto_usd": round(gasto, 4), "comentarios_pedidos": maximo,
           "runs": regs, "perfil_lido": perfil is not None and perfil.get("seguidores") is not None, "erros": erros}
    (priv / "manifesto_coleta.json").write_text(json.dumps(man, ensure_ascii=False, indent=1), encoding="utf-8")
    return man


def main(argv=None, executar=None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    caso, url, teto = arg(argv, "--caso"), arg(argv, "--url"), arg(argv, "--teto")
    maximo = int(arg(argv, "--comentarios", "2000"))
    token = os.environ.get("APIFY_TOKEN", "").strip()
    interno = os.environ.get("ODI_INTERNO_DIR")
    if not (caso and url and teto and interno and (token or executar)):
        print("⛔ faltam --caso, --url, --teto, ODI_INTERNO_DIR ou APIFY_TOKEN (o teto é obrigatório)")
        return 1
    url = url.split("?")[0]
    if not re.match(r"https://www\.instagram\.com/(reel|p)/[\w-]+/?$", url):
        print("⛔ URL de post do Instagram inválida")
        return 1
    executar = executar or (lambda ator, pl, cap: run_actor(token, ator, pl, cap))
    man = coletar(caso, url, float(teto), maximo, Path(interno) / f"casos/{caso}/apify", executar, "--transcricao" in argv)
    print(f"caso {caso}: {len(man['runs'])} execuções · itens {[r['itens'] for r in man['runs']]} · perfil lido: {man['perfil_lido']} · dentro do teto: {man['gasto_usd'] <= man['teto_usd']}")
    for e in man["erros"]:
        print("⛔ " + e)
    return 0 if man["runs"] and not man["erros"] and all(r["status"] == "SUCCEEDED" for r in man["runs"]) else 1


if __name__ == "__main__":
    raise SystemExit(main())
