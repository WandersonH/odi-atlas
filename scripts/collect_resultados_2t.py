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
            if str(o.get("c", "")).startswith("ele20"):
                pleito = o["c"]
            if pleito and "2026" in pleito and str(o.get("t")) == "2" and o.get("cd") and str(o["cd"]).isdigit():
                achados.append((pleito, str(o["cd"]), str(o.get("nm") or o.get("ds") or "")))
            # o config de 18/10 só lista o 1º turno; o 2º vem em "cdt2" (6257 → 6258 na eleição federal)
            if pleito and "2026" in pleito and str(o.get("t")) == "1" and str(o.get("cdt2") or "").isdigit():
                achados.append((pleito, str(o["cdt2"]), str(o.get("nm") or "").replace("1º Turno", "2º Turno")))
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
    """Arquivo de resultado da divulgação de 2026 (dados/<uf>/<uf>-c0001-e<ele>-u.json; estrutura conferida em 25/10/2026,
    17h06, no navegador do responsável): s = seções, e = eleitorado/comparecimento, v = votos, carg[0].agr[].par[].cand[]."""
    S, E, V = d.get("s") or {}, d.get("e") or {}, d.get("v") or {}
    cands = []
    for cg in d.get("carg") or []:
        if str(cg.get("cd")) != "1":
            continue
        for ag in cg.get("agr") or []:
            for pa in ag.get("par") or []:
                for c in pa.get("cand") or []:
                    cands.append({"numero": str(c.get("n")), "nome": c.get("nmu") or c.get("nm"), "votos": num(c.get("vap")), "pct": pct(c.get("pvap")),
                                  "eleito": str(c.get("e")).lower() == "s", "situacao": c.get("st") or c.get("dvt"),
                                  "vice": ((c.get("vs") or [{}])[0]).get("nmu")})
    return {"data_hora_tse": f"{d.get('dg', '')} {d.get('hg', '')}".strip() or None, "pct_secoes_totalizadas": pct(S.get("pst")),
            "secoes_totalizadas": num(S.get("st")), "secoes": num(S.get("ts")), "eleitores": num(E.get("te")),
            "comparecimento": num(E.get("c")), "pct_comparecimento": pct(E.get("pc")), "abstencao": num(E.get("a")), "pct_abstencao": pct(E.get("pa")),
            "validos": num(V.get("vv")), "brancos": num(V.get("vb")), "pct_brancos": pct(V.get("pvb")), "nulos": num(V.get("tvn") or V.get("vn")),
            "pct_nulos": pct(V.get("ptvn")), "matematicamente_definido": str(d.get("md")).lower() == "s", "totalizacao_final": str(d.get("tf")).lower() == "s",
            "candidatos": sorted(cands, key=lambda c: c["numero"] != "13")}


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
    url = lambda ab: f"{BASE}/{pleito}/{ele}/dados/{ab}/{ab}-c0001-e{int(ele):06d}-u.json"  # noqa: E731
    out = {"lido_em_utc": agora, "fonte": f"{BASE}/{pleito}/{ele}/dados/ (divulgação oficial do TSE, cargo Presidente)",
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
    if "--sonda-mun" in (argv or sys.argv[1:]):  # descobre o arquivo por município (pedido de 25/10, 19h43)
        b = f"{BASE}/{pleito}/{ele}/dados/sp/"
        for nome in ("sp-c0001-e006258-u.json", "sp71072-c0001-e006258-u.json", "sp-c0001-e006258-v.json", "sp-e006258-ab.json",
                     "sp-c0001-e006258-ab.json", "sp-c0001-e006258-e.json", "sp-e006258-u.json", "sp71072-c0001-e006258-v.json"):
            try:
                with urllib.request.urlopen(urllib.request.Request(b + nome, headers=UA), timeout=30) as r:
                    raw = r.read()
                dd = json.loads(raw.decode("utf-8"))
                print(f"sonda {nome}: 200 · {len(raw)} bytes · chaves {sorted(dd.keys())[:25]} · {json.dumps(dd, ensure_ascii=False)[:500]}")
            except Exception as e:  # noqa: BLE001
                print(f"sonda {nome}: {type(e).__name__} {getattr(e, 'code', '')}")
        ab = get(b + "sp-e006258-ab.json")
        x = ab["abr"][0]
        print("sonda ab[0] chaves", sorted(x.keys()), "·", json.dumps({k: v for k, v in x.items() if k not in ("s", "e")}, ensure_ascii=False)[:1500])
        print("sonda ab tipos", sorted({a.get("tpabr") for a in ab["abr"]}), "n", len(ab["abr"]))
        cm = get(f"{BASE}/{pleito}/{ele}/config/mun-e{int(ele):06d}-cm.json")
        print("sonda cm: abr", len(cm.get("abr", [])), "· 1º mun", json.dumps(cm["abr"][0]["mu"][0], ensure_ascii=False))
        return 0
    if "brasil" not in out and "--sonda" in (argv or sys.argv[1:]):  # confere o caminho e a leitura com o 1º turno (6257)
        try:
            t1 = get(f"{BASE}/{pleito}/6257/dados/br/br-c0001-e006257-u.json")
            r1 = resumo(t1)
            print("conferência com o 1º turno (6257): chaves", sorted(t1.keys())[:40], "· resumo", json.dumps({k: r1[k] for k in ("pct_secoes_totalizadas", "eleitores", "pct_abstencao")}, ensure_ascii=False),
                  "· 2 primeiros", json.dumps(r1["candidatos"][:2], ensure_ascii=False)[:400])
        except Exception as e:  # noqa: BLE001
            print(f"conferência com o 1º turno: ⛔ {type(e).__name__}: {str(e)[:150]}")
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
