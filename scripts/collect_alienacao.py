#!/usr/bin/env python3
"""Alienação eleitoral (abstenção + brancos + nulos) por município, local de votação e seção — eleição presidencial 2026.

Pedido do responsável (22/10/2026, 01h26): mapa por cidade e por seção, na página de Eleitorado, como o mapa de voto.

Fontes (TSE, Dados Abertos; estrutura conferida pela sonda C19.95, run 39723264242):
- "Detalhe da apuração por seção eleitoral" (pacote resultados-2026): detalhe_votacao_secao_2026.zip — por seção e cargo:
  aptos, comparecimento, abstenções, brancos e nulos. Usa o cargo Presidente (aptos e abstenção são os mesmos em todos os
  cargos da seção; brancos e nulos são os do voto para presidente).
- "Eleitorado por local de votação 2026" (pacote eleitorado-2026): eleitorado_local_votacao_2026.zip — liga cada seção ao
  local de votação (nome, bairro, latitude e longitude). Seção sem coordenada fica fora do mapa de pontos e entra nas somas.
- Correspondência TSE → IBGE dos municípios: data/elections.json (a mesma do mapa de voto; tabela de exceções revisada).

Alienação = (abstenções + brancos + nulos) / aptos. Índice descritivo: não separa motivo (abstenção inclui quem mudou de
cidade, morreu sem baixa no cadastro, justificou etc.).

Saída pública (dado público do TSE, só agregados por seção — nenhum eleitor):
  data/tse/alienacao/<N>t/resumo.json        Brasil, UFs e municípios (código IBGE)
  data/tse/alienacao/<N>t/locais_<UF>.json   locais de votação com coordenadas e as seções de cada um
Uso: python scripts/collect_alienacao.py [--turno 1|2] [--uf AC] (sem --uf: todas)
"""
from __future__ import annotations

import csv
import io
import json
import sys
import tempfile
import urllib.request
import zipfile
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from net import now_utc  # noqa: E402

URL_SECAO = "https://cdn.tse.jus.br/estatistica/sead/odsele/detalhe_votacao_secao/detalhe_votacao_secao_2026.zip"
URL_LOCAL = "https://cdn.tse.jus.br/estatistica/sead/odsele/eleitorado_locais_votacao/eleitorado_local_votacao_2026.zip"
FONTES = {"secao": "https://dadosabertos.tse.jus.br/dataset/resultados-2026", "local": "https://dadosabertos.tse.jus.br/dataset/eleitorado-2026"}
csv.field_size_limit(10**9)
UA = {"User-Agent": "Mozilla/5.0 (ODI Atlas; pesquisa acadêmica)"}


def baixar(url: str, pasta: Path) -> Path:
    destino = pasta / url.rsplit("/", 1)[1]
    if not destino.exists():
        with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=1800) as r, open(destino, "wb") as f:
            while True:
                b = r.read(1 << 20)
                if not b:
                    break
                f.write(b)
    return destino


def linhas(z: zipfile.ZipFile, nome: str):
    with z.open(nome) as f:
        yield from csv.DictReader(io.TextIOWrapper(f, encoding="latin-1", newline=""), delimiter=";")


def inteiro(v) -> int:
    try:
        return int(str(v).strip())
    except ValueError:
        return 0


def col(r: dict, *nomes) -> str:
    for n in nomes:
        if n in r and r[n] not in (None, ""):
            return r[n]
    return ""


def eh_presidente(r: dict) -> bool:
    return str(col(r, "CD_CARGO")).strip() == "1" or col(r, "DS_CARGO").strip().upper() == "PRESIDENTE"


def secoes(z: zipfile.ZipFile, turno: str, ufs: set | None) -> tuple[dict, list[str]]:
    """(uf, cd_mun, zona, secao) → contagens do cargo Presidente no turno."""
    out, colunas = {}, []
    for nome in z.namelist():
        if not nome.lower().endswith(".csv") or "BRASIL" in nome.upper():
            continue
        uf_arq = nome.rsplit("_", 1)[-1].split(".")[0].upper()
        if ufs and uf_arq not in ufs:
            continue
        for r in linhas(z, nome):
            if not colunas:
                colunas = list(r.keys())
            if str(r.get("NR_TURNO")) != turno or not eh_presidente(r):
                continue
            k = (r["SG_UF"], r["CD_MUNICIPIO"], r["NR_ZONA"], r["NR_SECAO"])
            out[k] = {"nm_mun": r.get("NM_MUNICIPIO", ""), "local": col(r, "NR_LOCAL_VOTACAO"),
                      "aptos": inteiro(col(r, "QT_APTOS")), "comparecimento": inteiro(col(r, "QT_COMPARECIMENTO")),
                      "abstencoes": inteiro(col(r, "QT_ABSTENCOES")), "brancos": inteiro(col(r, "QT_VOTOS_BRANCOS", "QT_VOTOS_BRANCO")),
                      "nulos": inteiro(col(r, "QT_TOTAL_VOTOS_NULOS", "QT_VOTOS_NULOS", "QT_VOTOS_NULO"))}
    return out, colunas


def locais(z: zipfile.ZipFile, turno: str, ufs: set | None) -> dict:
    """(uf, cd_mun, zona, secao) → local de votação (nome, bairro, coordenadas)."""
    out = {}
    for nome in z.namelist():
        if not nome.lower().endswith(".csv"):
            continue
        uf_arq = nome.rsplit("_", 1)[-1].split(".")[0].upper()
        if ufs and uf_arq not in ufs:
            continue
        for r in linhas(z, nome):
            if r.get("NR_TURNO") and str(r["NR_TURNO"]) != turno:
                continue
            try:
                lat, lon = float(r["NR_LATITUDE"].replace(",", ".")), float(r["NR_LONGITUDE"].replace(",", "."))
                coord = (round(lat, 5), round(lon, 5)) if lat != -1 and lon != -1 and lat and lon else None
            except (ValueError, KeyError):
                coord = None
            out[(r["SG_UF"], r["CD_MUNICIPIO"], r["NR_ZONA"], r["NR_SECAO"])] = {
                "local": r.get("NR_LOCAL_VOTACAO", ""), "nome": (r.get("NM_LOCAL_VOTACAO") or "").strip(), "bairro": (r.get("NM_BAIRRO") or "").strip(), "coord": coord}
    return out


def mapa_ibge(root: Path) -> dict:
    d = json.loads((root / "data/elections.json").read_text(encoding="utf-8"))
    return {str(int(v["cd_municipio_tse"])): v["ibge"] for v in d["years"]["2026"].values() if str(v.get("cd_municipio_tse") or "").isdigit() and v.get("ibge")}


CAMPOS = ("aptos", "comparecimento", "abstencoes", "brancos", "nulos")


def soma(xs) -> dict:
    s = {k: sum(x[k] for x in xs) for k in CAMPOS}
    s["alienacao"] = s["abstencoes"] + s["brancos"] + s["nulos"]
    a = s["aptos"] or 0
    s.update({f"pct_{k}": round(100 * s[k] / a, 2) if a else None for k in ("abstencoes", "brancos", "nulos", "alienacao")})
    return s


def agregar(sec: dict, loc: dict, ibge: dict) -> tuple[dict, dict]:
    por_uf, por_mun, por_local = defaultdict(list), defaultdict(list), defaultdict(list)
    sem_local, sem_coord, sem_ibge = 0, 0, set()
    for k, s in sec.items():
        uf, cd, zona, nr = k
        por_uf[uf].append(s)
        cod = ibge.get(str(int(cd))) if cd.isdigit() else None
        if uf != "ZZ":
            if cod:
                por_mun[(uf, cod, s["nm_mun"])].append(s)
            else:
                sem_ibge.add(f"{uf} {cd} {s['nm_mun']}")
        lc = loc.get(k)
        if not lc:
            sem_local += 1
            continue
        if not lc["coord"]:
            sem_coord += 1
        por_local[(uf, cod, zona, lc["local"])].append((nr, s, lc))
    resumo = {"brasil": soma(sec.values()), "ufs": {uf: soma(xs) for uf, xs in sorted(por_uf.items())},
              "municipios": {cod: {"uf": uf, "nome": nm, **soma(xs), "secoes": len(xs)} for (uf, cod, nm), xs in por_mun.items()},
              "diagnostico": {"secoes": len(sec), "secoes_sem_local": sem_local, "secoes_sem_coordenada": sem_coord,
                              "municipios_sem_codigo_ibge": sorted(sem_ibge)[:50], "n_municipios_sem_codigo_ibge": len(sem_ibge)}}
    locs = defaultdict(list)
    for (uf, cod, zona, nrl), xs in por_local.items():
        if uf == "ZZ":
            continue
        lc = xs[0][2]
        t = soma([s for _, s, _ in xs])
        locs[uf].append({"mun": cod, "zona": zona, "local": nrl, "nome": lc["nome"], "bairro": lc["bairro"],
                         "lat": lc["coord"][0] if lc["coord"] else None, "lon": lc["coord"][1] if lc["coord"] else None,
                         **{k: t[k] for k in ("aptos", "abstencoes", "brancos", "nulos", "pct_alienacao")},
                         "secoes": [[nr, s["aptos"], s["abstencoes"], s["brancos"], s["nulos"]] for nr, s, _ in sorted(xs, key=lambda x: int(x[0]) if x[0].isdigit() else 0)]})
    return resumo, locs


def main(argv=None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    turno = argv[argv.index("--turno") + 1] if "--turno" in argv else "1"
    ufs = {argv[argv.index("--uf") + 1].upper()} if "--uf" in argv else None
    root = Path(".")
    pasta = root / f"data/tse/alienacao/{turno}t"
    with tempfile.TemporaryDirectory() as t:
        zs, zl = zipfile.ZipFile(baixar(URL_SECAO, Path(t))), zipfile.ZipFile(baixar(URL_LOCAL, Path(t)))
        sec, colunas = secoes(zs, turno, ufs)
        print(f"colunas do detalhe por seção: {colunas}")
        if not sec:
            print(f"⛔ nenhuma seção do {turno}º turno para Presidente no arquivo do TSE (ainda não publicado?)")
            return 1
        loc = locais(zl, turno, ufs)
    resumo, locs = agregar(sec, loc, mapa_ibge(root))
    pasta.mkdir(parents=True, exist_ok=True)
    meta = {"schema_version": 1, "turno": int(turno), "cargo": "Presidente", "gerado_em_utc": now_utc(), "fontes": FONTES,
            "arquivos": [URL_SECAO, URL_LOCAL], "definicao": "alienação = abstenções + brancos + nulos, sobre o eleitorado apto da seção",
            "nota": "Índice descritivo, sem separar motivos: a abstenção inclui quem mudou de cidade sem transferir o título, eleitor "
                    "falecido sem baixa, quem justificou etc. Brancos e nulos são do voto para presidente."}
    (pasta / "resumo.json").write_text(json.dumps({**meta, **resumo}, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    for uf, xs in locs.items():
        (pasta / f"locais_{uf}.json").write_text(json.dumps({**meta, "uf": uf, "campos_secao": ["secao", "aptos", "abstencoes", "brancos", "nulos"],
                                                             "locais": xs}, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    b, d = resumo["brasil"], resumo["diagnostico"]
    print(f"{turno}º turno: {d['secoes']} seções · aptos {b['aptos']} · abstenção {b['pct_abstencoes']}% · brancos {b['pct_brancos']}% · nulos {b['pct_nulos']}% · "
          f"alienação {b['pct_alienacao']}% · municípios {len(resumo['municipios'])} · locais {sum(len(v) for v in locs.values())} · "
          f"sem local {d['secoes_sem_local']} · sem coordenada {d['secoes_sem_coordenada']} · sem código IBGE {d['n_municipios_sem_codigo_ibge']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
