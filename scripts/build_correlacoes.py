"""Correlações territoriais (município): perfil do eleitorado × voto presidencial × participação. Só agregados oficiais do TSE.

Pedido do responsável (02/11/2026, ideias de correlação; 03/11/2026: "as correlações acho que deveriam entrar aqui",
página "Escala digital em contexto eleitoral"). Entradas (todas já no repositório):
- data/tse/presidente_{1t,2t}_{2022,2026}_munzona.csv.gz — votos nominais válidos por município (TSE);
- data/tse/perfil/eleitorado_2026_municipios.csv e eleitorado_2026_municipios_perfil.csv.gz — cadastro 2026 (TSE);
- data/tse/perfil/comparecimento_2026_municipios.csv — comparecimento do 1º turno (TSE);
- data/tse/auditoria_urna/2t/municipios.csv — 2º turno: aptos, comparecimento, brancos, nulos, liberados sem biometria (BU/TSE).
Saída: data/tse/correlacoes/municipios.csv (um município por linha, indicadores em %) e resumo.json (matriz de
correlação de Pearson, Spearman e Pearson dentro da UF; n; universo). Correlação ecológica: descreve municípios, não
pessoas — não permite dizer que mulheres, jovens etc. votaram de um jeito.
"""
from __future__ import annotations

import csv
import gzip
import json
import math
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from net import now_utc  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
TSE = ROOT / "data/tse"
OUT = TSE / "correlacoes"

# (chave, rótulo, grupo, papel) — papel x = característica do município, y = resultado eleitoral
IND = [
    ("lula_2t_2026", "Lula, % válidos, 2º turno 2026", "Voto", "y"),
    ("lula_1t_2026", "Lula, % válidos, 1º turno 2026", "Voto", "y"),
    ("d_lula_2t_22_26", "Lula 2º turno: 2026 − 2022 (p.p.)", "Voto", "y"),
    ("d_lula_1t_2t_2026", "Lula 2026: 2º − 1º turno (p.p.)", "Voto", "y"),
    ("terceira_via_1t_2026", "Fora de 13 e 22, % válidos, 1º turno 2026", "Voto", "y"),
    ("abst_1t_2026", "Abstenção, 1º turno 2026 (%)", "Participação", "y"),
    ("abst_2t_2026", "Abstenção, 2º turno 2026 (%)", "Participação", "y"),
    ("d_abst_1t_2t", "Abstenção: 2º − 1º turno (p.p.)", "Participação", "y"),
    ("bn_2t_2026", "Brancos + nulos, 2º turno 2026 (% comparecimento)", "Participação", "y"),
    ("mulheres", "Mulheres no eleitorado (%)", "Perfil", "x"),
    ("jovens_16_24", "16 a 24 anos (%)", "Perfil", "x"),
    ("idosos_60", "60 anos ou mais (%)", "Perfil", "x"),
    ("ate_fund_inc", "Até fundamental incompleto (%)", "Perfil", "x"),
    ("superior", "Superior completo (%)", "Perfil", "x"),
    ("pretos_pardos", "Pretos e pardos (% dos que declararam)", "Perfil", "x"),
    ("raca_declarada", "Cor/raça declarada no cadastro (%)", "Perfil", "x"),
    ("biometria", "Eleitorado com biometria (%)", "Perfil", "x"),
    ("sem_bio_2t", "Liberados sem biometria, 2º turno (% comparecimento)", "Perfil", "x"),
    ("log_eleitorado", "Tamanho do eleitorado (log10)", "Perfil", "x"),
]


def cod(v) -> int | None:
    try:
        return int(str(v).strip())
    except (TypeError, ValueError):
        return None


def votos(arq: Path) -> dict[int, dict]:
    m: dict[int, dict] = defaultdict(lambda: {"uf": "", "nome": "", "v": defaultdict(int)})
    if not arq.exists():
        return {}
    with gzip.open(arq, "rt", encoding="utf-8", errors="replace", newline="") as f:
        for r in csv.DictReader(f, delimiter=";"):
            if r.get("SG_UF") in ("ZZ", "VT", "BR") or "Presidente" not in (r.get("DS_CARGO") or "Presidente"):
                continue
            c = cod(r.get("CD_MUNICIPIO"))
            if c is None:
                continue
            x = m[c]
            x["uf"], x["nome"] = r.get("SG_UF", ""), r.get("NM_MUNICIPIO", "")
            x["v"][str(r.get("NR_CANDIDATO"))] += cod(r.get("QT_VOTOS_NOMINAIS_VALIDOS")) or 0
    return m


def pct(a, b):
    return round(100 * a / b, 3) if b else None


def perfil_mun() -> dict[int, dict]:
    arq = TSE / "perfil/eleitorado_2026_municipios_perfil.csv.gz"
    acc: dict[int, dict] = defaultdict(lambda: defaultdict(int))
    if not arq.exists():
        return {}
    with gzip.open(arq, "rt", encoding="utf-8", newline="") as f:
        r = csv.reader(f, delimiter=";")
        next(r)
        for _t, _uf, c, dim, val, q in r:
            acc[cod(c)][(dim, val)] += int(q or 0)
    out = {}
    for c, d in acc.items():
        g = lambda dim: {v: q for (dd, v), q in d.items() if dd == dim}  # noqa: E731
        gen, ida, esc, rac = g("DS_GENERO"), g("DS_FAIXA_ETARIA"), g("DS_GRAU_ESCOLARIDADE"), g("DS_RACA_COR")
        tot = sum(gen.values())
        def idade(v: str) -> int | None:
            n = v.split(" ")[0]
            return int(n) if n.isdigit() else None
        jov = sum(q for v, q in ida.items() if (idade(v) is not None and idade(v) <= 24))
        ido = sum(q for v, q in ida.items() if (idade(v) is not None and idade(v) >= 60))
        bx = sum(esc.get(k, 0) for k in ("ANALFABETO", "LÊ E ESCREVE", "ENSINO FUNDAMENTAL INCOMPLETO"))
        dec = sum(q for v, q in rac.items() if v.upper() != "NÃO INFORMADO")
        out[c] = {"mulheres": pct(gen.get("FEMININO", 0), tot), "jovens_16_24": pct(jov, tot), "idosos_60": pct(ido, tot),
                  "ate_fund_inc": pct(bx, tot), "superior": pct(esc.get("SUPERIOR COMPLETO", 0), tot),
                  "pretos_pardos": pct(rac.get("Preta", 0) + rac.get("Parda", 0), dec), "raca_declarada": pct(dec, tot)}
    return out


def ler_csv(arq: Path):
    if not arq.exists():
        return []
    with open(arq, encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f, delimiter=";"))


def montar() -> list[dict]:
    v = {k: votos(TSE / f"presidente_{k}_munzona.csv.gz") for k in ("1t_2022", "2t_2022", "1t_2026", "2t_2026")}
    perf = perfil_mun()
    ele = {cod(r["cd_municipio_tse"]): r for r in ler_csv(TSE / "perfil/eleitorado_2026_municipios.csv")}
    comp1 = {cod(r["cd_municipio_tse"]): r for r in ler_csv(TSE / "perfil/comparecimento_2026_municipios.csv") if r["turno"] == "1"}
    urna = {cod(r["cd_municipio_tse"]): r for r in ler_csv(TSE / "auditoria_urna/2t/municipios.csv")}
    linhas = []
    for c, base in sorted(v["2t_2026"].items()):
        val = lambda k: sum(v[k][c]["v"].values()) if c in v[k] else 0  # noqa: E731
        lula = lambda k: v[k][c]["v"].get("13", 0) if c in v[k] else 0  # noqa: E731
        r = {"cd_municipio_tse": c, "uf": base["uf"], "municipio": base["nome"]}
        r["lula_2t_2026"] = pct(lula("2t_2026"), val("2t_2026"))
        r["lula_1t_2026"] = pct(lula("1t_2026"), val("1t_2026"))
        l22 = pct(lula("2t_2022"), val("2t_2022"))
        r["d_lula_2t_22_26"] = round(r["lula_2t_2026"] - l22, 3) if (r["lula_2t_2026"] is not None and l22 is not None) else None
        r["d_lula_1t_2t_2026"] = round(r["lula_2t_2026"] - r["lula_1t_2026"], 3) if (r["lula_2t_2026"] is not None and r["lula_1t_2026"] is not None) else None
        if c in v["1t_2026"]:
            vv = v["1t_2026"][c]["v"]
            r["terceira_via_1t_2026"] = pct(sum(q for n, q in vv.items() if n not in ("13", "22")), val("1t_2026"))
        else:
            r["terceira_via_1t_2026"] = None
        a1 = comp1.get(c)
        r["abst_1t_2026"] = pct(int(a1["QT_ABSTENCAO"]), int(a1["QT_APTOS"])) if a1 and int(a1["QT_APTOS"] or 0) else None
        u = urna.get(c)
        if u and int(u["aptos"] or 0):
            ap, cm = int(u["aptos"]), int(u["comparecimento"])
            r["abst_2t_2026"] = pct(ap - cm, ap)
            r["bn_2t_2026"] = pct(int(u["brancos"]) + int(u["nulos"]), cm)
            r["sem_bio_2t"] = pct(int(u["sem_biometria"]), cm)
        else:
            r["abst_2t_2026"] = r["bn_2t_2026"] = r["sem_bio_2t"] = None
        r["d_abst_1t_2t"] = round(r["abst_2t_2026"] - r["abst_1t_2026"], 3) if (r["abst_2t_2026"] is not None and r["abst_1t_2026"] is not None) else None
        e = ele.get(c)
        n_ele = int(e["QT_ELEITORES"]) if e else 0
        r["eleitorado"] = n_ele or None
        r["biometria"] = pct(int(e["QT_ELEITORES_BIOMETRIA"]), n_ele) if n_ele else None
        r["log_eleitorado"] = round(math.log10(n_ele), 4) if n_ele else None
        r.update(perf.get(c, {k: None for k in ("mulheres", "jovens_16_24", "idosos_60", "ate_fund_inc", "superior", "pretos_pardos", "raca_declarada")}))
        linhas.append(r)
    return linhas


def pearson(xs, ys):
    n = len(xs)
    if n < 3:
        return None
    mx, my = sum(xs) / n, sum(ys) / n
    sxy = sum((a - mx) * (b - my) for a, b in zip(xs, ys))
    sxx = sum((a - mx) ** 2 for a in xs)
    syy = sum((b - my) ** 2 for b in ys)
    return round(sxy / math.sqrt(sxx * syy), 3) if sxx and syy else None


def postos(xs):
    ordem = sorted(range(len(xs)), key=lambda i: xs[i])
    rk = [0.0] * len(xs)
    i = 0
    while i < len(ordem):
        j = i
        while j + 1 < len(ordem) and xs[ordem[j + 1]] == xs[ordem[i]]:
            j += 1
        for k in range(i, j + 1):
            rk[ordem[k]] = (i + j) / 2 + 1
        i = j + 1
    return rk


def correlacoes(linhas: list[dict], a: str, b: str) -> dict:
    par = [(r[a], r[b], r["uf"]) for r in linhas if r.get(a) is not None and r.get(b) is not None]
    xs, ys = [p[0] for p in par], [p[1] for p in par]
    # dentro da UF: tira a média da UF de cada variável (controla diferenças regionais grosseiras)
    gx, gy = defaultdict(list), defaultdict(list)
    for x, y, u in par:
        gx[u].append(x)
        gy[u].append(y)
    mx = {u: sum(v) / len(v) for u, v in gx.items()}
    my = {u: sum(v) / len(v) for u, v in gy.items()}
    return {"n": len(par), "pearson": pearson(xs, ys), "spearman": pearson(postos(xs), postos(ys)),
            "dentro_uf": pearson([x - mx[u] for x, _, u in par], [y - my[u] for _, y, u in par])}


def main() -> int:
    linhas = montar()
    if not linhas:
        print("⛔ sem votos do 2º turno 2026 por município")
        return 1
    OUT.mkdir(parents=True, exist_ok=True)
    cols = ["cd_municipio_tse", "uf", "municipio", "eleitorado", *[k for k, *_ in IND]]
    with open(OUT / "municipios.csv", "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f, delimiter=";")
        w.writerow(cols)
        for r in linhas:
            w.writerow(["" if r.get(c) is None else r.get(c) for c in cols])
    ks = [k for k, *_ in IND]
    matriz = {a: {b: correlacoes(linhas, a, b) for b in ks if b != a} for a in ks}
    cobertura = {k: sum(1 for r in linhas if r.get(k) is not None) for k in ks}
    destaques = sorted(({"x": a, "y": b, **matriz[a][b]} for a, _, _, pa in IND if pa == "x"
                        for b, _, _, pb in IND if pb == "y" and matriz[a][b]["pearson"] is not None),
                       key=lambda d: -abs(d["pearson"]))
    out = {"schema_version": 1, "gerado_em_utc": now_utc(),
           "universo": f"{len(linhas)} municípios com votação de 2º turno 2026 (TSE, votos por município e zona; exterior excluído). Não é amostra: todos os municípios publicados.",
           "cobertura": cobertura,
           "indicadores": [{"chave": k, "rotulo": r, "grupo": g, "papel": p} for k, r, g, p in IND],
           "matriz": matriz, "destaques": destaques[:12],
           "fontes": ["https://dadosabertos.tse.jus.br/dataset/resultados-2026", "https://dadosabertos.tse.jus.br/dataset/resultados-2022",
                      "https://dadosabertos.tse.jus.br/dataset/eleitorado-2026", "https://dadosabertos.tse.jus.br/dataset/comparecimento-e-abstencao-2026"],
           "nota": "Correlação ecológica entre municípios: mostra que municípios com mais X tendem a ter mais (ou menos) Y. Não diz como cada grupo de pessoas votou nem indica causa. 'Dentro da UF' compara municípios com a média do próprio estado. O perfil é o cadastro de 2026 (o de 2022 não está no repositório)."}
    (OUT / "resumo.json").write_text(json.dumps(out, ensure_ascii=False, separators=(",", ":")) + "\n", encoding="utf-8")
    print(f"{len(linhas)} municípios · cobertura {cobertura}")
    for d in destaques[:12]:
        print(f"{d['x']} × {d['y']}: r={d['pearson']} ρ={d['spearman']} dentro_uf={d['dentro_uf']} n={d['n']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
