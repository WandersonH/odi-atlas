#!/usr/bin/env python3
"""Saturação da coleta de um caso: quanto cada rodada ainda trouxe de publicação nova.

Pedido do responsável (28/10/2026, 01h14): "preciso de uma coleta que me traga uma real ideia desse universo de temática".
As plataformas não informam o total de publicações sobre o tema (regra 9: universo ⛔, nunca estimado). O indício de cobertura é a
saturação: ampliando o vocabulário (rodadas de termos descobertos nos próprios textos), quantas publicações ainda não estavam no acervo.
Quando novas buscas trazem quase só o que já tinha sido lido, a busca da plataforma está perto do que ela alcança sobre o tema.

Lê os brutos do privado (ODI_INTERNO_DIR/casos/<caso>/bruto_<rede>_<AAAAMMDDTHHMMSSZ>.jsonl.gz, um por coleta e rede, em ordem de
tempo), identifica cada publicação pelo mesmo id do coletor (collect_casos.norm) e só conta as do período do caso.
Público: data/casos/<caso>/saturacao.json (só contagens por coleta, rede e termo).
Uso: python scripts/saturacao_caso.py --caso 014
"""
from __future__ import annotations

import gzip
import json
import os
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from collect_casos import norm  # noqa: E402
from net import now_utc  # noqa: E402

RX = re.compile(r"bruto_([a-z]+)_(\d{8}T\d{6}Z)\.jsonl\.gz$")


def main(argv=None) -> int:
    argv = sys.argv[1:] if argv is None else list(argv)
    caso = argv[argv.index("--caso") + 1] if "--caso" in argv else "014"
    interno = os.environ.get("ODI_INTERNO_DIR")
    if not interno:
        print("⛔ ODI_INTERNO_DIR ausente")
        return 1
    cfg = next(c for c in json.loads(Path("data/config/casos.json").read_text(encoding="utf-8"))["casos"] if c["id"] == caso)
    priv = Path(interno) / "casos" / caso
    arqs = sorted((f for f in priv.glob("bruto_*.jsonl.gz") if RX.search(f.name)), key=lambda f: RX.search(f.name).group(2))
    vistos, coletas, acumulado = set(), [], 0
    for f in arqs:
        rede, stamp = RX.search(f.name).groups()
        por_termo, novos_c, itens_c = {}, 0, 0
        for linha in gzip.open(f, "rt", encoding="utf-8"):
            x = json.loads(linha)
            try:
                r = norm(rede, x, x.get("_termo") or "", "")
            except ValueError:
                continue
            if not r or (r.get("publicado_em") or "9")[:10] < cfg["desde"]:
                continue
            k = (rede, r["item_id"])
            t = por_termo.setdefault(x.get("_termo") or "?", {"itens": 0, "novos": 0})
            t["itens"] += 1
            itens_c += 1
            if k not in vistos:
                vistos.add(k)
                t["novos"] += 1
                novos_c += 1
        acumulado += novos_c
        coletas.append({"coleta_utc": f"{stamp[:4]}-{stamp[4:6]}-{stamp[6:8]}T{stamp[9:11]}:{stamp[11:13]}Z", "rede": rede, "itens_no_periodo": itens_c,
                        "novos": novos_c, "pct_novos": round(100 * novos_c / itens_c, 1) if itens_c else None, "acumulado": acumulado,
                        "por_termo": {k: {**v, "pct_novos": round(100 * v["novos"] / v["itens"], 1) if v["itens"] else None} for k, v in por_termo.items()}})
    out = {"caso": caso, "gerado_em_utc": now_utc(), "publicacoes_unicas": len(vistos), "coletas": coletas,
           "o_que_e": "Cada linha é uma coleta (rede × momento): publicações do período lidas, quantas ainda não estavam no acervo e o acumulado. "
                      "Percentual de novas perto de zero em buscas com vocabulário novo indica saturação: a busca da plataforma está perto do que alcança "
                      "sobre o tema. Não é o universo (que as plataformas não informam), é o limite do que as buscas encontram."}
    dest = Path("data/casos") / caso
    dest.mkdir(parents=True, exist_ok=True)
    (dest / "saturacao.json").write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"caso {caso} saturação: {len(coletas)} coletas · {len(vistos)} publicações únicas · última: "
          + (f"{coletas[-1]['rede']} {coletas[-1]['novos']} novas de {coletas[-1]['itens_no_periodo']}" if coletas else "—"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
