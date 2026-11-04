#!/usr/bin/env python3
"""Processos da Justiça Eleitoral ligados a um caso, a partir dos dados abertos do TSE já lidos pelo Atlas (collect_processual.py).

Pedido do responsável (04/11/2026, 01h16, caso 034): "você consegue consultar processos que temos deste e sobre IA aqui?
https://consultaunificadapje.tse.jus.br/ e anexar documentos". A consulta pública do PJe pede código de imagem (CAPTCHA), que o
Atlas não contorna; os metadados (número, classe, assunto, tribunal, autuação, decisões, partes candidatas à Presidência) vêm do
Portal de Dados Abertos do TSE (processual 2026), sem o texto das peças.
Entrada: data/tse/processual/resumo.json → temas["inteligência artificial ou conteúdo sintético"] (todos os processos do tema).
Saída: data/casos/<caso>/processos.json — universo (processos de 2026 no arquivo do TSE), recorte (IA ou deep fake no assunto),
contagens por assunto, tribunal, mês de autuação e classe, decisões e baixa, processos com candidatura à Presidência como parte
(com o link da consulta pública), e o processo do caso em destaque. Peças baixadas à mão pelo responsável ficam listadas em
data/casos/<caso>/pecas.json (texto só no privado).
Uso: python scripts/processos_caso.py --caso 034 [--destaque 0601315-97.2026.6.00.0000]
"""
from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TEMA = "inteligência artificial ou conteúdo sintético"


def montar(resumo: dict, destaque: str | None) -> dict:
    t = resumo["temas"][TEMA]
    L = t["lista"]
    tem = lambda x, s: any(s in a for a in x["assuntos"])  # noqa: E731
    df = [x for x in L if tem(x, "Deep Fake")]
    pres = [x for x in L if x.get("chapas")]
    cont = lambda xs, k: Counter(k(x) for x in xs).most_common()  # noqa: E731
    return {
        "fonte": resumo.get("fonte"), "arquivos": resumo.get("arquivos"), "gerado_pelo_tse": resumo.get("gerado_pelo_tse"),
        "lido_em_utc": resumo.get("coletado_em_utc"),
        "universo": {"processos_2026": resumo["totais"]["processos"],
                     "o_que_e": "todos os processos eleitorais de 2026 no arquivo de dados abertos do TSE (todas as classes e tribunais)"},
        "recorte": {"criterio": "assunto do processo com \"Uso de Inteligência Artificial\" ou \"Deep Fake\" (tabela de assuntos do TSE) ou termo de IA no assunto",
                    "processos": len(L), "pct_do_universo": round(100 * len(L) / resumo["totais"]["processos"], 2),
                    "deep_fake": len(df), "uso_de_ia": sum(1 for x in L if tem(x, "Uso de Inteligência Artificial")),
                    "os_dois": sum(1 for x in L if tem(x, "Deep Fake") and tem(x, "Uso de Inteligência Artificial")),
                    "com_decisao": sum(1 for x in L if x.get("decisoes")), "baixados": sum(1 for x in L if x.get("baixa"))},
        "por_mes": sorted(cont(L, lambda x: (x.get("autuacao") or "")[:7])),
        "por_mes_deep_fake": sorted(cont(df, lambda x: (x.get("autuacao") or "")[:7])),
        "por_tribunal": cont(L, lambda x: x["tribunal"])[:15],
        "por_tribunal_deep_fake": cont(df, lambda x: x["tribunal"])[:15],
        "por_classe": cont(L, lambda x: x["classe"]),
        "presidencia": {"processos": len(pres),
                        "por_chapa_e_polo": Counter(c for x in pres for c in x["chapas"]).most_common(),
                        "lista": sorted(pres, key=lambda x: x.get("autuacao") or "")},
        "destaque": next((x for x in L if x["processo"] == destaque), None) if destaque else None,
        "nota": "Metadados públicos do TSE (sem texto das peças). A lista de partes do arquivo só identifica candidaturas à Presidência; "
                "processos de outros cargos entram nas contagens sem nomes. A consulta pública do PJe pede código de imagem (CAPTCHA): "
                "as peças são baixadas à mão e anexadas pelo responsável."}


def main(argv: list[str]) -> int:
    arg = lambda k, d=None: argv[argv.index(k) + 1] if k in argv else d  # noqa: E731
    caso = arg("--caso", "034")
    rj = ROOT / "data/tse/processual/resumo.json"
    if not rj.exists():
        print("⛔ data/tse/processual/resumo.json não existe")
        return 1
    out = montar(json.loads(rj.read_text(encoding="utf-8")), arg("--destaque"))
    pc = ROOT / "data/casos" / caso / "pecas.json"
    if pc.exists():
        out["pecas"] = json.loads(pc.read_text(encoding="utf-8")).get("pecas", [])
    dest = ROOT / "data/casos" / caso / "processos.json"
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(out, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    r = out["recorte"]
    print(f"caso {caso}: {r['processos']} processos de IA/deep fake de {out['universo']['processos_2026']} ({r['pct_do_universo']}%) · deep fake {r['deep_fake']} · "
          f"com candidatura à Presidência {out['presidencia']['processos']} · destaque {'achado' if out['destaque'] else 'não achado'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
