#!/usr/bin/env python3
"""Cofre das coletas da Apify: confere se cada execução das contas está guardada e guarda o que faltar, antes de a Apify apagar.

Pedido do responsável (02/11/2026, 00h51): "verifique se todas as coletas feitas na conta estão armazenadas no banco, pois algumas
vão vencer os 30 dias de armazenamento da Apify".
Para cada conta (segredos APIFY_TOKEN, APIFY_TOKEN_2 … APIFY_TOKEN_15, APIFY_TOKEN_FL; o token nunca é impresso):
  1. lista as execuções dos últimos DIAS dias (GET /actor-runs, mais recentes primeiro);
  2. marca se o id da execução aparece em algum manifesto do repositório público (data/**/manifest*.json) — é como cada coleta
     registra o que rodou;
  3. marca se o conjunto de dados já está no cofre privado (ODI_INTERNO_DIR/apify_cofre/indice.csv);
  4. com --guardar, baixa os itens de toda execução ainda fora do cofre (GET /datasets/<id>/items) para
     apify_cofre/<conta>/<data>_<ator>_<execução>.jsonl.gz, sem alterar nada do que já existe (nunca apaga nem sobrescreve).
Saída: apify_cofre/relatorio.json e indice.csv no privado (ids de execução, ator, data, nº de itens, situação). Não registra
custo. Sem --guardar, só confere. Uso: python scripts/apify_cofre.py [--guardar] [--dias 40] [--max 250]
"""
from __future__ import annotations

import csv
import datetime as dt
import gzip
import json
import os
import re
import sys
import urllib.error
import urllib.request
from pathlib import Path

API = "https://api.apify.com/v2"
CONTAS = ["APIFY_TOKEN"] + [f"APIFY_TOKEN_{i}" for i in range(2, 16)] + ["APIFY_TOKEN_FL"]
RETENCAO_DIAS = 30  # informado pelo responsável
ROOT = Path(__file__).resolve().parents[1]


def get(path: str, token: str, timeout: int = 120):
    req = urllib.request.Request(API + path, headers={"Authorization": f"Bearer {token}"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8"))


def execucoes(token: str, desde: dt.datetime) -> list[dict]:
    out, off = [], 0
    while True:
        d = get(f"/actor-runs?desc=1&limit=1000&offset={off}", token)["data"]
        itens = d.get("items") or []
        for r in itens:
            t = dt.datetime.fromisoformat(str(r.get("startedAt")).replace("Z", "+00:00"))
            if t < desde:
                return out
            out.append(r)
        if len(itens) < 1000:
            return out
        off += 1000


def ids_nos_manifestos() -> set[str]:
    ids = set()
    for f in list((ROOT / "data").rglob("manifest*.json")):
        try:
            ids |= set(re.findall(r'"([A-Za-z0-9]{17})"', f.read_text(encoding="utf-8", errors="ignore")))
        except OSError:
            pass
    return ids


def nome_ator(token: str, act_id: str, cache: dict) -> str:
    if act_id not in cache:
        try:
            a = get(f"/acts/{act_id}", token)["data"]
            cache[act_id] = f"{a.get('username')}~{a.get('name')}"
        except Exception:  # noqa: BLE001
            cache[act_id] = act_id
    return cache[act_id]


def main(argv: list[str]) -> int:
    guardar = "--guardar" in argv
    dias = int(argv[argv.index("--dias") + 1]) if "--dias" in argv else 40
    maximo = int(argv[argv.index("--max") + 1]) if "--max" in argv else 250  # por execução do workflow: cada lote vira um commit
    baixadas = 0
    priv = Path(os.environ.get("ODI_INTERNO_DIR", "")) / "apify_cofre"
    if not os.environ.get("ODI_INTERNO_DIR"):
        print("⛔ ODI_INTERNO_DIR ausente: o cofre fica só no repositório privado")
        return 1
    priv.mkdir(parents=True, exist_ok=True)
    indice_arq = priv / "indice.csv"
    campos = ["conta", "execucao", "dataset", "ator", "inicio_utc", "status", "itens", "no_manifesto", "arquivo", "guardado_em_utc"]
    indice = {}
    if indice_arq.exists():
        for r in csv.DictReader(open(indice_arq, encoding="utf-8")):
            indice[r["execucao"]] = r
    agora = dt.datetime.now(dt.timezone.utc)
    desde = agora - dt.timedelta(days=dias)
    conhecidos = ids_nos_manifestos()
    rel = {"gerado_em_utc": agora.strftime("%Y-%m-%dT%H:%M:%SZ"), "dias_conferidos": dias, "retencao_informada_dias": RETENCAO_DIAS,
           "modo": "guardar" if guardar else "só conferir", "contas": [], "metodo": " ".join(__doc__.split("Saída:")[0].split()[2:])}
    atores: dict = {}
    for conta in CONTAS:
        tok = os.environ.get(conta, "").strip()
        if not tok:
            rel["contas"].append({"conta": conta, "situacao": "segredo ausente neste workflow"})
            continue
        try:
            runs = sorted(execucoes(tok, desde), key=lambda r: str(r.get("startedAt")))  # as mais antigas (mais perto de vencer) primeiro
        except Exception as e:  # noqa: BLE001 — a mensagem pode ter a URL, nunca o token (vai no cabeçalho)
            rel["contas"].append({"conta": conta, "situacao": f"⛔ erro ao listar: {type(e).__name__} {getattr(e, 'code', '')}"})
            continue
        c = {"conta": conta, "execucoes": len(runs), "itens": 0, "faltam_no_cofre": 0, "com_itens": 0, "no_manifesto": 0, "ja_no_cofre": 0, "guardadas_agora": 0,
             "sem_itens": 0, "falhas": [], "vencem_em_7_dias_fora_do_cofre": 0}
        for r in runs:
            rid, ds = r["id"], r.get("defaultDatasetId")
            ini = str(r.get("startedAt"))
            idade = (agora - dt.datetime.fromisoformat(ini.replace("Z", "+00:00"))).days
            n = None
            try:
                n = get(f"/datasets/{ds}", tok)["data"].get("itemCount") if ds else 0
            except Exception:  # noqa: BLE001
                n = None
            if not n:
                c["sem_itens"] += 1
                continue
            c["com_itens"] += 1
            c["itens"] += n
            no_man = rid in conhecidos
            c["no_manifesto"] += no_man
            if rid in indice and indice[rid].get("arquivo"):
                c["ja_no_cofre"] += 1
                continue
            if RETENCAO_DIAS - idade <= 7:
                c["vencem_em_7_dias_fora_do_cofre"] += 1
            if not guardar or baixadas >= maximo:
                c["faltam_no_cofre"] += 1
                continue
            ator = nome_ator(tok, r.get("actId", ""), atores)
            nome = f"{ini[:10]}_{re.sub(r'[^A-Za-z0-9_-]', '-', ator)[:60]}_{rid}.jsonl.gz"
            dest = priv / conta / nome
            if dest.exists():
                c["ja_no_cofre"] += 1
            else:
                try:
                    dest.parent.mkdir(parents=True, exist_ok=True)
                    tmp = dest.with_suffix(".parcial")
                    total, off = 0, 0
                    with gzip.open(tmp, "wt", encoding="utf-8") as fh:
                        while True:
                            req = urllib.request.Request(f"{API}/datasets/{ds}/items?format=json&clean=false&offset={off}&limit=5000",
                                                         headers={"Authorization": f"Bearer {tok}"})
                            with urllib.request.urlopen(req, timeout=300) as resp:
                                lote = json.loads(resp.read().decode("utf-8"))
                            for it in lote:
                                fh.write(json.dumps(it, ensure_ascii=False) + "\n")
                            total += len(lote)
                            off += len(lote)
                            if len(lote) < 5000:
                                break
                    tmp.rename(dest)
                    c["guardadas_agora"] += 1
                    baixadas += 1
                except Exception as e:  # noqa: BLE001
                    c["falhas"].append(f"{rid}: {type(e).__name__} {getattr(e, 'code', '')}")
                    continue
            indice[rid] = {"conta": conta, "execucao": rid, "dataset": ds, "ator": ator, "inicio_utc": ini, "status": r.get("status"),
                           "itens": n, "no_manifesto": "sim" if no_man else "não", "arquivo": f"apify_cofre/{conta}/{nome}",
                           "guardado_em_utc": agora.strftime("%Y-%m-%dT%H:%M:%SZ")}
        rel["contas"].append(c)
    with open(indice_arq, "w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=campos)
        w.writeheader()
        for r in sorted(indice.values(), key=lambda r: r["inicio_utc"]):
            w.writerow({k: r.get(k, "") for k in campos})
    tot = {k: sum(c.get(k, 0) for c in rel["contas"] if isinstance(c.get(k), int)) for k in
           ("execucoes", "itens", "com_itens", "no_manifesto", "ja_no_cofre", "guardadas_agora", "faltam_no_cofre", "sem_itens", "vencem_em_7_dias_fora_do_cofre")}
    rel["total"] = tot
    (priv / "relatorio.json").write_text(json.dumps(rel, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"cofre Apify ({rel['modo']}, {dias} dias): {tot}")
    for c in rel["contas"]:
        if "execucoes" in c:
            print(f"  {c['conta']}: {c['execucoes']} execuções, {c['com_itens']} com itens, {c['no_manifesto']} no manifesto, "
                  f"{c['ja_no_cofre']} já no cofre, {c['guardadas_agora']} guardadas agora, {len(c['falhas'])} falhas")
        else:
            print(f"  {c['conta']}: {c['situacao']}")
    return 1 if any(c.get("falhas") for c in rel["contas"]) else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
