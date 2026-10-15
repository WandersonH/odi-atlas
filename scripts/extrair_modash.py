#!/usr/bin/env python3
"""Relatórios Modash (PDF exportado pelo usuário) → dados do atlas.

Uso:
  python scripts/extrair_modash.py entrada/modash/*.pdf            # só extrai e grava data/modash/
  python scripts/extrair_modash.py entrada/modash/*.pdf --html      # também atualiza as constantes do ODI_Atlas_v15_MVP.html

Os PDFs NÃO entram no repositório (pasta entrada/ está no .gitignore); a prova de origem é o SHA-256 de cada arquivo.
Texto extraído com `pdftotext -layout` (poppler). Nada é estimado aqui: só se lê o que o PDF imprime.

Saídas (data/modash/):
  perfis/<data>_<perfil>.json   tudo o que foi lido de cada relatório (inclui hashtags, menções, interesses, idade × sexo)
  historico.csv                  formato longo (capture_date;profile_id;...;metric;value) — o mesmo do caderno 03
  provas.json                    arquivo, data, SHA-256 e comparação com a captura anterior do mesmo perfil
  conferencia.json               seguidores Modash × coleta própria do mesmo dia (API YouTube / Apify Instagram)
"""
from __future__ import annotations

import csv
import hashlib
import json
import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path

MESES = {m: i for i, m in enumerate(["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"], 1)}
FAIXAS = ["13–17", "18–24", "25–34", "35–44", "45–64"]
ALCANCE = {"<500 accounts": "lt500", "500-1k accounts": "500to1k", "1k-1.5k accounts": "1kto1500", ">1.5k accounts": "gt1500"}
TABELAS = {"Gender split": "genero", "Languages": "idiomas", "Age split": "idade", "Male age split": "idade_masc",
           "Female age split": "idade_fem", "Location by Country": "paises", "Location by City": "cidades",
           "Audience interests": "interesses", "Audience brand affinity": "marcas"}
SUBSECOES = {"All content": "geral", "Videos": "videos", "Shorts": "shorts", "Reels": "reels", "Stories": "stories",
             "Collaborations": "parcerias"}
CELULA = re.compile(r"^([\d,]+) / ([\d.]+)%$")


def numero(s: str) -> float | None:
    s = s.strip().replace(",", "")
    m = re.fullmatch(r"(-?[\d.]+)([kKM]?)%?", s)
    if not m:
        return None
    v = float(m.group(1)) * {"": 1, "k": 1e3, "K": 1e3, "M": 1e6}[m.group(2)]
    return round(v, 4) if s.endswith("%") or v != int(v) else int(v)


def colunas(linha: str) -> list[str]:
    return [c for c in re.split(r"\s{2,}", linha.strip()) if c]


def data_do_arquivo(nome: str) -> str:
    m = re.search(r"-(\w{3})-(\d{1,2})-(\d{4})", nome)
    return f"{m.group(3)}-{MESES[m.group(1)]:02d}-{int(m.group(2)):02d}" if m else ""


def nome_original(nome: str) -> str:
    """O upload prefixa um identificador (ex.: 396b57cc-report-...pdf); o Modash dá o mesmo nome a relatórios
    de plataformas diferentes, por isso a pasta de entrada guarda o prefixo e o atlas registra o nome original."""
    return re.sub(r"^[0-9a-f]{8}-(?=report-)", "", nome)


def texto_pdf(p: Path) -> str:
    return subprocess.run(["pdftotext", "-layout", str(p), "-"], capture_output=True, text=True, check=True).stdout


def normalizado(txt: str) -> str:
    """Texto sem diferenças de espaçamento (o PDF muda a diagramação quando um número muda de largura)."""
    return "\n".join(" ".join(l.split()) for l in txt.splitlines() if l.strip())


def plataforma(txt: str) -> str:
    if "Fake followers" in txt or re.search(r"^\s*Reels\s*$", txt, re.M):
        return "Instagram"
    if re.search(r"^\s*Shorts\s*$", txt, re.M):
        return "YouTube"
    return "TikTok"


def pares_pct(linhas: list[str]) -> list[list]:
    out = []
    for l in linhas:
        c = colunas(l)
        if len(c) == 2 and c[1].endswith("%") and numero(c[1]) is not None:
            out.append([c[0], numero(c[1])])
    return out


def bloco(linhas: list[str], inicio: str, fim: set[str]) -> list[str]:
    try:
        i = next(k for k, l in enumerate(linhas) if l.strip() == inicio)
    except StopIteration:
        return []
    out = []
    for l in linhas[i + 1:]:
        if l.strip() in fim:
            break
        out.append(l)
    return out


def parse(txt: str) -> dict:
    L = txt.splitlines()
    nao_vazias = [l.strip() for l in L if l.strip()]
    r: dict = {"platform": plataforma(txt)}
    i_h = next(k for k, l in enumerate(nao_vazias) if l.startswith("@"))
    r["handle"], r["name"], r["local"] = nao_vazias[i_h], nao_vazias[i_h - 1], nao_vazias[i_h + 1]
    m = re.search(r"^Followers\s{2,}([\d.]+[kKM]?)\s*$", txt, re.M)
    r["followers"] = numero(m.group(1)) if m else None
    # seção Followers: credibilidade, composição, alcance
    seg = bloco(L, "Followers", {"Content"})
    for rot, val in pares_pct(seg):
        if rot == "Fake followers":
            r["fake_followers"] = val
    comp = pares_pct(bloco(L, "Audience breakdown", {"Audience reachability", "Followers growth"}))
    if comp:
        r["audience_breakdown"] = {k: v for k, v in comp}
    alc = dict(pares_pct(bloco(L, "Audience reachability", {"Followers growth"})))
    if alc:
        r["reachability"] = [alc.get(k) for k in ALCANCE]
    # seção Content
    sub, conteudo = "cabecalho", {}
    for l in bloco(L, "Content", {"Engagement rate distribution", "Creator Interests", "Audience data by followers"}):
        s = l.strip()
        if s in SUBSECOES:
            sub = SUBSECOES[s]
            continue
        c = colunas(l)
        if len(c) == 2:
            v = numero(c[1].split()[0])
            if v is not None:
                conteudo.setdefault(sub, {})[c[0]] = v
                if c[0] == "Engagement rate" and len(c[1].split()) > 1:
                    conteudo[sub]["comparacao"] = c[1].split(None, 1)[1]
    g = conteudo.get("geral", {})
    r["engagement"] = g.get("Engagement rate")
    r["engagement_comparison"] = g.get("comparacao")
    for k, chave in [("Average likes", "avg_likes"), ("Average comments", "avg_comments"), ("Average views", "avg_views"),
                     ("Average saves", "avg_saves"), ("Average shares", "avg_shares"),
                     ("Estimated impressions", "impressions"), ("Estimated reach", "estimated_reach")]:
        if k in g:
            r[chave] = g[k]
    if "Fake likers" in conteudo.get("cabecalho", {}):
        r["fake_likers"] = conteudo["cabecalho"]["Fake likers"]
    for fmt, chave_views in [("reels", "Average reel plays"), ("videos", "Average video views"), ("shorts", "Average short views")]:
        d = conteudo.get(fmt)
        if d:
            r[fmt] = {"engagement": d.get("Engagement rate"), "views": d.get(chave_views), "likes": d.get("Average likes"),
                      "comments": d.get("Average comments")}
            if "Average shares" in d:
                r[fmt]["shares"] = d["Average shares"]
    if conteudo.get("stories"):
        r["stories"] = {"reach": conteudo["stories"].get("Estimated reach"), "impressions": conteudo["stories"].get("Estimated impressions")}
    if conteudo.get("parcerias"):
        r["paid"] = {"engagement": conteudo["parcerias"].get("Paid engagement"), "views": conteudo["parcerias"].get("Paid views")}
    ci = [l.strip() for l in bloco(L, "Creator Interests", {"Audience data by followers"}) if l.strip()]
    if ci:
        r["creator_interests"] = ci
    # resumo da audiência (seguidores)
    res = bloco(L, "Audience data by followers", {"Audience data by likers"})
    cab = {"Gender", "Age", "Countries", "Cities", "Languages"}
    resumo, atual = {}, None
    for l in res:
        s = l.strip()
        if s in cab:
            atual = s
            continue
        if atual:
            resumo.setdefault(atual, []).extend(pares_pct([l]))
    gen = dict(resumo.get("Gender", []))
    r["female"], r["male"] = gen.get("Female"), gen.get("Male")
    r["ages"] = {f: dict(resumo.get("Age", [])).get(f.replace("–", "-")) for f in FAIXAS}
    r["brazil"] = dict(resumo.get("Countries", [])).get("Brazil")
    if resumo.get("Cities"):
        r["cities"] = resumo["Cities"]
    # hashtags e menções mais usadas pelo perfil (% dos posts analisados pelo Modash)
    hs, ms = [], []
    i_pop = next((k for k, l in enumerate(L) if re.match(r"^\s*Popular hashtags\s{2,}Popular mentions\s*$", l)), None)
    if i_pop is not None:
        for l in L[i_pop + 1:]:
            if not l.strip():
                continue
            c = colunas(l)
            if not c or not (c[0].startswith("#") or c[0].startswith("@")):
                break
            for a, b in zip(c[::2], c[1::2]):
                (hs if a.startswith("#") else ms).append([a, numero(b)])
    r["hashtags"], r["mentions"] = hs, ms
    # tabelas detalhadas (com contagens absolutas estimadas)
    tab, atual, colnomes = {}, None, []
    i0 = next((k for k, l in enumerate(L) if l.strip() == "Gender split"), len(L))
    for l in L[i0:]:
        s = l.strip()
        if not s:
            continue
        if s in TABELAS:
            atual, colnomes = TABELAS[s], None
            continue
        if atual is None:
            continue
        c = colunas(l)
        if colnomes is None:
            colnomes = [x.lower() for x in c[1:]]
            continue
        if len(c) == len(colnomes) + 1 and all(x == "-" or CELULA.match(x) for x in c[1:]):
            linha = {"rotulo": c[0]}
            for nome, x in zip(colnomes, c[1:]):
                m = CELULA.match(x)
                linha[nome] = None if x == "-" else {"n": int(m.group(1).replace(",", "")), "pct": float(m.group(2))}
            tab.setdefault(atual, []).append(linha)
    r["tabelas"] = tab
    if "likers" in (tab.get("genero") or [{}])[0]:
        gl = {x["rotulo"]: x["likers"]["pct"] for x in tab["genero"] if x.get("likers")}
        il = {x["rotulo"]: x["likers"]["pct"] for x in tab.get("idade", []) if x.get("likers")}
        r["likers"] = {"female": gl.get("Female"), "male": gl.get("Male"), "ages": [il.get(f.replace("–", "-")) for f in FAIXAS]}
    return {k: v for k, v in r.items() if v not in (None, [], {})}


def historico(perfil: dict, pid: str, data: str, fonte: str, dicionario: dict) -> list[dict]:
    p = perfil
    met = {k: p.get(k) for k in ("followers", "engagement", "avg_likes", "avg_comments", "impressions", "estimated_reach",
                                 "female", "male", "brazil", "fake_followers", "fake_likers", "avg_views", "avg_shares", "avg_saves")}
    if p.get("likers"):
        met["likers_female"], met["likers_male"] = p["likers"]["female"], p["likers"]["male"]
        for f, v in zip(FAIXAS, p["likers"]["ages"]):
            met[f"likers_age_{f}"] = v
    for k in ("engagement", "views", "likes", "comments", "shares"):
        met[f"reels_{k}"] = (p.get("reels") or {}).get(k)
    for k, v in zip(ALCANCE.values(), p.get("reachability") or []):
        met[f"followers_reach_{k}"] = v
    for f in FAIXAS:
        met[f"age_{f}"] = p.get("ages", {}).get(f)
    out = []
    for k, v in met.items():
        if v is None or k not in dicionario:
            continue
        rot, uni, nota = dicionario[k]
        out.append({"capture_date": data, "profile_id": pid, "name": p["name"], "platform": p["platform"], "handle": p["handle"],
                    "metric": k, "metric_label": rot, "value": v, "unit": uni, "source_pdf": fonte, "notes": nota,
                    "capture_type": "PDF Modash — extração textual"})
    return out


def comparar(atual: dict, anterior: dict) -> dict:
    """Quais indicadores mudaram em relação à captura anterior do mesmo perfil."""
    a = {(r["metric"]): r["value"] for r in atual}
    b = {(r["metric"]): r["value"] for r in anterior}
    comuns = sorted(set(a) & set(b))
    mud = [{"metric": k, "antes": b[k], "depois": a[k]} for k in comuns if a[k] != b[k]]
    return {"indicadores_comparados": len(comuns), "iguais": len(comuns) - len(mud), "mudaram": mud}


# ---------- página ----------
def ler_const(html: str, nome: str):
    m = re.search(r"const " + nome + r"=(.*?);\n", html, re.S)
    return json.loads(m.group(1)), m


def trocar_const(html: str, nome: str, valor) -> str:
    _, m = ler_const(html, nome)
    return html[:m.start(1)] + json.dumps(valor, ensure_ascii=False, separators=(",", ":")) + html[m.end(1):]


def main(argv: list[str]) -> int:
    root = Path(".")
    pdfs = [Path(a) for a in argv if a.lower().endswith(".pdf")]
    if not pdfs:
        print("⛔ nenhum PDF informado")
        return 1
    pag = root / "ODI_Atlas_v15_MVP.html"
    html = pag.read_text(encoding="utf-8")
    dados, _ = ler_const(html, "DATA")
    dicionario, _ = ler_const(html, "DICTIONARY")
    hist_antigo, _ = ler_const(html, "INITIAL_HISTORY")
    provas, _ = ler_const(html, "PROOFS")
    ids = {(p["platform"], p["handle"].lower()): p["id"] for p in dados["profiles"]}
    saida = root / "data/modash"
    (saida / "perfis").mkdir(parents=True, exist_ok=True)
    lidos = []
    for p in sorted(pdfs, key=lambda x: (data_do_arquivo(x.name), x.name)):
        txt = texto_pdf(p)
        perf = parse(txt)
        pid = ids.get((perf["platform"], perf["handle"].lower()))
        if not pid:
            print(f"⛔ {p.name}: perfil {perf['platform']} {perf['handle']} não está no atlas — ignorado")
            continue
        data = data_do_arquivo(p.name)
        perf.update({"id": pid, "source": nome_original(p.name), "captured_at": data,
                     "sha256": hashlib.sha256(p.read_bytes()).hexdigest(), "texto_normalizado_sha256":
                     hashlib.sha256(normalizado(txt).encode()).hexdigest()})
        (saida / "perfis" / f"{data}_{pid}.json").write_text(json.dumps(perf, ensure_ascii=False, indent=1), encoding="utf-8")
        lidos.append(perf)
        print(f"{data} {pid:10s} {perf['platform']:9s} {perf['handle']:18s} seguidores {perf.get('followers')} "
              f"engaj. {perf.get('engagement')} ← {p.name}")
    # histórico: as capturas novas substituem registros do mesmo perfil/data/indicador/arquivo
    novos = [r for perf in lidos for r in historico(perf, perf["id"], perf["captured_at"], perf["source"], dicionario)]
    chave = lambda r: (r["capture_date"], r["profile_id"], r["metric"], r["source_pdf"])  # noqa: E731
    hist = {chave(r): r for r in hist_antigo}
    hist.update({chave(r): r for r in novos})
    hist = sorted(hist.values(), key=lambda r: (r["capture_date"], r["profile_id"], r["metric"]))
    campos = ["capture_date", "profile_id", "name", "platform", "handle", "metric", "metric_label", "value", "unit",
              "source_pdf", "notes", "capture_type"]
    with open(saida / "historico.csv", "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, campos, delimiter=";", lineterminator="\n")
        w.writeheader()
        w.writerows(hist)
    # provas: SHA-256 + comparação com a captura anterior (por indicador e por texto)
    por_arquivo = {(pv["file"], pv["sha256"]): pv for pv in provas}
    for perf in lidos:
        anteriores = sorted({r["capture_date"] for r in hist if r["profile_id"] == perf["id"] and r["capture_date"] < perf["captured_at"]})
        pv = {"file": perf["source"], "date": perf["captured_at"], "sha256": perf["sha256"], "profile_id": perf["id"],
              "textual_diff_from_prior_day": por_arquivo.get((perf["source"], perf["sha256"]), {}).get("textual_diff_from_prior_day")}
        if anteriores:
            ant = anteriores[-1]
            cmp = comparar([r for r in hist if r["profile_id"] == perf["id"] and r["capture_date"] == perf["captured_at"]],
                           [r for r in hist if r["profile_id"] == perf["id"] and r["capture_date"] == ant])
            pv["comparado_com"] = ant
            pv.update(cmp)
            ant_txt = next((x for x in lidos if x["id"] == perf["id"] and x["captured_at"] == ant), None)
            if ant_txt:
                pv["texto_igual_ao_anterior"] = ant_txt["texto_normalizado_sha256"] == perf["texto_normalizado_sha256"]
            if not cmp["mudaram"]:
                pv["textual_diff_from_prior_day"] = ("idêntico" if pv.get("texto_igual_ao_anterior")
                                                     else f"vs. {ant}: {cmp['iguais']} de {cmp['indicadores_comparados']} indicadores iguais (nenhum mudou)")
            else:
                pv["textual_diff_from_prior_day"] = (f"vs. {ant}: {cmp['iguais']} de {cmp['indicadores_comparados']} indicadores iguais; "
                                                     "mudaram " + ", ".join(m["metric"] for m in cmp["mudaram"]))
        por_arquivo[(perf["source"], perf["sha256"])] = pv
    provas = sorted(por_arquivo.values(), key=lambda x: (x["date"], x["file"]))
    (saida / "provas.json").write_text(json.dumps(provas, ensure_ascii=False, indent=1), encoding="utf-8")
    # conferência com a coleta própria do mesmo dia
    conf = conferencia(root, lidos)
    (saida / "conferencia.json").write_text(json.dumps(conf, ensure_ascii=False, indent=1), encoding="utf-8")
    for c in conf["linhas"]:
        print(f"  conferência {c['profile_id']}: Modash {c['modash']} × própria {c.get('coleta_propria')} ({c.get('diferenca_pct')}%)")
    if "--html" in argv:
        ultimo = {}
        for perf in lidos:
            if perf["captured_at"] >= ultimo.get(perf["id"], {}).get("captured_at", ""):
                ultimo[perf["id"]] = perf
        extras = ("sha256", "texto_normalizado_sha256", "tabelas", "local", "paid", "engagement_comparison")
        for i, p in enumerate(dados["profiles"]):
            n = ultimo.get(p["id"])
            if n and n["captured_at"] >= p["captured_at"]:
                novo = {k: v for k, v in n.items() if k not in extras}
                novo = {**{k: p[k] for k in p if k in ("source_caveat",)}, **novo}
                dados["profiles"][i] = {k: novo[k] for k in ["id", "platform", "name", "handle", "source", "captured_at"]} | \
                    {k: v for k, v in novo.items() if k not in ("id", "platform", "name", "handle", "source", "captured_at")}
        bn, _ = ler_const(html, "BN_BASE")
        for b in bn:
            n = next((x for x in ultimo.values() if x["platform"] == b["platform"] and x["handle"].lstrip("@").lower() == b["handle"].lower()), None)
            if n and n["captured_at"] >= b["capture_date"]:
                d = datetime.strptime(n["captured_at"], "%Y-%m-%d").strftime("%d/%m/%Y")
                b.update({"followers": n["followers"], "capture_date": n["captured_at"], "source_label": f"Relatório Modash · {d}"})
        html = trocar_const(html, "DATA", dados)
        html = trocar_const(html, "BN_BASE", bn)
        html = trocar_const(html, "INITIAL_HISTORY", hist)
        html = trocar_const(html, "PROOFS", [{k: pv.get(k) for k in ("file", "date", "sha256", "textual_diff_from_prior_day")} for pv in provas])
        pag.write_text(html, encoding="utf-8")
        print(f"página atualizada: {len(ultimo)} perfis, {len(hist)} registros no histórico, {len(provas)} provas")
    return 0


def conferencia(root: Path, lidos: list[dict]) -> dict:
    """Seguidores do relatório Modash × coleta própria (mesma data), quando existe."""
    fontes = {"YouTube": root / "data/seguidores/youtube_latest.csv", "Instagram": root / "data/seguidores/latest.csv"}
    proprio = {}
    for plat, f in fontes.items():
        if f.exists():
            for r in csv.DictReader(open(f, encoding="utf-8"), delimiter=";"):
                if r["platform"] == plat and r["followers"].isdigit():
                    for u in (r["url"], r["source_url"]):
                        h = u.split("?")[0].rstrip("/").split("/")[-1].lstrip("@").lower()
                        proprio[(plat, h, r["captured_at"])] = (int(r["followers"]), r["source_url"], f.name)
    ultimo = {}
    for p in lidos:
        if p["captured_at"] >= ultimo.get(p["id"], {}).get("captured_at", ""):
            ultimo[p["id"]] = p
    linhas = []
    for p in sorted(ultimo.values(), key=lambda x: x["id"]):
        h = p["handle"].lstrip("@").lower()
        ref = proprio.get((p["platform"], h, p["captured_at"]))
        l = {"profile_id": p["id"], "platform": p["platform"], "handle": p["handle"], "data": p["captured_at"], "modash": p["followers"]}
        if ref:
            l.update({"coleta_propria": ref[0], "fonte_propria": ref[2], "url": ref[1],
                      "diferenca_pct": round(100 * (p["followers"] - ref[0]) / ref[0], 1)})
        else:
            l["coleta_propria"] = None
            l["motivo"] = ("sem coleta própria de seguidores nesta plataforma" if p["platform"] == "TikTok"
                           else "sem coleta própria deste perfil na mesma data")
        linhas.append(l)
    return {"nota": "Modash imprime seguidores arredondados (ex.: 16.5M). Coleta própria: YouTube Data API (inscritos, "
                    "arredondados pelo YouTube a 3 dígitos) e Apify para Instagram. Diferença = (Modash − própria) ÷ própria.",
            "linhas": linhas}


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
