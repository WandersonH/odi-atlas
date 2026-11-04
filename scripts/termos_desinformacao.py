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
import time
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
    "montagem": {"nome": "montagem", "tipo": "popular", "rx": r"montage(m|ns)"},
    "fora_de_contexto": {"nome": "fora de contexto / notícia antiga", "tipo": "popular",
                         "rx": r"fora de contexto|descontextualizad|tirad[oa] de contexto|(reportagem|noticia|materia) (e )?(antig[oa]|velh[oa])|nao e atual"},
    "editado": {"nome": "editado / cortado / acelerado", "tipo": "popular",
                "rx": r"video editado|foi editado|editaram|editado pra|cortaram o video|video cortado|corte malicioso|recortad|acelerad[oa] o video|video acelerado|desacelerad"},
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


ALVOS = {k: re.compile(v) for k, v in {
    "Lula": r"\blula\w*|\blulinha\b|\bpresidente lula",
    "Flávio/Bolsonaro": r"\bflavio\b|bolsonar\w*",
    "TSE e urna": r"\btse\b|\burnas?\b|justica eleitoral|eleicao fraudada|apuracao",
    "STF e Moraes": r"\bstf\b|moraes|xandao|supremo",
    "Imprensa": r"\bglobo\w*|imprensa|\bmidia\b|jornalis\w*|\bcnn\b|folha|estadao|band\b|record\b|sbt\b",
    "PT e esquerda": r"\bpt\b|petist\w*|esquerd\w*|comunis\w*",
    "Direita e bolsonarismo": r"\bdireita\b|bolsonarist\w*|\bpl\b|extrema direita",
    "IA": r"inteligencia artificial|\bia\b|\bai\b|chatgpt|gerad\w* por",
}.items()}


def grupos_no(texto: str) -> list[str]:
    t = norm(texto or "")
    return [k for k, r in RX.items() if r.search(t)]


def fontes(priv: Path):
    """(corpus, rede, id, texto, data) de todo o acervo privado de textos."""
    for rede in ("youtube", "facebook", "tiktok"):
        f = priv / rede / "comentarios" / "comentarios.csv.gz"
        if f.exists():
            for r in csv.DictReader(gzip.open(f, "rt", encoding="utf-8"), delimiter=";"):
                yield "comentarios_campanhas", rede, r.get("comment_id"), r.get("texto"), r.get("publicado_em"), None
    for f in sorted((priv / "instagram" / "comentarios").glob("apify_*.jsonl.gz")):
        for linha in gzip.open(f, "rt", encoding="utf-8"):
            x = json.loads(linha)
            yield "comentarios_campanhas", "instagram", x.get("id") or x.get("comment_id"), x.get("text"), x.get("created_at_utc") or x.get("created_at"), None
    for f in sorted((priv / "x" / "respostas").glob("*.jsonl.gz")):
        for linha in gzip.open(f, "rt", encoding="utf-8"):
            x = json.loads(linha)
            yield "comentarios_campanhas", "x", x.get("id"), x.get("text"), x.get("createdAt"), None
    for f in sorted((priv / "kwai" / "comentarios").glob("*.jsonl.gz")):
        for linha in gzip.open(f, "rt", encoding="utf-8"):
            x = json.loads(linha)
            yield "posts_kwai", "kwai", x.get("id"), " ".join(str(x.get(k) or "") for k in ("caption", "transcript")), x.get("createTime"), None
    for d in sorted((priv / "casos").glob("*")):
        f = d / "itens.csv.gz"
        if f.exists():
            for r in csv.DictReader(gzip.open(f, "rt", encoding="utf-8"), delimiter=";"):
                seg = int(r["seguidores"]) if str(r.get("seguidores") or "").isdigit() else 0
                conta = f"{r.get('rede')}:@{r.get('conta')}" if seg >= 10000 and r.get("conta") else None
                yield "casos_publicacoes", r.get("rede"), f"{d.name}:{r.get('item_id')}", r.get("texto"), r.get("publicado_em"), conta
        for nome, rede in (("youtube_comentarios.csv.gz", "youtube"), ("instagram_comentarios.csv.gz", "instagram")):
            f = d / nome
            if f.exists():
                for r in csv.DictReader(gzip.open(f, "rt", encoding="utf-8"), delimiter=";"):
                    yield "casos_comentarios", rede, r.get("comment_id") or r.get("id"), r.get("texto") or r.get("text"), r.get("publicado_em") or r.get("created_at"), None


def corpus(priv: Path) -> dict:
    vistos = set()
    total = Counter()                       # (corpus, rede) -> textos
    por_mes = defaultdict(Counter)          # mes -> {total, grupo...}
    por_rede = defaultdict(Counter)         # (corpus, rede) -> grupo
    cooc = Counter()
    sem_data = 0
    # 01/11/2026, pedido: "cadê o Gephi de circulação" — termo × rede, termo × caso, termo × alvo citado no mesmo texto, conta pública (10 mil+) × termo
    circ = Counter()
    alvos_m = defaultdict(Counter)
    for corp, rede, iid, texto, data, conta in fontes(priv):
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
        if g:
            alvos = [k for k, rx in ALVOS.items() if rx.search(norm(texto))]
            caso = str(iid).split(":")[0] if corp.startswith("casos") and ":" in str(iid) else None
            for x in g:
                circ[(f"termo:{x}", f"rede:{rede}")] += 1
                if caso:
                    circ[(f"termo:{x}", f"caso:{caso}")] += 1
                for al in alvos:
                    circ[(f"termo:{x}", f"alvo:{al}")] += 1
                    alvos_m[x][al] += 1
                if conta:
                    circ[(f"conta:{conta}", f"termo:{x}")] += 1
    n = sum(total.values())
    tot_g = Counter()
    for c in por_rede.values():
        tot_g.update(c)
    from redes_caso import _desenho, gexf
    nos = {}
    for (a, b), w in circ.items():
        for k in (a, b):
            tipo, nome = k.split(":", 1)
            rot = GRUPOS[nome]["nome"] if tipo == "termo" else nome
            nos.setdefault(k, {"rotulo": rot, "tipo": tipo, "n": 0})["n"] += w
    Path("data/termos").mkdir(parents=True, exist_ok=True)
    gexf(nos, dict(circ), Path("data/termos/rede_circulacao.gexf"))
    cn = {f"termo:{k}": {"rotulo": v["nome"], "tipo": "termo", "n": 0} for k, v in GRUPOS.items()}
    for (a, b), w in cooc.items():
        cn[f"termo:{a}"]["n"] += w
        cn[f"termo:{b}"]["n"] += w
    co_ar = {(f"termo:{a}", f"termo:{b}"): w for (a, b), w in cooc.items()}
    gexf(cn, co_ar, Path("data/termos/rede_coocorrencia.gexf"))
    # desenho sem as contas (deixavam o centro ilegível); as contas ficam no GEXF e numa lista à parte
    sem_conta = Counter({k: w for k, w in circ.items() if not k[0].startswith("conta:")})
    contas = Counter()
    contas_termos = defaultdict(Counter)
    for (a, b), w in circ.items():
        if a.startswith("conta:"):
            contas[a] += w
            contas_termos[a][GRUPOS[b.split(":", 1)[1]]["nome"]] += w
    rede_c = {"desenho": _desenho({k: v for k, v in nos.items() if not k.startswith("conta:")}, sem_conta, 60), "total_nos": len(nos), "total_arestas": len(circ),
              "contas_publicas": [{"conta": k.split(":", 1)[1], "textos": v, "termos": dict(contas_termos[k].most_common())} for k, v in contas.most_common(25)],
              "alvos": {k: dict(v) for k, v in alvos_m.items()},
              "nota": "Ligações: termo × rede (onde o texto foi lido), termo × caso do Atlas, termo × alvo citado no mesmo texto (Lula, Flávio/Bolsonaro, "
                      "TSE/urna, STF/Moraes, imprensa, PT/esquerda, direita/bolsonarismo, IA/inteligência artificial) e conta pública (10 mil+ seguidores, "
                      "publicações dos casos) × termo. Peso = textos. Alvo é co-ocorrência no mesmo texto, não quer dizer que o termo foi dirigido ao alvo."}
    return {"rede_circulacao": rede_c,
            "coocorrencias_todas": [{"a": a, "b": b, "textos": v} for (a, b), v in cooc.most_common()],
            "textos_lidos": n, "sem_data": sem_data,
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
            for tentativa in range(3):  # o Trends devolve 429 em rajadas: espera e tenta de novo
                try:
                    ws = {w["id"]: w for w in t.explore(q["termos"], janela, geo)}
                    break
                except Exception as e:  # noqa: BLE001
                    if tentativa == 2 or "429" not in str(e):
                        reg["erro"] = f"{type(e).__name__}: {str(e)[:160]}"
                        break
                    time.sleep(90 * (tentativa + 1))
            if "erro" in reg:
                out["consultas"].append(reg)
                continue
            try:
                ts = t.widget("multiline", ws["TIMESERIES"])
                reg["pontos"] = [{"mes": dt.datetime.fromtimestamp(int(p["time"]), dt.timezone.utc).strftime("%Y-%m"),
                                  "v": dict(zip(q["termos"], p.get("value") or []))} for p in ts["default"]["timelineData"]]
            except Exception as e:  # noqa: BLE001
                reg["erro"] = f"{type(e).__name__}: {str(e)[:160]}"
            out["consultas"].append(reg)
    return out


TRENDS_UF = ["deepfake", "deep fake", "fake news", "desinformação"]


def trends_uf() -> dict:
    """Interesse por estado (Google Trends, Brasil, resolução UF), uma consulta por termo — 04/11/2026, 01h05: "se quiser mapa de
    'deepfake' por UF, precisa rodar uma consulta nova. pode implantar". Termo sozinho: o índice 0–100 de cada UF é a parcela das
    buscas do estado que foram por aquele termo, relativa ao estado com a maior parcela (não é volume nem comparação entre termos)."""
    from collect_trends import Trends
    hoje = (dt.datetime.now(dt.timezone.utc) - dt.timedelta(hours=3)).strftime("%Y-%m-%d")
    janelas = [("2017-01-01 " + hoje, "2017 até hoje"), ("today 12-m", "últimos 12 meses")]
    t = Trends(pause=5)
    out = {"termos": TRENDS_UF, "janelas": [{"id": j, "rotulo": r} for j, r in janelas], "consultas": []}
    for termo in TRENDS_UF:
        for jan, rot in janelas:
            reg = {"termo": termo, "janela": jan, "rotulo": rot, "ufs": None}
            for tentativa in range(3):
                try:
                    ws = {w["id"]: w for w in t.explore([termo], jan, "BR")}
                    gw = next((w for k, w in ws.items() if k.startswith("GEO_MAP")), None)
                    gm = t.widget("comparedgeo", gw) if gw else None
                    reg["ufs"] = [{"uf": (r.get("geoCode") or "").replace("BR-", ""), "nome": r.get("geoName"),
                                   "v": (r.get("value") or [None])[0], "tem_dado": bool((r.get("hasData") or [bool((r.get("value") or [0])[0])])[0])}
                                  for r in (gm or {}).get("default", {}).get("geoMapData", [])]
                    reg.pop("erro", None)
                    break
                except Exception as e:  # noqa: BLE001
                    reg["erro"] = f"{type(e).__name__}: {str(e)[:160]}"
                    if "429" not in str(e) or tentativa == 2:
                        break
                    time.sleep(90 * (tentativa + 1))
            out["consultas"].append(reg)
            print(f"trends UF {termo} · {rot}: {len(reg['ufs'] or [])} UFs {reg.get('erro', '')}")
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
                         "aviso": "Google Trends: índice 0–100 relativo ao maior ponto de cada consulta (não é volume). \"fake news\" aparece nas duas consultas como âncora; termos sem volume suficiente aparecem como 0. \"Montagem\" e \"inteligência artificial\" são palavras de uso geral: a busca não separa o sentido de manipulação. Universo de buscas ⛔ (o Google não informa)."}
        for c in out["trends"]["consultas"]:
            print(f"trends {c['geo']} {c['id']}: {len(c['pontos'] or [])} meses {c.get('erro', '')}")
    if "--uf" in argv:
        out["trends_uf"] = {**trends_uf(), "lido_em_utc": now_utc(),
                            "aviso": "Google Trends por estado: uma consulta por termo; índice 0–100 = parcela das buscas do estado que foram pelo termo, relativa ao estado com a maior parcela. Não é volume, não soma entre estados e não compara termos entre si. Estados com pouca busca aparecem como 0 (sem dado suficiente). Universo de buscas ⛔ (o Google não informa)."}
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
