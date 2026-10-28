#!/usr/bin/env python3
"""Bolhas de apoio: quem declarou voto ou apoio a Lula ou a Flávio Bolsonaro no 2º turno de 2026 (perfis com 100 mil+ seguidores)
e os políticos eleitos em 2026 com o sinal indireto do partido.

Pedido do responsável (28/10/2026, 15h05): "seria possível construirmos uma página com essa lógica com nome bolhas de apoio"
(referência: quemapoiaquem.com.br). Bases escolhidas: políticos pelo TSE (grátis), coleta paga X + Instagram (caso 015, teto US$ 4,00)
e pedir a base ao Quem Apoia Quem (e-mail, fora deste script).

Três passos (cada um pode rodar sozinho):
  --tse      votos dos eleitos (TSE, votacao_candidato_munzona_2026.zip, descoberto pelo CKAN) → privado/bolhas_apoio/votos_2026.json.
             Sem o arquivo, o tamanho da bolha do político fica ⛔ (nada estimado).
  --perfis   seguidores dos autores de reels com frase de declaração (o leitor de reels não traz seguidores): apify/instagram-scraper
             "details", conta 1, teto em casos.json (perfis_teto_usd), cada perfil lido uma vez só.
  --montar   data/bolhas_apoio/bolhas.json (público).
Regras: declaração = frase de voto/apoio na primeira pessoa encontrada no texto (pré-codificação automática, conferência humana pendente);
negação logo antes ("nunca vou votar no Lula") anula; frase dos dois lados = ambígua, fora da contagem; republicação (RT) não conta.
Nome, link e trecho só de contas com 100 mil+ seguidores (acima da regra geral de 10 mil do Atlas). Universo de figuras públicas: ⛔.
Uso: python scripts/bolhas_apoio.py --tse --perfis --montar
"""
from __future__ import annotations

import csv
import datetime as dt
import gzip
import io
import json
import os
import re
import sys
import tempfile
import zipfile
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from build_conteudo import norm  # noqa: E402
from net import now_utc  # noqa: E402

CASO = "015"
MIN_SEG = 100000
CARGOS = ("GOVERNADOR", "SENADOR", "DEPUTADO FEDERAL", "DEPUTADO ESTADUAL", "DEPUTADO DISTRITAL")
FAIXAS = [(100_000, "100 mil–500 mil"), (500_000, "500 mil–1 mi"), (1_000_000, "1 mi–5 mi"), (5_000_000, "5 mi–10 mi"), (10_000_000, "10 mi+")]
NEG = re.compile(r"(?<![a-z0-9])(nao|nunca|jamais|nem|ninguem|quem)(?![a-z0-9])[a-z0-9 #]{0,18}$")
_L = r"(lula|13|#lula13|#elula13|#elula)"
_F = r"(flavio|flavio bolsonaro|22|#flavio22|#flaviopresidente|#flavio)"


def _rx(c):
    return re.compile(
        r"(?<![a-z0-9])(meu voto (e|eh|sera|vai ser|ja e) (do |no |o )?C|voto no C|voto em C|vou votar (no |em |o )?C|vou de C|voto C"
        r"|fechado com (o )?C|fechada com (o )?C|(to|tou|estou|tamo|estamos) com (o )?C|declaro (meu |o meu )?(voto|apoio)( [a-z0-9#]+){0,6} C"
        r"|apoio (o )?C no segundo turno)(?![a-z0-9])".replace("C", c))


RX = {"lula": _rx(_L), "flavio": _rx(_F),
      "nulo": re.compile(r"(?<![a-z0-9])(vou anular|anular (o |meu )?voto|meu voto (e|sera) nulo|vou votar nulo|vou votar em branco|nem lula nem flavio"
                         r"|nao voto em nenhum)(?![a-z0-9])")}
HASHTAGS_SOZINHAS = re.compile(r"^ ?(#[a-z0-9]+ ?)+$")


def classificar(texto: str) -> tuple[str | None, dict]:
    """Lado declarado no texto: 'lula', 'flavio', 'nulo', 'ambiguo' ou None; e o trecho de cada lado."""
    t = norm(texto)
    achados = {}
    for lado, rx in RX.items():
        for m in rx.finditer(t):
            if NEG.search(t[max(0, m.start() - 24):m.start()]):
                continue
            achados[lado] = t[max(0, m.start() - 60):m.end() + 60].strip()
            break
    lados = [k for k in ("lula", "flavio") if k in achados]
    if len(lados) == 2:
        return "ambiguo", achados
    if lados:
        return lados[0], achados
    return ("nulo", achados) if "nulo" in achados else (None, achados)


def faixa(n: int) -> str | None:
    out = None
    for lim, nome in FAIXAS:
        if n >= lim:
            out = nome
    return out


def semana(iso: str) -> str | None:
    if not iso:
        return None
    try:
        d = (dt.datetime.fromisoformat(iso.replace("Z", "+00:00")) - dt.timedelta(hours=3)).date()
    except ValueError:
        return None
    return (d - dt.timedelta(days=d.weekday())).isoformat()


def handle(url: str, plataforma: str) -> str | None:
    u = (url or "").strip().lower()
    dom = {"x": r"(?:x|twitter)\.com/", "instagram": r"instagram\.com/"}[plataforma]
    m = re.search(dom + r"@?([a-z0-9_.]+)", u)
    h = m.group(1).strip(".") if m else None
    return h if h and h not in ("p", "reel", "explore", "home", "intent", "share", "hashtag", "i") else None


# ---------------------------------------------------------------- TSE
def votos_munzona(zp: Path) -> dict:
    """{SQ_CANDIDATO: {turno: {"votos": n, "situacao": s}}} sem presidente; ignora o arquivo _BR quando há arquivos por UF."""
    z = zipfile.ZipFile(zp)
    nomes = [n for n in z.namelist() if n.lower().endswith(".csv")]
    por_uf = [n for n in nomes if not re.search(r"_BR(ASIL)?\.csv$", n, re.I)]
    out: dict = defaultdict(lambda: defaultdict(lambda: {"votos": 0, "situacao": None}))
    for nome in por_uf or nomes:
        with z.open(nome) as f:
            for r in csv.DictReader(io.TextIOWrapper(f, encoding="latin-1", newline=""), delimiter=";"):
                if (r.get("CD_CARGO") or "").strip() in ("1", "2"):
                    continue
                reg = out[r["SQ_CANDIDATO"]][r["NR_TURNO"]]
                reg["votos"] += int(r.get("QT_VOTOS_NOMINAIS") or r.get("QT_VOTOS_NOMINAIS_VALIDOS") or 0)
                reg["situacao"] = r.get("DS_SIT_TOT_TURNO") or reg["situacao"]
    return {k: dict(v) for k, v in out.items()}


def passo_tse(priv: Path) -> dict:
    from fetch_sources import CKAN, pick_munzona
    from collect_alienacao import baixar
    from net import get_json
    man = {"lido_em_utc": now_utc()}
    try:
        res = get_json(CKAN.format(year="2026"), timeout=60)["result"]["resources"]
        rec = pick_munzona(res, "2026")
        if not rec:
            man["status"] = "⛔ o TSE ainda não publicou votacao_candidato_munzona_2026.zip no Portal de Dados Abertos"
        else:
            man["fonte"] = rec["url"]
            with tempfile.TemporaryDirectory() as t:
                zp = baixar(rec["url"], Path(t))
                man["bytes"] = zp.stat().st_size
                votos = votos_munzona(zp)
            (priv / "votos_2026.json").write_text(json.dumps(votos), encoding="utf-8")
            man.update(status="ok", candidatos=len(votos))
    except Exception as e:  # noqa: BLE001
        man["status"] = f"⛔ {type(e).__name__}: {str(e)[:200]}"
    (priv / "votos_2026_manifesto.json").write_text(json.dumps(man, ensure_ascii=False, indent=1), encoding="utf-8")
    print("TSE votos:", man["status"])
    return man


def sinal(partido: str, uf: str, cfg: dict) -> tuple[str, str, list]:
    p = cfg["partidos"].get(partido)
    if not p:
        return "sem_fonte", "posição do partido não encontrada nas fontes", []
    pos = p["posicao"]
    if pos == "por_uf":
        pos = "lula" if uf in p["lula_ufs"] else p["demais_ufs"]
    return pos, p["nota"], p["fontes"]


def politicos(root: Path, priv: Path, cfg: dict) -> tuple[list[dict], dict]:
    cand = list(csv.DictReader(gzip.open(root / "data/tse/candidatos_2026.csv.gz", "rt", encoding="utf-8"), delimiter=";"))
    redes = defaultdict(dict)
    for r in csv.DictReader(gzip.open(root / "data/tse/redes_sociais_candidatos_2026.csv.gz", "rt", encoding="utf-8"), delimiter=";"):
        if r["PLATAFORMA"] in ("x", "instagram"):
            h = handle(r["DS_URL"], r["PLATAFORMA"])
            if h:
                redes[r["SQ_CANDIDATO"]].setdefault(r["PLATAFORMA"], h)
    vf = priv / "votos_2026.json"
    votos = json.loads(vf.read_text(encoding="utf-8")) if vf.exists() else {}
    vman = json.loads((priv / "votos_2026_manifesto.json").read_text(encoding="utf-8")) if (priv / "votos_2026_manifesto.json").exists() else {}
    out, vistos = [], set()
    for r in cand:
        if r["DS_CARGO"] not in CARGOS:
            continue
        sq, t = r["SQ_CANDIDATO"], r["NR_TURNO"]
        v = votos.get(sq, {})
        sit = (v.get(t) or {}).get("situacao") or r["DS_SIT_TOT_TURNO"]
        eleito = sit.startswith("ELEITO")
        segundo = r["DS_CARGO"] == "GOVERNADOR" and t == "2"
        if not (eleito or (segundo and not sit.startswith("NÃO ELEITO"))) or sq in vistos:
            continue
        vistos.add(sq)
        pos, nota, fontes = sinal(r["SG_PARTIDO"], r["SG_UF"], cfg)
        out.append({"sq": sq, "nome": r["NM_URNA_CANDIDATO"], "cargo": r["DS_CARGO"], "uf": r["SG_UF"], "partido": r["SG_PARTIDO"],
                    "situacao": sit if eleito else "disputou o 2º turno (resultado não lido do TSE)", "votos": (v.get(t) or {}).get("votos"),
                    "sinal": pos, "sinal_nota": nota, "sinal_fontes": fontes, "x": redes[sq].get("x"), "instagram": redes[sq].get("instagram"),
                    "declarou": None})
    universo = Counter(p["cargo"] for p in out)
    return out, {"universo_por_cargo": dict(universo), "fonte": "TSE, candidaturas 2026 (data/tse/candidatos_2026.csv.gz) e redes declaradas ao TSE",
                 "votos": vman.get("status") or "⛔ votos por candidato ainda não lidos do TSE"}


# ---------------------------------------------------------------- coleta (caso 015)
def itens(priv_caso: Path, desde: str) -> list[dict]:
    arq = priv_caso / "itens.csv.gz"
    if not arq.exists():
        return []
    rows = [r for r in csv.DictReader(gzip.open(arq, "rt", encoding="utf-8"), delimiter=";") if (r.get("publicado_em") or "")[:10] >= desde
            and (r.get("publicado_em") or "")[:10] <= "2026-10-25"]
    return list({(r["rede"], r["item_id"]): r for r in rows}.values())


def pendentes_ig(rows: list[dict], ja: dict) -> list[str]:
    contas = Counter()
    for r in rows:
        if r["rede"] == "instagram" and not str(r.get("seguidores") or "").isdigit() and r["conta"] and r["conta"].lower() not in ja:
            lado, _ = classificar(r.get("texto") or "")
            if lado in ("lula", "flavio"):
                contas[r["conta"].lower()] += int(r.get("visualizacoes") or 0) if str(r.get("visualizacoes") or "").isdigit() else 0
    return [c for c, _ in contas.most_common()]


def passo_perfis(root: Path, priv: Path, caso: dict, executar=None) -> dict:
    arq = priv / "perfis_ig.json"
    ja = json.loads(arq.read_text(encoding="utf-8")) if arq.exists() else {}
    man_f = priv / "perfis_ig_manifesto.json"
    man = json.loads(man_f.read_text(encoding="utf-8")) if man_f.exists() else {"runs": [], "gasto_usd": 0.0}
    sobra = round(caso.get("perfis_teto_usd", 0) - man["gasto_usd"], 4)
    lista = pendentes_ig(itens(Path(os.environ["ODI_INTERNO_DIR"]) / "casos" / CASO, caso["desde"]), ja)
    n = min(len(lista), int((sobra * 0.9) / 0.0026)) if sobra > 0.05 else 0
    if not n:
        print(f"perfis IG: nada a ler (pendentes {len(lista)}, sobra do teto US$ {sobra})")
        return man
    if executar is None:
        from collect_meta_apify import run_actor
        tok = os.environ.get(caso["segredo"], "").strip()
        if not tok:
            print("⛔ APIFY_TOKEN ausente")
            return man
        executar = lambda a, p, c: run_actor(tok, a, p, c)  # noqa: E731
    pl = {"directUrls": [f"https://www.instagram.com/{c}/" for c in lista[:n]], "resultsType": "details", "resultsLimit": 1}
    run, its = executar("apify~instagram-scraper", pl, round(min(sobra, 0.0026 * n * 1.3 + 0.02), 4))
    for x in its or []:
        u = str(x.get("username") or "").lower()
        if u:
            ja[u] = {"seguidores": x.get("followersCount"), "nome": x.get("fullName"), "verificada": x.get("verified")}
    for c in lista[:n]:
        ja.setdefault(c, {"seguidores": None, "erro": "sem item"})
    gasto = float((run or {}).get("usageTotalUsd") or 0) or round(0.0026 * len(its or []), 4)
    man["runs"].append({"run": (run or {}).get("id"), "pedidos": n, "itens": len(its or []), "custo_usd": gasto, "em_utc": now_utc()})
    man["gasto_usd"] = round(man["gasto_usd"] + gasto, 4)
    arq.write_text(json.dumps(ja, ensure_ascii=False, indent=1), encoding="utf-8")
    man_f.write_text(json.dumps(man, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"perfis IG: {n} pedidos, {len(its or [])} lidos, US$ {gasto}")
    return man


def montar(root: Path, priv: Path, caso: dict) -> dict:
    cfg = json.loads((root / "data/config/apoio_partidos_2t.json").read_text(encoding="utf-8"))
    pols, pman = politicos(root, priv, cfg)
    perfis = json.loads((priv / "perfis_ig.json").read_text(encoding="utf-8")) if (priv / "perfis_ig.json").exists() else {}
    pman_ig = json.loads((priv / "perfis_ig_manifesto.json").read_text(encoding="utf-8")) if (priv / "perfis_ig_manifesto.json").exists() else {}
    rows = itens(Path(os.environ["ODI_INTERNO_DIR"]) / "casos" / CASO, caso["desde"])
    por_rede = defaultdict(Counter)
    autores = {}
    conferencia = []
    for r in rows:
        rede = r["rede"]
        por_rede[rede]["lidas"] += 1
        txt = r.get("texto") or ""
        if rede == "x" and norm(txt).startswith(" rt "):
            por_rede[rede]["republicacoes"] += 1
            continue
        lado, ach = classificar(txt)
        if not lado:
            continue
        por_rede[rede]["com_frase"] += 1
        por_rede[rede][f"lado_{lado}"] += 1
        seg = int(r["seguidores"]) if str(r.get("seguidores") or "").isdigit() else None
        nome = r.get("nome_conta") or ""
        if seg is None and rede == "instagram":
            p = perfis.get((r["conta"] or "").lower()) or {}
            seg, nome = p.get("seguidores"), p.get("nome") or nome
        conferencia.append([rede, r["item_id"], r["conta"], seg, r["publicado_em"], lado, r["url"], txt])
        if seg is None:
            por_rede[rede]["sem_seguidores"] += 1
            continue
        if seg < MIN_SEG or lado == "ambiguo":
            por_rede[rede]["abaixo_100mil" if seg < MIN_SEG else "ambiguas"] += 1
            continue
        por_rede[rede]["declaracoes_100mil"] += 1
        k = (rede, (r["conta"] or "").lower())
        a = autores.setdefault(k, {"rede": rede, "conta": r["conta"], "nome": nome, "seguidores": seg, "verificada": r.get("verificada"), "provas": []})
        a["seguidores"] = max(a["seguidores"], seg)
        a["provas"].append({"lado": lado, "data": (r.get("publicado_em") or "")[:10], "url": r["url"], "trecho": ach.get(lado, "")[:200],
                            "curtidas": int(r["curtidas"]) if str(r.get("curtidas") or "").isdigit() else None,
                            "visualizacoes": int(r["visualizacoes"]) if str(r.get("visualizacoes") or "").isdigit() else None})
    pessoas = []
    for a in autores.values():
        lados = {p["lado"] for p in a["provas"]}
        lado = "ambiguo" if {"lula", "flavio"} <= lados else ("lula" if "lula" in lados else "flavio" if "flavio" in lados else "nulo")
        a["provas"].sort(key=lambda p: p["data"])
        a.update(lado=lado, primeira=a["provas"][0]["data"], faixa=faixa(a["seguidores"]), provas=a["provas"][:5], n_provas=len(a["provas"]),
                 conferencia="pendente (pré-codificação automática por frase)")
        pessoas.append(a)
    pessoas.sort(key=lambda a: -a["seguidores"])
    # políticos que declararam pela própria conta
    idx = {(r, h): p for p in pols for r, h in (("x", p["x"]), ("instagram", p["instagram"])) if h}
    for a in pessoas:
        p = idx.get((a["rede"], (a["conta"] or "").lower()))
        if p and a["lado"] in ("lula", "flavio", "nulo"):
            p["declarou"] = a["lado"]
            a["politico"] = f"{p['cargo'].title()} {p['uf']} ({p['partido']})"
    sem = defaultdict(Counter)
    for a in pessoas:
        if a["lado"] in ("lula", "flavio"):
            sem[semana(a["primeira"])][a["lado"]] += 1
    dec = [a for a in pessoas if a["lado"] in ("lula", "flavio")]
    man_col = []
    for f in sorted((root / "data/casos" / CASO).glob("manifesto-*.json")):
        m = json.loads(f.read_text(encoding="utf-8"))
        for rd in m.get("redes", []):
            for t in rd.get("termos", []):
                if isinstance(t, dict) and "termo" in t:
                    man_col.append({"rede": rd["rede"], "termo": t["termo"], "itens": t.get("itens"), "no_periodo": t.get("no_periodo"),
                                    "no_limite": t.get("no_limite"), "run": t.get("run")})
    out = {"gerado_em_utc": now_utc(), "pedido": "Responsável em 28/10/2026, 15h05: \"seria possível construirmos uma página com essa lógica com nome bolhas de apoio\" (referência: quemapoiaquem.com.br)",
           "referencia": {"nome": "Quem apoia quem", "url": "https://quemapoiaquem.com.br/", "nota": "base curada por Allan Hert/Hertwave; não reproduzida aqui (pedido de dados enviado à parte)"},
           "periodo": {"desde": caso["desde"], "ate": "2026-10-25"},
           "regras": {"min_seguidores": MIN_SEG, "declaracao": "frase de voto ou apoio na primeira pessoa no texto da própria conta; negação logo antes anula; os dois lados = ambígua (fora); republicação não conta",
                      "conferencia": "pré-codificação automática; conferência humana pendente (planilha no privado)",
                      "nao_e": "não é pesquisa eleitoral e não mede intenção de voto"},
           "universo": {"figuras_publicas": None, "fonte": "⛔ nenhuma plataforma informa quantos perfis com 100 mil+ seguidores declararam voto",
                        "amostra": "busca por frase no X (Top, curtidas mínimas, 01/08 a 25/10) e busca de reels no Instagram (sem filtro de data no buscador)"},
           "coleta": {"por_rede": {k: dict(v) for k, v in por_rede.items()}, "buscas": man_col, "perfis_instagram_lidos": len(perfis),
                      "perfis_instagram_runs": pman_ig.get("runs", [])},
           "totais": {"pessoas": len(pessoas), "lula": sum(1 for a in pessoas if a["lado"] == "lula"), "flavio": sum(1 for a in pessoas if a["lado"] == "flavio"),
                      "nulo": sum(1 for a in pessoas if a["lado"] == "nulo"), "ambiguo": sum(1 for a in pessoas if a["lado"] == "ambiguo")},
           "por_faixa": {f: {l: sum(1 for a in dec if a["faixa"] == f and a["lado"] == l) for l in ("lula", "flavio")} for _, f in FAIXAS},
           "por_semana": [{"semana": s, "lula": c["lula"], "flavio": c["flavio"]} for s, c in sorted(sem.items()) if s],
           "pessoas": pessoas,
           "politicos": {**pman, "lista": pols,
                         "sinal_totais": dict(Counter(p["sinal"] for p in pols)),
                         "fontes": cfg["fontes"], "regra": cfg["regra"]}}
    dest = root / "data/bolhas_apoio"
    dest.mkdir(parents=True, exist_ok=True)
    (dest / "bolhas.json").write_text(json.dumps(out, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    with gzip.open(priv / "conferencia_declaracoes.csv.gz", "wt", encoding="utf-8", newline="") as f:
        w = csv.writer(f, delimiter=";")
        w.writerow(["rede", "item_id", "conta", "seguidores", "publicado_em", "lado_automatico", "url", "texto", "lado_conferido", "codificador"])
        w.writerows(c + ["", ""] for c in conferencia)
    print(f"bolhas: {len(rows)} publicações lidas · {sum(v['com_frase'] for v in por_rede.values())} com frase · pessoas 100 mil+: "
          f"{out['totais']} · políticos {len(pols)} ({out['politicos']['sinal_totais']}) · votos: {pman['votos']}")
    return out


def main(argv=None) -> int:
    argv = sys.argv[1:] if argv is None else list(argv)
    root = Path(".")
    interno = os.environ.get("ODI_INTERNO_DIR")
    if not interno:
        print("⛔ ODI_INTERNO_DIR ausente")
        return 1
    priv = Path(interno) / "bolhas_apoio"
    priv.mkdir(parents=True, exist_ok=True)
    caso = next(c for c in json.loads((root / "data/config/casos.json").read_text(encoding="utf-8"))["casos"] if c["id"] == CASO)
    if "--tse" in argv:
        passo_tse(priv)
    if "--perfis" in argv:
        passo_perfis(root, priv, caso)
    if "--montar" in argv:
        montar(root, priv, caso)
    return 0


if __name__ == "__main__":
    sys.exit(main())
