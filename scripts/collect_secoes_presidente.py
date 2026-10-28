#!/usr/bin/env python3
"""Votação para presidente por seção eleitoral (urna): quantas seções cada candidato venceu e o percentual em cada uma.

Pedido do responsável (27/10/2026, 22h47): "preciso validar uma informação, então teremos mais uma página: quantas urnas cada
candidato teve, todos os percentuais por seção eleitoral".

Fonte: TSE, Dados Abertos, "Votação por seção eleitoral" (votacao_secao_2026_BR.zip: presidente, uma linha por seção × votável,
com NR_TURNO). Se o arquivo não existir ou não trouxer o turno pedido, o resultado é ⛔ (nada estimado) e a coleta diária tenta de novo.
Seção = urna (cada seção tem uma urna; seções agregadas contam como a seção principal, como no arquivo do TSE).
Por seção: votos de cada candidato, brancos (95), nulos (96), válidos, % de cada candidato nos válidos; vencedor (empate quando iguais).
Saída pública (dados abertos do TSE, sem dado pessoal): data/tse/secoes/presidente_<turno>t_resumo.json (contagens, distribuição,
por UF, seções extremas) e presidente_<turno>t_secoes.csv.gz (todas as seções com votos e percentuais, para conferência).
Uso: python scripts/collect_secoes_presidente.py --turno 2 [--arquivo caminho_local.zip]
"""
from __future__ import annotations

import csv
import gzip
import io
import json
import sys
import tempfile
import urllib.error
import zipfile
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from collect_alienacao import baixar  # noqa: E402
from net import now_utc  # noqa: E402

URL = "https://cdn.tse.jus.br/estatistica/sead/odsele/votacao_secao/votacao_secao_2026_BR.zip"
BRANCO, NULO = "95", "96"
FAIXAS = [0, 10, 20, 30, 40, 50, 60, 70, 80, 90, 100]


def ler(zp: Path, turno: str) -> tuple[dict, dict, list[str]]:
    z = zipfile.ZipFile(zp)
    nomes = [n for n in z.namelist() if n.lower().endswith(".csv")]
    secoes, cands, turnos = defaultdict(lambda: defaultdict(int)), {}, Counter()
    meta = {}
    for nome in nomes:
        with z.open(nome) as f:
            for r in csv.DictReader(io.TextIOWrapper(f, encoding="latin-1", newline=""), delimiter=";"):
                turnos[r.get("NR_TURNO")] += 1
                if r.get("NR_TURNO") != turno or "PRESIDENTE" not in (r.get("DS_CARGO") or "").upper():
                    continue
                k = (r["SG_UF"], r["CD_MUNICIPIO"], r["NR_ZONA"], r["NR_SECAO"])
                nv = r["NR_VOTAVEL"]
                secoes[k][nv] += int(r["QT_VOTOS"] or 0)
                if nv not in (BRANCO, NULO):
                    cands[nv] = r.get("NM_VOTAVEL") or nv
                meta.setdefault(k, r.get("NM_MUNICIPIO"))
    return {k: (dict(v), meta[k]) for k, v in secoes.items()}, cands, [f"{t}: {n}" for t, n in sorted(turnos.items())]


def analisar(secoes: dict, cands: dict) -> tuple[dict, list[list]]:
    nums = sorted(cands, key=lambda n: -sum(v.get(n, 0) for v, _ in secoes.values()))
    venc, faixas, por_uf, zeros, cem = Counter(), {n: Counter() for n in nums}, defaultdict(Counter), Counter(), Counter()
    linhas, sem_validos = [], 0
    for (uf, mun, zona, sec), (v, nm) in secoes.items():
        validos = sum(v.get(n, 0) for n in nums)
        pct = {n: round(100 * v.get(n, 0) / validos, 2) if validos else None for n in nums}
        if not validos:
            sem_validos += 1
            w = "sem votos válidos"
        else:
            m = max(v.get(n, 0) for n in nums)
            top = [n for n in nums if v.get(n, 0) == m]
            w = top[0] if len(top) == 1 else "empate"
            for n in nums:
                p = pct[n]
                faixas[n][min(9, int(p // 10)) if p < 100 else 10] += 1
                if v.get(n, 0) == 0:
                    zeros[n] += 1
                if v.get(n, 0) == validos:
                    cem[n] += 1
        venc[w] += 1
        por_uf[uf][w] += 1
        linhas.append([uf, mun, nm, zona, sec, *[v.get(n, 0) for n in nums], v.get(BRANCO, 0), v.get(NULO, 0), validos, *[pct[n] for n in nums],
                       cands.get(w, w)])
    total = len(secoes)
    rot = lambda n: cands.get(n, n)  # noqa: E731
    resumo = {
        "secoes": total, "candidatos": [{"numero": n, "nome": cands[n], "votos": sum(v.get(n, 0) for v, _ in secoes.values()),
                                         "secoes_vencidas": venc.get(n, 0), "pct_secoes_vencidas": round(100 * venc.get(n, 0) / total, 2) if total else None,
                                         "secoes_com_zero_votos": zeros.get(n, 0), "secoes_com_100pct_dos_validos": cem.get(n, 0),
                                         "distribuicao_pct": {("100%" if i == 10 else f"{FAIXAS[i]}–{FAIXAS[i + 1]}%"): faixas[n].get(i, 0) for i in range(11)}}
                                        for n in nums],
        "empates": venc.get("empate", 0), "sem_votos_validos": sem_validos,
        "brancos": sum(v.get(BRANCO, 0) for v, _ in secoes.values()), "nulos": sum(v.get(NULO, 0) for v, _ in secoes.values()),
        "por_uf": {uf: {"secoes": sum(c.values()), **{rot(k): c[k] for k in c}} for uf, c in sorted(por_uf.items())},
    }
    return resumo, linhas


def main(argv=None) -> int:
    argv = sys.argv[1:] if argv is None else list(argv)
    turno = argv[argv.index("--turno") + 1] if "--turno" in argv else "2"
    dest = Path("data/tse/secoes")
    dest.mkdir(parents=True, exist_ok=True)
    man = {"fonte": URL, "turno": turno, "lido_em_utc": now_utc()}
    try:
        with tempfile.TemporaryDirectory() as t:
            zp = Path(argv[argv.index("--arquivo") + 1]) if "--arquivo" in argv else baixar(URL, Path(t))
            man["bytes"] = zp.stat().st_size
            secoes, cands, turnos = ler(zp, turno)
    except urllib.error.HTTPError as e:
        man["status"] = f"⛔ o TSE ainda não publicou o arquivo (HTTP {e.code})"
        secoes, cands, turnos = {}, {}, []
    except Exception as e:  # noqa: BLE001
        man["status"] = f"⛔ {type(e).__name__}: {str(e)[:200]}"
        secoes, cands, turnos = {}, {}, []
    man["linhas_por_turno_no_arquivo"] = turnos
    if not secoes:
        man.setdefault("status", f"⛔ o arquivo não traz o {turno}º turno para presidente (linhas por turno: {turnos})")
        (dest / f"presidente_{turno}t_resumo.json").write_text(json.dumps(man, ensure_ascii=False, indent=1), encoding="utf-8")
        print(man["status"])
        return 0
    resumo, linhas = analisar(secoes, cands)
    nums = [c["numero"] for c in resumo["candidatos"]]
    with gzip.open(dest / f"presidente_{turno}t_secoes.csv.gz", "wt", encoding="utf-8", newline="") as f:
        w = csv.writer(f, delimiter=";")
        w.writerow(["uf", "cd_municipio", "municipio", "zona", "secao", *[f"votos_{cands[n]}" for n in nums], "brancos", "nulos", "validos",
                    *[f"pct_validos_{cands[n]}" for n in nums], "vencedor"])
        w.writerows(sorted(linhas))
    man.update(status="ok", **resumo)
    (dest / f"presidente_{turno}t_resumo.json").write_text(json.dumps(man, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"{turno}º turno: {resumo['secoes']} seções · " + " · ".join(f"{c['nome']} venceu {c['secoes_vencidas']} ({c['pct_secoes_vencidas']}%), zero votos em "
          f"{c['secoes_com_zero_votos']}, 100% em {c['secoes_com_100pct_dos_validos']}" for c in resumo["candidatos"]) + f" · empates {resumo['empates']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
