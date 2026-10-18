#!/usr/bin/env python3
"""Verifica as contas Apify (APIFY_TOKEN, APIFY_TOKEN_2 … APIFY_TOKEN_15): plano, uso do mês e limite. Só leitura.

Nada que identifique a conta é gravado (sem nome de usuário, e-mail ou id): só "conta N", o plano e os valores em US$.
Saída: data/apify/contas.json.
"""
from __future__ import annotations

import json
import os
import sys
import urllib.error
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from collect_meta_apify import api  # noqa: E402
from net import now_utc  # noqa: E402

NOMES = ["APIFY_TOKEN"] + [f"APIFY_TOKEN_{i}" for i in range(2, 16)]


def ler(token: str) -> dict:
    me = (api("GET", "/users/me", token) or {}).get("data", {})
    lim = (api("GET", "/users/me/limits", token) or {}).get("data", {})
    plano = me.get("plan") or {}
    cur, mx = lim.get("current") or {}, lim.get("limits") or {}
    uso = cur.get("monthlyUsageUsd")
    teto = mx.get("maxMonthlyUsageUsd")
    return {"plano": plano.get("id"), "credito_mensal_plano_usd": plano.get("monthlyUsageCreditsUsd"),
            "uso_mes_usd": round(uso, 4) if isinstance(uso, (int, float)) else None, "limite_mes_usd": teto,
            "restante_usd": round(teto - uso, 4) if isinstance(uso, (int, float)) and isinstance(teto, (int, float)) else None,
            "ciclo": {k: (lim.get("monthlyUsageCycle") or {}).get(k) for k in ("startAt", "endAt")}}


def main() -> int:
    out = {"verificado_em_utc": now_utc(), "contas": []}
    for i, nome in enumerate(NOMES, 1):
        tok = os.environ.get(nome, "").strip()
        if not tok:
            out["contas"].append({"conta": i, "segredo": nome, "status": "⛔ segredo ausente"})
            continue
        try:
            out["contas"].append({"conta": i, "segredo": nome, "status": "ok", **ler(tok)})
        except urllib.error.HTTPError as e:
            out["contas"].append({"conta": i, "segredo": nome, "status": f"⛔ HTTP {e.code}"})
        except Exception as e:  # noqa: BLE001 — a mensagem não contém o token (vai no cabeçalho)
            out["contas"].append({"conta": i, "segredo": nome, "status": f"⛔ {type(e).__name__}"})
    d = Path("data/apify")
    d.mkdir(parents=True, exist_ok=True)
    (d / "contas.json").write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    for c in out["contas"]:
        print(f"conta {c['conta']} ({c['segredo']}): {c['status']} · plano {c.get('plano')} · uso US$ {c.get('uso_mes_usd')} de {c.get('limite_mes_usd')} · resta {c.get('restante_usd')}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
