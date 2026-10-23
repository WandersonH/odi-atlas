#!/usr/bin/env python3
"""Sonda (teste, grátis): o Diário de Justiça Eletrônico Nacional (DJEN, CNJ) devolve as comunicações (decisões, despachos,
intimações) dos processos eleitorais de IA/deepfake pelo número do processo?

Pedido do responsável (23/10/2026, 11h53: "teste"). Lê 5 processos de data/tse/processual/resumo.json (tema "inteligência
artificial ou conteúdo sintético"), priorizando os que têm decisão registrada e os ligados a chapas presidenciais, e consulta
https://comunicaapi.pje.jus.br/api/v1/comunicacao?numeroProcesso=<só dígitos>. Respostas brutas só no repositório privado
(ODI_INTERNO_DIR/sondas/djen/); no log, só status, quantidade, campos e tamanho dos textos.
"""
from __future__ import annotations

import json
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

API = "https://comunicaapi.pje.jus.br/api/v1/comunicacao"


def alvos(n: int = 5) -> list[dict]:
    d = json.loads(Path("data/tse/processual/resumo.json").read_text(encoding="utf-8"))
    lista = d["temas"]["inteligência artificial ou conteúdo sintético"]["lista"]
    return sorted(lista, key=lambda p: (-(1 if p.get("chapas") else 0), -(p.get("decisoes") or 0), p["autuacao"] or ""))[:n]


def consultar(numero: str) -> tuple[int | None, dict | None, str | None]:
    url = API + "?" + urllib.parse.urlencode({"numeroProcesso": re.sub(r"\D", "", numero), "pagina": 1, "itensPorPagina": 20})
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (ODI Atlas; pesquisa acadêmica PPGCOM/UNIP)", "Accept": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=40) as r:
            return r.status, json.loads(r.read() or b"null"), None
    except urllib.error.HTTPError as e:
        return e.code, None, (e.read() or b"")[:300].decode("utf-8", "replace")
    except Exception as e:  # noqa: BLE001
        return None, None, f"{type(e).__name__}: {str(e)[:200]}"


def main() -> int:
    priv = Path(os.environ.get("ODI_INTERNO_DIR") or "/tmp") / "sondas/djen"
    priv.mkdir(parents=True, exist_ok=True)
    ok = 0
    for p in alvos():
        st, d, err = consultar(p["processo"])
        itens = (d or {}).get("items") or (d or {}).get("data") or (d if isinstance(d, list) else [])
        campos = sorted(itens[0].keys())[:25] if itens and isinstance(itens[0], dict) else sorted((d or {}).keys())[:15] if isinstance(d, dict) else []
        textos = [len(str(i.get("texto") or i.get("conteudo") or "")) for i in itens if isinstance(i, dict)]
        (priv / f"{re.sub(r'[^0-9]', '', p['processo'])}.json").write_text(json.dumps({"processo": p, "status": st, "erro": err, "resposta": d}, ensure_ascii=False), encoding="utf-8")
        ok += 1 if st == 200 and itens else 0
        print(f"{p['processo']} ({p['tribunal']}, decisões {p.get('decisoes')}, chapas {len(p.get('chapas') or [])}): HTTP {st} · {len(itens)} comunicações · "
              f"tamanho dos textos {textos[:5]} · campos {campos} {('· erro ' + err) if err else ''}")
    print(f"resultado: {ok} de 5 processos com comunicações devolvidas")
    return 0


if __name__ == "__main__":
    sys.exit(main())
