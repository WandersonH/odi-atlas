#!/usr/bin/env python3
"""Coletas de dados públicos de governo, com proveniência.

Subcomandos:
  tse-candidatos  Cadastro de candidaturas e redes sociais declaradas ao TSE (CKAN `candidatos-<ANO>`).
                  Do cadastro, mantém SÓ colunas de interesse público (allowlist): CPF, título,
                  e-mail, data de nascimento e demais dados pessoais nunca são gravados.
  sidra           Tabelas da PNAD Contínua sobre Internet, descobertas pelo catálogo oficial
                  do IBGE (nenhum número de tabela escrito à mão), para Brasil e UFs.

Os ZIPs/JSONs originais ficam em raw/ (vão para Release pelo workflow); os recortes e
o manifesto vão para data/. Dado ausente é bloqueio: o script sai com código 1.
"""
from __future__ import annotations

import argparse
import csv
import gzip
import io
import json
import re
import sys
import urllib.parse
import zipfile
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from net import download, get_json, now_utc, sha256_file  # noqa: E402

CKAN = "https://dadosabertos.tse.jus.br/api/3/action/package_show?id=candidatos-{year}"
SIDRA_CATALOGO = "https://servicodados.ibge.gov.br/api/v3/agregados"
SIDRA_META = "https://servicodados.ibge.gov.br/api/v3/agregados/{id}/metadados"
SIDRA_VALORES = ("https://servicodados.ibge.gov.br/api/v3/agregados/{id}/periodos/{periodos}"
                 "/variaveis/all?localidades=N1[all]|N3[all]")

# Colunas do cadastro que podem ser publicadas. Qualquer outra é descartada na leitura.
CAND_ALLOW = ["ANO_ELEICAO", "NR_TURNO", "CD_ELEICAO", "DS_ELEICAO", "SG_UF", "SG_UE", "NM_UE",
              "CD_CARGO", "DS_CARGO", "SQ_CANDIDATO", "NR_CANDIDATO", "NM_URNA_CANDIDATO",
              "NR_PARTIDO", "SG_PARTIDO", "NM_PARTIDO", "SQ_COLIGACAO", "NM_COLIGACAO",
              "DS_COMPOSICAO_COLIGACAO", "DS_SITUACAO_CANDIDATURA", "DS_DETALHE_SITUACAO_CAND",
              "DS_SIT_TOT_TURNO"]
CAND_KEY = ("SQ_CANDIDATO", "NR_TURNO")

PLATAFORMAS = [("instagram", r"instagram\.com"), ("facebook", r"(facebook|fb)\.com"),
               ("x", r"(twitter|x)\.com"), ("youtube", r"(youtube\.com|youtu\.be)"),
               ("tiktok", r"tiktok\.com"), ("kwai", r"kwai\.(com|app)"), ("threads", r"threads\.(net|com)"),
               ("telegram", r"(t\.me|telegram\.(me|org))"), ("linkedin", r"linkedin\.com"),
               ("whatsapp", r"(whatsapp\.com|wa\.me)"), ("flickr", r"flickr\.com"),
               ("spotify", r"spotify\.com"), ("gettr", r"gettr\.com"), ("kwai", r"kw\.ai")]


def plataforma(url: str) -> str:
    u = url.strip().lower()
    host = urllib.parse.urlparse(u if "://" in u else "https://" + u).hostname or ""
    for nome, pat in PLATAFORMAS:
        if re.search(rf"(^|\.){pat}$", host):
            return nome
    return "site_ou_outro" if host else "invalida"


def pick_file(resources: list[dict], filename: str) -> dict | None:
    hits = [r for r in resources if r.get("url", "").lower().endswith("/" + filename.lower())]
    return hits[0] if len(hits) == 1 else None


def read_zip_rows(zpath: Path):
    """Itera (arquivo, cabeçalho, linha) por todos os CSVs do ZIP (Latin-1, ';')."""
    with zipfile.ZipFile(zpath) as z:
        for name in sorted(n for n in z.namelist() if n.lower().endswith(".csv")):
            with z.open(name) as raw:
                rd = csv.reader(io.TextIOWrapper(raw, encoding="latin-1", newline=""), delimiter=";")
                header = next(rd)
                for row in rd:
                    yield name, header, row


def build_candidatos(zpath: Path, out_gz: Path) -> tuple[dict, dict]:
    """Recorta o cadastro em allowlist, deduplica por (SQ_CANDIDATO, NR_TURNO) e devolve o índice por SQ."""
    stats = {"rows_read": 0, "rows_written": 0, "duplicates_dropped": 0, "columns_kept": None,
             "columns_dropped": None, "by_cargo": Counter()}
    index: dict[str, dict] = {}
    seen = set()
    out_gz.parent.mkdir(parents=True, exist_ok=True)
    with gzip.open(out_gz, "wt", encoding="utf-8", newline="") as gz:
        w = None
        for name, header, row in read_zip_rows(zpath):
            stats["rows_read"] += 1
            if w is None:
                keep = [c for c in CAND_ALLOW if c in header]
                missing_key = [c for c in CAND_KEY if c not in header]
                if missing_key:
                    raise ValueError(f"cadastro sem colunas-chave {missing_key}")
                stats["columns_kept"] = keep
                stats["columns_dropped"] = [c for c in header if c not in keep]
                ix = [header.index(c) for c in keep]
                w = csv.writer(gz, delimiter=";", lineterminator="\n")
                w.writerow(keep)
            d = {c: row[header.index(c)] for c in keep}
            key = tuple(d[c] for c in CAND_KEY)
            if key in seen:
                stats["duplicates_dropped"] += 1
                continue
            seen.add(key)
            w.writerow([row[i] for i in ix])
            stats["rows_written"] += 1
            stats["by_cargo"][d.get("DS_CARGO", "")] += 1
            index.setdefault(d["SQ_CANDIDATO"], d)
    stats["by_cargo"] = dict(stats["by_cargo"].most_common())
    stats["output_sha256"] = sha256_file(out_gz)
    return stats, index


def build_redes(zpath: Path, index: dict, out_gz: Path) -> dict:
    """Junta as redes declaradas com cargo/partido/nome de urna e classifica a plataforma pelo domínio."""
    extra = ["DS_CARGO", "SG_UF_CAND", "NR_CANDIDATO", "NM_URNA_CANDIDATO", "SG_PARTIDO", "PLATAFORMA"]
    stats = {"rows_read": 0, "rows_written": 0, "duplicates_dropped": 0, "sem_cadastro": 0,
             "by_plataforma": Counter(), "presidencia": []}
    seen = set()
    with gzip.open(out_gz, "wt", encoding="utf-8", newline="") as gz:
        w = None
        for name, header, row in read_zip_rows(zpath):
            stats["rows_read"] += 1
            if "SQ_CANDIDATO" not in header or "DS_URL" not in header:
                raise ValueError(f"{name}: arquivo de redes sem SQ_CANDIDATO/DS_URL")
            if w is None:
                w = csv.writer(gz, delimiter=";", lineterminator="\n")
                w.writerow(header + extra)
                hdr = header
            elif header != hdr:
                raise ValueError(f"{name}: cabeçalho diferente")
            sq, url = row[header.index("SQ_CANDIDATO")], row[header.index("DS_URL")]
            if (sq, url) in seen:
                stats["duplicates_dropped"] += 1
                continue
            seen.add((sq, url))
            c = index.get(sq)
            if c is None:
                stats["sem_cadastro"] += 1
            p = plataforma(url)
            w.writerow(row + ([c.get("DS_CARGO", ""), c.get("SG_UF", ""), c.get("NR_CANDIDATO", ""),
                               c.get("NM_URNA_CANDIDATO", ""), c.get("SG_PARTIDO", "")] if c else [""] * 5) + [p])
            stats["rows_written"] += 1
            stats["by_plataforma"][p] += 1
            if c and c.get("DS_CARGO", "").upper() in ("PRESIDENTE", "VICE-PRESIDENTE"):
                stats["presidencia"].append({"cargo": c["DS_CARGO"], "nr": c.get("NR_CANDIDATO"),
                                             "urna": c.get("NM_URNA_CANDIDATO"), "plataforma": p, "url": url})
    stats["by_plataforma"] = dict(stats["by_plataforma"].most_common())
    stats["output_sha256"] = sha256_file(out_gz)
    return stats


def cmd_tse(args, root: Path, man: dict):
    for year in args.years:
        e = man["tse_candidatos"].setdefault(year, {"ckan": CKAN.format(year=year)})
        try:
            res = get_json(e["ckan"])["result"]["resources"]
            e["ckan_resources_listed"] = len(res)
            cad, red = pick_file(res, f"consulta_cand_{year}.zip"), pick_file(res, f"rede_social_candidato_{year}.zip")
            if not cad or not red:
                e["status"] = "recurso_nao_encontrado"
                e["candidatos_proximos"] = [r.get("url") for r in res if "cand" in r.get("url", "")][:30]
                man["blocked"].append(f"TSE candidatos {year}: consulta_cand/rede_social não encontrados no CKAN")
                continue
            e["download_cadastro"] = download(cad["url"], root / "raw" / Path(cad["url"]).name)
            e["download_redes"] = download(red["url"], root / "raw" / Path(red["url"]).name)
            e["cadastro"], index = build_candidatos(root / "raw" / Path(cad["url"]).name,
                                                    root / "data" / "tse" / f"candidatos_{year}.csv.gz")
            e["redes"] = build_redes(root / "raw" / Path(red["url"]).name, index,
                                     root / "data" / "tse" / f"redes_sociais_candidatos_{year}.csv.gz")
            (root / "data" / "tse" / f"redes_presidencia_{year}.json").write_text(
                json.dumps(e["redes"]["presidencia"], ensure_ascii=False, indent=1), encoding="utf-8")
            e["status"] = "ok"
        except Exception as ex:
            e["status"] = "erro"
            e["error"] = f"{type(ex).__name__}: {ex}"
            man["blocked"].append(f"TSE candidatos {year}: {e['error']}")


def tabelas_internet(catalogo: list[dict]) -> list[dict]:
    """Agregados da PNAD Contínua cujo nome menciona Internet."""
    out = []
    for pesq in catalogo:
        if "contínua" not in pesq.get("nome", "").lower():
            continue
        for ag in pesq.get("agregados", []):
            if re.search(r"internet", ag.get("nome", ""), re.I):
                out.append({"id": ag["id"], "nome": ag["nome"], "pesquisa": pesq["nome"]})
    return out


def cmd_sidra(args, root: Path, man: dict, save=lambda: None):
    import time
    s = man["sidra"]
    t0 = time.monotonic()
    try:
        cat = get_json(SIDRA_CATALOGO, timeout=180)
        s["catalogo_pesquisas"] = len(cat)
        tabs = tabelas_internet(cat)[: args.max_tabelas]
        s["tabelas"] = tabs
        if not tabs:
            man["blocked"].append("SIDRA: nenhuma tabela da PNAD Contínua com 'Internet' no catálogo")
            return
        outdir = root / "data" / "ibge" / "sidra"
        outdir.mkdir(parents=True, exist_ok=True)
        (outdir / "indice.json").write_text(json.dumps(tabs, ensure_ascii=False, indent=1), encoding="utf-8")
        for t in tabs:
            if time.monotonic() - t0 > args.orcamento_min * 60:
                t.update(status="pulada", error="orçamento de tempo esgotado")
                man["warnings"].append(f"SIDRA tabela {t['id']}: pulada (orçamento de {args.orcamento_min} min)")
                continue
            try:
                meta = get_json(SIDRA_META.format(id=t["id"]), timeout=60)
                vals = get_json(SIDRA_VALORES.format(id=t["id"], periodos=args.periodos), timeout=120)
                f = outdir / f"tabela_{t['id']}.json"
                f.write_text(json.dumps({"metadados": meta, "valores": vals, "coletado_utc": now_utc()},
                                        ensure_ascii=False), encoding="utf-8")
                t.update(status="ok", arquivo=f.name, sha256=sha256_file(f), bytes=f.stat().st_size,
                         segundos=round(time.monotonic() - t0))
            except Exception as ex:
                t.update(status="erro", error=f"{type(ex).__name__}: {ex}")
                man["warnings"].append(f"SIDRA tabela {t['id']}: {t['error']}")
            save()  # manifesto parcial a cada tabela: um corte do job não apaga o que já veio
        if not any(t.get("status") == "ok" for t in tabs):
            man["blocked"].append("SIDRA: nenhuma tabela baixada")
    except Exception as ex:
        s["error"] = f"{type(ex).__name__}: {ex}"
        man["blocked"].append(f"SIDRA catálogo: {s['error']}")


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("comandos", nargs="+", choices=["tse-candidatos", "sidra"])
    p.add_argument("--years", nargs="+", default=["2026"])
    p.add_argument("--periodos", default="-12", help="períodos do SIDRA (ex.: -12 = os 12 mais recentes)")
    p.add_argument("--max-tabelas", type=int, default=25)
    p.add_argument("--orcamento-min", type=float, default=15, help="tempo máximo para o SIDRA, em minutos")
    p.add_argument("--root", default=".")
    a = p.parse_args(argv)
    root = Path(a.root)
    man = {"schema_version": 1, "stage": "coleta-gov", "run_started_utc": now_utc(), "comandos": a.comandos,
           "tse_candidatos": {}, "sidra": {}, "blocked": [], "warnings": []}
    mdir = root / "data" / "manifest"
    mdir.mkdir(parents=True, exist_ok=True)
    nome = "_".join(c.replace("-", "") for c in a.comandos)
    stamp = man["run_started_utc"].replace(":", "").replace("-", "")

    def save(final: bool = False):
        man["status"] = ("bloqueado" if man["blocked"] else "ok") if final else "em_andamento"
        txt = json.dumps(man, ensure_ascii=False, indent=2, default=dict)
        (mdir / f"gov_{nome}_latest.json").write_text(txt, encoding="utf-8")
        (mdir / f"gov_{nome}-{stamp}.json").write_text(txt, encoding="utf-8")
        return txt

    if "tse-candidatos" in a.comandos:
        cmd_tse(a, root, man)
        save()
    if "sidra" in a.comandos:
        cmd_sidra(a, root, man, save)
    man["run_finished_utc"] = now_utc()
    print(save(final=True)[:4000])
    return 1 if man["blocked"] else 0


if __name__ == "__main__":
    sys.exit(main())
