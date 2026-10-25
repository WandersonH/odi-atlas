#!/usr/bin/env python3
"""2º turno × 1º turno, município a município e UF a UF, em tempo real (pedido de 25/10/2026, 19h43).

- 2º turno: divulgação oficial do TSE (resultados.tse.jus.br, eleição 6258). Para cada UF, o arquivo de abrangências
  (<uf>-e006258-ab.json) diz o horário da última totalização de cada município; só os municípios que mudaram desde a leitura
  anterior são baixados de novo (<uf><mun>-c0001-e006258-u.json). Estrutura conferida pela sonda de 25/10, 19h4x.
- 1º turno: totalização oficial por município e zona (Dados Abertos, data/tse/presidente_1t_2026_munzona.csv.gz), votos
  nominais válidos de Lula (13) e Flávio Bolsonaro (22) sobre o total de válidos do município.
- Comparação: % dos válidos de cada um no 1º e no 2º turno e a diferença em pontos percentuais. No 1º turno havia 12
  candidatos; no 2º, dois: a diferença mostra para onde foram os votos, não "virada" de eleitor individual.
Saída: data/tse/segundo_turno/municipios.json (compacto) e base_1t.json (cache do 1º turno).
"""
from __future__ import annotations

import csv
import gzip
import json
import sys
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from collect_resultados_2t import BASE, get, num, pct, resumo  # noqa: E402
from net import now_utc  # noqa: E402

L, F = "13", "22"


def base_1t(root: Path) -> dict:
    p = root / "data/tse/segundo_turno/base_1t.json"
    if p.exists():
        return json.loads(p.read_text(encoding="utf-8"))
    mun = defaultdict(lambda: {"v": 0, L: 0, F: 0})
    nome = {}
    for r in csv.DictReader(gzip.open(root / "data/tse/presidente_1t_2026_munzona.csv.gz", "rt", encoding="utf-8"), delimiter=";"):
        if r["CD_CARGO"] != "1" or r["NM_TIPO_DESTINACAO_VOTOS"] != "Válido":
            continue
        k = r["CD_MUNICIPIO"].zfill(5)
        v = int(r["QT_VOTOS_NOMINAIS_VALIDOS"] or 0)
        mun[k]["v"] += v
        if r["NR_CANDIDATO"] in (L, F):
            mun[k][r["NR_CANDIDATO"]] += v
        nome[k] = (r["SG_UF"], r["NM_MUNICIPIO"])
    out = {k: {"uf": nome[k][0], "nome": nome[k][1], "validos": m["v"], "l": m[L], "f": m[F]} for k, m in mun.items()}
    p.write_text(json.dumps(out, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    return out


def votos(r: dict) -> dict:
    c = {x["numero"]: x for x in r["candidatos"]}
    return {"pst": r["pct_secoes_totalizadas"], "l": (c.get(L) or {}).get("votos"), "f": (c.get(F) or {}).get("votos"),
            "validos": r["validos"], "pct_abst": r["pct_abstencao"], "brancos": r["brancos"], "nulos": r["nulos"]}


def main(root: Path = Path("."), pleito: str = "ele2026", ele: str = "6258") -> int:
    pasta = root / "data/tse/segundo_turno"
    pasta.mkdir(parents=True, exist_ok=True)
    agora = now_utc()
    b1 = base_1t(root)
    cm_p = pasta / "mun_cm.json"
    if not cm_p.exists():
        cm_p.write_text(json.dumps(get(f"{BASE}/{pleito}/{ele}/config/mun-e{int(ele):06d}-cm.json"), ensure_ascii=False), encoding="utf-8")
    cm = json.loads(cm_p.read_text(encoding="utf-8"))
    ant_p = pasta / "municipios.json"
    ant = json.loads(ant_p.read_text(encoding="utf-8")) if ant_p.exists() else {"m": {}}
    M = ant.get("m", {})
    pendentes, erros = [], 0
    for uf in cm["abr"]:
        sg = uf["cd"].lower()
        try:
            ab = get(f"{BASE}/{pleito}/{ele}/dados/{sg}/{sg}-e{int(ele):06d}-ab.json", timeout=40)
            ht = {a["cdabr"]: f"{a.get('dt', '')} {a.get('ht', '')}".strip() for a in ab.get("abr", []) if a.get("tpabr") == "mun"}
        except Exception:  # noqa: BLE001
            ht, erros = {}, erros + 1
        for mu in uf.get("mu", []):
            k = mu["cd"]
            reg = M.get(k)
            novo_ht = ht.get(k)
            if reg is None or (novo_ht and novo_ht != reg.get("ht")) or (not novo_ht and (reg.get("pst") or 0) < 100):
                pendentes.append((sg, k, mu, novo_ht))
            M.setdefault(k, {"uf": uf["cd"].upper(), "nome": mu.get("nm"), "ibge": mu.get("cdi")})

    import time
    tipos = {}

    limite = time.monotonic() + 150  # o laço do resultado nacional não pode esperar: até 2,5 min por leitura
    falhas_seguidas = [0]

    def baixa(t):
        sg, k, mu, novo_ht = t
        if time.monotonic() > limite or falhas_seguidas[0] > 40:  # sem tempo, ou o TSE recusando em sequência: fica para a próxima
            return k, None, None, "adiado"
        for tent in range(2):  # o TSE limita a frequência (403/429): espera e tenta de novo
            try:
                v = votos(resumo(get(f"{BASE}/{pleito}/{ele}/dados/{sg}/{sg}{k}-c0001-e{int(ele):06d}-u.json", timeout=15)))
                falhas_seguidas[0] = 0
                return k, novo_ht, v, None
            except Exception as e:  # noqa: BLE001
                err = f"{type(e).__name__} {getattr(e, 'code', '')}".strip()
                if getattr(e, "code", None) == 404:
                    return k, None, None, err
                time.sleep(1 + tent)
        falhas_seguidas[0] += 1
        return k, None, None, err
    # prioridade: municípios ainda sem nenhum dado, depois os maiores (válidos no 1º turno)
    pendentes.sort(key=lambda t: (M.get(t[1], {}).get("l") is not None, -(b1.get(t[1], {}).get("validos") or 0)))
    with ThreadPoolExecutor(max_workers=8) as ex:
        for k, novo_ht, v, err in ex.map(baixa, pendentes):
            if v is None:
                erros += 1
                tipos[err] = tipos.get(err, 0) + 1
                continue
            M[k].update(v)
            M[k]["ht"] = novo_ht or M[k].get("ht")
    # comparação com o 1º turno
    for k, m in M.items():
        b = b1.get(k)
        if b and b["validos"]:
            m["l1"], m["f1"] = round(100 * b["l"] / b["validos"], 2), round(100 * b["f"] / b["validos"], 2)
            m["v1"] = b["validos"]
        tot = (m.get("l") or 0) + (m.get("f") or 0)
        if tot:
            m["l2"], m["f2"] = round(100 * m["l"] / tot, 2), round(100 * m["f"] / tot, 2)
    # UFs (soma dos municípios: 2º turno; 1º turno da base)
    U = defaultdict(lambda: {"l": 0, "f": 0, "v1": 0, "l1": 0, "f1": 0, "mun": 0, "mun_100": 0})
    for k, m in M.items():
        u = U[m["uf"]]
        u["l"] += m.get("l") or 0
        u["f"] += m.get("f") or 0
        u["mun"] += 1
        u["mun_100"] += 1 if (m.get("pst") or 0) >= 100 else 0
        b = b1.get(k)
        if b:
            u["v1"] += b["validos"]
            u["l1"] += b["l"]
            u["f1"] += b["f"]
    ufs = {}
    for s, u in U.items():
        t2 = u["l"] + u["f"]
        ufs[s] = {"l2": round(100 * u["l"] / t2, 2) if t2 else None, "f2": round(100 * u["f"] / t2, 2) if t2 else None,
                  "l1": round(100 * u["l1"] / u["v1"], 2) if u["v1"] else None, "f1": round(100 * u["f1"] / u["v1"], 2) if u["v1"] else None,
                  "votos_l": u["l"], "votos_f": u["f"], "municipios": u["mun"], "municipios_100": u["mun_100"]}
    # 2º turno da UF: o número oficial do arquivo da UF (resultado.json), não a soma dos municípios já baixados
    rp = pasta / "resultado.json"
    if rp.exists():
        for sg, r in (json.loads(rp.read_text(encoding="utf-8")).get("ufs") or {}).items():
            c = {x["numero"]: x for x in r.get("candidatos", [])}
            if sg in ufs and c.get(L) and c.get(F):
                ufs[sg].update(l2=c[L]["pct"], f2=c[F]["pct"], votos_l=c[L]["votos"], votos_f=c[F]["votos"], pst=r.get("pct_secoes_totalizadas"))
    lidos = sum(1 for m in M.values() if m.get("l") is not None)
    out = {"lido_em_utc": agora, "fonte_2t": f"{BASE}/{pleito}/{ele}/dados/<uf>/<uf><mun>-c0001-e{int(ele):06d}-u.json",
           "fonte_1t": "TSE, Dados Abertos: votacao_candidato_munzona_2026, 1º turno (data/tse/presidente_1t_2026_munzona.csv.gz)",
           "nota": "Percentuais sobre os votos válidos. No 1º turno, % de Lula e de Flávio entre os válidos de 12 candidatos; no 2º, entre os "
                   "dois. A diferença (pontos percentuais) mostra a redistribuição dos votos, não a mudança de voto de cada eleitor. "
                   "A soma das UFs usa os municípios (exterior em ZZ).",
           "municipios_total": len(M), "municipios_lidos": lidos, "baixados_nesta_leitura": len(pendentes) - erros, "erros": erros, "erros_por_tipo": tipos, "ufs": ufs, "m": M}
    ant_p.write_text(json.dumps(out, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(f"municípios: {lidos} de {len(M)} com dados · baixados agora {len(pendentes) - erros} · erros {erros} {tipos}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
