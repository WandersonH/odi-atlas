"""Reposição de dias perdidos nas coletas diárias pagas (pedido do responsável em 25/10/2026, 18h34: "já ajustei a conta,
força rodar com uma carga histórica desses 2 dias").

data/config/reposicao.json = {"desde": "AAAA-MM-DD", "ate": "AAAA-MM-DD", ...}: enquanto a data de hoje (Brasília) for até
"ate", o modo diário recua a janela para "desde" e multiplica o teto do dia pelo número de dias cobertos. O teto do mês
continua valendo. Depois de "ate", tudo volta ao normal sem mexer em nada.
"""
from __future__ import annotations

import datetime as dt
import json
from pathlib import Path


def hoje_brt() -> dt.date:
    return dt.datetime.now(dt.timezone(dt.timedelta(hours=-3))).date()


def janela(ontem: str, root: Path = Path(".")) -> tuple[str, int]:
    """(data inicial da janela, multiplicador do teto do dia)."""
    p = root / "data/config/reposicao.json"
    if not p.exists():
        return ontem, 1
    c = json.loads(p.read_text(encoding="utf-8"))
    hoje = hoje_brt()
    if hoje.isoformat() > c.get("ate", ""):
        return ontem, 1
    desde = min(ontem, c["desde"])
    return desde, max(1, (hoje - dt.date.fromisoformat(desde)).days + 1)
