#!/usr/bin/env python3
"""Uso dos termos "fake news", "deepfake" e "cheapfake" (e dos nomes populares para o mesmo fenômeno) fora da academia.

Pedido do responsável (30/10/2026, 09h27): "comparar o uso dos termos fora da academia com a recepção acadêmica que o artigo
reconstrói: a frequência de 'fake news', 'deepfake' e 'cheapfake' no Google Trends desde 2017 e nos comentários coletados pelo Atlas"
(artigo "Da notícia falsa ao conteúdo sintético", em preparação).

Duas camadas, ambas grátis:
  --trends  Google Trends, Brasil e mundo, de 2017-01-01 até hoje, por mês: os três termos acadêmicos e os nomes populares
            ("notícia falsa", "montagem", "inteligência artificial"), com "fake news" como âncora comum entre as consultas
            (o Trends dá 0–100 relativo ao pico de cada consulta; nada de volume absoluto: universo de buscas ⛔).
  --corpus  Acervo do Atlas no privado (comentários aos posts das campanhas no YouTube, Facebook, TikTok, Instagram e X, e
            publicações e comentários dos casos): quantos textos citam cada termo, por mês e por rede, sempre com o total de
            textos lidos como denominador (a amostra é o acervo, não a rede inteira). Só contagens no público.
Saída: data/termos/desinformacao.json (público). Marcos acadêmicos: data/config/marcos_termos_desinformacao.json (do artigo).
Uso: python scripts/termos_desinformacao.py --trends --corpus
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

sys.path.insert(0, str(Path(__file__).resolve().parent))
from build_conteudo import norm  # noqa: E402
from net import now_utc  # noqa: E402

csv.field_size_limit(10**8)

# grupos de termos (texto normalizado: minúsculas, sem acento, só letras, números e #)
GRUPOS = {
    "fake_news": {"nome": "fake news", "tipo": "academico", "rx": r"fakes? ?news|fake ?new\b|#fakenews"},
    "deepfake": {"nome": "deepfake", "tipo": "academico", "rx": r"deep ?fakes?|#deepfake"},
    "cheapfake": {"nome": "cheapfake / shallowfake", "tipo": "academico", "rx": r"cheap ?fakes?|shallow ?fakes?"},
    "noticia_falsa": {"nome": "notícia falsa", "tipo": "popular", "rx": r"noticias? falsas?"},
    "desinformacao": {"nome": "desinformação", "tipo": "popular", "rx": r"desinforma(cao|coes|r|ndo)"},
    "fake": {"nome": "\"fake\" (sozinho)", "tipo": "popular", "rx": r"(?<!deep )(?<!cheap )(?<!shallow )(?<!deep)(?<!cheap)(?<!shallow)fakes?(?!s? ?news)"},
    "ia": {"nome": "atribuição a IA (\"feito com IA\", \"isso é IA\")", "tipo": "popular",
           "rx": r"(feito|feita|gerado|gerada|criado|criada|fizeram|fez) (com|por|na|de) ia|(video|imagem|foto|audio|voz) (de|com|feito com|feita com) ia|(isso|isto|essa|esse) (e|foi) ia\b|\bia\b (fez|faz|criou|gerou)|\bchat ?gpt\b"},
    "ia_tema": {"nome": "inteligência artificial (tema)", "tipo": "contexto", "rx": r"inteligencia artificial"},
    "montagem": {"nome": "montagem / editado / fora de contexto", "tipo": "popular",
                 "rx": r"montage(m|ns)|video editado|foi editado|editaram|editado pra|fora de contexto|descontextualizad|cortaram o video|video cortado|corte malicioso|recortad"},
}
RX = {k: re.compile(r"(?<![a-z0-9])(?:" + v["rx"] + r")") for k, v in GRUPOS.items()}

TRENDS_CONSULTAS = [
    {"id": "academicos", "termos": ["fake news", "deepfake", "cheapfake", "shallowfake", "desinformação"]},
    {"id": "populares", "termos": ["fake news", "notícia falsa", "montagem", "inteligência artificial", "deep fake"]},
]


def mes(v) -> str | None:
    if v in (None, ""):
        return None
    try:
        if isinstance(v, (int, float)) or str(v).isdigit():
            n = float(v)
            n = n / 1000 if n > 1e11 else n
            d = dt.datetime.fromtimestamp(n, dt.timezone.utc)
        else:
            s = str(v).replace("Z", "+00:00")
            try:
                d = dt.datetime.fromisoformat(s)
            except ValueError:
                d = dt.datetime.strptime(str(v), "%a %b %d %H:%M:%S %z %Y")
        if d.tzinfo is None:
            d = d.replace(tzinfo=dt.timezone.utc)
        return (d - dt.timedelta(hours=3)).strftime("%Y-%m")
    except Exception:  # noqa: BLE001
        return None


def grupos_no(texto: str) -> list[str]:
    t = norm(texto or "")
    return [k for k, r in RX.items() if r.search(t)]


def fontes(priv: Path):
    """(corpus, rede, id, texto, data) de todo o acervo privado de textos."""
    for rede in ("youtube", "facebook", "tiktok"):
        f = priv / rede / "comentarios" / "comentarios.csv.gz"
        if f.exists():
            for r in csv.DictReader(gzip.open(f, "rt", encoding="utf-8"), delimiter=";"):
                yield "comentarios_campanhas", rede, r.get("comment_id"), r.get("texto"), r.get("publicado_em")
    for f in sorted((priv / "instagram" / "comentarios").glob("apify_*.jsonl.gz")):
        for linha in gzip.open(f, "rt", encoding="utf-8"):
            x = json.loads(linha)
            yield "comentarios_campanhas", "instagram", x.get("id") or x.get("comment_id"), x.get("text"), x.get("created_at_utc") or x.get("created_at")
    for f in sorted((priv / "x" / "respostas").glob("*.jsonl.gz")):
        for linha in gzip.open(f, "rt", encoding="utf-8"):
            x = json.loads(linha)
            yield "comentarios_campanhas", "x", x.get("id"), x.get("text"), x.get("createdAt")
    for f in sorted((priv / "kwai" / "comentarios").glob("*.jsonl.gz")):
        for linha in gzip.open(f, "rt", encoding="utf-8"):
            x = json.loads(linha)
            yield "posts_kwai", "kwai", x.get("id"), " ".join(str(x.get(k) or "") for k in ("caption", "transcript")), x.get("createTime")
    for d in sorted((priv / "casos").glob("*")):
        f = d / "itens.csv.gz"
        if f.exists():
            for r in csv.DictReader(gzip.open(f, "rt", encoding="utf-8"), delimiter=";"):
                yield "casos_publicacoes", r.get("rede"), f"{d.name}:{r.get('item_id')}", r.get("texto"), r.get("publicado_em")
        for nome, rede in (("youtube_comentarios.csv.gz", "youtube"), ("instagram_comentarios.csv.gz", "instagram")):
            f = d / nome
            if f.exists():
                for r in csv.DictReader(gzip.open(f, "rt", encoding="utf-8"), delimiter=";"):
                    yield "casos_comentarios", rede, r.get("comment_id") or r.get("id"), r.get("texto") or r.get("text"), r.get("publicado_em") or r.get("created_at")


def corpus(priv: Path) -> dict:
    vistos = set()
    total = Counter()                       # (corpus, rede) -> textos
    por_mes = defaultdict(Counter)          # mes -> {total, grupo...}
    por_rede = defaultdict(Counter)         # (corpus, rede) -> grupo
    cooc = Counter()
    sem_data = 0
    for corp, rede, iid, texto, data in fontes(priv):
        k = (corp, rede, str(iid) if iid else norm(texto or "")[:200])
        if k in vistos or not (texto or "").strip():
            continue
        vistos.add(k)
        total[(corp, rede)] += 1
        g = grupos_no(texto)
        m = mes(data)
        if m:
            por_mes[m]["_textos"] += 1
        else:
            sem_data += 1
        for x in g:
            por_rede[(corp, rede)][x] += 1
            if m:
                por_mes[m][x] += 1
        for a in g:
            for b in g:
                if a < b:
                    cooc[(a, b)] += 1
    n = sum(total.values())
    tot_g = Counter()
    for c in por_rede.values():
        tot_g.update(c)
    return {"textos_lidos": n, "sem_data": sem_data,
            "por_corpus_rede": [{"corpus": c, "rede": r, "textos": t, "grupos": dict(por_rede[(c, r)])} for (c, r), t in sorted(total.items())],
            "totais": {k: {"textos": tot_g.get(k, 0), "por_10_mil": round(1e4 * tot_g.get(k, 0) / n, 2) if n else None} for k in GRUPOS},
            "por_mes": [{"mes": m, "textos": c["_textos"], **{k: c.get(k, 0) for k in GRUPOS}} for m, c in sorted(por_mes.items())],
            "coocorrencias": [{"a": a, "b": b, "textos": v} for (a, b), v in cooc.most_common(12)]}


def trends() -> dict:
    from collect_trends import Trends
    hoje = (dt.datetime.now(dt.timezone.utc) - dt.timedelta(hours=3)).strftime("%Y-%m-%d")
    janela = f"2017-01-01 {hoje}"
    out = {"janela": janela, "consultas": []}
    t = Trends(pause=5)
    for geo, rotulo in (("BR", "Brasil"), ("", "Mundo")):
        for q in TRENDS_CONSULTAS:
            reg = {"id": q["id"], "geo": rotulo, "termos": q["termos"], "pontos": None}
            try:
                ws = {w["id"]: w for w in t.explore(q["termos"], janela, geo)}
                ts = t.widget("multiline", ws["TIMESERIES"])
                reg["pontos"] = [{"mes": dt.datetime.fromtimestamp(int(p["time"]), dt.timezone.utc).strftime("%Y-%m"),
                                  "v": dict(zip(q["termos"], p.get("value") or []))} for p in ts["default"]["timelineData"]]
            except Exception as e:  # noqa: BLE001
                reg["erro"] = f"{type(e).__name__}: {str(e)[:160]}"
            out["consultas"].append(reg)
    return out


def main(argv=None) -> int:
    argv = sys.argv[1:] if argv is None else list(argv)
    dest = Path("data/termos")
    dest.mkdir(parents=True, exist_ok=True)
    arq = dest / "desinformacao.json"
    out = json.loads(arq.read_text(encoding="utf-8")) if arq.exists() else {}
    out.update(pedido="Responsável em 30/10/2026, 09h27: \"comparar o uso dos termos fora da academia com a recepção acadêmica que o artigo reconstrói\"",
               grupos={k: {"nome": v["nome"], "tipo": v["tipo"]} for k, v in GRUPOS.items()})
    if "--trends" in argv:
        out["trends"] = {**trends(), "lido_em_utc": now_utc(),
                         "aviso": "Google Trends: índice 0–100 relativo ao maior ponto de cada consulta (não é volume). \"fake news\" aparece nas duas consultas como âncora; termos sem volume suficiente aparecem como 0. Universo de buscas ⛔ (o Google não informa)."}
        for c in out["trends"]["consultas"]:
            print(f"trends {c['geo']} {c['id']}: {len(c['pontos'] or [])} meses {c.get('erro', '')}")
    if "--corpus" in argv:
        interno = os.environ.get("ODI_INTERNO_DIR")
        if not interno:
            print("⛔ ODI_INTERNO_DIR ausente")
            return 1
        out["corpus"] = {**corpus(Path(interno)), "lido_em_utc": now_utc(),
                         "aviso": "Amostra = acervo do Atlas (comentários aos posts das campanhas e publicações e comentários dos casos, coletados para outras perguntas); não representa as redes inteiras. Percentuais e taxas valem para os textos lidos."}
        c = out["corpus"]
        print(f"corpus: {c['textos_lidos']} textos · " + " · ".join(f"{k} {v['textos']} ({v['por_10_mil']}/10 mil)" for k, v in c["totais"].items()))
    out["gerado_em_utc"] = now_utc()
    arq.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
