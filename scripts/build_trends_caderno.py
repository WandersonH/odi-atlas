#!/usr/bin/env python3
"""Caderno 12 — consolida a coleta mais recente do Google Trends num arquivo para a página.

Entrada: data/trends/AAAA-MM-DD/HHMMSS/ (collect_trends.py; usa a pasta mais recente com status ok)
Saída:   data/trends/caderno.json  (séries e mapa por UF de cada grupo × período, com o tópico usado)
Os valores do Trends são 0–100 relativos DENTRO de cada consulta: não são volume e não se comparam entre consultas.
"""
from __future__ import annotations

import csv
import json
import statistics
import sys
from pathlib import Path


def ultima_execucao(base: Path) -> Path | None:
    pastas = sorted((p for p in base.glob("????-??-??/??????") if (p / "manifesto.json").exists()), reverse=True)
    for p in pastas:
        if json.loads((p / "manifesto.json").read_text(encoding="utf-8")).get("status") == "ok":
            return p
    return None


def ler(p: Path) -> list[dict]:
    return list(csv.DictReader(open(p, encoding="utf-8"), delimiter=";")) if p.exists() else []


def vegetativo(datas: list[str], valores: list[int | None], k: float = 2.0, ks=(1, 2), blocos=(7, 15)) -> dict:
    """Série diária de um termo → média, desvio, mediana, picos (> média + k·desvio), série sem picos (pico → mediana)
    e médias por blocos de N dias a partir do início da série. Ignora dias sem valor."""
    pares = [(d, v) for d, v in zip(datas, valores) if v is not None]
    if len(pares) < 3:
        return {}
    vals = [v for _, v in pares]
    media = statistics.fmean(vals)
    desvio = statistics.pstdev(vals)
    mediana = statistics.median(vals)
    lim = media + k * desvio
    picos = [{"data": d, "valor": v, "z": round((v - media) / desvio, 2) if desvio else None} for d, v in pares if v > lim]
    sem_picos = [mediana if v > lim else v for _, v in pares]
    out = {"media": round(media, 2), "desvio": round(desvio, 2), "mediana": mediana, "k": k, "limite_pico": round(lim, 2),
           "faixa_normal": [round(max(0, media - desvio), 2), round(media + desvio, 2)],
           "picos": picos, "picos_por_k": {str(x): sum(1 for v in vals if v > media + x * desvio) for x in ks},
           "datas": [d for d, _ in pares], "serie_vegetativa": sem_picos, "medias_por_bloco": {}}
    for n in blocos:
        bl = []
        for i in range(0, len(pares), n):
            trecho = pares[i:i + n]
            bl.append({"inicio": trecho[0][0], "fim": trecho[-1][0], "dias": len(trecho),
                       "media": round(statistics.fmean(v for _, v in trecho), 2),
                       "media_sem_picos": round(statistics.fmean(sem_picos[i:i + n]), 2)})
        out["medias_por_bloco"][str(n)] = bl
    return out


def main(argv=None) -> int:
    root = Path(argv[0]) if argv else Path(".")
    base = root / "data/trends"
    pasta = ultima_execucao(base)
    if not pasta:
        print("⛔ nenhuma coleta do Trends com status ok")
        return 1
    m = json.loads((pasta / "manifesto.json").read_text(encoding="utf-8"))
    out = {"schema_version": 1, "coleta_utc": m["run_started_utc"], "pasta": str(pasta.relative_to(root)),
           "aviso": m.get("aviso_metodologico", ""), "nota": m["config"].get("nota", ""),
           "nota_relacionados": (m["config"].get("relacionados") or {}).get("nota", ""),
           "nota_vegetativo": (m["config"].get("metodo_vegetativo") or {}).get("nota", ""), "consultas": []}
    for c in m["consultas"]:
        if c.get("status") != "ok":
            continue
        stem = f"{c['grupo']}__{c['periodo'].replace(' ', '_')}"
        serie = ler(pasta / f"{stem}__serie.csv")
        uf = ler(pasta / f"{stem}__uf.csv")
        rel = ler(pasta / f"{stem}__relacionados.csv")

        termos = c["termos"]
        mv = m["config"].get("metodo_vegetativo") or {}
        serie_ok = [{"t": r["timestamp_utc"], "v": [int(r[t]) if r.get(t, "").strip() != "" else None for t in termos]}
                    for r in serie if r.get("parcial") not in ("1", "True", "true")]
        diaria = c["periodo"] != "now 7-d"  # séries por hora não entram no método (picos de hora não são agenda diária)
        out["consultas"].append({
            "grupo": c["grupo"], "periodo": c["periodo"], "termos": termos,
            "itens": [{"rotulo": i["rotulo"], "modo": i["modo"], "tipo": i.get("topico_tipo", ""), "consulta": i["consulta"]} for i in c["itens"]],
            "serie": [{"t": r["timestamp_utc"], "parcial": r.get("parcial") in ("1", "True", "true"),
                       "v": [int(r[t]) if r.get(t, "").strip() != "" else None for t in termos]} for r in serie],
            "uf": [{"uf": r["geo_code"].replace("BR-", ""), "nome": r["geo_nome"],
                    "v": [int(r[t]) if r.get(t, "").strip() != "" else None for t in termos]} for r in uf],
            "vegetativo": ({t: vegetativo([p["t"][:10] for p in serie_ok], [p["v"][i] for p in serie_ok],
                                          k=mv.get("k_desvio", 2), ks=tuple(mv.get("k_sensibilidade", [1, 2])),
                                          blocos=tuple(mv.get("periodos_media_dias", [7, 15])))
                            for i, t in enumerate(termos)} if diaria else {}),
            "relacionados": [{"termo": r["termo"], "tipo": r["tipo"], "lista": r["lista"], "pos": int(r["posicao"]),
                              "texto": r["texto"], "tipo_assunto": r["tipo_assunto"], "valor": r["valor"],
                              "rotulo": r["valor_formatado"]} for r in rel],
            "arquivos": {"serie": f"{out['pasta']}/{stem}__serie.csv", "uf": f"{out['pasta']}/{stem}__uf.csv",
                         **({"relacionados": f"{out['pasta']}/{stem}__relacionados.csv"} if rel else {})}})
    (base / "caderno.json").write_text(json.dumps(out, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(f"trends: {len(out['consultas'])} consultas da coleta {out['coleta_utc']} ({out['pasta']})")
    return 0 if out["consultas"] else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
