#!/usr/bin/env python3
"""Lê o número de seguidores de UM perfil (uma execução, conta 1, teto US$ 0,10 — o mínimo do Apify) para decidir se o
perfil pode aparecer com nome no Atlas (regra: 10 mil seguidores ou mais).

Uso pontual, autorizado pelo responsável a cada vez (22/10/2026, 02h0x: autor do reel do caso 007).
Saída privada: ODI_INTERNO_DIR/casos/<caso>/perfil_<rede>.json (usuário, seguidores, verificado, data, run).
Saída pública: nenhuma direta — o build do caso decide, pelo arquivo privado, se mostra o nome (10 mil+) ou não.
Sem --usuario, lê o autor do post do caso no bruto privado (item do reel com ownerUsername), para o nome não passar por
parâmetro do workflow (que fica visível nos metadados do run, num repositório público).
Uso: python scripts/checar_seguidores_perfil.py --caso 007 --rede instagram [--usuario <perfil>]
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from collect_meta_apify import run_actor  # noqa: E402
from net import now_utc  # noqa: E402

ATORES = {"instagram": ("apify~instagram-profile-scraper", lambda u: {"usernames": [u]})}


def main(argv=None, executar=None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    a = lambda k: argv[argv.index(k) + 1] if k in argv else None  # noqa: E731
    caso, rede, usuario = a("--caso"), a("--rede") or "instagram", (a("--usuario") or "").lstrip("@")
    interno = os.environ.get("ODI_INTERNO_DIR")
    token = os.environ.get("APIFY_TOKEN", "").strip()
    if not usuario and interno and caso:
        import glob
        for f in sorted(glob.glob(str(Path(interno) / f"casos/{caso}/apify/*.json"))):
            for x in (json.loads(Path(f).read_text(encoding="utf-8")).get("items") or []):
                if x.get("ownerUsername") and "videoPlayCount" in x:
                    usuario = x["ownerUsername"]
    if not (caso and usuario and interno and (token or executar)):
        print("⛔ faltam --caso, --usuario, ODI_INTERNO_DIR ou APIFY_TOKEN")
        return 1
    ator, entrada = ATORES[rede]
    executar = executar or (lambda pl: run_actor(token, ator, pl, 0.1))
    run, itens = executar(entrada(usuario))
    x = next((i for i in (itens or []) if i.get("username") or i.get("followersCount") is not None), {})
    out = {"usuario": x.get("username") or usuario, "seguidores": x.get("followersCount"), "verificado": x.get("verified"),
           "nome": x.get("fullName"), "privado": x.get("private"), "lido_em_utc": now_utc(), "run": (run or {}).get("id"),
           "custo_usd": (run or {}).get("usageTotalUsd"), "ator": ator.replace("~", "/")}
    d = Path(interno) / f"casos/{caso}"
    d.mkdir(parents=True, exist_ok=True)
    (d / f"perfil_{rede}.json").write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    pub = isinstance(out["seguidores"], int) and out["seguidores"] >= 10000
    print(f"perfil lido · seguidores {'10 mil ou mais' if pub else 'abaixo de 10 mil ou sem número'} · custo {out['custo_usd']}")
    return 0 if out["seguidores"] is not None else 1


if __name__ == "__main__":
    raise SystemExit(main())
