"""Teste (≤ US$ 1, conta 1, autorizado pelo usuário em 19/10/2026 23h0x): alguma ferramenta da Apify devolve o rótulo de IA do Instagram?

Lê os posts e reels mais recentes dos perfis oficiais de Lula e de Flávio Bolsonaro com dois atores que devolvem o JSON completo,
procura campos cujo nome indique rótulo de IA e grava em data/ia/teste_instagram.json só nomes de campos, contagens e os
posts (de perfis públicos de campanha) em que algum campo de IA veio preenchido. O bruto não é guardado.
"""
from __future__ import annotations

import json
import os
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from collect_meta_apify import run_actor  # noqa: E402
from collect_meta_anuncios_apify import custo_run  # noqa: E402
from collect_rotulo_ia import campos_ia, tem_rotulo  # noqa: E402
from net import now_utc  # noqa: E402

PERFIS = ["https://www.instagram.com/lulaoficial/", "https://www.instagram.com/flaviobolsonaro/"]
POSTS = ["https://www.instagram.com/p/DenaM-yuWjG/", "https://www.instagram.com/reel/DenNo9hu3GT/", "https://www.instagram.com/reel/DemdquUNuDl/",
         "https://www.instagram.com/p/Dek4NddOSly/", "https://www.instagram.com/reel/DelvH6wRefD/", "https://www.instagram.com/p/Dek6QqqOJXW/",
         "https://www.instagram.com/reel/DenGv40ptw9/", "https://www.instagram.com/reel/Dem9eVkCZak/", "https://www.instagram.com/reel/Dem1vz2Js1s/",
         "https://www.instagram.com/reel/Demk-2NpFWb/", "https://www.instagram.com/reel/DemT6e7p5F_/", "https://www.instagram.com/reel/DelIY11Jk_r/"]
# 1ª rodada (run 39357421750 e seguinte): perfis voltaram "Empty or private data"; 2ª: endereços de posts recentes (já coletados) dos dois perfis
TESTES = [("apify~instagram-scraper", {"directUrls": POSTS, "resultsType": "details", "resultsLimit": 12, "addParentData": False}, 0.3, 12)]
TESTES_PERFIL = [("apify~instagram-scraper", {"directUrls": PERFIS, "resultsType": "posts", "resultsLimit": 30, "addParentData": False}, 0.35, 60),
          ("apify~instagram-reel-scraper", {"username": ["lulaoficial", "flaviobolsonaro"], "resultsLimit": 25}, 0.35, 50)]
TETO_TOTAL = 1.0


def chaves(o, p=""):
    if isinstance(o, dict):
        for k, v in o.items():
            c = f"{p}.{k}" if p else k
            yield c
            yield from chaves(v, c)
    elif isinstance(o, list):
        for v in o[:2]:
            yield from chaves(v, p + "[]")


def main() -> int:
    token = os.environ.get("APIFY_TOKEN", "").strip()
    if not token:
        print("⛔ APIFY_TOKEN ausente")
        return 1
    out = {"executado_em_utc": now_utc(), "autorizacao": "usuário, 19/10/2026 23h0x: teste de até US$ 1 na conta 1", "testes": []}
    gasto = 0.0
    for ator, entrada, cap, maximo in TESTES:
        cap = min(cap, round(TETO_TOTAL - gasto, 2))
        if cap < 0.05:
            break
        try:
            run, itens = run_actor(token, ator, {**entrada, "maxItems": maximo}, cap)
            custo = custo_run(run or {})
            erro = None
        except Exception as e:  # noqa: BLE001
            run, itens, custo, erro = {}, [], 0.0, f"{type(e).__name__} {getattr(e, 'code', '')}"
        gasto += custo
        todas = Counter(k for it in itens for k in set(chaves(it)))
        ia = [(it, campos_ia(it)) for it in itens]
        rot = [{"perfil": it.get("ownerUsername"), "codigo": it.get("shortCode"), "url": it.get("url"), "data": it.get("timestamp"), "campos_ia": c}
               for it, c in ia if tem_rotulo(c)]
        campos = Counter(k for _, c in ia for k in c)
        t = {"ator": ator.replace("~", "/"), "run": (run or {}).get("id"), "status": (run or {}).get("status"), "itens": len(itens), "custo_usd": custo,
             "erro": erro, "erros_dos_itens": sorted({f"{it.get('error')}: {str(it.get('errorDescription'))[:160]}" for it in itens if it.get("error")}),
             "campos_ia_vistos": campos.most_common(), "itens_com_rotulo": len(rot), "rotulados": rot,
             "total_de_campos": len(todas), "campos": sorted(todas)[:400]}
        out["testes"].append(t)
        print(f"{ator}: {t['erros_dos_itens'][:2]} · {len(itens)} itens · {len(todas)} campos · campos de IA {campos.most_common(6)} · rotulados {len(rot)} · run {t['run']} {erro or ''}")
    out["custo_total_usd"] = round(gasto, 4)
    Path("data/ia").mkdir(parents=True, exist_ok=True)
    Path("data/ia/teste_instagram.json").write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"custo total US$ {gasto:.4f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
