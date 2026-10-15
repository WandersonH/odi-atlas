#!/usr/bin/env python3
"""P1 — Origem: baixa os originais oficiais (TSE e IBGE) e registra a proveniência.

O script não interpreta nem totaliza votos. Ele:
  1. descobre, pela API CKAN do Portal de Dados Abertos do TSE, o arquivo
     "votacao_candidato_munzona_<ANO>.zip" de cada ano pedido;
  2. baixa cada original para raw/ (não versionado; vai para um Release do GitHub);
  3. calcula SHA-256, tamanho e guarda os cabeçalhos HTTP de cada download;
  4. extrai, sem alterar nenhuma coluna, só as linhas de Presidente (CD_CARGO=1)
     do 1º turno (NR_TURNO=1) para data/tse/presidente_1t_<ANO>_munzona.csv.gz;
  5. detecta linhas duplicadas entre arquivos do mesmo ZIP (ex.: arquivo BR + UFs)
     e as descarta UMA vez, registrando quantas foram;
  6. baixa o cadastro de municípios do IBGE (API de localidades) e, se pedido,
     a malha municipal;
  7. grava data/manifest/latest.json e um manifesto datado com tudo isso.

Só usa a biblioteca padrão do Python, para rodar em qualquer runner sem instalar nada.
Saída com código 1 se algum ano pedido não tiver o arquivo encontrado ou baixado:
dado ausente é bloqueio, não sucesso.
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import gzip
import hashlib
import io
import json
import os
import re
import sys
import urllib.error
import urllib.request
import zipfile
from pathlib import Path

CKAN = "https://dadosabertos.tse.jus.br/api/3/action/package_show?id=resultados-{year}"
IBGE_MUNICIPIOS = "https://servicodados.ibge.gov.br/api/v1/localidades/municipios"
IBGE_MALHA_DIR = ("https://geoftp.ibge.gov.br/organizacao_do_territorio/malhas_territoriais/"
                  "malhas_municipais/municipio_{ano}/Brasil/")
UA = "odi-atlas-coletor/1.0 (+https://github.com/WandersonH/odi-atlas)"
CHUNK = 1 << 20

# Colunas mínimas que o arquivo precisa ter para a extração ser considerada válida.
REQUIRED = ("CD_CARGO", "NR_TURNO", "SG_UF", "CD_MUNICIPIO", "NR_ZONA")
# Coluna com o número do candidato muda de nome entre anos/arquivos do TSE.
CAND_COLS = ("NR_CANDIDATO", "NR_VOTAVEL")


def now_utc() -> str:
    return dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def http_get(url: str, timeout: int = 120):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    return urllib.request.urlopen(req, timeout=timeout)


def get_json(url: str):
    with http_get(url) as r:
        return json.load(r)


def pick_munzona(resources: list[dict], year: str) -> dict | None:
    """Escolhe o recurso 'votacao_candidato_munzona_<ANO>.zip' na lista do CKAN.

    Exige casamento exato do nome de arquivo para não pegar, por engano,
    'votacao_partido_munzona' ou 'detalhe_votacao_munzona'.
    """
    pat = re.compile(rf"/votacao_candidato_munzona_{year}\.zip$", re.I)
    hits = [r for r in resources if pat.search(r.get("url", ""))]
    return hits[0] if len(hits) == 1 else None


def download(url: str, dest: Path) -> dict:
    """Baixa em streaming, calcula SHA-256 e devolve a ficha de proveniência."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    h = hashlib.sha256()
    size = 0
    started = now_utc()
    with http_get(url, timeout=600) as r, open(dest, "wb") as f:
        headers = {k: r.headers.get(k) for k in ("Last-Modified", "ETag", "Content-Length", "Content-Type")}
        while True:
            b = r.read(CHUNK)
            if not b:
                break
            h.update(b)
            f.write(b)
            size += len(b)
    expected = headers.get("Content-Length")
    if expected and int(expected) != size:
        raise IOError(f"download incompleto: {size} de {expected} bytes")
    return {"url": url, "file": dest.name, "bytes": size, "sha256": h.hexdigest(),
            "http": headers, "started_at_utc": started, "finished_at_utc": now_utc()}


def _decode_lines(raw: io.BufferedIOBase):
    # Os CSVs do TSE vêm em Latin-1, separados por ';' e com aspas.
    return io.TextIOWrapper(raw, encoding="latin-1", newline="")


def extract_presidente_1t(zip_path: Path, out_gz: Path) -> dict:
    """Copia, sem alterar colunas, as linhas de Presidente/1º turno de todos os CSVs do ZIP.

    Deduplica por (SG_UF, CD_MUNICIPIO, NR_ZONA, candidato) entre arquivos:
    se o ZIP trouxer um arquivo nacional e arquivos por UF, a mesma linha
    apareceria duas vezes e o total seria dobrado.
    """
    seen: dict[tuple, str] = {}
    stats = {"files": [], "rows_written": 0, "duplicates_dropped": 0,
             "rows_by_uf": {}, "header": None, "candidate_column": None}
    header_ref: list[str] | None = None
    out_gz.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(zip_path) as z, gzip.open(out_gz, "wt", encoding="utf-8", newline="") as gz:
        writer = None
        names = sorted(n for n in z.namelist() if n.lower().endswith(".csv"))
        if not names:
            raise ValueError("ZIP sem nenhum CSV")
        for name in names:
            fstat = {"name": name, "rows_read": 0, "rows_presidente_1t": 0, "duplicates": 0}
            with z.open(name) as raw:
                rd = csv.reader(_decode_lines(raw), delimiter=";", quotechar='"')
                header = next(rd)
                missing = [c for c in REQUIRED if c not in header]
                cand_col = next((c for c in CAND_COLS if c in header), None)
                if missing or not cand_col:
                    raise ValueError(f"{name}: colunas ausentes {missing or list(CAND_COLS)}")
                if header_ref is None:
                    header_ref = header
                    stats["header"] = header
                    stats["candidate_column"] = cand_col
                    writer = csv.writer(gz, delimiter=";", lineterminator="\n")
                    writer.writerow(header)
                elif header != header_ref:
                    raise ValueError(f"{name}: cabeçalho diferente do primeiro arquivo")
                ix = {c: header.index(c) for c in REQUIRED + (cand_col,)}
                for row in rd:
                    fstat["rows_read"] += 1
                    if row[ix["CD_CARGO"]].strip() != "1" or row[ix["NR_TURNO"]].strip() != "1":
                        continue
                    fstat["rows_presidente_1t"] += 1
                    key = (row[ix["SG_UF"]], row[ix["CD_MUNICIPIO"]], row[ix["NR_ZONA"]], row[ix[cand_col]])
                    if key in seen:
                        fstat["duplicates"] += 1
                        stats["duplicates_dropped"] += 1
                        if seen[key] != tuple(row):
                            # mesma chave com conteúdo diferente: não escolher em silêncio
                            stats.setdefault("duplicate_conflicts", []).append(
                                {"key": list(key), "file": name})
                        continue
                    seen[key] = tuple(row)
                    writer.writerow(row)
                    stats["rows_written"] += 1
                    uf = row[ix["SG_UF"]]
                    stats["rows_by_uf"][uf] = stats["rows_by_uf"].get(uf, 0) + 1
            stats["files"].append(fstat)
    stats["output"] = str(out_gz)
    stats["output_sha256"] = hashlib.sha256(out_gz.read_bytes()).hexdigest()
    return stats


def read_dbf(data: bytes, encoding: str = "utf-8") -> tuple[list[str], list[list[str]]]:
    """Leitor mínimo de DBF (dBase III), suficiente para a tabela de atributos da malha IBGE."""
    nrec = int.from_bytes(data[4:8], "little")
    hlen = int.from_bytes(data[8:10], "little")
    rlen = int.from_bytes(data[10:12], "little")
    fields, pos = [], 32
    while data[pos] != 0x0D:
        name = data[pos:pos + 11].split(b"\x00")[0].decode("ascii")
        fields.append((name, data[pos + 16]))
        pos += 32
    rows = []
    for i in range(nrec):
        rec = data[hlen + i * rlen: hlen + (i + 1) * rlen]
        if rec[:1] == b"*":  # registro apagado
            continue
        off, row = 1, []
        for _, size in fields:
            row.append(rec[off:off + size].decode(encoding).strip())
            off += size
        rows.append(row)
    return [f[0] for f in fields], rows


def municipios_from_malha(zip_path: Path, out_csv: Path) -> dict:
    """Gera a tabela oficial de municípios (código IBGE, nome, UF) a partir do .dbf da malha."""
    with zipfile.ZipFile(zip_path) as z:
        dbfs = [n for n in z.namelist() if n.lower().endswith(".dbf")]
        if len(dbfs) != 1:
            raise ValueError(f"esperado 1 .dbf na malha, achei {len(dbfs)}")
        cpg = [n for n in z.namelist() if n.lower().endswith(".cpg")]
        enc = z.read(cpg[0]).decode("ascii").strip() if cpg else "utf-8"
        header, rows = read_dbf(z.read(dbfs[0]), "latin-1" if "1252" in enc or "8859" in enc else "utf-8")
    out_csv.parent.mkdir(parents=True, exist_ok=True)
    with open(out_csv, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f, delimiter=";", lineterminator="\n")
        w.writerow(header)
        w.writerows(rows)
    return {"source_dbf": dbfs[0], "encoding": enc, "columns": header, "count": len(rows),
            "output": str(out_csv), "output_sha256": hashlib.sha256(out_csv.read_bytes()).hexdigest()}


def find_malha_zip(year: str) -> str | None:
    """Lê a listagem do diretório do IBGE e devolve o .zip da malha de municípios."""
    base = IBGE_MALHA_DIR.format(ano=year)
    with http_get(base) as r:
        html = r.read().decode("utf-8", "replace")
    zips = sorted(set(re.findall(r'href="([^"]*Municipios[^"]*\.zip)"', html, re.I)))
    return base + zips[0] if len(zips) == 1 else None


def run(args) -> int:
    root = Path(args.root)
    raw = root / "raw"
    stamp = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    manifest = {"schema_version": 1, "stage": "P1-origem", "run_started_utc": now_utc(),
                "runner": {"github_run_id": os.getenv("GITHUB_RUN_ID"),
                           "github_sha": os.getenv("GITHUB_SHA"),
                           "github_repository": os.getenv("GITHUB_REPOSITORY")},
                "tse": {}, "ibge": {}, "blocked": []}

    for year in args.years:
        entry: dict = {"ckan": CKAN.format(year=year)}
        manifest["tse"][year] = entry
        try:
            pkg = get_json(entry["ckan"])
            res = pkg["result"]["resources"]
            entry["ckan_resources_listed"] = len(res)
            entry["ckan_metadata_modified"] = pkg["result"].get("metadata_modified")
            chosen = pick_munzona(res, year)
            if not chosen:
                entry["status"] = "recurso_nao_encontrado"
                entry["candidatos_proximos"] = [r.get("url") for r in res if "munzona" in r.get("url", "")]
                manifest["blocked"].append(f"TSE {year}: votacao_candidato_munzona_{year}.zip não está no CKAN")
                continue
            entry["resource"] = {k: chosen.get(k) for k in ("id", "name", "url", "last_modified", "created", "size")}
            zpath = raw / Path(chosen["url"]).name
            entry["download"] = download(chosen["url"], zpath)
            entry["extract"] = extract_presidente_1t(zpath, root / "data" / "tse" / f"presidente_1t_{year}_munzona.csv.gz")
            if entry["extract"].get("duplicate_conflicts"):
                manifest["blocked"].append(f"TSE {year}: linhas duplicadas com valores diferentes (ver extract.duplicate_conflicts)")
            if entry["extract"]["rows_written"] == 0:
                manifest["blocked"].append(f"TSE {year}: nenhuma linha de Presidente/1º turno no arquivo")
            entry["status"] = "ok"
        except Exception as e:  # registra e segue para os demais anos
            entry["status"] = "erro"
            entry["error"] = f"{type(e).__name__}: {e}"
            manifest["blocked"].append(f"TSE {year}: {entry['error']}")

    # A tabela oficial de municípios vem do .dbf da malha (mesma fonte da geometria).
    # A API de localidades é só complementar: em 15/10/2026 ela respondeu com cadeia
    # de certificados incompleta, por isso sua falha vira aviso, não bloqueio.
    manifest["warnings"] = []
    if args.malha:
        try:
            url = find_malha_zip(args.malha)
            if not url:
                raise ValueError("zip de municípios não identificado de forma única na listagem")
            zpath = raw / Path(url).name
            manifest["ibge"]["malha"] = download(url, zpath)
            manifest["ibge"]["municipios_malha"] = municipios_from_malha(
                zpath, root / "data" / "ibge" / f"municipios_malha_{args.malha}.csv")
        except Exception as e:
            manifest["ibge"]["malha"] = {"status": "erro", "error": f"{type(e).__name__}: {e}"}
            manifest["blocked"].append(f"IBGE malha {args.malha}: {e}")

    try:
        dest = root / "data" / "ibge" / "municipios_api.json"
        info = download(IBGE_MUNICIPIOS, dest)
        info["count"] = len(json.loads(dest.read_text(encoding="utf-8")))
        manifest["ibge"]["municipios_api"] = info
    except Exception as e:
        manifest["ibge"]["municipios_api"] = {"status": "erro", "error": f"{type(e).__name__}: {e}"}
        manifest["warnings"].append(f"IBGE API de localidades indisponível: {e}")

    manifest["run_finished_utc"] = now_utc()
    manifest["status"] = "bloqueado" if manifest["blocked"] else "ok"
    mdir = root / "data" / "manifest"
    mdir.mkdir(parents=True, exist_ok=True)
    txt = json.dumps(manifest, ensure_ascii=False, indent=2)
    (mdir / f"p1-{stamp}.json").write_text(txt, encoding="utf-8")
    (mdir / "latest.json").write_text(txt, encoding="utf-8")
    print(txt)
    return 1 if manifest["blocked"] else 0


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--years", nargs="+", default=["2022", "2026"])
    p.add_argument("--malha", default="2025", help="ano da malha municipal do IBGE ('' para pular)")
    p.add_argument("--root", default=".")
    return run(p.parse_args(argv))


if __name__ == "__main__":
    sys.exit(main())
