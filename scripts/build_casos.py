#!/usr/bin/env python3
"""Agregados públicos dos casos (página "Casos e análises"), a partir do arquivo privado de cada caso.

Entrada: ODI_INTERNO_DIR/casos/<id>/itens.csv.gz (collect_casos.py), data/casos/<id>/google.json e manifestos.
Saída pública:
- data/casos/indice.json: todos os casos da configuração, com estado (coletado, aguardando confirmação);
- data/casos/<id>/caso.json: números por rede e termo, série por hora (horário de Brasília), marco zero, quem puxou,
  galeria, palavras, Google (Trends e Notícias), desenho da rede e método. Sem custo de coleta.
- data/casos/<id>/rede.gexf, rede_nos.csv, rede_arestas.csv: contas × hashtags/menções, para o Gephi.
Privacidade: conta com menos de `min_seguidores_publico` seguidores (o selo não basta: C19.353) aparece só como código (C001…, ordem de
atividade), sem texto nem link; perfis declarados ao TSE e contas grandes aparecem com nome. Palavras: só contagens.
Tom da audiência: não calculado (o caso não coleta comentários) — fica ⛔ na página.
"""
from __future__ import annotations

import csv
import datetime as dt
import gzip
import json
import os
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).resolve().parent))
import build_conteudo as bc  # noqa: E402
from collect_primeiro_turno import perfil_de  # noqa: E402
from net import now_utc  # noqa: E402

BRT = ZoneInfo("America/Sao_Paulo")
ROTULO = {"tiktok": "TikTok", "x": "X", "instagram": "Instagram", "facebook": "Facebook", "kwai": "Kwai"}


def num(v) -> int:
    try:
        return int(float(v))
    except (TypeError, ValueError):
        return 0


def hora_brt(iso: str) -> str | None:
    try:
        d = dt.datetime.strptime(iso[:19], "%Y-%m-%dT%H:%M:%S").replace(tzinfo=dt.timezone.utc).astimezone(BRT)
    except ValueError:
        return None
    return d.strftime("%Y-%m-%dT%H:00")


def declarados(root: Path) -> dict[tuple[str, str], str]:
    """(rede, conta) → candidato que declarou o perfil ao TSE (presidente e vice, todas as chapas)."""
    urna = json.loads((root / "data/elections.json").read_text(encoding="utf-8"))["candidates"]["2026"]
    out = {}
    for r in csv.DictReader(gzip.open(root / "data/tse/redes_sociais_candidatos_2026.csv.gz", "rt", encoding="utf-8"), delimiter=";"):
        if r.get("DS_CARGO", "").upper() not in ("PRESIDENTE", "VICE-PRESIDENTE"):
            continue
        p = perfil_de(r.get("PLATAFORMA", ""), r.get("DS_URL", ""))
        if p:
            chave = p[1].rstrip("/").split("/")[-1].lower() if p[0] == "facebook" else p[1].lower()
            out[(p[0], chave)] = f"{r.get('NM_URNA_CANDIDATO', '').title()} ({r['NR_CANDIDATO']}{'' if r['NR_CANDIDATO'] in urna else ', fora da urna'})"
    return out


def meia_vida(serie: list[int]) -> tuple[int | None, int | None]:
    """(índice do pico, horas do pico até a primeira hora com até metade do pico). None se a série não cair à metade."""
    if not serie or max(serie) == 0:
        return None, None
    p = serie.index(max(serie))
    for i in range(p + 1, len(serie)):
        if serie[i] <= serie[p] / 2:
            return p, i - p
    return p, None


def gexf(nos: dict, arestas: Counter, caminho: Path):
    linhas = ['<?xml version="1.0" encoding="UTF-8"?>', '<gexf xmlns="http://gexf.net/1.3" version="1.3">',
              '<graph defaultedgetype="directed">', '<attributes class="node"><attribute id="0" title="tipo" type="string"/>'
              '<attribute id="1" title="rede" type="string"/><attribute id="2" title="publicacoes" type="integer"/></attributes>', "<nodes>"]
    esc = lambda s: str(s).replace("&", "&amp;").replace("<", "&lt;").replace('"', "&quot;")  # noqa: E731
    for k, v in nos.items():
        linhas.append(f'<node id="{esc(k)}" label="{esc(v["rotulo"])}"><attvalues><attvalue for="0" value="{v["tipo"]}"/>'
                      f'<attvalue for="1" value="{esc(v.get("rede", ""))}"/><attvalue for="2" value="{v["n"]}"/></attvalues></node>')
    linhas.append("</nodes><edges>")
    for i, ((a, b), w) in enumerate(arestas.items()):
        linhas.append(f'<edge id="{i}" source="{esc(a)}" target="{esc(b)}" weight="{w}"/>')
    linhas += ["</edges>", "</graph>", "</gexf>"]
    caminho.write_text("\n".join(linhas), encoding="utf-8")


def marcas_intolerancia(cid: str) -> dict | None:
    """item_id → lista de marcas da triagem (ofensivo; ódio: <alvo>), limiar 0,5; None se o caso não tem escores."""
    interno = os.environ.get("ODI_INTERNO_DIR")
    f = Path(interno or "") / "casos" / cid / "intolerancia" / "escores.csv.gz"
    if not interno or not f.exists():
        return None
    out = {}
    for r in csv.DictReader(gzip.open(f, "rt", encoding="utf-8"), delimiter=";"):
        mk = []
        if float(r.get("ofensividade_hatebr:True") or 0) >= 0.5:
            mk.append("ofensivo")
        mk += [f"ódio: {k.split(':', 1)[1]}" for k, v in r.items() if k.startswith("odio_") and v and float(v) >= 0.5]
        out[r["id"]] = mk
    return out


def gexf_dinamico(nos: dict, dias: dict, caminho: Path, marcas: dict | None = None):
    """GEXF 1.3 dinâmico (timeformat=date): cada ligação com um intervalo por dia em que houve publicação e o peso daquele dia;
    cada nó começa no dia da primeira publicação. Abre na linha do tempo do Gephi (Janela → Linha do tempo)."""
    esc = lambda s: str(s).replace("&", "&amp;").replace("<", "&lt;").replace('"', "&quot;")  # noqa: E731
    fim = max((d for c in dias.values() for d in c), default="")
    L = ['<?xml version="1.0" encoding="UTF-8"?>', '<gexf xmlns="http://gexf.net/1.3" version="1.3">',
         f'<graph defaultedgetype="directed" mode="dynamic" timeformat="date" timerepresentation="interval">',
         '<attributes class="node" mode="static"><attribute id="0" title="tipo" type="string"/><attribute id="1" title="rede" type="string"/>'
         '<attribute id="2" title="publicacoes" type="integer"/></attributes>',
         '<attributes class="edge" mode="dynamic"><attribute id="peso_dia" title="publicacoes no dia" type="integer"/></attributes>'
         + ('<attributes class="edge" mode="static"><attribute id="marcas" title="marcas da triagem" type="string"/></attributes>' if marcas else ''), "<nodes>"]
    for k, v in nos.items():
        L.append(f'<node id="{esc(k)}" label="{esc(v["rotulo"])}" start="{v.get("d0") or ""}" end="{fim}"><attvalues><attvalue for="0" value="{esc(v["tipo"])}"/>'
                 f'<attvalue for="1" value="{esc(v.get("rede", ""))}"/><attvalue for="2" value="{v["n"]}"/></attvalues></node>')
    L.append("</nodes><edges>")
    for i, ((a, b), c) in enumerate(dias.items()):
        ds = sorted(c)
        att = "".join(f'<attvalue for="peso_dia" value="{c[d]}" start="{d}" end="{d}"/>' for d in ds)
        if marcas:
            att += f'<attvalue for="marcas" value="{esc("; ".join(f"{m} {n}" for m, n in marcas[(a, b)].most_common()))}"/>'
        sp = "".join(f'<spell start="{d}" end="{d}"/>' for d in ds)
        L.append(f'<edge id="{i}" source="{esc(a)}" target="{esc(b)}" weight="{sum(c.values())}"><attvalues>{att}</attvalues><spells>{sp}</spells></edge>')
    L += ["</edges>", "</graph>", "</gexf>"]
    caminho.write_text("\n".join(L), encoding="utf-8")


def construir(root: Path, caso: dict, cfg: dict, itens: list[dict]) -> dict:
    pasta = root / "data/casos" / caso["id"]
    minimo = cfg.get("min_seguidores_publico", 10000)
    dec = declarados(root)
    itens = [r for r in itens if r.get("publicado_em", "")[:10] >= caso["desde"]]
    # só os termos atuais do caso (ex.: @verdeeamarelo saiu em 18/10); publicação trazida só por termo removido sai
    validos = {f"#{h}" for h in caso.get("hashtags", [])} | {f"@{m}" for m in caso.get("mencoes_x", [])} | {f"@{p}" for p in caso.get("perfis_instagram", [])}
    # 28/10/2026: as buscas por frase (complementos do X e buscas do TikTok) também são termos do caso; antes ficavam fora do agregado
    validos |= {c["termo"] for c in caso.get("complementos_x", [])} | set(caso.get("buscas_tiktok", []))
    validos |= {f"#{h}" for h in caso.get("hashtags_instagram", [])} | set(caso.get("buscas_facebook", [])) | set(caso.get("buscas_kwai", []))
    validos |= {f"reels: {q}" for q in caso.get("buscas_instagram", [])}
    for k_, v_ in caso.items():  # listas de rodadas de ampliação (hashtags_instagram_r2, buscas_instagram_r2…)
        if k_.startswith("hashtags_instagram_r"):
            validos |= {f"#{h}" for h in v_}
        if k_.startswith("buscas_instagram_r"):
            validos |= {f"reels_{k_.rsplit('_', 1)[1]}: {q}" for q in v_}
        if k_.startswith("buscas_facebook_r"):  # 07/11/2026: a rodada 2 do Facebook (caso 030) não entrava no agregado
            validos |= set(v_)
    if caso.get("posts_instagram"):
        validos.add("indicado pelo responsável")
    itens = [{**r, "termo": "|".join(t for t in r["termo"].split("|") if t in validos)} for r in itens]
    itens = [r for r in itens if r["termo"]]
    if caso.get("mascarar_regex"):  # proteção de criança (caso 020): o nome não sai nos textos públicos (galeria, palavras)
        mascara = re.compile(caso["mascarar_regex"], re.I)
        itens = [{**r, "texto": mascara.sub("[menino]", r["texto"] or "")} for r in itens]
    itens.sort(key=lambda r: r["publicado_em"])
    # quem aparece com nome
    ativ = Counter((r["rede"], r["conta"]) for r in itens if r["conta"])
    codigo = {k: f"C{i:04d}" for i, (k, _) in enumerate(ativ.most_common(), 1)}

    oculta = re.compile(caso["contas_ocultas_regex"], re.I) if caso.get("contas_ocultas_regex") else None

    def publico(r) -> str | None:
        k = (r["rede"], r["conta"].lower())
        if oculta and (oculta.search(r["conta"] or "") or oculta.search(r.get("nome_conta") or "")):
            return None  # proteção de criança (caso 020): a conta nunca aparece pelo nome, mesmo com 10 mil+ seguidores
        if k in dec:
            return f"@{r['conta']} · perfil de {dec[k]}"
        # 07/11/2026: o selo deixou de valer sozinho. No TikTok o campo "verified" do coletor oscila (a mesma conta vem
        # verdadeira e falsa; no caso 030, 306 itens de contas com menos de 10 mil seguidores vinham com selo) e no X o selo é pago.
        # Regra do responsável: nome só com 10 mil+ seguidores ou perfil declarado ao TSE.
        if num(r.get("seguidores")) >= minimo:
            return f"@{r['conta']}" if r["rede"] != "facebook" else r["conta"]
        return None

    def quem(r) -> dict:
        p = publico(r)
        return {"conta": p or f"perfil pequeno {codigo.get((r['rede'], r['conta']), '')}".strip(), "publico": bool(p),
                "seguidores": num(r.get("seguidores")) if p else None, "declarado_tse": (r["rede"], r["conta"].lower()) in dec}
    termos = sorted({t for r in itens for t in r["termo"].split("|") if t})
    # números por rede e por termo
    redes = {}
    for rede in ROTULO:
        rs = [r for r in itens if r["rede"] == rede]
        redes[rede] = {"publicacoes": len(rs), "contas": len({r["conta"] for r in rs if r["conta"]}),
                       "visualizacoes": sum(num(r["visualizacoes"]) for r in rs), "curtidas": sum(num(r["curtidas"]) for r in rs),
                       "comentarios": sum(num(r["comentarios"]) for r in rs), "compartilhamentos": sum(num(r["compartilhamentos"]) for r in rs),
                       "visualizacoes_informadas": sum(1 for r in rs if str(r.get("visualizacoes") or "").strip() not in ("", "None")),
                       "por_termo": {t: sum(1 for r in rs if t in r["termo"].split("|")) for t in termos},
                       "primeira": rs[0]["publicado_em"] if rs else None, "ultima": rs[-1]["publicado_em"] if rs else None}
    # série por hora
    horas = sorted({h for r in itens if (h := hora_brt(r["publicado_em"]))})
    if horas:
        h0 = dt.datetime.fromisoformat(horas[0])
        h1 = dt.datetime.fromisoformat(horas[-1])
        eixo = [(h0 + dt.timedelta(hours=i)).strftime("%Y-%m-%dT%H:00") for i in range(int((h1 - h0).total_seconds() // 3600) + 1)]
    else:
        eixo = []
    pos = {h: i for i, h in enumerate(eixo)}
    serie = {rede: [0] * len(eixo) for rede in ROTULO}
    serie_termo = {t: [0] * len(eixo) for t in termos}
    for r in itens:
        h = hora_brt(r["publicado_em"])
        if h in pos:
            serie[r["rede"]][pos[h]] += 1
            for t in r["termo"].split("|"):
                if t in serie_termo:
                    serie_termo[t][pos[h]] += 1
    total = [sum(serie[rd][i] for rd in serie) for i in range(len(eixo))]
    ip, mv = meia_vida(total)
    # decolagem: 1ª hora com pelo menos 5% do pico (mínimo 10 publicações) — o marco zero pode ser uso antigo ou sem relação
    lim_d = max(10, 0.05 * max(total)) if total else None
    i_d = next((i for i, v in enumerate(total) if lim_d and v >= lim_d), None)
    decolagem = {"hora_brt": eixo[i_d], "publicacoes": total[i_d], "criterio": "1ª hora com pelo menos 5% do pico (mínimo 10 publicações)"} if i_d is not None else None
    # marco zero: geral, por rede e por termo
    def marco(rs):
        if not rs:
            return None
        r = rs[0]
        q = quem(r)
        return {"rede": ROTULO[r["rede"]], "hora_brt": hora_brt(r["publicado_em"]), "publicado_em_utc": r["publicado_em"], **q,
                "url": r["url"] if q["publico"] else None, "termo": r["termo"]}
    marcos = {"geral": marco(itens), "por_rede": {ROTULO[rd]: marco([r for r in itens if r["rede"] == rd]) for rd in ROTULO},
              "por_termo": {t: marco([r for r in itens if t in r["termo"].split("|")]) for t in termos}}
    # quem puxou: primeiros e maiores (só contas públicas com nome; pequenas entram como código)
    vistos, primeiros = set(), []
    for r in itens:
        k = (r["rede"], r["conta"])
        if r["conta"] and k not in vistos:
            vistos.add(k)
            primeiros.append({**quem(r), "rede": ROTULO[r["rede"]], "hora_brt": hora_brt(r["publicado_em"])})
        if len(primeiros) == 10:
            break
    alcance = defaultdict(lambda: [0, 0, 0, None])
    for r in itens:
        a = alcance[(r["rede"], r["conta"])]
        a[0] += num(r["visualizacoes"])
        a[1] += num(r["curtidas"]) + num(r["comentarios"]) + num(r["compartilhamentos"])
        a[2] += 1
        a[3] = r
    maiores = [{**quem(v[3]), "rede": ROTULO[k[0]], "visualizacoes": v[0], "interacoes": v[1], "publicacoes": v[2]}
               for k, v in sorted(alcance.items(), key=lambda kv: (kv[1][0], kv[1][1]), reverse=True) if k[1]][:10]
    # galeria: peças de contas públicas com maior alcance
    pecas = sorted([r for r in itens if publico(r)], key=lambda r: (num(r["visualizacoes"]), num(r["curtidas"])), reverse=True)[:12]
    galeria = [{"rede": ROTULO[r["rede"]], **quem(r), "hora_brt": hora_brt(r["publicado_em"]), "texto": r["texto"][:220], "url": r["url"],
                "visualizacoes": num(r["visualizacoes"]) or None, "curtidas": num(r["curtidas"]) or None,
                "compartilhamentos": num(r["compartilhamentos"]) or None, "termo": r["termo"]} for r in pecas]
    # palavras (só contagens)
    base = {bc.norm(t.lstrip("#@")) for t in termos} | {bc.norm(h) for h in caso.get("hashtags", [])}
    excl = base | {"#" + b for b in base} | {"@" + b for b in base}
    palavras = bc.nuvem([r["texto"] for r in itens], excl, top=60, minimo=3)
    # rede para o Gephi: conta → hashtag/menção
    # 08/11/2026 (pedido do responsável: rede dinâmica "se temos as datas de todas as publicações" e rede das mensagens marcadas como
    # linguagem ofensiva e discurso de ódio): o mesmo laço guarda o dia de cada ligação e, à parte, a rede só das publicações que a
    # triagem automática (intolerancia.py, limiar 0,5, NÃO validada) marcou.
    marca = marcas_intolerancia(caso["id"])
    # 020 (criança): desde C19.371 as redes saem e scripts/anonimizar_publico.py (rodado no commit_push.sh) troca o que identifica a
    # criança; sem anonimizar_publico_regex o caso protegido continua sem rede pública nova.
    protegido = bool(caso.get("mascarar_regex")) and not caso.get("anonimizar_publico_regex")
    nos, arestas = {}, Counter()
    dias = defaultdict(Counter)  # (a, b) → dia → publicações
    nos_of, arestas_of, dias_of, tipo_of = {}, Counter(), defaultdict(Counter), defaultdict(Counter)
    n_of, n_esc, por_marca = 0, 0, Counter()
    for r in itens:
        if not r["conta"]:
            continue
        q = quem(r)
        a = f"{r['rede']}:{r['conta']}" if q["publico"] else codigo[(r["rede"], r["conta"])]
        dia = (r.get("publicado_em") or "")[:10]
        mk = marca.get(r.get("item_id")) if marca else None
        if marca and r.get("item_id") in marca:
            n_esc += 1
        if mk:
            n_of += 1
            por_marca.update(mk)
        alvos = []
        nos.setdefault(a, {"rotulo": q["conta"], "tipo": "conta oficial" if q["declarado_tse"] else "conta", "rede": ROTULO[r["rede"]], "n": 0, "d0": dia})["n"] += 1
        for tag in set(re.findall(r"#(\w+)", r["texto"].lower())) | {t.lstrip("#").lower() for t in r["termo"].split("|") if t.startswith("#")}:
            b = f"#{tag}"
            nos.setdefault(b, {"rotulo": b, "tipo": "hashtag", "n": 0, "d0": dia})["n"] += 1
            arestas[(a, b)] += 1
            dias[(a, b)][dia] += 1
            alvos.append((b, {"rotulo": b, "tipo": "hashtag"}))
        for m in set(re.findall(r"@(\w{2,30})", r["texto"].lower())):
            if (r["rede"], m) in dec:  # só menções a perfis declarados ao TSE (os demais podem ser pessoas comuns)
                b = f"{r['rede']}:{m}"
                nos.setdefault(b, {"rotulo": f"@{m} · perfil de {dec[(r['rede'], m)]}", "tipo": "conta oficial mencionada", "rede": ROTULO[r["rede"]], "n": 0, "d0": dia})
                arestas[(a, b)] += 1
                dias[(a, b)][dia] += 1
                alvos.append((b, {"rotulo": nos[b]["rotulo"], "tipo": "conta oficial mencionada", "rede": ROTULO[r["rede"]]}))
        if mk:
            nos_of.setdefault(a, {**{k: v for k, v in nos[a].items() if k not in ("n", "d0")}, "n": 0, "d0": dia})["n"] += 1
            for b, info in alvos:
                nos_of.setdefault(b, {**info, "n": 0, "d0": dia})["n"] += 1
                arestas_of[(a, b)] += 1
                dias_of[(a, b)][dia] += 1
                tipo_of[(a, b)].update(mk)
    if nos:
        gexf(nos, arestas, pasta / "rede.gexf")
        with open(pasta / "rede_nos.csv", "w", encoding="utf-8", newline="") as f:
            w = csv.writer(f, delimiter=";")
            w.writerow(["id", "rotulo", "tipo", "rede", "publicacoes"])
            for k, v in nos.items():
                w.writerow([k, v["rotulo"], v["tipo"], v.get("rede", ""), v["n"]])
        with open(pasta / "rede_arestas.csv", "w", encoding="utf-8", newline="") as f:
            w = csv.writer(f, delimiter=";")
            w.writerow(["origem", "destino", "peso"])
            for (a, b), p in arestas.items():
                w.writerow([a, b, p])
    rede_ofensiva = None
    if nos and not protegido:
        gexf_dinamico(nos, dias, pasta / "rede_dinamica.gexf")
    if marca is not None and not protegido:
        rede_ofensiva = {"publicacoes_na_rede": sum(1 for r in itens if r["conta"]), "com_escore": n_esc, "marcadas": n_of,
                         "por_marca": dict(por_marca.most_common()), "nos": len(nos_of), "ligacoes": len(arestas_of),
                         "aviso": "Triagem automática (HateBR para ofensividade; BERTabaporu para ódio por alvo), limiar 0,5, NÃO validada por pessoas: "
                                  "uma ligação entra se a publicação que a gerou foi marcada. Percentuais valem para as publicações lidas e com escore.",
                         "arquivos": None}
        if nos_of:
            gexf(nos_of, arestas_of, pasta / "rede_ofensiva.gexf")
            gexf_dinamico(nos_of, dias_of, pasta / "rede_ofensiva_dinamica.gexf", tipo_of)
            rede_ofensiva["arquivos"] = {"gexf": f"data/casos/{caso['id']}/rede_ofensiva.gexf", "dinamica": f"data/casos/{caso['id']}/rede_ofensiva_dinamica.gexf"}
    desenho = None
    try:
        import networkx as nx
        G = nx.Graph()
        top_tags = {k for k, v in sorted(((k, v) for k, v in nos.items() if v["tipo"] == "hashtag"), key=lambda kv: -kv[1]["n"])[:25]}
        top_contas = {k for k, v in sorted(((k, v) for k, v in nos.items() if v["tipo"] != "hashtag"), key=lambda kv: -kv[1]["n"])[:35]}
        for (a, b), p in arestas.items():
            if a in top_contas and (b in top_tags or b in top_contas):
                G.add_edge(a, b, weight=p)
        if G.number_of_nodes():
            pos2 = nx.spring_layout(G, seed=7, weight="weight")
            desenho = {"nos": [{"id": k, "rotulo": nos[k]["rotulo"], "tipo": nos[k]["tipo"], "rede": nos[k].get("rede"), "n": nos[k]["n"],
                                "x": round(float(pos2[k][0]), 4), "y": round(float(pos2[k][1]), 4)} for k in G.nodes],
                       "arestas": [[a, b, d["weight"]] for a, b, d in G.edges(data=True)]}
    except ImportError:
        pass
    # rede com algum termo no limite em qualquer coleta: o total é piso e o começo pode estar fora
    limite, coletadas = set(), set()
    for f in pasta.glob("manifesto-*.json"):
        for m in json.loads(f.read_text(encoding="utf-8")).get("redes", []):
            if m.get("rede") in ROTULO:  # rede que alguma coleta tentou: 0 é resultado; sem tentativa é "não coletada" (23/10/2026)
                coletadas.add(ROTULO[m["rede"]])
            if any(isinstance(t, dict) and t.get("no_limite") for t in m.get("termos", [])) and m.get("rede") in ROTULO:
                limite.add(ROTULO[m["rede"]])
    g = json.loads((pasta / "google.json").read_text(encoding="utf-8")) if (pasta / "google.json").exists() else {}
    noticias = g.get("noticias") or []
    if caso.get("mascarar_regex"):
        _m = re.compile(caso["mascarar_regex"], re.I)
        noticias = [{**n, "titulo": _m.sub("[menino]", n.get("titulo") or "")} for n in noticias]
    man = json.loads((pasta / "manifesto_latest.json").read_text(encoding="utf-8")) if (pasta / "manifesto_latest.json").exists() else {}
    metodo = [{"rede": ROTULO.get(m.get("rede"), "Google" if m.get("rede") == "google" else m.get("rede")), "ferramenta": m.get("ferramenta") or ", ".join(sorted({t.get("ator", "") for t in m.get("termos", []) if isinstance(t, dict)})),
               "status": m.get("status"), "itens_pedidos_por_termo": m.get("itens_pedidos_por_termo"),
               "termos_no_limite": [t["termo"] for t in m.get("termos", []) if isinstance(t, dict) and t.get("no_limite")]} for m in man.get("redes", [])]
    return {"schema_version": 1, "gerado_em_utc": now_utc(), "id": caso["id"], "titulo": caso["titulo"], "tipo": caso.get("rotulo_tipo"),
            "descricao": caso.get("descricao"), "aviso_termos": caso.get("aviso_termos"), "desde": caso["desde"], "termos": termos,
            "coletado_em": man.get("run_started_utc"), "publicacoes": len(itens), "contas": len(ativ),
            "redes": {ROTULO[k]: {**v, "no_limite": ROTULO[k] in limite, "coletada": ROTULO[k] in coletadas} for k, v in redes.items()}, "eixo_horas_brt": eixo,
            "serie_por_rede": {ROTULO[k]: v for k, v in serie.items()}, "serie_por_termo": serie_termo,
            "decolagem": decolagem,
            "pico": {"hora_brt": eixo[ip] if ip is not None else None, "publicacoes": total[ip] if ip is not None else None,
                     "horas_desde_marco_zero": ip, "meia_vida_horas": mv},
            "marco_zero": marcos, "primeiros": primeiros, "maiores": maiores, "galeria": galeria, "palavras": palavras,
            "rede_ofensiva": rede_ofensiva,
            "rede_desenho": desenho, "rede_arquivos": {"dinamica": None if protegido else f"data/casos/{caso['id']}/rede_dinamica.gexf", "gexf": f"data/casos/{caso['id']}/rede.gexf", "nos": f"data/casos/{caso['id']}/rede_nos.csv",
                                                     "arestas": f"data/casos/{caso['id']}/rede_arestas.csv"} if nos else None,
            "google": {"trends": g.get("trends"), "noticias": len(noticias), "veiculos": len({n.get("veiculo") for n in noticias if n.get("veiculo")}),
                       "primeira_noticia": noticias[0] if noticias else None, "titulos": noticias[:15], "coletado_em": g.get("coletado_em")},
            "lacunas": caso.get("lacunas") or [], "nota_x": caso.get("nota_x"),
            "tom": None, "tom_motivo": "⛔ não calculado: a coleta do caso traz publicações, não os comentários a elas.",
            "metodo": metodo, "privacidade": f"Contas com menos de {minimo:,} seguidores aparecem só como código (ordem de atividade; o selo da plataforma não basta), sem texto nem link. Textos completos só no repositório privado.".replace(",", ".")}


def main(argv=None) -> int:
    root = Path(argv[0]) if argv else Path(".")
    cfg = json.loads((root / "data/config/casos.json").read_text(encoding="utf-8"))
    interno = os.environ.get("ODI_INTERNO_DIR")
    indice = []
    for caso in cfg["casos"]:
        pasta = root / "data/casos" / caso["id"]
        arq = Path(interno) / "casos" / caso["id"] / "itens.csv.gz" if interno else None
        estado = "aguardando confirmação de datas e termos" if not caso.get("coletar") else "sem coleta ainda"
        if caso.get("aba"):
            estado = "página própria do caso"
        if caso.get("unido_a"):
            estado = f"unido ao caso {caso['unido_a']}"  # 22/10/2026: o responsável juntou o 004 ao 003
        n = None
        if arq and arq.exists():
            pasta.mkdir(parents=True, exist_ok=True)
            itens = list(csv.DictReader(gzip.open(arq, "rt", encoding="utf-8"), delimiter=";"))
            out = construir(root, caso, cfg, itens)
            (pasta / "caso.json").write_text(json.dumps(out, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
            estado, n = "coletado", out["publicacoes"]
            print(f"caso {caso['id']}: {n} publicações, {out['contas']} contas · " + " · ".join(f"{k} {v['publicacoes']}" for k, v in out["redes"].items()))
        elif (pasta / "caso.json").exists():
            estado = "coletado"
            n = json.loads((pasta / "caso.json").read_text(encoding="utf-8")).get("publicacoes")
        # 23/10/2026: o cartão do resumo mostra os mesmos números da página do caso (coleta diária grátis em busca.json e
        # conversas importadas), com a data de cada coleta; a coleta paga das redes (caso.json) aparece com a própria data
        resumo, bj = None, pasta / "busca.json"
        if bj.exists():
            b = json.loads(bj.read_text(encoding="utf-8"))
            y, c = b.get("youtube") or {}, b.get("comentarios") or {}
            conv = [{"plataforma": v.get("plataforma"), "comentarios": (v.get("unificacao") or {}).get("comentarios_unicos") or (v.get("unificacao") or {}).get("posts_unicos")}
                    for v in b.get("conversas") or []]
            resumo = {"coletado_em_utc": b.get("coletado_em_utc"), "youtube_videos": y.get("videos"), "youtube_visualizacoes": y.get("visualizacoes"),
                      "youtube_comentarios_lidos": c.get("comentarios"), "noticias": len(b.get("noticias") or []), "checagens": len(b.get("checagens") or []),
                      "conversas": conv}
        coleta_redes = json.loads((pasta / "caso.json").read_text(encoding="utf-8")).get("coletado_em") if (pasta / "caso.json").exists() else None
        indice.append({"id": caso["id"], "titulo": caso["titulo"], "resumo": resumo, "coleta_redes_em": coleta_redes, "tipo": caso.get("rotulo_tipo"), "descricao": caso.get("descricao"),
                       "desde": caso.get("desde"), "janela_indicada": caso.get("janela_indicada"), "redes_previstas": caso.get("redes_previstas"),
                       "estado": estado, "publicacoes": n, "aba": caso.get("aba"), "oculto": bool(caso.get("oculto")), "busca_google": bool(caso.get("busca_google")), "arquivo": f"data/casos/{caso['id']}/caso.json" if estado == "coletado" else None})
    (root / "data/casos").mkdir(parents=True, exist_ok=True)
    (root / "data/casos/indice.json").write_text(json.dumps({"gerado_em_utc": now_utc(), "casos": indice}, ensure_ascii=False, indent=1), encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
