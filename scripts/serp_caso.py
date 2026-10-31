#!/usr/bin/env python3
"""Resultados ranqueados da busca do Google para um caso (posição, título, endereço, domínio), um retrato por leitura.

Pedido do responsável (30/10/2026, 20h58, caso 020): "traga notícias e resultados ranqueados na busca relacionados a ele".
Apify apify~google-search-scraper (preço informado pela loja: a partir de US$ 1,80 por 1.000 páginas de resultados; o teto do caso
vai em cada execução como maxTotalChargeUsd). Uma página (10 resultados orgânicos) por consulta, Brasil, português.
Conta: segredo do caso (APIFY_TOKEN), sem consulta de saldo. Público: data/casos/<caso>/serp.json (acumula os retratos).
Uso: python scripts/serp_caso.py --caso 020
"""
from __future__ import annotations

import json
import os
import sys
import urllib.parse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from collect_meta_anuncios_apify import custo_run  # noqa: E402
from collect_meta_apify import run_actor  # noqa: E402
from net import now_utc  # noqa: E402

ATOR = "apify~google-search-scraper"


def dominio(u: str) -> str:
    return urllib.parse.urlparse(u or "").netloc.lower().removeprefix("www.")


def gasto_antes(pasta: Path) -> float:
    f = pasta / "serp.json"
    if not f.exists():
        return 0.0
    return round(sum(float(r.get("custo_usd") or 0) for r in json.loads(f.read_text(encoding="utf-8")).get("leituras", [])), 4)


def main(argv=None, executar=None) -> int:
    argv = sys.argv[1:] if argv is None else list(argv)
    caso_id = argv[argv.index("--caso") + 1] if "--caso" in argv else "020"
    caso = next(c for c in json.loads(Path("data/config/casos.json").read_text(encoding="utf-8"))["casos"] if c["id"] == caso_id)
    consultas = caso.get("buscas_google_serp") or []
    pasta = Path("data/casos") / caso_id
    pasta.mkdir(parents=True, exist_ok=True)
    f = pasta / "serp.json"
    acervo = json.loads(f.read_text(encoding="utf-8")) if f.exists() else {"caso": caso_id, "leituras": []}
    teto_total = float((caso.get("teto_usd") or {}).get("google_serp", 0))
    ja = gasto_antes(pasta)
    cap = round(min(teto_total - ja, float(caso.get("teto_serp_por_leitura_usd", 0.05))), 4)
    agora = now_utc()
    if not consultas:
        print("sem consultas de SERP no caso")
        return 0
    if cap < 0.01:
        print(f"⛔ teto da busca do Google esgotado (gasto {ja} de {teto_total})")
        return 0
    if executar is None:
        token = os.environ.get(caso.get("segredo", "APIFY_TOKEN"), "").strip()
        if not token:
            print("⛔ segredo do Apify ausente")
            return 1
        executar = lambda pl, c: run_actor(token, ATOR, pl, c)  # noqa: E731
    payload = {"queries": "\n".join(consultas), "countryCode": "br", "languageCode": "pt-BR", "maxPagesPerQuery": 1,
               "mobileResults": False, "saveHtml": False, "saveHtmlToKeyValueStore": False, "includeUnfilteredResults": False}
    # A Apify exige maxTotalChargeUsd ≥ US$ 0,50 para este ator (erro 400 em 31/10/2026). O gasto real é limitado pela entrada:
    # 1 página por consulta × até US$ 0,005 por página (maior preço de tabela) = estimativa máxima abaixo, que precisa caber no teto.
    estimativa = round(len(consultas) * 0.005, 4)
    if estimativa > cap:
        print(f"⛔ estimativa máxima US$ {estimativa} acima do que resta do teto (US$ {cap})")
        return 0
    try:
        run, items = executar(payload, max(cap, 0.5))
        custo = custo_run(run) if run else 0.0
        erro = None if (run or {}).get("status") == "SUCCEEDED" else (run or {}).get("status")
    except Exception as e:  # noqa: BLE001
        run, items, custo, erro = None, [], 0.0, f"{type(e).__name__} {getattr(e, 'code', '')}".strip()
    res = []
    for it in items or []:
        q = (it.get("searchQuery") or {}).get("term") or it.get("query")
        org = it.get("organicResults") or []
        res.append({"consulta": q, "total_informado": (it.get("searchQuery") or {}).get("resultsTotal") or it.get("resultsTotal"),
                    "resultados": [{"posicao": o.get("position"), "titulo": o.get("title"), "url": o.get("url"), "dominio": dominio(o.get("url")),
                                    "descricao": (o.get("description") or "")[:300], "data": o.get("date")} for o in org],
                    "noticias_destaque": [{"titulo": n.get("title"), "url": n.get("url"), "veiculo": n.get("source") or n.get("siteName"), "data": n.get("date")}
                                          for n in (it.get("topStories") or [])][:10],
                    "relacionadas": [r.get("title") for r in (it.get("relatedQueries") or [])][:10],
                    "pessoas_tambem_perguntam": [r.get("question") for r in (it.get("peopleAlsoAsk") or [])][:8]})
    acervo["leituras"].append({"lido_em_utc": agora, "custo_usd": round(float(custo or 0), 4), "erro": erro, "consultas": res})
    acervo.update(atualizado_em_utc=agora, ferramenta=f"Apify {ATOR}, Brasil, português, 1 página por consulta",
                  universo="Total de resultados que o Google informa por consulta (estimativa do próprio Google), quando o coletor devolve; "
                           "o Atlas lê a primeira página (10 resultados orgânicos), que é o que a maioria das pessoas vê.")
    f.write_text(json.dumps(acervo, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"caso {caso_id} SERP: {len(res)} consultas · {sum(len(r['resultados']) for r in res)} resultados · erro {erro}")
    for r in res:
        print(f"  '{r['consulta']}': " + " | ".join(f"{x['posicao']}. {x['dominio']}" for x in r["resultados"][:6]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
