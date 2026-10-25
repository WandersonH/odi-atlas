#!/usr/bin/env python3
"""Resultado do 2º turno para Presidente (25/10/2026), pela divulgação oficial do TSE (resultados.tse.jus.br), Brasil e UFs.

Pedido do responsável (25/10/2026, 16h24): "preciso de uma página para receber os dados do 2º turno do TSE".
- Descobre o código da eleição em /oficial/comum/config/ele-c.json (pleito de 2026, turno 2, eleição federal), ou usa o
  código fixado em data/config/resultados_2t.json → "eleicao".
- Lê os arquivos simplificados (os mesmos do app Resultados): br e cada UF, cargo 0001 (Presidente).
- Guarda cada leitura (série da apuração: % de seções totalizadas × votos) e o último retrato.
Saída pública (dado público do TSE, só agregados): data/tse/segundo_turno/resultado.json e leituras/AAAAMMDD-HHMM.json.
A totalização oficial por município/zona (Dados Abertos) sai dias depois; aí entram mapa e alienação (collect_alienacao --turno 2).
"""
from __future__ import annotations

import json
import sys
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from net import now_utc  # noqa: E402

BASE = "https://resultados.tse.jus.br/oficial"
UFS = "ac al am ap ba ce df es go ma mg ms mt pa pb pe pi pr rj rn ro rr rs sc se sp to zz".split()
UA = {"User-Agent": "Mozilla/5.0 (ODI Atlas, pesquisa acadêmica PPGCOM/UNIP)", "Accept": "application/json"}


def get(url: str, timeout: int = 30) -> dict:
    with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8"))


def descobrir(cfg: dict) -> tuple[str, str]:
    """(pasta do pleito, código da eleição) do 2º turno de 2026, federal."""
    if cfg.get("eleicao") and cfg.get("pleito"):
        return cfg["pleito"], str(cfg["eleicao"])
    d = get(f"{BASE}/comum/config/ele-c.json")
    Path("data/tse/segundo_turno").mkdir(parents=True, exist_ok=True)
    Path("data/tse/segundo_turno/config_tse.json").write_text(json.dumps(d, ensure_ascii=False, indent=1), encoding="utf-8")  # conferência
    achados = []

    def walk(o, pleito=None):
        if isinstance(o, dict):
            if str(o.get("cd", "")).startswith("ele20"):
                pleito = o["cd"]
            if pleito and "2026" in pleito and str(o.get("t")) == "2" and o.get("cd") and str(o["cd"]).isdigit():
                achados.append((pleito, str(o["cd"]), str(o.get("nm") or o.get("ds") or "")))
            for v in o.values():
                walk(v, pleito)
        elif isinstance(o, list):
            for v in o:
                walk(v, pleito)
    walk(d)
    fed = [a for a in achados if "federal" in a[2].lower()] or achados
    if not fed:
        raise RuntimeError("2º turno de 2026 não encontrado no ele-c.json: " + json.dumps(d, ensure_ascii=False)[:600])
    return fed[0][0], fed[0][1]


def num(x) -> int | None:
    try:
        return int(str(x).replace(".", "").replace(",", ""))
    except (TypeError, ValueError):
        return None


def pct(x) -> float | None:
    try:
        return float(str(x).replace(",", "."))
    except (TypeError, ValueError):
        return None


def resumo(d: dict) -> dict:
    """Campos do arquivo simplificado (mesmos nomes de 2022; ausentes ficam None)."""
    cands = []
    for c in d.get("cand") or []:
        cands.append({"numero": str(c.get("n")), "nome": c.get("nm"), "votos": num(c.get("vap")), "pct": pct(c.get("pvap")),
                      "eleito": str(c.get("e")).lower() in ("s", "true", "1"), "situacao": c.get("st") or c.get("dvt")})
    return {"data_hora_tse": f"{d.get('dg', '')} {d.get('hg', '')}".strip() or None, "pct_secoes_totalizadas": pct(d.get("pst")),
            "secoes_totalizadas": num(d.get("st")), "secoes": num(d.get("s")), "eleitores": num(d.get("e")),
            "comparecimento": num(d.get("c")), "pct_comparecimento": pct(d.get("pc")), "abstencao": num(d.get("a")), "pct_abstencao": pct(d.get("pa")),
            "validos": num(d.get("vv")), "brancos": num(d.get("vb")), "pct_brancos": pct(d.get("pvb")), "nulos": num(d.get("tvn") or d.get("vn")),
            "pct_nulos": pct(d.get("ptvn") or d.get("pvn")), "matematicamente_definido": d.get("md"), "candidatos": sorted(cands, key=lambda c: c["numero"] != "13")}


def main(argv=None) -> int:
    root = Path(".")
    cp = root / "data/config/resultados_2t.json"
    cfg = json.loads(cp.read_text(encoding="utf-8")) if cp.exists() else {}
    pasta = root / "data/tse/segundo_turno"
    (pasta / "leituras").mkdir(parents=True, exist_ok=True)
    agora = now_utc()
    try:
        pleito, ele = descobrir(cfg)
    except Exception as e:  # noqa: BLE001
        print(f"⛔ descoberta da eleição: {type(e).__name__}: {str(e)[:700]}")
        return 1
    url = lambda ab: f"{BASE}/{pleito}/{ele}/dados-simplificados/{ab}/{ab}-c0001-e{int(ele):06d}-r.json"  # noqa: E731
    out = {"lido_em_utc": agora, "fonte": f"{BASE}/{pleito}/{ele}/ (divulgação oficial do TSE, arquivos simplificados, cargo Presidente)",
           "pleito": pleito, "eleicao": ele, "erros": {}}
    try:
        br_raw = get(url("br"))
        out["brasil"] = resumo(br_raw)
        if "--sonda" in (argv or sys.argv[1:]):
            print("chaves br:", sorted(br_raw.keys()), "· 1º candidato:", json.dumps((br_raw.get("cand") or [{}])[0], ensure_ascii=False)[:300])
    except Exception as e:  # noqa: BLE001
        out["erros"]["br"] = f"{type(e).__name__}: {str(e)[:200]}"
    out["ufs"] = {}
    for uf in UFS:
        try:
            out["ufs"][uf.upper()] = resumo(get(url(uf)))
        except Exception as e:  # noqa: BLE001
            out["erros"][uf] = f"{type(e).__name__}"
    if "brasil" not in out:
        print(f"⛔ sem o arquivo do Brasil: {out['erros'].get('br')} · {url('br')}")
        (pasta / "ultima_tentativa.json").write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
        return 1
    stamp = agora[:16].replace("-", "").replace(":", "").replace("T", "-")
    (pasta / "leituras" / f"{stamp}.json").write_text(json.dumps(out, ensure_ascii=False), encoding="utf-8")
    serie = []
    for f in sorted((pasta / "leituras").glob("*.json")):
        r = json.loads(f.read_text(encoding="utf-8"))
        b = r.get("brasil") or {}
        serie.append({"t": r["lido_em_utc"], "tse": b.get("data_hora_tse"), "pst": b.get("pct_secoes_totalizadas"),
                      "c": {c["numero"]: c["pct"] for c in b.get("candidatos", [])}})
    out["serie_apuracao"] = serie
    (pasta / "resultado.json").write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    b = out["brasil"]
    print(f"2º turno: {b['pct_secoes_totalizadas']}% das seções · " + " · ".join(f"{c['nome']} {c['pct']}%" for c in b["candidatos"])
          + f" · UFs lidas {len(out['ufs'])}/27 · erros {len(out['erros'])}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
