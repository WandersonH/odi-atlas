#!/usr/bin/env python3
"""P2 + P3 — gera data/elections.json para o caderno 06, a partir dos recortes da P1.

Entrada:  data/tse/presidente_1t_<ANO>_munzona.csv.gz   (P1)
          data/ibge/municipios_malha_2025.csv              (P1.1, malha oficial)
          data/config/tse_ibge_excecoes.csv                (exceções revisadas à mão)
Saída:    data/elections.json   (formato schema_version=1 lido pelo caderno 06)

Regras:
- Votos válidos = soma de QT_VOTOS_NOMINAIS_VALIDOS de todas as candidaturas do município.
  Brancos, nulos e abstenção NÃO estão neste arquivo do TSE.
- Exterior (UF "ZZ") fica fora do mapa, mas seus totais entram no diagnóstico.
- Correspondência TSE→IBGE: primeiro a tabela de exceções (por código TSE), depois nome
  idêntico após normalização (sem acento/pontuação). Nada de aproximação automática:
  município sem correspondência bloqueia a geração.
- Portões: somas por UF e nacional precisam bater com o recorte bruto; nenhum código IBGE
  pode aparecer duas vezes no mesmo ano.
"""
from __future__ import annotations

import csv
import datetime as dt
import gzip
import json
import re
import sys
import unicodedata
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def norm(s: str) -> str:
    """Mesma normalização do caderno 06 (cityNorm)."""
    s = unicodedata.normalize("NFKD", str(s or ""))
    s = "".join(ch for ch in s if not unicodedata.combining(ch))
    return re.sub(r"[^A-Z0-9]+", " ", s.upper()).strip()


def load_ibge(path: Path):
    by_name, by_code = {}, {}
    for r in csv.DictReader(open(path, encoding="utf-8"), delimiter=";"):
        if r["CD_MUN"] in ("4300001", "4300002"):  # áreas operacionais Lagoa Mirim e Lagoa dos Patos (não são municípios)
            continue
        key = (r["SIGLA_UF"], norm(r["NM_MUN"]))
        if key in by_name:
            raise ValueError(f"nome repetido na malha: {key}")
        by_name[key] = r["CD_MUN"]
        by_code[r["CD_MUN"]] = (r["SIGLA_UF"], r["NM_MUN"])
    return by_name, by_code


def load_exceptions(path: Path):
    return {(r["uf"], r["cd_municipio_tse"]): r for r in csv.DictReader(open(path, encoding="utf-8"), delimiter=";")}


def build_year(year: str, by_name, by_code, exc, root: Path, turno: str = "1"):
    src = root / "data" / "tse" / f"presidente_{turno}t_{year}_munzona.csv.gz"
    mun = defaultdict(lambda: {"validos": 0, "cand": defaultdict(int), "nome_tse": None})
    names, raw_uf, exterior = {}, defaultdict(int), defaultdict(int)
    for r in csv.DictReader(gzip.open(src, "rt", encoding="utf-8"), delimiter=";"):
        if r["CD_CARGO"] != "1" or r["NR_TURNO"] != turno:
            raise ValueError(f"{src.name}: linha fora de Presidente/{turno}º turno")
        v = int(r["QT_VOTOS_NOMINAIS_VALIDOS"])
        nr = r["NR_CANDIDATO"]
        names[nr] = r["NM_URNA_CANDIDATO"]
        if r["SG_UF"] == "ZZ":
            exterior[nr] += v
            continue
        raw_uf[r["SG_UF"]] += v
        m = mun[(r["SG_UF"], r["CD_MUNICIPIO"])]
        m["validos"] += v
        m["cand"][nr] += v
        m["nome_tse"] = r["NM_MUNICIPIO"]

    table, unmapped, used, via_exc = {}, [], {}, []
    for (uf, cd_tse), m in mun.items():
        e = exc.get((uf, cd_tse))
        ibge = e["cd_mun_ibge"] if e else by_name.get((uf, norm(m["nome_tse"])))
        if e:
            via_exc.append(f"{uf} {cd_tse} {m['nome_tse']} → {ibge}")
        if not ibge:
            unmapped.append({"uf": uf, "cd_municipio_tse": cd_tse, "nome_tse": m["nome_tse"]})
            continue
        if ibge in used:
            raise ValueError(f"{year}: código IBGE {ibge} atribuído a dois municípios do TSE ({used[ibge]} e {cd_tse})")
        if by_code[ibge][0] != uf:
            raise ValueError(f"{year}: {cd_tse} ({uf}) mapeado para {ibge} de outra UF")
        used[ibge] = cd_tse
        nome = by_code[ibge][1]
        table[f"{uf}|{norm(nome)}"] = {"uf": uf, "municipio": nome, "ibge": ibge, "cd_municipio_tse": cd_tse,
                                       "nome_tse": m["nome_tse"], "validos_nominais": m["validos"],
                                       "candidatos": dict(sorted(m["cand"].items()))}

    # portões de integridade
    agg_uf = defaultdict(int)
    for r in table.values():
        agg_uf[r["uf"]] += r["validos_nominais"]
    diffs = {uf: (raw_uf[uf], agg_uf.get(uf, 0)) for uf in raw_uf if raw_uf[uf] != agg_uf.get(uf, 0)}
    diag = {"fonte": src.name, "municipios": len(table), "sem_correspondencia": unmapped,
            "via_tabela_de_excecoes": sorted(via_exc), "validos_brasil_sem_exterior": sum(raw_uf.values()),
            "validos_exterior": sum(exterior.values()), "exterior_por_candidatura": dict(sorted(exterior.items())),
            "divergencias_por_uf": diffs,
            "totais_brasil_sem_exterior": {nr: sum(r["candidatos"].get(nr, 0) for r in table.values()) for nr in sorted(names)}}
    return table, dict(sorted(names.items())), diag


def build_2t_resultados(by_code, root: Path):
    """2º turno de 2026 enquanto o arquivo de dados abertos (munzona) não traz o 2º turno: lê a totalização oficial
    por município já gravada em data/tse/segundo_turno/municipios.json (resultados.tse.jus.br, um JSON por município).
    Mesmo formato do build_year; a correspondência IBGE é a que o TSE publica no próprio arquivo (conferida contra a malha)."""
    f = root / "data" / "tse" / "segundo_turno" / "municipios.json"
    if not f.exists():
        return None
    d = json.loads(f.read_text(encoding="utf-8"))
    table, unmapped, used, parcial = {}, [], set(), []
    tot = defaultdict(int)
    for cd, m in (d.get("m") or {}).items():
        if m.get("uf") == "ZZ":
            continue
        ibge = str(m.get("ibge") or "")
        if ibge not in by_code or by_code[ibge][0] != m.get("uf") or ibge in used:
            unmapped.append({"uf": m.get("uf"), "cd_municipio_tse": cd, "nome_tse": m.get("nome")})
            continue
        used.add(ibge)
        if float(m.get("pst") or 0) < 100:
            parcial.append(ibge)
        nome = by_code[ibge][1]
        l, fl = int(m.get("l") or 0), int(m.get("f") or 0)
        tot["13"] += l
        tot["22"] += fl
        table[f"{m['uf']}|{norm(nome)}"] = {"uf": m["uf"], "municipio": nome, "ibge": ibge, "cd_municipio_tse": cd, "nome_tse": m.get("nome"),
                                            "validos_nominais": l + fl, "candidatos": {"13": l, "22": fl}}
    diag = {"fonte": "data/tse/segundo_turno/municipios.json (" + str(d.get("fonte_2t")) + ")", "lido_em_utc": d.get("lido_em_utc"),
            "municipios": len(table), "sem_correspondencia": unmapped, "municipios_com_totalizacao_parcial": len(parcial),
            "validos_brasil_sem_exterior": sum(tot.values()), "totais_brasil_sem_exterior": dict(tot)}
    return table, {"13": "LULA", "22": "FLÁVIO BOLSONARO"}, diag


def build_segundo_turno(by_name, by_code, exc, root: Path) -> dict:
    """data/elections_2t.json: Presidente, 2º turno, por município (2022 e 2026), no mesmo formato do elections.json."""
    out = {"schema_version": 1, "status": "ok", "turno": 2, "years": {}, "candidates": {}, "diagnostics": {"sources": {}, "blocked": []},
           "generated_at_utc": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
           "source": {"electoral": "TSE · votacao_candidato_munzona (2º turno, Presidente); 2026, enquanto os dados abertos não trazem o 2º turno: "
                                   "totalização oficial por município (resultados.tse.jus.br)",
                      "geographic": "IBGE · malha municipal 2025 (BR_Municipios_2025)",
                      "nota": "No 2º turno, válidos = votos nos dois candidatos. 2022: Lula (13) × Jair Bolsonaro (22); 2026: Lula (13) × Flávio Bolsonaro (22)."}}
    for year in ("2022", "2026"):
        try:
            if (root / "data" / "tse" / f"presidente_2t_{year}_munzona.csv.gz").exists():
                res = build_year(year, by_name, by_code, exc, root, turno="2")
            elif year == "2026":
                res = build_2t_resultados(by_code, root)
            else:
                res = None
        except Exception as e:  # noqa: BLE001
            out["diagnostics"]["blocked"].append(f"{year}: {type(e).__name__}: {e}")
            continue
        if not res:
            out["diagnostics"]["blocked"].append(f"{year}: ⛔ recorte do 2º turno ausente (data/tse/presidente_2t_{year}_munzona.csv.gz)")
            continue
        table, names, diag = res
        out["years"][year], out["candidates"][year], out["diagnostics"]["sources"][year] = table, names, diag
        if diag["sem_correspondencia"]:
            out["diagnostics"]["blocked"].append(f"{year}: {len(diag['sem_correspondencia'])} município(s) sem correspondência IBGE")
        if diag.get("divergencias_por_uf"):
            out["diagnostics"]["blocked"].append(f"{year}: soma municipal diverge do recorte bruto em {list(diag['divergencias_por_uf'])}")
    if out["diagnostics"]["blocked"]:
        out["status"] = "parcial" if out["years"] else "bloqueado"
    (root / "data" / "elections_2t.json").write_text(json.dumps(out, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    for y, d in out["diagnostics"]["sources"].items():
        print("2º turno", y, "municípios", d["municipios"], "| sem correspondência", len(d["sem_correspondencia"]),
              "| válidos BR", d["validos_brasil_sem_exterior"], "| 13:", d["totais_brasil_sem_exterior"].get("13"), "| 22:", d["totais_brasil_sem_exterior"].get("22"))
    print("2º turno status", out["status"], out["diagnostics"]["blocked"])
    return out


def main(argv=None) -> int:
    root = Path(argv[0]) if argv else ROOT
    by_name, by_code = load_ibge(root / "data" / "ibge" / "municipios_malha_2025.csv")
    exc = load_exceptions(root / "data" / "config" / "tse_ibge_excecoes.csv")
    out = {"schema_version": 1, "status": "ok", "years": {}, "candidates": {}, "diagnostics": {"sources": {}},
           "generated_at_utc": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
           "source": {"electoral": "TSE · votacao_candidato_munzona (1º turno, Presidente) — ver data/manifest/latest.json",
                      "geographic": "IBGE · malha municipal 2025 (BR_Municipios_2025)",
                      "nota": "Comparação 2022→2026 é por NÚMERO de urna: o 22 é Jair Bolsonaro em 2022 e Flávio Bolsonaro em 2026. "
                              "Válidos = votos nominais válidos; brancos, nulos e abstenção não estão incluídos."}}
    blocked = []
    for year in ("2022", "2026"):
        table, names, diag = build_year(year, by_name, by_code, exc, root)
        out["years"][year], out["candidates"][year], out["diagnostics"]["sources"][year] = table, names, diag
        if diag["sem_correspondencia"]:
            blocked.append(f"{year}: {len(diag['sem_correspondencia'])} município(s) sem correspondência IBGE")
        if diag["divergencias_por_uf"]:
            blocked.append(f"{year}: soma municipal diverge do recorte bruto em {list(diag['divergencias_por_uf'])}")
    out["diagnostics"]["blocked"] = blocked
    build_segundo_turno(by_name, by_code, exc, root)
    if blocked:
        out["status"] = "bloqueado"
    (root / "data" / "elections.json").write_text(json.dumps(out, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    for y, d in out["diagnostics"]["sources"].items():
        print(y, "municípios", d["municipios"], "| exceções usadas", len(d["via_tabela_de_excecoes"]),
              "| sem correspondência", len(d["sem_correspondencia"]), "| válidos BR", d["validos_brasil_sem_exterior"],
              "| exterior", d["validos_exterior"], "| 13:", d["totais_brasil_sem_exterior"].get("13"),
              "| 22:", d["totais_brasil_sem_exterior"].get("22"))
    print("status", out["status"], blocked)
    return 1 if blocked else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
