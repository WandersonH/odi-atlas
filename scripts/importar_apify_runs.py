#!/usr/bin/env python3
"""Importa execuções JÁ FEITAS no Apify (só leitura: nenhuma execução nova, nenhum custo de ator) para o repositório privado.

Pedido do responsável (22/10/2026, 01h05): caso 006 — coletas do X feitas à mão no Apify em 23 e 24/09/2026
(atores xquik: "X (Twitter) Engagement Scraper" e "X (Twitter) Tweet Scraper"), sobre o post de Marco Rubio que anuncia a
classificação do PCC e do CV como organizações terroristas (x.com/SecRubio/status/2060119225176404134).

Lê, na conta indicada (padrão APIFY_TOKEN = conta 1):
  GET /v2/actor-runs (lista do usuário, mais recentes primeiro, paginada) → filtra por data de início e por nome do ator;
  GET /v2/acts/{id} (nome do ator); GET /v2/key-value-stores/{kv}/records/INPUT (entrada usada);
  GET /v2/datasets/{ds}/items (resultados). O Apify apaga armazenamentos sem nome depois de alguns dias (retenção do plano):
  dataset ou entrada já apagados ficam registrados como ⛔, nunca estimados.

Saída privada: ODI_INTERNO_DIR/casos/<caso>/apify/<run_id>.json (metadados, entrada e itens brutos) e manifesto.json.
Saída pública: data/casos/<caso>/importacao_apify.json (só metadados das execuções: ator, datas, contagens; sem texto nem autor).
Uso: python scripts/importar_apify_runs.py --caso 006 --de 2026-09-23 --ate 2026-09-24 [--ator xquik] [--segredo APIFY_TOKEN] [--url <código do post>]
"""
from __future__ import annotations

import json
import os
import sys
import urllib.error
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from collect_meta_apify import api  # noqa: E402
from net import now_utc  # noqa: E402


def arg(argv: list[str], nome: str, padrao: str | None = None) -> str | None:
    return argv[argv.index(nome) + 1] if nome in argv else padrao


def listar_runs(token: str, de: str, ate: str, chamar=api) -> list[dict]:
    """Runs com início entre `de` e `ate` (datas UTC, inclusive). Para de paginar quando passa de `de`."""
    out, offset = [], 0
    while True:
        d = (chamar("GET", f"/actor-runs?desc=1&limit=1000&offset={offset}", token) or {}).get("data") or {}
        itens = d.get("items") or []
        for r in itens:
            dia = (r.get("startedAt") or "")[:10]
            if de <= dia <= ate:
                out.append(r)
        if not itens or (itens[-1].get("startedAt") or "")[:10] < de or len(itens) < 1000:
            return out
        offset += len(itens)


def paginas(chamar, token: str, ds: str, n: int = 500, tentativas: int = 3) -> list:
    """Itens do dataset em páginas, com nova tentativa por página (a leitura de uma vez falhou com IncompleteRead nos casos 008 e 009)."""
    out, off = [], 0
    while True:
        for t in range(tentativas):
            try:
                pg = chamar("GET", f"/datasets/{ds}/items?clean=true&format=json&limit={n}&offset={off}", token) or []
                break
            except urllib.error.HTTPError:
                raise
            except Exception:  # noqa: BLE001 — IncompleteRead, conexão interrompida
                if t == tentativas - 1:
                    raise
        out.extend(pg)
        if len(pg) < n:
            return out
        off += n


def importar(token: str, caso: str, de: str, ate: str, filtro_ator: str, priv: Path, pub: Path, chamar=api, filtro_url: str = "") -> dict:
    agora = now_utc()
    nomes, regs = {}, []
    runs = listar_runs(token, de, ate, chamar)
    for r in runs:
        aid = r.get("actId")
        if aid not in nomes:
            try:
                a = (chamar("GET", f"/acts/{aid}", token) or {}).get("data") or {}
                nomes[aid] = f"{a.get('username', '?')}/{a.get('name', '?')}" + (f" · {a['title']}" if a.get("title") else "")
            except Exception as e:  # noqa: BLE001
                nomes[aid] = f"? ({type(e).__name__} {getattr(e, 'code', '')})"
        ator = nomes[aid]
        if filtro_ator and filtro_ator.lower() not in ator.lower():
            continue
        reg = {"run_id": r.get("id"), "ator": ator, "status": r.get("status"), "inicio_utc": r.get("startedAt"), "fim_utc": r.get("finishedAt"),
               "origem": (r.get("meta") or {}).get("origin"), "custo_usd": r.get("usageTotalUsd")}
        entrada, itens = None, None
        try:
            entrada = chamar("GET", f"/key-value-stores/{r.get('defaultKeyValueStoreId')}/records/INPUT", token)
            reg["entrada"] = "ok"
        except urllib.error.HTTPError as e:
            reg["entrada"] = f"⛔ HTTP {e.code} (apagada pela retenção do Apify ou inexistente)"
        except Exception as e:  # noqa: BLE001
            reg["entrada"] = f"⛔ {type(e).__name__}"
        # 26/10/2026: caso 009 e 009b usam o mesmo ator no mesmo dia; --url separa pelo código do post na entrada
        if filtro_url and filtro_url not in json.dumps(entrada or {}, ensure_ascii=False):
            continue
        try:
            itens = paginas(chamar, token, r.get("defaultDatasetId"))
            reg["itens"] = len(itens)
        except urllib.error.HTTPError as e:
            reg["itens"] = None
            reg["dataset"] = f"⛔ HTTP {e.code} (apagado pela retenção do Apify ou inexistente)"
        except Exception as e:  # noqa: BLE001
            reg["itens"] = None
            reg["dataset"] = f"⛔ {type(e).__name__}"
        priv.mkdir(parents=True, exist_ok=True)
        (priv / f"{r.get('id')}.json").write_text(json.dumps({**reg, "run": r, "input": entrada, "items": itens}, ensure_ascii=False), encoding="utf-8")
        regs.append(reg)
        print(f"{reg['inicio_utc']} {ator} · {reg['status']} · origem {reg['origem']} · entrada {reg['entrada']} · itens {reg['itens']} {reg.get('dataset', '')}")
    man = {"caso": caso, "importado_em_utc": agora, "janela": [de, ate], "filtro_ator": filtro_ator, "runs_na_janela": len(runs),
           "runs_importados": len(regs), "com_itens": sum(1 for x in regs if x.get("itens")), "itens_total": sum(x.get("itens") or 0 for x in regs),
           "runs": sorted(regs, key=lambda x: x["inicio_utc"] or "")}
    (priv / "manifesto.json").write_text(json.dumps(man, ensure_ascii=False, indent=1), encoding="utf-8")
    pub.mkdir(parents=True, exist_ok=True)
    (pub / "importacao_apify.json").write_text(json.dumps(man, ensure_ascii=False, indent=1), encoding="utf-8")
    return man


def main(argv=None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    caso, de, ate = arg(argv, "--caso", "006"), arg(argv, "--de"), arg(argv, "--ate")
    segredo = arg(argv, "--segredo", "APIFY_TOKEN")
    token = os.environ.get(segredo, "").strip()
    interno = os.environ.get("ODI_INTERNO_DIR")
    if not (de and ate):
        print("⛔ informe --de e --ate (AAAA-MM-DD)")
        return 1
    if not token or not interno:
        print(f"⛔ falta {segredo if not token else 'ODI_INTERNO_DIR'}")
        return 1
    man = importar(token, caso, de, ate, arg(argv, "--ator", "") or "", Path(interno) / f"casos/{caso}/apify", Path("data/casos") / caso,
                   filtro_url=arg(argv, "--url", "") or "")
    print(f"janela {de}..{ate}: {man['runs_na_janela']} runs; importados {man['runs_importados']}; com itens {man['com_itens']}; itens {man['itens_total']}")
    return 0 if man["runs_importados"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
