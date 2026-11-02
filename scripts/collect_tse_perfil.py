"""Comparecimento e abstenção por perfil (2026) e perfil do eleitorado (2026), dados abertos do TSE, só agregados.

Pedido do responsável (02/11/2026, 15h57 "pode aplicar"; 17h10 "terminou isso … comparecimento por perfil e perfil do
eleitorado por município"). Arquivos (sonda C19.298, run 41506429826):
- perfil_comparecimento_abstencao_2026.zip (229,2 MB; dataset comparecimento-e-abstencao-2026)
- perfil_eleitorado_2026.zip (408,5 MB; dataset eleitorado-2026)
Agregação genérica: soma de todas as colunas QT_* por turno (quando houver), por cada dimensão DS_* de perfil (gênero,
faixa etária, escolaridade, estado civil, raça/cor, identidade de gênero…), no Brasil e por UF; e totais por município.
Saída: data/tse/perfil/<nome>.json e <nome>_municipios.csv. Nenhuma linha individual (os arquivos já são agregados pelo TSE).
Uso: python scripts/collect_tse_perfil.py [comparecimento] [eleitorado]
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

csv.field_size_limit(10**9)
ROOT = Path(__file__).resolve().parents[1]
UA = {"User-Agent": "Mozilla/5.0 (ODI Atlas; pesquisa acadêmica)"}
ARQ = {
    "comparecimento": ("https://cdn.tse.jus.br/estatistica/sead/odsele/perfil_comparecimento_abstencao/perfil_comparecimento_abstencao_2026.zip",
                       "https://dadosabertos.tse.jus.br/dataset/comparecimento-e-abstencao-2026"),
    "eleitorado": ("https://cdn.tse.jus.br/estatistica/sead/odsele/perfil_eleitorado/perfil_eleitorado_2026.zip",
                   "https://dadosabertos.tse.jus.br/dataset/eleitorado-2026"),
}
NAO_DIM = {"DS_ELEICAO", "DS_TIPO_ELEICAO", "DS_CARGO", "DS_MUN_SIT_BIOMETRIA", "DS_TURNO"}


def baixar(url: str, pasta: Path) -> Path:
    destino = pasta / url.rsplit("/", 1)[1]
    with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=1800) as r, open(destino, "wb") as f:
        while b := r.read(1 << 20):
            f.write(b)
    return destino


def num(v) -> int:
    try:
        return int(v)
    except (TypeError, ValueError):
        return 0


def agregar(z: zipfile.ZipFile) -> dict:
    nomes = [n for n in z.namelist() if n.lower().endswith(".csv")]
    br = [n for n in nomes if "brasil" in n.lower() or n.lower().endswith("_br.csv")]
    nomes = br or nomes
    cab, qts, dims = None, [], []
    nac = defaultdict(lambda: defaultdict(lambda: defaultdict(int)))  # (turno, dim) → valor → qt
    uf = defaultdict(lambda: defaultdict(lambda: defaultdict(lambda: defaultdict(int))))  # uf → (turno, dim) → valor → qt
    mun = defaultdict(lambda: defaultdict(int))  # (turno, uf, cd, nome) → qt
    tot = defaultdict(lambda: defaultdict(int))
    linhas = 0
    for n in nomes:
        with z.open(n) as f:
            for r in csv.DictReader(io.TextIOWrapper(f, encoding="latin-1", newline=""), delimiter=";"):
                if cab is None:
                    cab = list(r.keys())
                    qts = [c for c in cab if c.startswith("QT_")]
                    dims = [c for c in cab if c.startswith("DS_") and c not in NAO_DIM]
                linhas += 1
                t = r.get("NR_TURNO") or "-"
                for q in qts:
                    v = num(r.get(q))
                    tot[t][q] += v
                    mun[(t, r.get("SG_UF"), r.get("CD_MUNICIPIO"), r.get("NM_MUNICIPIO"))][q] += v
                for d in dims:
                    val = r.get(d) or "?"
                    for q in qts:
                        v = num(r.get(q))
                        nac[(t, d)][val][q] += v
                        uf[r.get("SG_UF")][(t, d)][val][q] += v
    dd = lambda x: {k: dict(v) for k, v in x.items()}  # noqa: E731
    return {"arquivos_csv": nomes, "linhas_lidas": linhas, "colunas": cab, "medidas": qts, "dimensoes": dims,
            "totais_por_turno": dd(tot),
            "brasil": {f"turno {t} · {d}": dd(v) for (t, d), v in nac.items()},
            "ufs": {u: {f"turno {t} · {d}": dd(v) for (t, d), v in x.items()} for u, x in sorted(uf.items())},
            "_mun": mun}


def main(argv: list[str]) -> int:
    alvo = argv or list(ARQ)
    pasta = ROOT / "data/tse/perfil"
    pasta.mkdir(parents=True, exist_ok=True)
    rc = 0
    for nome in alvo:
        url, fonte = ARQ[nome]
        try:
            with tempfile.TemporaryDirectory() as t:
                zp = baixar(url, Path(t))
                mb = round(zp.stat().st_size / 1e6, 1)
                a = agregar(zipfile.ZipFile(zp))
        except Exception as e:  # noqa: BLE001
            print(f"{nome}: ⛔ {type(e).__name__}: {str(e)[:200]}")
            rc = 1
            continue
        mun = a.pop("_mun")
        out = {"schema_version": 1, "gerado_em_utc": now_utc(), "fonte": fonte, "arquivo": url, "mb": mb,
               "universo": "agregados publicados pelo TSE para todo o eleitorado (não é amostra)", **a}
        (pasta / f"{nome}_2026.json").write_text(json.dumps(out, ensure_ascii=False, separators=(",", ":")) + "\n", encoding="utf-8")
        with open(pasta / f"{nome}_2026_municipios.csv", "w", encoding="utf-8", newline="") as fh:
            w = csv.writer(fh, delimiter=";")
            w.writerow(["turno", "uf", "cd_municipio_tse", "municipio", *a["medidas"]])
            for (t, u, cd, nm), v in sorted(mun.items(), key=lambda kv: tuple(str(x) for x in kv[0])):
                w.writerow([t, u, cd, nm, *[v.get(q, 0) for q in a["medidas"]]])
        print(f"{nome}: {a['linhas_lidas']} linhas · {mb} MB · medidas {a['medidas']} · dimensões {a['dimensoes']} · totais {a['totais_por_turno']} · municípios {len(mun)}")
    return rc


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
