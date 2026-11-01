#!/usr/bin/env python3
"""Origem das publicações de um caso: quanto veio de perfis com sinais do Brasil e quanto de outros países.

Pedido do responsável (01/11/2026, 18h26), caso 025: "#DeportTheBolsonaros, vamos entender quanto veio do Brasil e quanto veio de
outros países, buscas e redes, #BrasiliansStandWithFlavio".

Nenhuma rede informa o país de quem posta. A origem é inferida por sinais que o próprio perfil declara, e a regra é publicada na página:
  1. língua do texto: a que a rede marca (X: `lang`; Instagram: `original_lang_for_translations`) ou, sem ela, a do py3langid sobre o
     texto sem @menções, links e hashtags (só com 20+ letras);
  2. língua da bio (X: `profileDescriptionLanguage`);
  3. bandeiras no nome e na bio (pares de indicadores regionais, ex. 🇧🇷 → BR). 🇺🇸 e 🇮🇱 ao lado da 🇧🇷 são símbolo político comum
     no Brasil: com outro sinal do Brasil, bandeira estrangeira não muda a classe (fica contada à parte);
  4. lugares escritos no nome, na bio e no local da publicação (lista LUGARES, abaixo).
Classes (por publicação, pelos sinais do autor):
  - "Brasil": algum sinal do Brasil (português no texto ou na bio, 🇧🇷, lugar brasileiro) e nenhum de outro país;
  - "Brasil + outro país": sinal do Brasil e um lugar de outro país escrito no perfil (ex.: brasileiro que declara morar na Flórida);
  - "outro país": país declarado que não é o Brasil, sem sinal do Brasil;
  - "outra língua, país não declarado": texto ou bio em outra língua, sem país declarado;
  - "sem sinal": nada disso (ex.: post só com a hashtag e sem bio).
Português conta como sinal do Brasil; quem declara Portugal (🇵🇹 ou o nome) vai para "outro país". Língua não é nacionalidade: há
brasileiros que escrevem em inglês para alcançar americanos; por isso a página mostra também a língua do texto, separada.
Lê só o privado (ODI_INTERNO_DIR/casos/<caso>/itens.csv.gz e bruto_<rede>_*.jsonl.gz).
Público: data/casos/<caso>/origem.json (só contagens e percentuais; contas com nome só com 10 mil+ seguidores).
Uso: python scripts/caso_origem.py --caso 025
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
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from collect_casos import g, norm  # noqa: E402
from net import now_utc  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
MIN_PUBLICO = 10000
LIMPA = re.compile(r"@\w+|#\w+|https?://\S+")
SEM_LINGUA = {"und", "zxx", "qht", "qme", "qam", "art", "qst", ""}
LADOS = {
    "#DeportTheBolsonaros": re.compile(r"deport\w*\s*(the\s*)?bolsonar\w*|deport\w*\s*fl[aá]vio|deportem os bolsonaro", re.I),
    "#BrasiliansStandWithFlavio": re.compile(r"bra[sz]ilians?\s*stand\s*with\s*fl[aá]vio|brazil\s*stands?\s*with\s*fl[aá]vio", re.I),
}
UF = ("acre|alagoas|amap[aá]|amazonas|bahia|cear[aá]|distrito federal|esp[ií]rito santo|goi[aá]s|maranh[aã]o|mato grosso|minas gerais|pará|"
      "para[ií]ba|paran[aá]|pernambuco|piau[ií]|rio de janeiro|rio grande do norte|rio grande do sul|rond[oô]nia|roraima|santa catarina|"
      "s[aã]o paulo|sergipe|tocantins|bras[ií]lia|belo horizonte|fortaleza|recife|curitiba|porto alegre|manaus|goi[aâ]nia|"
      "florian[oó]polis|macei[oó]|jo[aã]o pessoa|teresina|campo grande|cuiab[aá]|aracaju|campinas|niter[oó]i")  # sem nomes ambíguos (Santos, Natal, Vitória, Salvador, Belém)
LUGARES = [  # (código, expressão); todos os que casarem contam. Revisado em 01/11/2026 numa amostra de bios do caso 014: "usa" (verbo), "Israel",
    # "Barcelona", "Roma", "Porto", "Geórgia" e "Carolina" davam falso lugar
    ("BR", rf"\bbra[sz]il\w*|\bbrasileir\w*|\b({UF})\b"),
    ("US", r"(?-i:\bUSA\b|\bU\.S\.A?\b)|\beua\b|estados unidos|united states|\bflorida\b|\bmiami\b|\borlando\b|\btexas\b|\bcalifornia\b"
           r"|new york|\bnyc\b|\bboston\b|new jersey|massachusetts|\batlanta\b|\bchicago\b|los angeles|\bohio\b|\barizona\b|\bvirginia\b"
           r"|washington,? d\.?c|\bseattle\b|\bdallas\b|\bhouston\b|\bdenver\b|\butah\b|\bnevada\b|las vegas|pennsylvania|(north|south) carolina|tennessee|michigan"
           r"|\balabama\b|\balaska\b|\barkansas\b|\bcolorado\b|connecticut|\bdelaware\b|\bhawai|\bidaho\b|\billinois\b|\bindiana\b|\biowa\b|\bkansas\b"
           r"|kentucky|louisiana|\bmaine\b|maryland|minnesota|mississippi|missouri|\bmontana\b|nebraska|new hampshire|new mexico|(north|south) dakota|oklahoma"
           r"|\boregon\b|rhode island|\bvermont\b|west virginia|wisconsin|wyoming|philadelphia|san francisco|san diego|\bbaltimore\b|\batlanta\b|\bportland\b"),
    ("PT", r"\bportugal\b|\blisboa\b|\blisbon\b"),
    ("GB", r"\blondon\b|\blondres\b|united kingdom|\bengland\b|\bscotland\b|(?-i:\bUK\b)|reino unido"),
    ("CA", r"\bcanad[aá]\b|\btoronto\b|\bvancouver\b|\bmontr[eé]al\b"),
    ("ES", r"\bespa[nñ]a\b|\bespanha\b|\bspain\b|\bmadrid\b"),
    ("IT", r"\bit[aá]lia\b|\bitaly\b"),
    ("FR", r"\bfran[cç]a\b|\bfrance\b|\bparis\b"),
    ("DE", r"\balemanha\b|\bgermany\b|\bdeutschland\b|\bberlin\b"),
    ("AR", r"\bargentina\b|\bbuenos aires\b"),
    ("JP", r"\bjap[aã]o\b|\bjapan\b|\btokyo\b|\bt[oó]quio\b"),
    ("IL", r"\btel aviv\b"),  # "Israel" na bio é, em geral, declaração política, não lugar
    ("AU", r"\baustr[aá]lia\b|\bsydney\b"),
    ("IE", r"\birlanda\b|\bireland\b|\bdublin\b"),
]
LUGARES = [(c, re.compile(r, re.I)) for c, r in LUGARES]
# bandeiras usadas como causa política nas bios (Palestina, Israel, Ucrânia, União Europeia, ONU): não indicam onde a pessoa está
SIMBOLOS = {"PS", "IL", "UA", "EU", "UN"}
BANDEIRA = re.compile("[\U0001F1E6-\U0001F1FF]{2}")
CLASSES = ["Brasil", "Brasil + outro país", "outro país", "outra língua, país não declarado", "sem sinal"]


def bandeiras(s: str) -> set[str]:
    b = {"".join(chr(ord(c) - 0x1F1E6 + 65) for c in m) for m in BANDEIRA.findall(s or "")}
    return {"US" if x == "UM" else x for x in b} - SIMBOLOS


def lugares(s: str) -> set[str]:
    return {c for c, rx in LUGARES if rx.search(s or "")}


_LID = None


def lingua(txt: str) -> str | None:
    global _LID
    t = LIMPA.sub(" ", txt or "")
    if len(re.findall(r"[^\W\d_]", t)) < 20:
        return None
    if _LID is None:
        from py3langid.langid import LanguageIdentifier, MODEL_FILE
        _LID = LanguageIdentifier.from_pickled_model(MODEL_FILE, norm_probs=True)
    lang, prob = _LID.classify(t)
    return lang if prob >= 0.8 else None


def sinais(rede: str, raw: dict, texto: str) -> dict:
    """Sinais declarados do autor de uma publicação (ver o cabeçalho)."""
    nome = bio = local = ""
    lt = lb = None
    if rede == "x":
        a = raw.get("author") or {}
        nome, bio, local = a.get("name") or "", a.get("description") or "", a.get("location") or ""
        lt = raw.get("lang") if raw.get("lang") not in SEM_LINGUA else None
        lb = a.get("profileDescriptionLanguage") or lingua(bio)
        lb = None if lb in SEM_LINGUA else lb
    elif rede == "instagram":
        nome = str(g(raw, "user.full_name", "owner.fullName", "ownerFullName", "owner.full_name") or "")
        bio = str(g(raw, "owner.biography", "user.biography") or "")
        local = str(g(raw, "location.name", "locationName") or "")
        lt = raw.get("original_lang_for_translations")
    elif rede == "facebook":
        nome = str(g(raw, "author.name") or "")
    lt = lt or lingua(texto)
    return {"lingua_texto": lt, "lingua_bio": lb, "lugares": sorted(lugares(f"{nome} {bio} {local}")), "bandeiras": sorted(bandeiras(f"{nome} {bio}"))}


def classe(s: dict) -> str:
    # bandeiras de outros países ao lado da 🇧🇷 (🇺🇸, 🇮🇱) são comuns como símbolo político no Brasil: com sinal do Brasil, só o lugar
    # escrito conta como "outro país"; sem sinal do Brasil, bandeira e lugar contam
    lug, band = set(s["lugares"]), set(s["bandeiras"])
    br = "BR" in lug or "BR" in band or s["lingua_bio"] == "pt" or s["lingua_texto"] == "pt"
    if br and lug - {"BR"}:
        return "Brasil + outro país"
    if br:
        return "Brasil"
    if (lug | band) - {"BR"}:
        return "outro país"
    if s["lingua_texto"] or s["lingua_bio"]:
        return "outra língua, país não declarado"
    return "sem sinal"


def lados(texto: str, termo: str) -> list[str]:
    out = [k for k, rx in LADOS.items() if rx.search(texto or "")]
    if not out:  # o texto pode não repetir a hashtag (busca casou com outra grafia): vale a busca que trouxe o item
        out = [k for k, rx in LADOS.items() if rx.search(termo or "") or k.lower() in (termo or "").lower()]
    return out or ["sem a hashtag no texto"]


def dia_brt(iso: str) -> str | None:
    try:
        return (dt.datetime.fromisoformat(iso.replace("Z", "+00:00")) - dt.timedelta(hours=3)).strftime("%Y-%m-%d")
    except Exception:  # noqa: BLE001
        return None


def pct(a: int, b: int) -> float | None:
    return round(100 * a / b, 1) if b else None


def tabela(regs: list[dict], chave: str, valores: list[str] | None = None) -> list[dict]:
    n = Counter(r[chave] for r in regs)
    v = Counter()
    for r in regs:
        v[r[chave]] += r["visualizacoes"] or 0
    contas = defaultdict(set)
    for r in regs:
        contas[r[chave]].add((r["rede"], r["conta"]))
    tot, totv = len(regs), sum(v.values())
    ordem = valores or [k for k, _ in n.most_common()]
    return [{"valor": k, "publicacoes": n[k], "pct": pct(n[k], tot), "contas": len(contas[k]), "visualizacoes": v[k], "pct_visualizacoes": pct(v[k], totv)}
            for k in ordem if n[k] or valores]


def main(argv: list[str]) -> int:
    caso = argv[argv.index("--caso") + 1] if "--caso" in argv else "025"
    priv = Path(os.environ.get("ODI_INTERNO_DIR", "")) / "casos" / caso
    if not (priv / "itens.csv.gz").exists():
        print(f"⛔ caso {caso}: sem itens.csv.gz no privado")
        return 1
    cfg = next(c for c in json.loads((ROOT / "data/config/casos.json").read_text(encoding="utf-8"))["casos"] if c["id"] == caso)
    brutos: dict[tuple[str, str], dict] = {}
    for f in sorted(priv.glob("bruto_*_*.jsonl.gz")):
        rede = f.name.split("_")[1]
        with gzip.open(f, "rt", encoding="utf-8") as fh:
            for l in fh:
                try:
                    x = json.loads(l)
                except Exception:  # noqa: BLE001
                    continue
                r = norm(rede, x, x.get("_termo", ""), "")
                if r:
                    brutos[(rede, r["item_id"])] = x
    with gzip.open(priv / "itens.csv.gz", "rt", encoding="utf-8") as fh:
        itens = list(csv.DictReader(io.StringIO(fh.read()), delimiter=";"))
    vistos, regs = set(), []
    for it in itens:
        k = (it["rede"], it["item_id"])
        if k in vistos or (it["publicado_em"] or "9") < cfg["desde"]:
            continue
        vistos.add(k)
        raw = brutos.get(k, {})
        s = sinais(it["rede"], raw, it["texto"])
        seg = int(it["seguidores"]) if str(it["seguidores"]).isdigit() else None
        rt = bool(raw.get("isRetweet")) or (it["rede"] == "x" and (it["texto"] or "").startswith("RT @"))
        for lado in lados(it["texto"], it["termo"]):
            regs.append({"rede": it["rede"], "conta": it["conta"], "seguidores": seg, "lado": lado, "dia": dia_brt(it["publicado_em"] or ""),
                         "visualizacoes": int(it["visualizacoes"]) if str(it["visualizacoes"]).isdigit() else 0, "classe": classe(s),
                         "lingua_texto": s["lingua_texto"] or "não identificada",
                         "pais": ",".join(sorted((set(s["lugares"]) | (set() if classe(s) == "Brasil" else set(s["bandeiras"]))) - {"BR"})) or None,
                         "bandeira_fora_com_br": classe(s) == "Brasil" and bool(set(s["bandeiras"]) - {"BR"}),
                         "repost": rt, "tem_bruto": bool(raw), "url": it["url"]})
    out = {"caso": caso, "gerado_em_utc": now_utc(), "desde": cfg["desde"],
           "metodo": __doc__.split("Lê só o privado")[0].strip(),
           "publicacoes_lidas": len(vistos), "contas_lidas": len({(r["rede"], r["conta"]) for r in regs}),
           "aviso": ("Origem inferida por sinais que o perfil declara; não é o país real de quem posta. Percentuais valem para a amostra lida, "
                     "não para tudo o que circulou. Usar a hashtag não é apoiar a causa: quem critica a campanha também a usa. "
                     "Uma publicação que cita as duas hashtags conta nos dois lados."),
           "lados": {}}
    for lado in [*LADOS, "sem a hashtag no texto"]:
        rl = [r for r in regs if r["lado"] == lado]
        if not rl:
            continue
        dias = sorted({r["dia"] for r in rl if r["dia"]})
        top = Counter()
        info = {}
        for r in rl:
            if (r["seguidores"] or 0) >= MIN_PUBLICO:
                top[(r["rede"], r["conta"])] += 1
                info[(r["rede"], r["conta"])] = (r["seguidores"], r["classe"], r["pais"])
        out["lados"][lado] = {
            "publicacoes": len(rl), "contas": len({(r["rede"], r["conta"]) for r in rl}),
            "reposts_x": sum(r["repost"] for r in rl if r["rede"] == "x"),
            "brasil_com_bandeira_de_outro_pais": sum(r["bandeira_fora_com_br"] for r in rl),
            "sem_dado_do_autor": sum(not r["tem_bruto"] for r in rl),
            "por_classe": tabela(rl, "classe", CLASSES),
            "por_classe_sem_reposts": tabela([r for r in rl if not r["repost"]], "classe", CLASSES),
            "por_lingua_texto": tabela(rl, "lingua_texto")[:12],
            "por_pais_declarado_fora": tabela([r for r in rl if r["pais"]], "pais")[:15],
            "por_rede": {rd: tabela([r for r in rl if r["rede"] == rd], "classe", CLASSES) for rd in sorted({r["rede"] for r in rl})},
            "por_dia": [{"dia": d, **{c: sum(1 for r in rl if r["dia"] == d and r["classe"] == c) for c in CLASSES}} for d in dias],
            "contas_10mil": [{"rede": k[0], "conta": k[1], "publicacoes": n, "seguidores": info[k][0], "classe": info[k][1], "pais_fora": info[k][2]}
                             for k, n in top.most_common(25)],
            "visualizacoes_total": sum(r["visualizacoes"] for r in rl),
            "maior_alcance": [{"rede": r["rede"], "conta": r["conta"] if (r["seguidores"] or 0) >= MIN_PUBLICO else None, "seguidores": r["seguidores"],
                               "visualizacoes": r["visualizacoes"], "pct_visualizacoes": pct(r["visualizacoes"], sum(x["visualizacoes"] for x in rl)),
                               "classe": r["classe"], "lingua_texto": r["lingua_texto"], "dia": r["dia"], "url": r["url"] if (r["seguidores"] or 0) >= MIN_PUBLICO else None}
                              for r in sorted(rl, key=lambda r: r["visualizacoes"], reverse=True)[:10]],
        }
    # universo × amostra (regra 9): o X não informa o total; os manifestos dizem quanto foi pedido e lido por busca
    uni = []
    pub = ROOT / "data/casos" / caso
    for m in sorted(pub.glob("manifesto-*.json")):
        try:
            man = json.loads(m.read_text(encoding="utf-8"))
        except Exception:  # noqa: BLE001
            continue
        for rd in man.get("redes", []) if isinstance(man.get("redes"), list) else []:
            for t in rd.get("termos", []) if isinstance(rd.get("termos"), list) else []:
                if isinstance(t, dict) and t.get("termo"):
                    uni.append({"rede": rd.get("rede"), "termo": t.get("termo"), "lidos": t.get("itens") if t.get("itens") is not None else t.get("lidos"),
                                "no_periodo": t.get("no_periodo"), "pedidos": rd.get("itens_pedidos_por_termo"), "bateu_no_limite": t.get("no_limite"),
                                "mais_antigo": t.get("mais_antigo"), "universo": t.get("universo"),
                                "fonte_universo": t.get("fonte_universo") or "⛔ a plataforma não informa o total de publicações com o termo",
                                "manifesto": m.name})
    out["universo"] = uni
    saida = Path(argv[argv.index("--saida") + 1]) if "--saida" in argv else pub / "origem.json"
    saida.parent.mkdir(parents=True, exist_ok=True)
    saida.write_text(json.dumps(out, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    for lado, d in out["lados"].items():
        print(f"caso {caso} · {lado}: {d['publicacoes']} publicações, {d['contas']} contas · " +
              " · ".join(f"{x['valor']} {x['pct']}%" for x in d["por_classe"] if x["publicacoes"]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
