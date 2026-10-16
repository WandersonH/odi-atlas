#!/usr/bin/env python3
"""Caderno 05 (Buscas) — 5 primeiros do Google Notícias por DIA e candidato, para o filtro de período da página.

Para cada dia D: busca no RSS público do Google Notícias "termo after:D-1 before:D+1" e guarda, na ordem do próprio
Google Notícias, os 5 primeiros itens cuja data de publicação (horário de Brasília) cai em D.
Reconstituição retroativa: a ordem é a que o Google Notícias devolve no momento da coleta para aquele dia, não
necessariamente a que um leitor viu no próprio dia. Dias já fechados não são recoletados; hoje e ontem são refeitos a cada execução.

Também guarda o UNIVERSO de cada dia (todos os itens que o feed devolve publicados naquele dia; o feed devolve no máximo
100 por busca) em data/trends/noticias/universo.csv.gz, base da nuvem, da rede (Gephi) e do corpus (IRaMuTeQ).

Uso: collect_google_noticias_diario.py [--desde AAAA-MM-DD] [--refazer]   (padrão: só ontem e hoje; --refazer recoleta dias fechados)
Saídas: data/trends/google_noticias_diario.json · data/trends/noticias/universo.csv.gz
"""
from __future__ import annotations

import csv
import datetime as dt
import gzip
import json
import sys
import time
import urllib.parse
from pathlib import Path
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).resolve().parent))
from collect_google_busca import RSS, parse_rss  # noqa: E402
from net import now_utc, open_url, read_body  # noqa: E402

BRT = ZoneInfo("America/Sao_Paulo")
UCOLS = ["dia", "candidate_id", "posicao", "titulo", "veiculo", "dominio", "link", "data_publicacao", "coletado_em"]
LIMITE_FEED = 100
METODO = ("Google Notícias (RSS público de busca, pt-BR/BR). Para cada dia, os 5 primeiros itens na ordem do Google Notícias "
          "publicados naquele dia (horário de Brasília), buscando o nome do candidato com os operadores after:/before:. "
          "Dias anteriores a 16/10/2026 são reconstituição retroativa: a ordem é a que o Google Notícias devolveu na data da "
          "coleta, não necessariamente a vista pelos leitores no próprio dia. Só notícias indexadas pelo Google Notícias.")


def do_dia(itens: list[dict], dia: str, n: int) -> list[dict]:
    out = []
    for it in itens:
        p = it.get("data_publicacao")
        if not p:
            continue
        local = dt.datetime.strptime(p, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=dt.timezone.utc).astimezone(BRT)
        if local.date().isoformat() == dia:
            out.append({"posicao": len(out) + 1, **{k: it[k] for k in ("titulo", "link", "veiculo", "dominio", "data_publicacao")}})
        if len(out) == n:
            break
    return out


def buscar(q: str, dia: dt.date) -> list[dict]:
    qq = f"{q} after:{(dia - dt.timedelta(days=1)).isoformat()} before:{(dia + dt.timedelta(days=1)).isoformat()}"
    url = f"{RSS}?{urllib.parse.urlencode({'q': qq, 'hl': 'pt-BR', 'gl': 'BR', 'ceid': 'BR:pt-419'})}"
    with open_url(url, timeout=40) as r:
        return parse_rss(read_body(r))


def main(argv=None, buscar_fn=buscar, hoje: dt.date | None = None) -> int:
    argv = list(argv or [])
    root = Path(".")
    cfg = json.loads((root / "data/config/google_busca.json").read_text(encoding="utf-8"))
    p = root / "data/trends/google_noticias_diario.json"
    d = json.loads(p.read_text(encoding="utf-8")) if p.exists() else {"dias": {}}
    hoje = hoje or dt.datetime.now(BRT).date()
    desde = dt.date.fromisoformat(argv[argv.index("--desde") + 1]) if "--desde" in argv else hoje - dt.timedelta(days=1)
    up = root / "data/trends/noticias/universo.csv.gz"
    univ = {}
    if up.exists():
        with gzip.open(up, "rt", encoding="utf-8") as f:
            for r in csv.DictReader(f, delimiter=";"):
                univ.setdefault((r["dia"], r["candidate_id"]), []).append(r)
    erros, feitos, sat = {}, 0, {}
    refazer_tudo = "--refazer" in argv
    dia = desde
    while dia <= hoje:
        k = dia.isoformat()
        refazer = dia >= hoje - dt.timedelta(days=1)
        if refazer or refazer_tudo or k not in d["dias"] or any((k, cid) not in univ for cid in cfg["consultas"]):
            reg = {}
            for cid, c in cfg["consultas"].items():
                try:
                    brutos = buscar_fn(c["q"], dia)
                    todos = do_dia(brutos, k, LIMITE_FEED)
                    reg[cid] = todos[:cfg["primeiros"]]
                    agora = now_utc()
                    univ[(k, cid)] = [{"dia": k, "candidate_id": cid, "coletado_em": agora, **x} for x in todos]
                    sat.setdefault(k, {})[cid] = len(brutos) >= LIMITE_FEED
                except Exception as e:  # noqa: BLE001
                    erros[f"{k} {c['nome']}"] = f"{type(e).__name__} {getattr(e, 'code', '')}".strip()
                time.sleep(0.5 if buscar_fn is buscar else 0)
            if reg:
                d["dias"][k] = {"coletado_em_utc": now_utc(), "fechado": not refazer, "candidatos": reg,
                                "universo": {cid: len(univ.get((k, cid), [])) for cid in reg}, "feed_no_limite": sat.get(k, {})}
                feitos += 1
        dia += dt.timedelta(days=1)
    d.update({"schema_version": 1, "atualizado_em_utc": now_utc(), "metodo": METODO,
              "candidatos": {cid: c["nome"] for cid, c in cfg["consultas"].items()},
              "dias": dict(sorted(d["dias"].items())), "erros_ultima_execucao": erros})
    p.write_text(json.dumps(d, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    up.parent.mkdir(parents=True, exist_ok=True)
    with gzip.open(up, "wt", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, UCOLS, delimiter=";", lineterminator="\n", extrasaction="ignore")
        w.writeheader()
        for key in sorted(univ):
            w.writerows(univ[key])
    vazios = sum(1 for v in d["dias"].values() for x in v["candidatos"].values() if not x)
    print(f"universo: {sum(len(v) for v in univ.values())} itens")
    print(f"google notícias diário: {feitos} dias coletados, {len(d['dias'])} no arquivo, {vazios} listas vazias, {len(erros)} erros")
    return 0 if not erros or feitos else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
