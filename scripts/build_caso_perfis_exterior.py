#!/usr/bin/env python3
"""Análise do caso 010: brasileiros (comentários em português) nos perfis de Donald Trump e Marco Rubio, X e Instagram.

Pedidos do responsável (27/10/2026): coleta de 01h56 e 01h58 e, às 02h00, "quero um % amostra comentários citando Brasil ou eleições".
Lê só o privado (ODI_INTERNO_DIR/casos/<caso>/):
  - X: bruto_x_*.jsonl.gz (xquik; cada item traz a busca que o trouxe em `_termo`). As buscas de resposta e de menção já vêm com
    lang:pt; a busca "posts dos perfis" traz o que Trump e Rubio publicaram e fica fora da amostra.
  - Instagram: instagram/<run>.json do datadoping (comentários) e do instagram-scraper (posts dos perfis). O ator não filtra idioma:
    o português é separado aqui por marcadores da língua (ver em_portugues), regra simples e declarada na página.
Categorias por expressão regular (CATEGORIAS), sobre o texto sem @menções. Uma mensagem pode cair em mais de uma.
Público: data/casos/<caso>/resumo.json (só contagens e percentuais; contas com nome só se tiverem 10 mil+ seguidores; posts dos
próprios perfis de Trump e Rubio com texto, por serem autoridades públicas). Texto de pessoas comuns não sai do privado.
Uso: python scripts/build_caso_perfis_exterior.py --caso 010
"""
from __future__ import annotations

import gzip
import json
import os
import re
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from collect_casos import iso  # noqa: E402
from net import now_utc  # noqa: E402

MIN_PUBLICO = 10000
ARROBA = re.compile(r"@\w+|https?://\S+")
CATEGORIAS = {
    "cita o Brasil": r"\bbrasil\w*|\bbrazil\w*|🇧🇷|\bbr\b",
    "cita a eleição": r"elei[cç][aãoõ]\w*|\beleit\w*|\belection\w*|\bvot[aeo]\w*|\bvote[ds]?\b|\burnas?\b|fraud\w*|\b2[ºo°] turno|segundo turno"
                      r"|apura[cç]\w*|\btse\b|rigged|stolen|roubad\w*|resultado",
    "cita Lula, Bolsonaro ou Flávio": r"\blula\w*|bolsonar\w*|fl[aá]vio\b|\bjair\b|\beduardo\b",
    "cita Moraes, STF ou censura": r"moraes|xand[aã]o|\bstf\b|supremo|zanin|\bdino\b|gilmar|barroso|fachin|toffoli|\bfux\b|c[aá]rmen l[uú]cia|mendon[cç]a|nunes marques"
                                   r"|censur\w*|censorship|ditadura|dictator\w*",
    "fala em golpe ou fraude": r"\bgolpe\w*|\bcoup\b|fraud\w*|roubad\w*|rigged|stolen|manipula\w*",
    "pede ajuda, sanção ou intervenção": r"\bsos\b|\bajud\w*|\bhelp\b|\bsave\b|salv[ae]\w*|san[cç]\w*|sanction\w*|tarif\w*|magnitsky|interven\w*|socorr\w*|liberta\w*",
}
UNIAO = "cita o Brasil ou a eleição"
PT = re.compile(r"[ãõç]|\b(n[ãa]o|voc[eê]|vc|pra|muito|obrigad[oa]|n[oó]s|est[aá]|s[ãa]o|tamb[eé]m|brasil\w*|ent[ãa]o|agora|nosso|nossa|povo|aqui|isso|tá|tô|deus|vai|esse|essa|mais)\b", re.I)
ES = re.compile(r"ñ|\b(y|gracias|usted|pero|muy|est[aá]n|nuestro|nuestra|pueblo|ahora|aqu[ií]|hay|eso|también)\b", re.I)
STOP = set("a o e de da do das dos que em um uma para pra por com não nao na no nas nos se é eu você vc ele ela isso esse essa mais mas "
           "the to and of you is in for on it this that are be we our your with they all he his have will just so not at as "
           "vai seu sua aqui está esta foi tem estão como ser pelo pela pode favor isso essa esse ele ela eles elas nós já quando "
           "também muito mais tudo nada sobre até sem só todos todo toda são era ter vamos agora porque pois onde quem qual dos das "
           "deu dar fazer faz feito ainda mesmo nem lhe meu minha nosso nossa seus suas bem aos às".split())


def em_portugues(texto: str) -> bool:
    if "🇧🇷" in texto:
        return True
    p, e = len(PT.findall(texto)), len(ES.findall(texto))
    return (p >= 2 and p > e) or (p == 1 and e == 0 and len(texto.split()) <= 8)


def categorias(texto: str) -> list[str]:
    t = ARROBA.sub(" ", texto or "")
    cs = [c for c, rx in CATEGORIAS.items() if re.search(rx, t, re.I)]
    if "cita o Brasil" in cs or "cita a eleição" in cs:
        cs.append(UNIAO)
    return cs


def g(x: dict, *ks):
    for k in ks:
        v = x
        for p in k.split("."):
            v = v.get(p) if isinstance(v, dict) else None
        if v not in (None, ""):
            return v
    return None


def ler_x(pasta: Path) -> tuple[list[dict], list[dict]]:
    vistos, amostra, proprios = set(), [], []
    for f in sorted(pasta.glob("bruto_x_*.jsonl.gz")):
        for linha in gzip.open(f, "rt", encoding="utf-8"):
            x = json.loads(linha)
            iid = str(g(x, "id", "id_str", "tweetId") or "")
            if not iid or (iid, x.get("_termo")) in vistos:
                continue
            vistos.add((iid, x.get("_termo")))
            r = {"id": iid, "termo": x.get("_termo"), "texto": " ".join(str(g(x, "fullText", "text") or "").split()),
                 "data": iso(g(x, "createdAt", "created_at")) or "", "conta": g(x, "author.userName", "author.username") or "",
                 "seguidores": g(x, "author.followers", "author.followersCount") or 0, "resposta_a": g(x, "inReplyToUsername", "in_reply_to_screen_name"),
                 "curtidas": g(x, "likeCount") or 0, "url": g(x, "url", "twitterUrl") or ""}
            (proprios if x.get("_termo") == "posts dos perfis" else amostra).append(r)
    return amostra, proprios


def ler_ig(pasta: Path) -> tuple[list[dict], list[dict]]:
    coms, posts, vistos = [], [], set()
    for f in sorted((pasta / "instagram").glob("*.json")):
        if f.name == "manifesto.json":
            continue
        d = json.loads(f.read_text(encoding="utf-8"))
        for x in d.get("items") or []:
            if "datadoping" in d.get("ator", ""):
                cid = str(g(x, "comment_id", "id") or "")
                if not cid or cid in vistos:
                    continue
                vistos.add(cid)
                coms.append({"id": cid, "texto": " ".join(str(x.get("text") or "").split()), "data": iso(g(x, "created_at_utc", "created_at")) or "",
                             "post": str(g(x, "input_url", "post_url") or ""), "curtidas": g(x, "like_count") or 0,
                             "conta": g(x, "username", "user.username") or ""})
            elif x.get("url") and not x.get("error"):  # perfil sem post no período volta como erro "no_items"
                posts.append({"perfil": x.get("ownerUsername"), "url": x.get("url"), "publicado_utc": x.get("timestamp"), "tipo": x.get("type"),
                              "curtidas": x.get("likesCount"), "comentarios": x.get("commentsCount"), "legenda": (x.get("caption") or "")[:400]})
    return coms, posts


def dia_brt(iso_utc: str) -> str:
    from datetime import datetime, timedelta
    try:
        return (datetime.fromisoformat(iso_utc.replace("Z", "+00:00")) - timedelta(hours=3)).strftime("%Y-%m-%d")
    except ValueError:
        return iso_utc[:10]


def resumo_grupo(rs: list[dict]) -> dict:
    n = len(rs)
    cont = Counter(c for r in rs for c in categorias(r["texto"]))
    dias = Counter(dia_brt(r["data"]) for r in rs if r.get("data"))
    palavras = Counter(w for r in rs for w in re.findall(r"[a-zà-úç]{3,}", ARROBA.sub(" ", r["texto"]).lower()) if w not in STOP)
    return {"n": n, "categorias": {c: {"n": cont.get(c, 0), "pct": round(100 * cont.get(c, 0) / n, 1) if n else None} for c in [*CATEGORIAS, UNIAO]},
            "por_dia": dict(sorted(dias.items())), "palavras": palavras.most_common(40)}


def main(argv=None) -> int:
    argv = sys.argv[1:] if argv is None else list(argv)
    caso = argv[argv.index("--caso") + 1] if "--caso" in argv else "010"
    interno = os.environ.get("ODI_INTERNO_DIR")
    if not interno:
        print("⛔ ODI_INTERNO_DIR ausente")
        return 1
    pasta = Path(interno) / "casos" / caso
    xa, xp = ler_x(pasta)
    ic, ip = ler_ig(pasta)
    ic_pt = [r for r in ic if em_portugues(r["texto"])]
    contas = Counter(r["conta"] for r in xa if (r["seguidores"] or 0) >= MIN_PUBLICO)
    seg = {r["conta"]: r["seguidores"] for r in xa}
    out = {"caso": caso, "gerado_em_utc": now_utc(), "categorias_regex": CATEGORIAS, "uniao": UNIAO,
           "nota": "X: respostas e menções com lang:pt (idioma detectado pelo X). Instagram: comentários dos posts de Trump e Rubio desde 24/10, "
                   "português separado por marcadores da língua (regra declarada). Português não prova nacionalidade.",
           "x": {"total": resumo_grupo(xa),
                 "por_busca": {t: resumo_grupo([r for r in xa if r["termo"] == t]) for t in sorted({r["termo"] for r in xa})},
                 "contas_10mil_que_mais_aparecem": [{"conta": c, "seguidores": seg[c], "mensagens": n} for c, n in contas.most_common(15)],
                 "posts_dos_perfis": [{k: r[k] for k in ("conta", "data", "texto", "curtidas", "url")} for r in sorted(xp, key=lambda r: r["data"])]},
           "instagram": {"comentarios_lidos": len(ic), "em_portugues": len(ic_pt),
                         "pct_em_portugues": round(100 * len(ic_pt) / len(ic), 1) if ic else None,
                         "pt": resumo_grupo(ic_pt), "todos": resumo_grupo(ic),
                         "por_post": [{**p, "comentarios_lidos": sum(1 for r in ic if p["url"].rstrip("/") in r["post"]),
                                       "em_portugues": sum(1 for r in ic_pt if p["url"].rstrip("/") in r["post"])} for p in ip]}}
    dest = Path("data/casos") / caso / "resumo.json"
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    t = out["x"]["total"]
    print(f"caso {caso}: X {t['n']} mensagens em português · {UNIAO}: {t['categorias'][UNIAO]['pct']}% · posts dos perfis {len(xp)} | "
          f"Instagram {len(ic)} comentários · {len(ic_pt)} em português · {UNIAO}: {out['instagram']['pt']['categorias'][UNIAO]['pct']}%")
    return 0


if __name__ == "__main__":
    sys.exit(main())
