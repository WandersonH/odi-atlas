"""Caso 019: análises dos comentários (rede de palavras, rede de respostas, classes de Reinert, corpus do IRaMuTeQ, Bardin e sentimento).

Pedido do responsável (30/10/2026, 22h25): "cadê os comentários, o Gephi, a linha do tempo dos vídeos, IRaMuTeQ, sentimento e Bardin".
Línguas: as palavras, as classes e o Bardin usam as línguas de escrita latina cobertas (en, es, pt, fr, de, it), com listas de
palavras vazias por língua; árabe, chinês, japonês, coreano, russo e outras escritas precisam de segmentação própria e ficam ⛔ (informado).
Sentimento: modelo multilíngue cardiffnlp/twitter-xlm-roberta-base-sentiment (XLM-R, treinado em tuítes de 8 línguas:
ar, en, fr, de, hi, it, es, pt), aplicado aos comentários dessas línguas; cache no privado. Sem o modelo instalado: ⛔ registrado.
Texto e autor dos comentários ficam só no privado (pessoas comuns); o público recebe contagens, palavras e códigos.
"""
from __future__ import annotations

import csv
import datetime as dt
import gzip
import json
import os
import re
import unicodedata
from collections import Counter, defaultdict
from pathlib import Path

LATINAS = ("en", "es", "pt", "fr", "de", "it")
MODELO_SENT = "cardiffnlp/twitter-xlm-roberta-base-sentiment"
LINGUAS_SENT = {"ar", "en", "fr", "de", "hi", "it", "es", "pt"}
_STOP = """
the a an and or but if of to in on at by for with from as is are was were be been being it its this that these those i you he she we they
me my your his her our their them us not no yes do does did done have has had will would can could should just so very really what who
which when where why how all any some more most such than then there here about into over also only even still too much many one get got
like dont im its thats youre theyre cant wont isnt arent was wasnt de la el los las un una unos unas y o pero si en con por para del al lo
le les que es son fue era ser se su sus mi mis tu tus nos este esta estos estas ese esa eso esto muy mas más ya no sí como cuando donde
porque pues tambien también todo todos toda todas hay solo sólo sobre entre hasta desde sin me te ni ha han he hemos le du des et ou mais
dans pour par sur avec pas plus ne ce cette ces est sont été être il elle ils elles nous vous je tu on qui quoi au aux une der die das und
oder aber in im ist sind war nicht ein eine einer zu mit auf für von den dem des sich es ich du er sie wir ihr auch nur noch wie il lo gli
i e di da del della che non per con su sono è era anche come più ma questo questa quello
""".split()


def norm(t: str) -> str:
    t = unicodedata.normalize("NFKD", (t or "").lower())
    return "".join(c for c in t if not unicodedata.combining(c))


try:
    import build_conteudo as bc
    STOP = {norm(w) for w in _STOP} | set(bc.STOP)
except Exception:  # noqa: BLE001
    STOP = {norm(w) for w in _STOP}


def tokens(t: str) -> list[str]:
    t = re.sub(r"https?://\S+|@\S+", " ", t or "")
    return [w for w in re.findall(r"[a-z]{3,}", norm(t)) if w not in STOP]


def rede_palavras(textos_ling: list[tuple[str, str]], minimo: int = 5, top: int = 90) -> tuple[dict, dict, dict | None]:
    from redes_caso import _desenho
    docs = [(set(tokens(t)), l) for t, l in textos_ling]
    df, lang = Counter(), defaultdict(Counter)
    for d, l in docs:
        for w in d:
            df[w] += 1
            lang[w][l] += 1
    voc = {w for w, n in df.items() if n >= minimo}
    ar = Counter()
    for d, _ in docs:
        ws = sorted(d & voc)
        for i, a in enumerate(ws):
            for b in ws[i + 1:]:
                ar[(a, b)] += 1
    ar = Counter({k: w for k, w in ar.items() if w >= 3})
    nos = {w: {"rotulo": w, "tipo": "palavra · " + lang[w].most_common(1)[0][0], "n": df[w]} for w in voc}
    return nos, dict(ar), _desenho(nos, ar, top)


def classes(textos: list[str], lingua: str) -> dict | None:
    import numpy as np
    import chd_reinert as cr
    if len(textos) < 100:
        return None
    docs = [set(tokens(s)) for s in textos]
    df = Counter(t for d in docs for t in d)
    voc = sorted(t for t, n in df.items() if n >= cr.MIN_FREQ)
    if len(voc) < 10:
        return None
    idx = {t: i for i, t in enumerate(voc)}
    X = np.zeros((len(docs), len(voc)))
    for i, d in enumerate(docs):
        for t in d:
            if t in idx:
                X[i, idx[t]] = 1
    n_at = int((X.sum(1) > 0).sum())
    rot, _ = cr.chd(X, k=6, min_classe=max(cr.MIN_CLASSE, int(0.05 * n_at)))
    ok = rot > 0
    if not ok.any():
        return None
    tot = X[ok].sum(0)
    out = []
    for k in sorted(set(rot[ok].tolist())):
        m = rot == k
        ch = cr.chi2_assoc(X[m].sum(0), tot, int(m.sum()), int(ok.sum()))
        js = [j for j in np.argsort(-ch) if ch[j] >= cr.CHI_CRIT][:15]
        out.append({"classe": int(k), "segmentos": int(m.sum()), "pct": round(100 * m.sum() / ok.sum(), 1),
                    "formas": [[voc[j], round(float(ch[j]), 1)] for j in js]})
    return {"lingua": lingua, "comentarios": len(textos), "classificados": int(ok.sum()), "pct_classificados": round(100 * ok.sum() / len(textos), 1),
            "classes": out, "nota": "CHD de Reinert do Atlas (chd_reinert.py), um comentário = um segmento, sem lematização, palavras vazias da língua removidas."}


def corpus_iramuteq(rows: list[dict], meta: dict) -> dict[str, str]:
    por = defaultdict(list)
    lim = lambda s: re.sub(r"[^A-Za-z0-9]", "", s or "x")[:30] or "x"  # noqa: E731
    for r in rows:
        tx = re.sub(r"[*\-$]", " ", r.get("texto") or "").strip()
        lc = r.get("lingua") or "?"
        if not tx or lc == "?":
            continue
        m = meta.get(r["video_id"]) or {}
        por[lc].append(f"**** *lingvideo_{lim(m.get('lingua'))} *lingcom_{lim(lc)} *cont_{lim(m.get('continente'))} *pais_{lim(m.get('pais'))} "
                       f"*video_{lim(r['video_id'])} *tipo_{lim(r.get('tipo'))}\n{tx}\n")
    return {l: "\n".join(v) for l, v in por.items()}


def bardin(rows: list[dict], livro: dict, meta: dict) -> dict:
    cats = {k: re.compile(v["regex"], re.I) for k, v in livro["categorias"].items()}
    cob = set(livro.get("linguas_cobertas", LATINAS))
    base = [r for r in rows if (r.get("lingua") or "?") in cob]
    cont, por_ling, por_cont = Counter(), defaultdict(Counter), defaultdict(Counter)
    n_ling, n_cont, com_cat = Counter(), Counter(), 0
    for r in base:
        hit = [k for k, rx in cats.items() if rx.search(r.get("texto") or "")]
        lc, ct = r.get("lingua"), (meta.get(r["video_id"]) or {}).get("continente", "⛔")
        n_ling[lc] += 1
        n_cont[ct] += 1
        if hit:
            com_cat += 1
        for k in hit:
            cont[k] += 1
            por_ling[lc][k] += 1
            por_cont[ct][k] += 1
    pc = lambda a, b: round(100 * a / b, 1) if b else None  # noqa: E731
    return {"o_que_e": livro["o_que_e"], "comentarios_cobertos": len(base), "fora_da_cobertura": len(rows) - len(base),
            "com_alguma_categoria": com_cat, "pct_com_categoria": pc(com_cat, len(base)),
            "categorias": {k: {"nome": v["nome"], "definicao": v["definicao"], "n": cont[k], "pct": pc(cont[k], len(base))} for k, v in livro["categorias"].items()},
            "por_lingua": {l: {"n": n_ling[l], "categorias": {k: pc(por_ling[l][k], n_ling[l]) for k in cats}} for l in n_ling},
            "por_continente": {c: {"n": n_cont[c], "categorias": {k: pc(por_cont[c][k], n_cont[c]) for k in cats}} for c in n_cont}}


def sentimento(rows: list[dict], priv: Path, meta: dict, max_novos: int = 4000) -> dict:
    f = priv / "sentimento.csv.gz"
    cache = {}
    if f.exists():
        cache = {r["comment_id"]: r for r in csv.DictReader(gzip.open(f, "rt", encoding="utf-8")) if r.get("modelo") == MODELO_SENT}
    alvo = [r for r in rows if (r.get("lingua") or "?") in LINGUAS_SENT and (r.get("texto") or "").strip()]
    novos = [r for r in alvo if r["comment_id"] not in cache][:max_novos]
    erro, revisao = None, ""
    if novos:
        try:
            import torch
            from transformers import AutoModelForSequenceClassification, AutoTokenizer
            tok = AutoTokenizer.from_pretrained(MODELO_SENT)
            m = AutoModelForSequenceClassification.from_pretrained(MODELO_SENT).eval()
            torch.set_num_threads(os.cpu_count() or 2)
            lab = {i: l.lower() for i, l in m.config.id2label.items()}
            revisao = getattr(m.config, "_commit_hash", "") or ""
            agora = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
            with torch.inference_mode():
                for i in range(0, len(novos), 32):
                    lote = novos[i:i + 32]
                    tx = [re.sub(r"https?://\S+", "http", re.sub(r"@\S+", "@user", r["texto"])) for r in lote]
                    enc = tok(tx, padding=True, truncation=True, max_length=128, return_tensors="pt")
                    pr = torch.softmax(m(**enc).logits, dim=-1).tolist()
                    for r, p in zip(lote, pr):
                        d = {lab[j]: p[j] for j in range(len(p))}
                        cache[r["comment_id"]] = {"comment_id": r["comment_id"], "rotulo": max(d, key=d.get), "p_pos": round(d.get("positive", 0), 4),
                                                  "p_neg": round(d.get("negative", 0), 4), "p_neu": round(d.get("neutral", 0), 4),
                                                  "modelo": MODELO_SENT, "revisao": revisao, "classificado_em": agora}
            with gzip.open(f, "wt", encoding="utf-8", newline="") as g:
                w = csv.DictWriter(g, fieldnames=["comment_id", "rotulo", "p_pos", "p_neg", "p_neu", "modelo", "revisao", "classificado_em"])
                w.writeheader()
                w.writerows(cache.values())
        except Exception as e:  # noqa: BLE001
            erro = f"⛔ modelo de sentimento indisponível nesta execução ({type(e).__name__})"
    feitos = [r for r in alvo if r["comment_id"] in cache]

    def dist(rs):
        c = Counter(cache[r["comment_id"]]["rotulo"] for r in rs)
        n = sum(c.values())
        return {"n": n, **{k: round(100 * c[k] / n, 1) if n else None for k in ("negative", "neutral", "positive")}}
    alvo_men = {"Lula": re.compile(r"\blula\w*", re.I), "Flávio/Bolsonaro": re.compile(r"fl[aá]vio|bolsonar\w*", re.I)}
    por_ling = defaultdict(list)
    por_cont = defaultdict(list)
    por_men = defaultdict(list)
    for r in feitos:
        por_ling[r["lingua"]].append(r)
        por_cont[(meta.get(r["video_id"]) or {}).get("continente", "⛔")].append(r)
        for k, rx in alvo_men.items():
            if rx.search(r["texto"]):
                por_men[k].append(r)
    return {"modelo": MODELO_SENT, "revisao": revisao or next((c.get("revisao") for c in cache.values() if c.get("revisao")), ""),
            "linguas_do_modelo": sorted(LINGUAS_SENT), "elegiveis": len(alvo), "classificados": len(feitos), "erro": erro,
            "geral": dist(feitos), "por_lingua": {k: dist(v) for k, v in por_ling.items()},
            "por_continente": {k: dist(v) for k, v in por_cont.items()},
            "por_mencao": {k: dist(por_men[k]) for k in alvo_men},
            "nota": "Tom do comentário (negativo, neutro, positivo) segundo o modelo; não diz a quem o tom se dirige. 'Por menção' = comentários "
                    "que citam o nome; Lula primeiro (atual presidente), a ordem não indica preferência."}


def analisar_textos(acervo: dict, vids: list[dict], priv: Path, pub: Path, livro_f: Path) -> dict:
    from redes_caso import gexf, respostas
    meta = {x["id"]: x for x in vids}
    rows = [r for r in acervo.values() if r["video_id"] in meta]
    out = {"comentarios_mundo": len(rows)}
    lat = [r for r in rows if (r.get("lingua") or "?") in LATINAS]
    nos, ar, des = rede_palavras([(r["texto"], r["lingua"]) for r in lat])
    gexf(nos, ar, pub / "rede_palavras_comentarios.gexf")
    out["rede_palavras"] = {"comentarios": len(lat), "linguas": list(LATINAS), "desenho": des,
                            "fora": len(rows) - len(lat), "nota": "palavras em 5+ comentários; ligação = aparecem juntas em 3+ comentários"}
    n2, a2, res = respostas(rows)
    gexf(n2, a2, pub / "rede_respostas_comentarios.gexf", dirigida=True)
    out["rede_respostas"] = res
    out["classes"] = [c for c in (classes([r["texto"] for r in lat if r["lingua"] == l], l) for l in LATINAS) if c]
    cps = corpus_iramuteq(rows, meta)
    for l, t in cps.items():
        (priv / f"corpus_iramuteq_{l}.txt").write_text(t, encoding="utf-8")
    out["iramuteq"] = {"arquivos_privados": {l: t.count("****") for l, t in cps.items()},
                       "nota": "Um corpus por língua do comentário (o IRaMuTeQ trabalha com um idioma por vez), com as variáveis *lingvideo_, *lingcom_, "
                               "*cont_, *pais_, *video_ e *tipo_. Os arquivos ficam no repositório privado (texto de pessoas comuns)."}
    livro = json.loads(livro_f.read_text(encoding="utf-8"))
    out["bardin"] = bardin(rows, livro, meta)
    out["sentimento"] = sentimento(rows, priv, meta)
    # linha do tempo de comentários (por dia, pela língua do comentário)
    dias = defaultdict(Counter)
    for r in rows:
        if r.get("publicado_em"):
            dias[r["publicado_em"][:10]][r.get("lingua") or "?"] += 1
    out["comentarios_por_dia"] = {k: dict(v) for k, v in sorted(dias.items())}
    return out
