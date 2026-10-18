#!/usr/bin/env python3
"""Assuntos do momento no X (Brasil) — página pública getdaytrends.com/brazil/, de hora em hora. Grátis, sem login.

O X não tem API gratuita de trends; o getdaytrends publica a lista do X por país com o volume de posts quando o X informa.
Saída: data/x/trends/AAAA-MM-DD.csv (uma linha por assunto e coleta) e data/x/trends/latest.json (resumo do dia: top 20,
assuntos que citam os candidatos, horas no topo).
"""
from __future__ import annotations

import csv
import datetime as dt
import html
import json
import re
import sys
import urllib.parse
import urllib.request
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from net import now_utc  # noqa: E402

URL = "https://getdaytrends.com/brazil/"
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
COLS = ["coletado_em", "posicao", "assunto", "volume", "volume_texto", "url"]
CAND = {"Lula": re.compile(r"lula|petista|\bpt\b|alckmin|faz o l", re.I),
        "Flávio Bolsonaro": re.compile(r"fl[aá]vio|bolsonaro|\bpl\b|gaspar|vote ?22", re.I)}


def volume(txt: str):
    m = re.search(r"([\d.,]+)\s*([KkMm]?)", txt or "")
    if not m:
        return None
    v = float(m.group(1).replace(",", ""))
    return int(v * {"k": 1e3, "m": 1e6}.get(m.group(2).lower(), 1))


def parse(pagina: str) -> list[dict]:
    """Primeira tabela da página (assuntos de agora): link /brazil/trend/<x>/ e o volume ('87.1K tweets') logo depois."""
    corpo = pagina.split("</table>")[0]
    out = []
    for m in re.finditer(r'<a[^>]+href="(/brazil/trend/[^"]+)"[^>]*>(.*?)</a>(.*?)</tr>', corpo, re.S):
        nome = html.unescape(re.sub(r"<[^>]+>", "", m.group(2))).strip()
        vt = re.search(r"([\d.,]+\s*[KkMm]?)\s*(?:tweets|posts)", m.group(3), re.I)
        if nome:
            out.append({"assunto": nome, "volume_texto": vt.group(0) if vt else "", "volume": volume(vt.group(1)) if vt else None,
                        "url": "https://x.com/search?q=" + urllib.parse.quote(nome)})
    for i, r in enumerate(out, 1):
        r["posicao"] = i
    return out


def resumo(rows: list[dict], dia: str) -> dict:
    horas = defaultdict(set)
    melhor = {}
    for r in rows:
        horas[r["assunto"]].add(r["coletado_em"][:13])
        p = int(r["posicao"])
        if r["assunto"] not in melhor or p < melhor[r["assunto"]]["melhor_posicao"]:
            melhor[r["assunto"]] = {"assunto": r["assunto"], "melhor_posicao": p, "volume_max": None, "url": r["url"]}
        v = int(r["volume"]) if str(r["volume"]).isdigit() else None
        if v and (melhor[r["assunto"]]["volume_max"] or 0) < v:
            melhor[r["assunto"]]["volume_max"] = v
    itens = sorted(melhor.values(), key=lambda x: (x["melhor_posicao"], -(x["volume_max"] or 0)))
    for x in itens:
        x["horas_na_lista"] = len(horas[x["assunto"]])
        x["cita"] = [c for c, rx in CAND.items() if rx.search(x["assunto"])]
    return {"dia": dia, "coletas": len({r["coletado_em"] for r in rows}), "top": itens[:30],
            "citam_candidatos": [x for x in itens if x["cita"]], "fonte": URL,
            "nota": "Lista de assuntos do momento do X no Brasil publicada pelo getdaytrends.com (sem login), lida de hora em hora. "
                    "Volume = número de posts quando o X informa. 'Cita' = o nome do assunto contém termos dos candidatos (dicionário aberto)."}


def main(argv=None, pagina: str | None = None) -> int:
    root = Path(argv[0]) if argv else Path(".")
    agora = now_utc()
    if pagina is None:
        req = urllib.request.Request(URL, headers={"User-Agent": UA, "Accept-Language": "pt-BR,pt;q=0.9"})
        with urllib.request.urlopen(req, timeout=60) as r:
            pagina = r.read().decode("utf-8", "replace")
    itens = parse(pagina)
    if not itens:  # diagnóstico do formato da página (sem dados pessoais: é a lista pública de assuntos)
        i = pagina.find("/trend/")
        print(f"página com {len(pagina)} caracteres; 1º '/trend/' em {i}: " + re.sub(r"\s+", " ", pagina[max(0, i - 300):i + 500]))
        (root / "data/x/trends").mkdir(parents=True, exist_ok=True)
        (root / "data/x/trends/diag_formato.txt").write_text(pagina[:200000], encoding="utf-8")
    pasta = root / "data/x/trends"
    pasta.mkdir(parents=True, exist_ok=True)
    dia = (dt.datetime.fromisoformat(agora.replace("Z", "+00:00")) - dt.timedelta(hours=3)).strftime("%Y-%m-%d")  # dia em Brasília
    arq = pasta / f"{dia}.csv"
    rows = list(csv.DictReader(open(arq, encoding="utf-8"), delimiter=";")) if arq.exists() else []
    rows += [{"coletado_em": agora, **{k: r.get(k, "") for k in COLS if k != "coletado_em"}} for r in itens]
    with open(arq, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, COLS, delimiter=";", lineterminator="\n")
        w.writeheader()
        w.writerows(rows)
    res = resumo(rows, dia)
    (pasta / "latest.json").write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"trends X: {len(itens)} assuntos agora · {res['coletas']} coletas hoje · {len(res['citam_candidatos'])} citam candidatos · "
          f"1º: {itens[0]['assunto'] if itens else '—'}")
    return 0 if itens else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
