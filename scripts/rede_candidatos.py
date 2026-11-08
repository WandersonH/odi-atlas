#!/usr/bin/env python3
"""Rede da influência dos candidatos na circulação dos casos (para o Gephi).

Pedido do responsável (07/11/2026, 21h46): "gere uma rede Gephi para entender a influência na circulação dos candidatos".

Nós e arestas (dirigidas):
- candidato → caso: o candidato publicou sobre o caso numa conta declarada ao TSE (data/casos/<id>/candidatos.json).
  Peso = nº de publicações; atributos curtidas (soma) e posição codificada, quando houver.
- conta → candidato: uma conta citou o @ de um candidato em posts lidos nos casos (itens privados). Peso = nº de citações.
  Mede quem puxa o candidato para a conversa: o candidato pode circular muito sem publicar nada sobre o caso.
Candidatos (todos os cargos, contas declaradas ao TSE) aparecem com nome, partido, cargo e UF. As demais contas aparecem com
nome só com 10 mil+ seguidores; as outras ficam em código (P00001…), como nas redes públicas.
Universo: as publicações e citações são as da amostra de cada caso (⛔ universo das plataformas não informado).
Entradas: data/casos/*/candidatos.json; ODI_INTERNO_DIR/casos/*/itens.csv.gz; data/tse/redes_sociais_candidatos_2026.csv.gz.
Saídas: data/redes/rede_candidatos.gexf e data/redes/rede_candidatos_resumo.csv (um candidato por linha).
Uso: ODI_INTERNO_DIR=… python scripts/rede_candidatos.py
"""
from __future__ import annotations

import csv
import glob
import gzip
import json
import os
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path
from xml.sax.saxutils import escape

sys.path.insert(0, str(Path(__file__).resolve().parent))
from collect_primeiro_turno import perfil_de  # noqa: E402
from net import now_utc  # noqa: E402

MIN = 10000


def num(v) -> int:
    try:
        return int(float(v))
    except (TypeError, ValueError):
        return 0


def main() -> int:
    root = Path(".")
    cfg = {c["id"]: c for c in json.loads((root / "data/config/casos.json").read_text(encoding="utf-8"))["casos"]}
    # contas declaradas ao TSE → candidato (todos os cargos)
    handle = {}
    info = {}
    for r in csv.DictReader(gzip.open(root / "data/tse/redes_sociais_candidatos_2026.csv.gz", "rt", encoding="utf-8"), delimiter=";"):
        p = perfil_de(r.get("PLATAFORMA", ""), r.get("DS_URL", ""))
        if not p or p[0] not in ("x", "instagram", "tiktok"):
            continue
        nome = (r.get("NM_URNA_CANDIDATO") or "").title()
        handle[(p[0], p[1].lower().lstrip("@"))] = nome
        info.setdefault(nome, {"partido": r.get("SG_PARTIDO", ""), "cargo": (r.get("DS_CARGO") or "").title(), "uf": r.get("SG_UF_CAND") or r.get("SG_UF", "")})
    nos, ar = {}, Counter()
    curt = Counter()
    posicao = {}

    def no(k, rot, tipo, **at):
        nos.setdefault(k, {"label": rot, "tipo": tipo, **at})
        return k

    # 1) candidato → caso
    pubs = Counter()
    for f in sorted(glob.glob("data/casos/*/candidatos.json")):
        cid = Path(f).parent.name
        d = json.loads(Path(f).read_text(encoding="utf-8"))
        for x in d.get("candidatos", []):
            nome = x["candidato"].title()
            c = no(f"cand:{nome}", nome, "candidato", partido=x.get("partido", ""), cargo=(x.get("cargo") or "").title(), uf=x.get("uf", ""),
                   situacao=x.get("situacao", ""))
            k = no(f"caso:{cid}", f"Caso {cid}: {cfg.get(cid, {}).get('titulo', '')[:60]}", "caso")
            for p in x.get("publicacoes", []):
                ar[(c, k)] += 1
                curt[(c, k)] += num(p.get("curtidas"))
                pubs[nome] += 1
            if x.get("posicao") and x["posicao"] != "nao_codificada":
                posicao[(c, k)] = x["posicao"]
    # 2) conta → candidato (citações do @ do candidato nos posts lidos)
    interno = os.environ.get("ODI_INTERNO_DIR")
    citacoes, codigo = Counter(), {}
    lidos = 0
    if interno:
        for f in sorted(glob.glob(os.path.join(interno, "casos/*/itens.csv.gz"))):
            for r in csv.DictReader(gzip.open(f, "rt", encoding="utf-8"), delimiter=";"):
                lidos += 1
                rede = r.get("rede")
                for h in set(re.findall(r"@([\w.]{2,30})", r.get("texto") or "")):
                    nome = handle.get((rede, h.lower()))
                    if not nome or (rede, (r.get("conta") or "").lower()) in handle and handle[(rede, (r.get("conta") or "").lower())] == nome:
                        continue
                    seg = num(r.get("seguidores"))
                    conta = r.get("conta") or "?"
                    if (rede, conta.lower()) in handle:
                        a = no(f"cand:{handle[(rede, conta.lower())]}", handle[(rede, conta.lower())], "candidato", **info.get(handle[(rede, conta.lower())], {}))
                    elif seg >= MIN:
                        a = no(f"{rede}:{conta}", f"@{conta}", "conta pública", rede=rede, seguidores=seg)
                    else:
                        codigo.setdefault((rede, conta), f"P{len(codigo) + 1:05d}")
                        a = no(codigo[(rede, conta)], f"perfil pequeno {codigo[(rede, conta)]}", "perfil pequeno", rede=rede)
                    c = no(f"cand:{nome}", nome, "candidato", **info.get(nome, {}))
                    ar[(a, c)] += 1
                    citacoes[nome] += 1
    # GEXF
    Path("data/redes").mkdir(parents=True, exist_ok=True)
    attrs = ["tipo", "partido", "cargo", "uf", "situacao", "rede", "seguidores"]
    with open("data/redes/rede_candidatos.gexf", "w", encoding="utf-8") as f:
        f.write('<?xml version="1.0" encoding="UTF-8"?>\n<gexf xmlns="http://gexf.net/1.3" version="1.3">\n'
                f'<meta lastmodifieddate="{now_utc()[:10]}"><description>Candidatos × casos (publicações) e contas × candidatos (citações do @), '
                f'amostra dos casos do ODI Atlas; {lidos} posts lidos para as citações</description></meta>\n'
                '<graph defaultedgetype="directed">\n<attributes class="node">'
                + "".join(f'<attribute id="{i}" title="{a}" type="string"/>' for i, a in enumerate(attrs))
                + '</attributes>\n<attributes class="edge"><attribute id="0" title="tipo" type="string"/><attribute id="1" title="curtidas" type="integer"/>'
                  '<attribute id="2" title="posicao" type="string"/></attributes>\n<nodes>\n')
        for k, v in nos.items():
            f.write(f'<node id="{escape(k, {chr(34): "&quot;"})}" label="{escape(str(v["label"]), {chr(34): "&quot;"})}"><attvalues>'
                    + "".join(f'<attvalue for="{i}" value="{escape(str(v.get(a, "")), {chr(34): "&quot;"})}"/>' for i, a in enumerate(attrs) if v.get(a, "") != "")
                    + "</attvalues></node>\n")
        f.write("</nodes>\n<edges>\n")
        for i, ((s, t), w) in enumerate(ar.items()):
            tp = "publicou no caso" if t.startswith("caso:") else "citou o candidato"
            f.write(f'<edge id="{i}" source="{escape(s, {chr(34): "&quot;"})}" target="{escape(t, {chr(34): "&quot;"})}" weight="{w}" label="{tp}"><attvalues>'
                    f'<attvalue for="0" value="{tp}"/><attvalue for="1" value="{curt.get((s, t), 0)}"/>'
                    + (f'<attvalue for="2" value="{escape(posicao[(s, t)])}"/>' if (s, t) in posicao else "") + "</attvalues></edge>\n")
        f.write("</edges>\n</graph>\n</gexf>\n")
    # resumo por candidato (Lula primeiro, depois por citações + publicações)
    casos_de = defaultdict(set)
    for (s, t) in ar:
        if s.startswith("cand:") and t.startswith("caso:"):
            casos_de[s[5:]].add(t[5:])
    quem_cita = defaultdict(set)
    for (s, t) in ar:
        if t.startswith("cand:") and not t.startswith("caso:"):
            quem_cita[t[5:]].add(s)
    nomes = sorted(set(pubs) | set(citacoes), key=lambda n: (0 if n.lower().startswith("lula") else 1, -(citacoes[n] + pubs[n])))
    with open("data/redes/rede_candidatos_resumo.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["candidato", "partido", "cargo", "uf", "publicacoes_nos_casos", "casos_em_que_publicou", "citacoes_recebidas", "contas_que_citaram"])
        for n in nomes:
            i = info.get(n, {})
            w.writerow([n, i.get("partido", ""), i.get("cargo", ""), i.get("uf", ""), pubs[n], len(casos_de[n]), citacoes[n], len(quem_cita[n])])
    print(f"rede_candidatos: {len(nos)} nós, {len(ar)} arestas · {len(pubs)} candidatos publicaram ({sum(pubs.values())} publicações) · "
          f"{len(citacoes)} candidatos citados ({sum(citacoes.values())} citações em {lidos} posts lidos)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
