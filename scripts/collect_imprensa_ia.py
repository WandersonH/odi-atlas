#!/usr/bin/env python3
"""Imprensa sobre IA nas eleições 2026 — busca diária no Google Notícias (RSS público, grátis), em português e em inglês.

Pedido do responsável (22/10/2026, 02h02): na página do caso de IA ("Rótulo de IA nas campanhas"), uma busca de notícias
"desta forma" — como a reportagem do New York Times de 21/10 entrou como referência.

Consultas em data/config/imprensa_ia.json (termos e idiomas). Só entram títulos que falam de IA/deepfake E de eleição,
candidato ou Brasil (filtro por expressões, conferível no arquivo). O acervo acumula: notícia vista uma vez fica guardada
(por link), com a data em que o Atlas a viu primeiro; nada é apagado.

Saída pública: data/ia/imprensa.json (título, veículo, domínio, data de publicação, link, consulta, idioma).
Uso: python scripts/collect_imprensa_ia.py
"""
from __future__ import annotations

import json
import re
import sys
import urllib.parse
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from collect_google_busca import RSS, parse_rss  # noqa: E402
from net import now_utc, open_url, read_body  # noqa: E402

IDIOMAS = {"pt": {"hl": "pt-BR", "gl": "BR", "ceid": "BR:pt-419"}, "en": {"hl": "en-US", "gl": "US", "ceid": "US:en"}}


def relevante(titulo: str, cfg: dict) -> bool:
    return bool(re.search(cfg["rx_ia"], titulo or "", re.I) and re.search(cfg["rx_eleicao"], titulo or "", re.I))


def buscar(cfg: dict, ler=None) -> tuple[list[dict], list[str]]:
    ler = ler or (lambda url: parse_rss(read_body(open_url(url, timeout=40))))
    itens, erros = [], []
    for c in cfg["consultas"]:
        q = c["q"] + (f" when:{cfg['janela']}" if cfg.get("janela") else "")
        url = RSS + "?" + urllib.parse.urlencode({"q": q, **IDIOMAS[c["idioma"]]})
        try:
            for x in ler(url):
                if relevante(x.get("titulo"), cfg):
                    itens.append({**{k: x.get(k) for k in ("titulo", "link", "veiculo", "dominio", "data_publicacao")}, "consulta": c["q"], "idioma": c["idioma"]})
        except Exception as e:  # noqa: BLE001
            erros.append(f"{c['q']}: {type(e).__name__}")
    return itens, erros


def juntar(antigos: list[dict], novos: list[dict], agora: str) -> list[dict]:
    """Acumula por link (e, sem link, por título + veículo); mantém o primeiro registro e soma as consultas que o trouxeram."""
    k = lambda x: x.get("link") or f"{x.get('titulo')}|{x.get('veiculo')}"  # noqa: E731
    por = {k(x): x for x in antigos}
    for x in novos:
        if k(x) in por:
            por[k(x)]["consultas"] = sorted(set(por[k(x)].get("consultas") or []) | {x["consulta"]})
        else:
            por[k(x)] = {**{c: v for c, v in x.items() if c != "consulta"}, "consultas": [x["consulta"]], "visto_pelo_atlas_em": agora}
    return sorted(por.values(), key=lambda x: x.get("data_publicacao") or "", reverse=True)


def main(argv=None, ler=None) -> int:
    root = Path(".")
    cfg = json.loads((root / "data/config/imprensa_ia.json").read_text(encoding="utf-8"))
    arq = root / "data/ia/imprensa.json"
    antigo = json.loads(arq.read_text(encoding="utf-8")) if arq.exists() else {}
    agora = now_utc()
    novos, erros = buscar(cfg, ler)
    lista = juntar(antigo.get("itens") or [], novos, agora)
    out = {"schema_version": 1, "atualizado_em_utc": agora, "fonte": "Google Notícias (RSS público de busca), português e inglês",
           "consultas": cfg["consultas"], "filtro": {"rx_ia": cfg["rx_ia"], "rx_eleicao": cfg["rx_eleicao"]}, "destaques": cfg.get("destaques", []),
           "total": len(lista), "lidos_nesta_coleta": len(novos), "por_veiculo": Counter(x.get("veiculo") for x in lista).most_common(15),
           "por_idioma": Counter(x.get("idioma") for x in lista).most_common(), "erros": erros,
           "nota": "Só notícias indexadas pelo Google Notícias, cujo título fala de IA ou deepfake e de eleição, candidato ou Brasil. "
                   "O acervo acumula a cada coleta (nada é apagado). O Atlas lista; não resume nem avalia cada notícia.",
           "itens": lista}
    arq.parent.mkdir(parents=True, exist_ok=True)
    arq.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"imprensa IA: {len(novos)} lidos nesta coleta · acervo {len(lista)} · erros {erros[:3]}")
    return 0 if (lista and not (erros and not novos)) else 1


if __name__ == "__main__":
    raise SystemExit(main())
