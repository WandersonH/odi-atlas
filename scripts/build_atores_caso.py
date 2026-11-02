"""Quem dissemina o quê em cada caso: atores políticos (perfis declarados ao TSE), partidos e principais postagens.

Pedido do responsável (02/11/2026, 15h57): "Em todos casos quero uma análise de quais principais atores políticos, partidos e
postagens pra entendermos quem ajuda a disseminar o que, temos tudo declarado".

Como funciona
- Universo de atores políticos: todos os perfis que as candidaturas de 2026 declararam ao TSE (data/tse/redes_sociais_candidatos_2026.csv.gz),
  de todos os cargos, ligados à candidatura em data/tse/candidatos_2026.csv.gz (nome de urna, número, partido, cargo, UF, situação).
  Situação depois da apuração: bolhas_apoio/votos_2026.json do privado, quando existe (votacao_candidato_munzona do TSE).
- Amostra: as publicações coletadas do caso (privado: casos/<id>/itens.csv.gz). A conta de cada publicação é comparada com os perfis
  declarados da mesma rede (X, Instagram, TikTok, Kwai). Facebook fica ⛔: a coleta traz o nome do autor, não o endereço do perfil,
  então não há como cruzar com segurança.
- Partido: soma das candidaturas do partido que aparecem no caso. Posição no 2º turno presidencial: data/config/apoio_partidos_2t.json
  (posição oficial do partido, com fonte; não é declaração do candidato).
- Quem é nomeado: candidaturas (perfil público declarado ao TSE) e contas com 10 mil seguidores ou mais. As demais entram só em contagens.
- Saídas públicas: data/casos/<id>/atores.json e atores.csv; data/casos/atores_todos.csv (todos os casos, uma linha por ator e caso).
Uso: ODI_INTERNO_DIR=... python scripts/build_atores_caso.py [--caso 029 ...]   (sem --caso: todos os casos com itens no privado)
"""
from __future__ import annotations

import csv
import gzip
import json
import os
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from net import now_utc  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
MIN_SEG = 10000
REDES_CRUZADAS = ("x", "instagram", "tiktok", "kwai")
NOME_REDE = {"x": "X", "instagram": "Instagram", "tiktok": "TikTok", "kwai": "Kwai", "facebook": "Facebook"}


def num(v) -> int:
    try:
        return int(float(v))
    except (TypeError, ValueError):
        return 0


def declarados(root: Path, priv_root: Path | None) -> tuple[dict, dict]:
    """{(rede, conta_minúscula): candidatura} e o resumo do universo."""
    from collect_primeiro_turno import perfil_de
    cand = {}
    for r in csv.DictReader(gzip.open(root / "data/tse/candidatos_2026.csv.gz", "rt", encoding="utf-8"), delimiter=";"):
        c = cand.setdefault(r["SQ_CANDIDATO"], {"sq": r["SQ_CANDIDATO"], "nome": r["NM_URNA_CANDIDATO"].title(), "numero": r["NR_CANDIDATO"],
                                                "partido": r["SG_PARTIDO"], "cargo": r["DS_CARGO"].title(), "uf": r["SG_UF"],
                                                "situacao": r["DS_SIT_TOT_TURNO"]})
        if r["NR_TURNO"] == "2" and r["DS_SIT_TOT_TURNO"] not in ("", "#NULO"):
            c["situacao"] = r["DS_SIT_TOT_TURNO"]
    vf = priv_root / "bolhas_apoio" / "votos_2026.json" if priv_root else None
    if vf and vf.exists():
        for sq, t in json.loads(vf.read_text(encoding="utf-8")).items():
            ult = t.get("2") or t.get("1") or {}
            if sq in cand and ult.get("situacao"):
                cand[sq]["situacao"] = ult["situacao"]
    cfg = json.loads((root / "data/config/apoio_partidos_2t.json").read_text(encoding="utf-8"))
    from bolhas_apoio import sinal
    perf, por_rede, cands = {}, Counter(), set()
    for r in csv.DictReader(gzip.open(root / "data/tse/redes_sociais_candidatos_2026.csv.gz", "rt", encoding="utf-8"), delimiter=";"):
        p = perfil_de(r.get("PLATAFORMA", ""), r.get("DS_URL", ""))
        c = cand.get(r["SQ_CANDIDATO"])
        if not p or not c or p[0] not in REDES_CRUZADAS:
            continue
        k = (p[0], p[1].lower().lstrip("@"))
        if k in perf:
            continue
        pos, _, _ = sinal(c["partido"], c["uf"], cfg)
        perf[k] = {**c, "posicao_partido_2t": pos}
        por_rede[p[0]] += 1
        cands.add(r["SQ_CANDIDATO"])
    return perf, {"perfis_declarados_por_rede": dict(por_rede), "candidaturas_com_perfil": len(cands),
                  "fonte": "TSE, Candidatos 2026 (consulta_cand e rede_social_candidato), dadosabertos.tse.jus.br/dataset/candidatos-2026"}


def analisar(caso: str, itens: list[dict], perf: dict, universo: dict, titulo: str = "") -> tuple[dict, list[dict]]:
    itens = list({(r["rede"], r["item_id"]): r for r in itens}.values())
    lidos = Counter(r["rede"] for r in itens)
    atores: dict = {}
    for r in itens:
        rede, conta = r["rede"], (r.get("conta") or "").strip()
        if not conta:
            continue
        c = perf.get((rede, conta.lower().lstrip("@"))) if rede in REDES_CRUZADAS else None
        seg = num(r.get("seguidores"))
        if not c and seg < MIN_SEG:
            continue
        a = atores.setdefault((rede, conta.lower()), {
            "tipo": "candidatura (perfil declarado ao TSE)" if c else "conta com 10 mil+ seguidores",
            "rede": NOME_REDE.get(rede, rede), "conta": conta, "nome": (c or {}).get("nome") or r.get("nome_conta") or "",
            "numero": (c or {}).get("numero"), "partido": (c or {}).get("partido"), "cargo": (c or {}).get("cargo"), "uf": (c or {}).get("uf"),
            "situacao": (c or {}).get("situacao"), "posicao_partido_2t": (c or {}).get("posicao_partido_2t"),
            "seguidores": seg or None, "publicacoes": 0, "visualizacoes": 0, "interacoes": 0, "primeira": None, "ultima": None,
            "termos": Counter(), "_top": None})
        a["seguidores"] = max(a["seguidores"] or 0, seg) or None
        inter = num(r.get("curtidas")) + num(r.get("comentarios")) + num(r.get("compartilhamentos"))
        a["publicacoes"] += 1
        a["visualizacoes"] += num(r.get("visualizacoes"))
        a["interacoes"] += inter
        d = r.get("publicado_em") or ""
        if d:
            a["primeira"] = min(a["primeira"] or d, d)
            a["ultima"] = max(a["ultima"] or d, d)
        a["termos"][r.get("termo") or ""] += 1
        if a["_top"] is None or inter > a["_top"]["interacoes"]:
            a["_top"] = {"url": r.get("url") or "", "texto": " ".join((r.get("texto") or "").split())[:280], "publicado_em": d,
                         "interacoes": inter, "visualizacoes": num(r.get("visualizacoes"))}
    lista = []
    for a in atores.values():
        a["termos"] = [t for t, _ in a["termos"].most_common(5) if t]
        lista.append(a)
    lista.sort(key=lambda a: (-a["interacoes"], -a["publicacoes"]))
    cands = [a for a in lista if a["tipo"].startswith("candidatura")]
    partidos = defaultdict(lambda: {"candidaturas": 0, "publicacoes": 0, "visualizacoes": 0, "interacoes": 0, "posicao_2t": None, "nomes": [], "_ids": set()})
    pessoa = lambda a: (a["nome"], a["numero"], a["uf"], a["cargo"])  # noqa: E731 — a mesma candidatura pode ter perfil em mais de uma rede
    for a in cands:
        p = partidos[a["partido"]]
        if pessoa(a) in p["_ids"]:
            p["publicacoes"] += a["publicacoes"]
            p["visualizacoes"] += a["visualizacoes"]
            p["interacoes"] += a["interacoes"]
            continue
        p["_ids"].add(pessoa(a))
        p["candidaturas"] += 1
        p["publicacoes"] += a["publicacoes"]
        p["visualizacoes"] += a["visualizacoes"]
        p["interacoes"] += a["interacoes"]
        p["posicao_2t"] = a["posicao_partido_2t"]
        if len(p["nomes"]) < 5:
            p["nomes"].append(a["nome"])
    tot = len(itens)
    tabp = sorted(({"partido": k, **{x: y for x, y in v.items() if x != "_ids"}, "pct_publicacoes_do_caso": round(100 * v["publicacoes"] / tot, 2) if tot else None}
                   for k, v in partidos.items()), key=lambda p: (-p["interacoes"], -p["publicacoes"]))
    posts = sorted(({"rede": a["rede"], "conta": a["conta"], "nome": a["nome"], "tipo": a["tipo"], "partido": a["partido"], **a["_top"]}
                    for a in lista if a["_top"]), key=lambda p: -p["interacoes"])[:15]
    pub_cand = sum(a["publicacoes"] for a in cands)
    pub_grandes = sum(a["publicacoes"] for a in lista if not a["tipo"].startswith("candidatura"))
    pos = Counter()
    for a in cands:
        pos[a["posicao_partido_2t"] or "sem_fonte"] += a["publicacoes"]
    out = {
        "caso": caso, "titulo": titulo, "gerado_em_utc": now_utc(),
        "pedido": "Responsável, 02/11/2026, 15h57: quais principais atores políticos, partidos e postagens ajudam a disseminar cada caso.",
        "universo": {**universo, "nota": "Universo de atores políticos = perfis declarados ao TSE por todas as candidaturas de 2026, nas redes cruzadas. "
                     "O universo de publicações do caso é ⛔ desconhecido (as plataformas não informam o total por termo)."},
        "amostra": {"publicacoes_lidas": tot, "por_rede": dict(lidos),
                    "como": "todas as publicações coletadas do caso por termo e hashtag (mesma coleta do dossiê); repetidas contam uma vez",
                    "facebook": "⛔ não cruzado: a coleta do Facebook traz o nome do autor, não o endereço do perfil"},
        "resumo": {"candidaturas_no_caso": len({pessoa(a) for a in cands}), "perfis_de_candidaturas_no_caso": len(cands), "publicacoes_de_candidaturas": pub_cand,
                   "pct_publicacoes_de_candidaturas": round(100 * pub_cand / tot, 2) if tot else None,
                   "contas_10mil_nao_candidatas": len(lista) - len(cands), "publicacoes_de_contas_10mil": pub_grandes,
                   "pct_publicacoes_de_contas_10mil": round(100 * pub_grandes / tot, 2) if tot else None,
                   "publicacoes_de_candidaturas_por_posicao_do_partido_2t": dict(pos)},
        "criterio_nomeacao": "Nomeadas: candidaturas (perfil público declarado ao TSE) e contas com 10 mil+ seguidores. Demais contas só nas contagens.",
        "metodo": "Cruzamento exato da conta da publicação com o perfil declarado ao TSE na mesma rede (minúsculas, sem @). "
                  "Partido e cargo vêm da candidatura; posição no 2º turno é a do partido (data/config/apoio_partidos_2t.json), não do candidato. "
                  "Interações = curtidas + comentários + compartilhamentos informados pela plataforma na coleta.",
        "partidos": tabp, "atores": [{k: v for k, v in a.items() if k != "_top"} | {"top_url": (a["_top"] or {}).get("url")} for a in lista[:60]],
        "atores_total": len(lista), "postagens": posts,
        "arquivos": {"csv": f"data/casos/{caso}/atores.csv"},
    }
    linhas = [{"caso": caso, **{k: (";".join(v) if isinstance(v, list) else v) for k, v in a.items() if k != "_top"},
               "top_url": (a["_top"] or {}).get("url")} for a in lista]
    return out, linhas


COLS = ["caso", "tipo", "rede", "conta", "nome", "numero", "partido", "cargo", "uf", "situacao", "posicao_partido_2t", "seguidores",
        "publicacoes", "visualizacoes", "interacoes", "primeira", "ultima", "termos", "top_url"]


def gravar_csv(p: Path, linhas: list[dict]):
    with open(p, "w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, COLS, delimiter=";", extrasaction="ignore")
        w.writeheader()
        w.writerows(linhas)


def main(argv: list[str]) -> int:
    interno = os.environ.get("ODI_INTERNO_DIR")
    if not interno:
        print("⛔ ODI_INTERNO_DIR não definido")
        return 1
    priv = Path(interno)
    pedidos = [argv[i + 1] for i, a in enumerate(argv) if a == "--caso"]
    casos = pedidos or sorted(p.parent.name for p in (priv / "casos").glob("*/itens.csv.gz"))
    perf, universo = declarados(ROOT, priv)
    print("perfis declarados:", universo["perfis_declarados_por_rede"], "candidaturas:", universo["candidaturas_com_perfil"])
    titulos = {}
    try:
        for c in json.loads((ROOT / "data/casos/indice.json").read_text(encoding="utf-8"))["casos"]:
            titulos[c["id"]] = c.get("titulo", "")
    except Exception:  # noqa: BLE001
        pass
    todas = []
    for caso in casos:
        arq = priv / "casos" / caso / "itens.csv.gz"
        if not arq.exists():
            print(caso, "⛔ sem itens no privado")
            continue
        itens = list(csv.DictReader(gzip.open(arq, "rt", encoding="utf-8"), delimiter=";"))
        out, linhas = analisar(caso, itens, perf, universo, titulos.get(caso, ""))
        d = ROOT / "data/casos" / caso
        d.mkdir(parents=True, exist_ok=True)
        (d / "atores.json").write_text(json.dumps(out, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
        gravar_csv(d / "atores.csv", linhas)
        todas += linhas
        r = out["resumo"]
        print(f"{caso}: {out['amostra']['publicacoes_lidas']} publicações · {r['candidaturas_no_caso']} candidaturas "
              f"({r['pct_publicacoes_de_candidaturas']}% das publicações) · {r['contas_10mil_nao_candidatas']} contas 10 mil+ · "
              f"partidos: {[p['partido'] for p in out['partidos'][:5]]}")
    if not pedidos:
        gravar_csv(ROOT / "data/casos/atores_todos.csv", todas)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
