#!/usr/bin/env python3
"""Análise de conteúdo categorial (Bardin) das publicações de um caso, no desenho do caderno 02 (corpus_populismo.py).

Pedido do responsável (28/10/2026, 00h05): caso 014, "quero aquela análise que temos de Bardin".
Entrada (privado): ODI_INTERNO_DIR/casos/<caso>/itens.csv.gz (publicações coletadas pelo collect_casos.py, todas as redes).
Livro de códigos: data/config/livro_codigos_caso<caso>.json (categorias com definição, indicadores e trechos de exclusão).
  - pré-codificação automática por presença/ausência (sugestão, não decisão), várias categorias por publicação;
  - percentuais no total, por rede, por termo de coleta e por dia (Brasília); pares de categorias que aparecem juntas;
  - blocos "incitação" (demissão, boicote, listas) × "reação" (relato de vítima, denúncia, ironia);
  - CHD de Reinert, palavras e rede de palavras (comentarios_caso.analisar, com amostra fixa para a CHD);
  - amostra estratificada (rede × dia, semente 42) para a codificação humana, gerada UMA vez e nunca sobrescrita, só no privado;
  - universo × amostra por rede e termo, a partir dos manifestos da coleta (regra 9 do CLAUDE.md).
Público: data/casos/<caso>/bardin.json (só agregados; exemplos só de contas com 10 mil+ seguidores, com o trecho que disparou).
Uso: python scripts/build_bardin_caso.py --caso 014
"""
from __future__ import annotations

import csv
import gzip
import json
import os
import random
import sys
from collections import Counter, defaultdict
from itertools import combinations
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import comentarios_caso as cmc  # noqa: E402
from corpus_populismo import compilar, precodificar  # noqa: E402
from net import now_utc  # noqa: E402

MIN_PUBLICO = 10000
INCITACAO = ("incita_demissao", "boicote_economico", "listas_exposicao")
REACAO = ("relato_vitima", "denuncia_ilegalidade", "ironia_inversao")
SEMENTE, N_AMOSTRA = 42, 200


def pct(n, d):
    return round(100 * n / d, 1) if d else None


def amostra(rows: list[dict], n: int) -> list[dict]:
    estratos = defaultdict(list)
    for r in rows:
        estratos[(r["rede"], r["dia"])].append(r)
    rnd, out = random.Random(SEMENTE), []
    for k in sorted(estratos):
        g = estratos[k]
        q = max(1, round(n * len(g) / len(rows)))
        out += rnd.sample(g, min(q, len(g)))
    return sorted(out, key=lambda r: (r["rede"], r["publicado_em"]))[:n] if len(out) > n else out


def universo(pub: Path) -> list[dict]:
    """Por rede e termo: itens lidos e se a busca bateu no limite pedido (somando os manifestos da coleta)."""
    acc = {}
    for f in sorted(pub.glob("manifesto-*.json")):
        m = json.loads(f.read_text(encoding="utf-8"))
        for r in m.get("redes", []):
            for t in r.get("termos", []):
                if isinstance(t, dict) and "termo" in t:
                    k = (r["rede"], t["termo"])
                    a = acc.setdefault(k, {"rede": r["rede"], "termo": t["termo"], "lidos_no_periodo": 0, "coletas": 0, "bateu_no_limite": False})
                    a["lidos_no_periodo"] += t.get("no_periodo") or 0
                    a["coletas"] += 1
                    a["bateu_no_limite"] |= bool(t.get("no_limite"))
    return [{**a, "universo": None, "fonte_universo": "⛔ a plataforma não informa o total de publicações com o termo",
             "leitura": "a busca chegou ao limite pedido: há mais publicações do que as lidas" if a["bateu_no_limite"]
             else "abaixo do limite pedido: tudo o que a busca da plataforma devolveu"} for a in acc.values()]


def main(argv=None) -> int:
    argv = sys.argv[1:] if argv is None else list(argv)
    caso = argv[argv.index("--caso") + 1] if "--caso" in argv else "014"
    interno = os.environ.get("ODI_INTERNO_DIR")
    if not interno:
        print("⛔ ODI_INTERNO_DIR ausente")
        return 1
    livro = json.loads(Path(f"data/config/livro_codigos_caso{caso}.json").read_text(encoding="utf-8"))
    cfg = next(c for c in json.loads(Path("data/config/casos.json").read_text(encoding="utf-8"))["casos"] if c["id"] == caso)
    priv, pub = Path(interno) / "casos" / caso, Path("data/casos") / caso
    pub.mkdir(parents=True, exist_ok=True)
    arq = priv / "itens.csv.gz"
    if not arq.exists():
        print(f"⛔ {arq} não existe")
        return 1
    rows = [r for r in csv.DictReader(gzip.open(arq, "rt", encoding="utf-8"), delimiter=";") if (r.get("publicado_em") or "")[:10] >= cfg["desde"]]
    rows = list({(r["rede"], r["item_id"]): r for r in rows}.values())
    regs = compilar(livro)
    cats = list(livro["categorias"])
    for r in rows:
        r["dia"] = cmc.dia_brt(r.get("publicado_em") or "") or "?"
        r["_cod"] = precodificar(r.get("texto") or "", regs)
    n = len(rows)
    tot = Counter(c for r in rows for c in r["_cod"])
    grupos = lambda rs: {c: {"n": sum(1 for r in rs if c in r["_cod"]), "pct": pct(sum(1 for r in rs if c in r["_cod"]), len(rs))} for c in cats}  # noqa: E731
    por_rede = {rede: {"n": len(rs), "categorias": grupos(rs)} for rede, rs in sorted(_agrupa(rows, lambda r: r["rede"]).items())}
    por_termo = {t: {"n": len(rs), "categorias": grupos(rs)} for t, rs in sorted(_agrupa_multi(rows).items())}
    por_dia = {d: {"n": len(rs), "categorias": grupos(rs)} for d, rs in sorted(_agrupa(rows, lambda r: r["dia"]).items())}
    pares = Counter(p for r in rows for p in combinations(sorted(r["_cod"]), 2))
    inc = sum(1 for r in rows if any(c in r["_cod"] for c in INCITACAO))
    rea = sum(1 for r in rows if any(c in r["_cod"] for c in REACAO))
    ambos = sum(1 for r in rows if any(c in r["_cod"] for c in INCITACAO) and any(c in r["_cod"] for c in REACAO))
    nenhuma = sum(1 for r in rows if not r["_cod"])
    exemplos = {c: [{"rede": r["rede"], "conta": r["conta"], "seguidores": int(r["seguidores"]), "data": r["publicado_em"][:10], "url": r["url"], "trecho": r["_cod"][c][:160]}
                    for r in sorted(rows, key=lambda r: -int(r["seguidores"] or 0)) if c in r["_cod"] and str(r.get("seguidores") or "").isdigit()
                    and int(r["seguidores"]) >= MIN_PUBLICO][:3] for c in cats}
    # amostra humana: uma vez, só no privado
    cod_dir = priv / "codificacao"
    cod_dir.mkdir(parents=True, exist_ok=True)
    plan = cod_dir / "amostra_bardin_v1.csv"
    if not plan.exists():
        am = amostra(rows, N_AMOSTRA)
        with open(plan, "w", encoding="utf-8", newline="") as f:
            w = csv.writer(f, delimiter=";")
            w.writerow(["id", "rede", "dia", "url", "texto", *cats, "observacao", "codificador"])
            for r in am:
                w.writerow([f"{r['rede']}:{r['item_id']}", r["rede"], r["dia"], r["url"], r["texto"], *[""] * len(cats), "", ""])
        with open(cod_dir / "amostra_bardin_v1_precodificacao.csv", "w", encoding="utf-8", newline="") as f:
            w = csv.writer(f, delimiter=";")
            w.writerow(["id", *cats])
            for r in am:
                w.writerow([f"{r['rede']}:{r['item_id']}", *[1 if c in r["_cod"] else 0 for c in cats]])
    n_amostra = sum(1 for _ in open(plan, encoding="utf-8")) - 1
    analise = cmc.analisar([{"texto": r.get("texto") or "", "publicado_em": r.get("publicado_em"), "autor_canal": r.get("conta"), "tipo": "post",
                             "comment_id": f"{r['rede']}:{r['item_id']}", "parent_id": ""} for r in rows], {}, pub, priv, "_posts")
    analise.pop("rede_respostas", None)
    out = {"caso": caso, "gerado_em_utc": now_utc(), "livro": {k: livro[k] for k in ("titulo", "versao", "metodo", "simetria", "amostra_humana", "regra_exclusao")},
           "categorias": {c: {"nome": livro["categorias"][c]["nome"], "definicao": livro["categorias"][c]["definicao"], "n": tot.get(c, 0), "pct": pct(tot.get(c, 0), n)} for c in cats},
           "publicacoes": n, "sem_categoria": {"n": nenhuma, "pct": pct(nenhuma, n)},
           "blocos": {"incitacao": {"categorias": INCITACAO, "n": inc, "pct": pct(inc, n)}, "reacao": {"categorias": REACAO, "n": rea, "pct": pct(rea, n)},
                      "os_dois": {"n": ambos, "pct": pct(ambos, n)}},
           "por_rede": por_rede, "por_termo": por_termo, "por_dia": por_dia,
           "pares": [{"a": a, "b": b, "n": k} for (a, b), k in pares.most_common(15)],
           "exemplos_contas_10mil": exemplos, "amostra_humana": {"arquivo_privado": "casos/%s/codificacao/amostra_bardin_v1.csv" % caso, "publicacoes": n_amostra,
                                                                  "status": "aguardando codificação humana (2 codificadores, kappa de Cohen)"},
           "chd_palavras": analise, "universo": universo(pub),
           "nota": "Pré-codificação automática por indicadores (sugestão, não decisão); várias categorias por publicação; percentuais sobre as publicações lidas, não sobre o universo."}
    (pub / "bardin.json").write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"caso {caso} Bardin: {n} publicações · incitação {out['blocos']['incitacao']['pct']}% · reação {out['blocos']['reacao']['pct']}% · sem categoria "
          f"{out['sem_categoria']['pct']}% · " + " · ".join(f"{c} {v['pct']}%" for c, v in out["categorias"].items()))
    return 0


def _agrupa(rows, chave):
    g = defaultdict(list)
    for r in rows:
        g[chave(r)].append(r)
    return g


def _agrupa_multi(rows):
    g = defaultdict(list)
    for r in rows:
        for t in (r.get("termo") or "").split("|"):
            if t:
                g[f"{r['rede']} · {t}"].append(r)
    return g


if __name__ == "__main__":
    sys.exit(main())
