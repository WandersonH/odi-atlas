#!/usr/bin/env python3
"""Cruza as publicações de um caso com as redes sociais que os candidatos de 2026 declararam ao TSE.

Pedido do responsável (30/10/2026, 20h55, caso 014): "realizar um cruzamento com as redes de candidato pra sinalizar candidatos e
legendas que faltam sobre o tema, em apoio ou crítica".
Entradas: ODI_INTERNO_DIR/casos/<caso>/itens.csv.gz (publicações do caso), data/tse/redes_sociais_candidatos_2026.csv.gz
(endereços declarados), data/tse/candidatos_2026.csv.gz (partido, cargo, UF, situação), data/config/candidatos_posicao_caso<caso>.json
(posição de cada publicação, lida no texto). Grátis. Público: data/casos/<caso>/candidatos.json (candidatos são figuras públicas
registradas no TSE; texto curto da publicação).
"Legenda que falta" = partido sem nenhuma publicação de candidato na amostra do caso. Não quer dizer que o partido não falou do
tema: a amostra é o que as buscas do caso devolveram (universo ⛔ não informado pelas plataformas).
Uso: python scripts/caso_candidatos.py --caso 014
"""
from __future__ import annotations

import csv
import gzip
import json
import os
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

REDES = {"instagram": "instagram", "x": "x", "twitter": "x", "facebook": "facebook", "tiktok": "tiktok", "kwai": "kwai"}
NAO_PERFIL = {"profile.php", "p", "reel", "reels", "share", "watch", "channel", "c", "hashtag", "explore", "intent", "home", "groups", "events", "stories"}


def perfil(url: str) -> str | None:
    """Nome da conta no endereço declarado (https://www.instagram.com/fulano/?utm=... → fulano)."""
    u = re.sub(r"^https?://(www\.|m\.|mobile\.|web\.)?", "", (url or "").strip().lower().split("?")[0].split("#")[0]).rstrip("/")
    p = u.split("/")
    if len(p) < 2 or not p[1] or p[1] in NAO_PERFIL:
        return None
    return p[1].lstrip("@") or None


def main(argv=None) -> int:
    argv = sys.argv[1:] if argv is None else list(argv)
    caso = argv[argv.index("--caso") + 1] if "--caso" in argv else "014"
    interno = os.environ.get("ODI_INTERNO_DIR") or str(Path(__file__).resolve().parents[2] / "odi-atlas-interno")
    raiz = Path(".")
    cand = {r["SQ_CANDIDATO"]: r for r in csv.DictReader(gzip.open(raiz / "data/tse/candidatos_2026.csv.gz", "rt", encoding="utf-8", errors="replace"), delimiter=";")}
    contas = defaultdict(set)
    for r in csv.DictReader(gzip.open(raiz / "data/tse/redes_sociais_candidatos_2026.csv.gz", "rt", encoding="utf-8", errors="replace"), delimiter=";"):
        rede = REDES.get((r.get("PLATAFORMA") or "").lower())
        h = rede and perfil(r["DS_URL"])
        if h:
            contas[(rede, h)].add(r["SQ_CANDIDATO"])
    pos_cfg = json.loads((raiz / f"data/config/candidatos_posicao_caso{caso}.json").read_text(encoding="utf-8"))
    POS = pos_cfg["por_item"]
    itens = list(csv.DictReader(gzip.open(Path(interno) / "casos" / caso / "itens.csv.gz", "rt", encoding="utf-8"), delimiter=";"))
    pubs, por_cand = [], defaultdict(list)
    for i in itens:
        sqs = contas.get((i["rede"], i["conta"].lower().lstrip("@")))
        if not sqs:
            continue
        k = f"{i['rede']}:{i['item_id']}"
        for sq in sorted(sqs):
            c = cand.get(sq, {})
            pubs.append(k)
            por_cand[sq].append({"rede": i["rede"], "conta": i["conta"], "url": i["url"], "publicado_em": i["publicado_em"],
                                 "curtidas": int(i["curtidas"]) if str(i.get("curtidas") or "").isdigit() else None,
                                 "trecho": (i.get("texto") or "")[:240], "posicao": POS.get(k, "nao_codificada")})
    faltam_codigo = sorted({k for k in pubs if k not in POS})
    linhas = []
    for sq, ps in por_cand.items():
        c = cand.get(sq, {})
        cont = Counter(p["posicao"] for p in ps)
        # posição do candidato: apoio ou crítica se houver; se tiver os dois, "as duas"
        if cont["apoio"] and cont["critica"]:
            pc = "as_duas"
        else:
            pc = next((x for x in ("apoio", "critica", "ambigua", "sem_texto", "outro_tema", "nao_codificada") if cont[x]), "nao_codificada")
        linhas.append({"candidato": c.get("NM_URNA_CANDIDATO"), "partido": c.get("SG_PARTIDO"), "cargo": c.get("DS_CARGO"), "uf": c.get("SG_UF"),
                       "situacao": c.get("DS_SIT_TOT_TURNO"), "posicao": pc, "publicacoes": sorted(ps, key=lambda p: p["publicado_em"])})
    linhas.sort(key=lambda x: (x["partido"] or "", x["candidato"] or ""))
    partidos_todos = Counter(c["SG_PARTIDO"] for c in cand.values() if c.get("SG_PARTIDO"))
    por_partido = defaultdict(Counter)
    for l in linhas:
        por_partido[l["partido"]][l["posicao"]] += 1
    faltam = sorted(p for p in partidos_todos if p not in por_partido)
    out = {"caso": caso, "gerado_em": __import__("datetime").datetime.now(__import__("datetime").timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
           "fonte_contas": "TSE, redes sociais declaradas pelos candidatos de 2026 (data/tse/redes_sociais_candidatos_2026.csv.gz)",
           "universo": {"publicacoes_do_caso": len(itens), "contas_declaradas": len(contas), "candidatos_com_conta": len({s for v in contas.values() for s in v}),
                        "nota": "Universo de publicações sobre o tema nas plataformas: ⛔ não informado. A amostra é o que as buscas do caso devolveram; candidato ausente aqui pode ter falado do tema com outras palavras ou em outra conta."},
           "publicacoes_de_candidatos": len(set(pubs)), "candidatos": linhas,
           "por_partido": {p: dict(v) | {"candidatos_2026": partidos_todos[p]} for p, v in sorted(por_partido.items(), key=lambda kv: -sum(kv[1].values()))},
           "partidos_sem_publicacao_na_amostra": [{"partido": p, "candidatos_2026": partidos_todos[p]} for p in sorted(faltam, key=lambda p: -partidos_todos[p])],
           "citados_fora_da_amostra": pos_cfg.get("citados_fora_da_amostra", []), "categorias": pos_cfg["categorias"], "codificacao": pos_cfg["o_que_e"], "faltam_codificar": faltam_codigo}
    Path(f"data/casos/{caso}").mkdir(parents=True, exist_ok=True)
    Path(f"data/casos/{caso}/candidatos.json").write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"caso {caso}: {len(set(pubs))} publicações de {len(linhas)} candidatos · partidos com publicação {len(por_partido)} · sem publicação {len(faltam)}"
          f" · faltam codificar {len(faltam_codigo)}")
    print({p: dict(v) for p, v in out["por_partido"].items()})
    return 0


if __name__ == "__main__":
    sys.exit(main())
