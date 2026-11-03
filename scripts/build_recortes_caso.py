"""Recortes temáticos dentro de um caso (ex.: 026 · Janones em Buenos Aires). Só agregados públicos.

Pedido do responsável (03/11/2026, 02h08, sobre o 026 · Buenos Aires): "isso deveria estar dentro de janonismo".
Config: data/config/casos.json, campo "recortes" do caso: [{"id", "titulo", "padrao" (regex), "desde", "nota"}].
Amostra: publicações já coletadas do caso (privado: casos/<id>/itens.csv.gz); o recorte é o subconjunto cujo TEXTO casa
com o padrão (o termo de busca sozinho não basta). Saída pública: data/casos/<id>/recortes.json com contagens por rede e
por dia, contas com ≥10 mil seguidores (regra de nomeação do projeto) e notícias do caso (busca.json) que casam no título.
Nenhum texto de publicação vai para o público.
Uso: ODI_INTERNO_DIR=... python scripts/build_recortes_caso.py [--caso 026]
"""
from __future__ import annotations

import csv
import gzip
import json
import os
import re
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from net import now_utc  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
MIN_SEG = 10_000


def num(v) -> int:
    try:
        return int(float(v))
    except (TypeError, ValueError):
        return 0


def recortar(itens: list[dict], rec: dict, noticias: list[dict]) -> dict:
    rx = re.compile(rec["padrao"], re.I)
    desde = rec.get("desde") or ""
    itens = list({(r["rede"], r["item_id"]): r for r in itens}.values())
    total = Counter(r["rede"] for r in itens)
    sel = [r for r in itens if rx.search(r.get("texto") or "") and (r.get("publicado_em") or "")[:10] >= desde]
    por_rede = Counter(r["rede"] for r in sel)
    por_dia = Counter((r.get("publicado_em") or "")[:10] for r in sel if r.get("publicado_em"))
    contas: dict[tuple, dict] = {}
    for r in sel:
        seg = num(r.get("seguidores"))
        if seg < MIN_SEG:
            continue
        k = (r["rede"], r.get("conta"))
        c = contas.setdefault(k, {"rede": r["rede"], "conta": r.get("conta"), "nome": r.get("nome_conta"), "seguidores": seg,
                                  "publicacoes": 0, "visualizacoes": 0, "curtidas": 0})
        c["publicacoes"] += 1
        c["visualizacoes"] += num(r.get("visualizacoes"))
        c["curtidas"] += num(r.get("curtidas"))
    eng = lambda r: num(r.get("curtidas")) + num(r.get("comentarios")) + num(r.get("compartilhamentos"))  # noqa: E731
    news = sorted((n for n in noticias if rx.search(n.get("titulo") or "") and (n.get("data_publicacao") or "")[:10] >= desde),
                  key=lambda n: n.get("data_publicacao") or "", reverse=True)
    return {"id": rec["id"], "titulo": rec["titulo"], "padrao": rec["padrao"], "desde": desde, "nota": rec.get("nota", ""),
            "universo": "publicações já coletadas no caso (amostra por termo; universo das plataformas ⛔ desconhecido)",
            "lidas_no_caso": dict(total), "no_recorte": dict(por_rede), "total_recorte": len(sel), "total_caso": len(itens),
            "pct_do_caso": round(100 * len(sel) / len(itens), 1) if itens else None,
            "por_dia": dict(sorted(por_dia.items())),
            "interacoes": sum(eng(r) for r in sel), "visualizacoes": sum(num(r.get("visualizacoes")) for r in sel),
            "contas_10k": sorted(contas.values(), key=lambda c: -c["publicacoes"])[:25],
            "contas_abaixo_10k": len({(r["rede"], r.get("conta")) for r in sel if num(r.get("seguidores")) < MIN_SEG}),
            "noticias": [{"titulo": n.get("titulo"), "link": n.get("link"), "veiculo": n.get("veiculo"), "data": n.get("data_publicacao")}
                         for n in news][:60],
            "n_noticias": len(news)}


def main(argv: list[str]) -> int:
    interno = os.environ.get("ODI_INTERNO_DIR")
    if not interno:
        print("⛔ ODI_INTERNO_DIR não definido")
        return 1
    cfg = json.loads((ROOT / "data/config/casos.json").read_text(encoding="utf-8"))
    pedidos = argv[argv.index("--caso") + 1:] if "--caso" in argv else None
    for c in cfg["casos"]:
        if not c.get("recortes") or (pedidos and c["id"] not in pedidos):
            continue
        arq = Path(interno) / "casos" / c["id"] / "itens.csv.gz"
        if not arq.exists():
            print(c["id"], "⛔ sem itens no privado")
            continue
        with gzip.open(arq, "rt", encoding="utf-8", newline="") as f:
            itens = list(csv.DictReader(f, delimiter=";"))
        bp = ROOT / "data/casos" / c["id"] / "busca.json"
        noticias = json.loads(bp.read_text(encoding="utf-8")).get("noticias", []) if bp.exists() else []
        out = {"schema_version": 1, "caso": c["id"], "gerado_em_utc": now_utc(), "recortes": [recortar(itens, r, noticias) for r in c["recortes"]]}
        (ROOT / "data/casos" / c["id"] / "recortes.json").write_text(json.dumps(out, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
        for r in out["recortes"]:
            print(c["id"], r["id"], r["total_recorte"], "de", r["total_caso"], r["no_recorte"], "notícias", r["n_noticias"], "contas ≥10k", len(r["contas_10k"]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
