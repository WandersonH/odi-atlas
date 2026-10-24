#!/usr/bin/env python3
"""Saúde da coleta: para cada série que o Atlas atualiza sozinho, quando foi o último DADO REAL (não a última tentativa).

Pedido do responsável (23/10/2026, 13h13): "como posso acreditar em vc que tudo tá sendo coletado". A resposta não pode
depender da palavra de quem programou: este script lê só os arquivos publicados (CSVs de seguidores e manifestos de
cada coleta, inclusive o histórico manifesto-*.json da mesma pasta) e marca ⛔ o que passou do prazo de
data/config/saude_coleta.json. Saída: data/saude_coleta.json (lida pela página). Com --falhar, sai com código 1 se houver
série atrasada — o workflow fica vermelho e o GitHub avisa o responsável por e-mail.
"""
from __future__ import annotations

import csv
import datetime as dt
import json
import sys
from pathlib import Path

OK = ("ok", "parcial")


def instante(s: str | None) -> dt.datetime | None:
    if not s:
        return None
    s = str(s).strip()
    try:
        if len(s) == 10:
            return dt.datetime.fromisoformat(s).replace(tzinfo=dt.timezone.utc)  # só a data: início do dia (UTC), nunca no futuro
        return dt.datetime.fromisoformat(s.replace("Z", "+00:00")).astimezone(dt.timezone.utc)
    except ValueError:
        return None


def ler_manifesto(p: Path) -> tuple[dt.datetime | None, str]:
    try:
        m = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None, "⛔ ilegível"
    t = instante(m.get("run_started_utc") or m.get("coletado_em_utc"))
    st = m.get("status", m.get("status_coleta"))
    return t, "ok" if st is None else str(st)


def avaliar_manifesto(root: Path, s: dict) -> dict:
    p = root / s["arquivo"]
    if not p.exists():
        return {"ultima_execucao": None, "status_ultima": "⛔ arquivo não existe", "ultimo_dado": None}
    t, st = ler_manifesto(p)
    sucessos = [t] if t and st.lower().startswith(OK) else []
    for h in p.parent.glob("manifesto-*.json"):  # histórico da mesma pasta
        th, sh = ler_manifesto(h)
        if th and sh.lower().startswith(OK):
            sucessos.append(th)
    return {"ultima_execucao": t, "status_ultima": st, "ultimo_dado": max(sucessos) if sucessos else None}


def avaliar_csv(root: Path, s: dict) -> dict:
    p = root / s["arquivo"]
    if not p.exists():
        return {"ultima_execucao": None, "status_ultima": "⛔ arquivo não existe", "ultimo_dado": None}
    datas = [instante(r.get(s["coluna"])) for r in csv.DictReader(open(p, encoding="utf-8"), delimiter=";")]
    datas = [d for d in datas if d]
    man = p.parent / p.name.replace("_latest.csv", "_manifesto_latest.json").replace("latest.csv", "manifesto_latest.json")
    t, st = ler_manifesto(man) if man.exists() else (None, "sem manifesto")
    return {"ultima_execucao": t, "status_ultima": st, "ultimo_dado": max(datas) if datas else None,
            "perfis": len(datas), "perfis_lidos_no_ultimo_dia": sum(1 for d in datas if datas and d.date() == max(datas).date())}


def main(argv=None) -> int:
    argv = sys.argv[1:] if argv is None else list(argv)
    root = Path(".")
    cfg = json.loads((root / "data/config/saude_coleta.json").read_text(encoding="utf-8"))
    agora = dt.datetime.now(dt.timezone.utc)
    if "--agora" in argv:
        agora = instante(argv[argv.index("--agora") + 1])
    out, atrasadas = [], []
    for s in cfg["series"]:
        r = avaliar_csv(root, s) if s["tipo"] == "csv" else avaliar_manifesto(root, s)
        horas = round((agora - r["ultimo_dado"]).total_seconds() / 3600, 1) if r["ultimo_dado"] else None
        em_dia = horas is not None and horas <= s["max_horas"]
        if not em_dia:
            atrasadas.append(s["nome"])
        iso = lambda d: d.strftime("%Y-%m-%dT%H:%M:%SZ") if d else None  # noqa: E731
        out.append({"nome": s["nome"], "pagina": s["pagina"], "fonte": s["arquivo"], "max_horas": s["max_horas"],
                    "ultimo_dado": iso(r["ultimo_dado"]), "horas_desde_ultimo_dado": horas,
                    "ultima_execucao": iso(r["ultima_execucao"]), "status_ultima_execucao": r["status_ultima"][:160],
                    **({"perfis_no_arquivo": r["perfis"], "perfis_lidos_no_ultimo_dia": r["perfis_lidos_no_ultimo_dia"]} if "perfis" in r else {}),
                    "so_data": s["tipo"] == "csv", "situacao": "em dia" if em_dia else "⛔ atrasada"})
    res = {"gerado_em_utc": agora.strftime("%Y-%m-%dT%H:%M:%SZ"), "regra": cfg["nota"], "series": out,
           "em_dia": len(out) - len(atrasadas), "atrasadas": atrasadas}
    (root / "data/saude_coleta.json").write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
    for x in out:
        print(f"{x['situacao']:12s} {x['nome']:32s} último dado {x['ultimo_dado']} ({x['horas_desde_ultimo_dado']} h) · última execução: {x['status_ultima_execucao'][:60]}")
    print(f"{res['em_dia']} de {len(out)} séries em dia")
    return 1 if atrasadas and "--falhar" in argv else 0


if __name__ == "__main__":
    sys.exit(main())
