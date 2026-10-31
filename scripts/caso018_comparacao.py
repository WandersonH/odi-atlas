#!/usr/bin/env python3
"""Caso 018 — circulação e comentários NA ÉPOCA × DEPOIS DA ELEIÇÃO, episódio por episódio.

Pedido do responsável (30/10/2026, 22h32): "eu tinha pedido uma comparação [da] circulação e [dos] comentários da data e pós-eleições".
Fontes (privado: ODI_INTERNO_DIR/casos/018): x_epoca_<ep>.jsonl.gz (busca do X na janela da época, lida uma vez), itens.csv.gz
(coleta desde 24/10/2026: X, Instagram, Facebook), youtube_comentarios.csv.gz (comentários datados dos vídeos originais).
Para cada episódio, os dois períodos passam pelo MESMO filtro de pertinência (regex do episódio) e são comparados em:
  - circulação: publicações, contas, visualizações, curtidas, respostas recebidas; curva por dia desde o 1º dia (dia 0), pico,
    dias até metade do total; contas de 10 mil+ seguidores em cada período e as que aparecem nos dois;
  - comentários: respostas no X (publicações que são resposta) e comentários datados dos vídeos originais do YouTube, antes e depois de 25/10/2026;
  - palavras: as mais típicas de cada período (razão de frequências com suavização);
  - tom: sentimento (pysentimiento/bertweet-pt-sentiment, o mesmo modelo dos comentários do Atlas) dos textos em português, se o
    modelo estiver instalado (senão ⛔ registrado).
A época do Instagram e do Facebook não tem busca retroativa: ⛔ (informado). Público: data/casos/018/comparacao.json (contagens,
palavras e contas de 10 mil+). Uso: python scripts/caso018_comparacao.py
"""
from __future__ import annotations

import csv
import datetime as dt
import gzip
import json
import math
import os
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from collect_casos import norm  # noqa: E402

CORTE = "2026-10-25"
EP = {
    "A": {"pertinente": r"haddad.{0,200}(boicot|davos|palito|n[aã]o compr)|(boicot|davos|palito|n[aã]o compr).{0,200}haddad",
          "termos_agora": ("A agora", "Haddad", "palito", "Carol De Toni", "reels: Haddad"), "youtube": ["qjmwYUs676E", "93cZU_d-KAg"]},
    "B": {"pertinente": r"greve.{0,200}(sergipe|professor)|(sergipe|professor).{0,200}greve",
          "termos_agora": ("B agora", "Sergipe", "greve"), "youtube": []},
    "C": {"pertinente": r"(bilh|congel|bloquei|corte|cortou|cortar).{0,200}(sa[uú]de|educa)|(sa[uú]de|educa).{0,200}(bilh|congel|bloquei|corte|cortou|cortar)",
          "termos_agora": ("C agora", "6 bilh", "cortou", "saúde educação", "saude educacao"), "youtube": []},
}
STOP = set("""a o e é de da do das dos em no na nos nas um uma para pra por pelo pela com sem que se não nao mais mas como ao aos à às ou
já ja só so isso esse essa este esta foi ser ter tem vai vou eu ele ela eles elas você voce vc vcs nós nos seu sua seus suas meu minha
the and rt https http com www está esta estão estao era são sao quando quem qual muito pq porque sobre até ate tá ta aqui lá la ai aí
todo toda todos todas ele dele dela isso nem bem pode mesmo ainda depois antes hoje agora""".split())


def tokens(t: str) -> list[str]:
    t = re.sub(r"https?://\S+|@\w+", " ", (t or "").lower())
    return [w for w in re.findall(r"[a-záéíóúâêôãõçà]{3,}", t) if w not in STOP]


def resumo(rows: list[dict]) -> dict:
    n = lambda k: sum(int(r.get(k) or 0) for r in rows)  # noqa: E731
    dias = Counter((r.get("publicado_em") or "")[:10] for r in rows if r.get("publicado_em"))
    ds = sorted(dias)
    serie, d0 = [], None
    if ds:
        d0 = dt.date.fromisoformat(ds[0])
        ult = dt.date.fromisoformat(ds[-1])
        serie = [dias.get((d0 + dt.timedelta(days=i)).isoformat(), 0) for i in range((ult - d0).days + 1)]
    acum, meia = 0, None
    for i, v in enumerate(serie):
        acum += v
        if meia is None and acum >= len(rows) / 2:
            meia = i
    grandes, segs = Counter(), {}
    for r in rows:
        if int(r.get("seguidores") or 0) >= 10000:
            k = (r["rede"], r["conta"])
            grandes[k] += 1
            segs[k] = max(segs.get(k, 0), int(r.get("seguidores") or 0))
    return {"publicacoes": len(rows), "contas": len({(r["rede"], r["conta"]) for r in rows}), "visualizacoes": n("visualizacoes"),
            "curtidas": n("curtidas"), "respostas_recebidas": n("comentarios"), "compartilhamentos": n("compartilhamentos"),
            "primeiro_dia": ds[0] if ds else None, "ultimo_dia": ds[-1] if ds else None,
            "pico": {"dia": max(dias, key=dias.get), "publicacoes": max(dias.values())} if dias else None,
            "dias_ate_metade": meia, "serie_desde_dia0": serie,
            "contas_10mil": [{"rede": a, "conta": b, "seguidores": segs[(a, b)], "publicacoes": k} for (a, b), k in grandes.most_common(12)]}


def tipicas(a: list[str], b: list[str], top: int = 15) -> tuple[list, list]:
    ca, cb = Counter(w for t in a for w in set(tokens(t))), Counter(w for t in b for w in set(tokens(t)))
    na, nb = max(1, len(a)), max(1, len(b))
    voc = {w for w in ca | cb if ca[w] + cb[w] >= 5}
    lr = {w: math.log(((ca[w] + .5) / na) / ((cb[w] + .5) / nb)) for w in voc}
    ea = sorted((w for w in voc if lr[w] > 0), key=lambda w: (-lr[w] * math.sqrt(ca[w])))[:top]
    eb = sorted((w for w in voc if lr[w] < 0), key=lambda w: (lr[w] * math.sqrt(cb[w])))[:top]
    return [[w, ca[w]] for w in ea], [[w, cb[w]] for w in eb]


_CLF = None


def sentimento(textos: dict[str, str], cache_f: Path) -> tuple[dict, str | None]:
    """{id: rótulo POS/NEG/NEU} com cache; usa o classificador do Atlas (build_sentimento_comentarios)."""
    global _CLF
    cache = {}
    if cache_f.exists():
        cache = {r["id"]: r["rotulo"] for r in csv.DictReader(gzip.open(cache_f, "rt", encoding="utf-8"))}
    novos = [(k, t) for k, t in textos.items() if k not in cache and t.strip()]
    erro = None
    if novos:
        try:
            if _CLF is None:
                from build_sentimento_comentarios import classificador
                cfg = json.loads(Path("data/config/sentimento_comentarios.json").read_text(encoding="utf-8"))
                _CLF = classificador(cfg["modelo"], cfg["max_tokens"], cfg["lote"])[0]
            res = _CLF([t for _, t in novos])
            for (k, _), r in zip(novos, res):
                cache[k] = r["rotulo"]
            with gzip.open(cache_f, "wt", encoding="utf-8", newline="") as g:
                w = csv.writer(g)
                w.writerow(["id", "rotulo"])
                w.writerows(cache.items())
        except Exception as e:  # noqa: BLE001
            erro = f"⛔ modelo de sentimento indisponível nesta execução ({type(e).__name__})"
    return {k: cache[k] for k in textos if k in cache}, erro


def dist(rot: list[str]) -> dict:
    c = Counter(rot)
    n = sum(c.values())
    return {"n": n, **{k: round(100 * c[k] / n, 1) if n else None for k in ("NEG", "NEU", "POS")}}


def main(argv=None) -> int:
    interno = os.environ.get("ODI_INTERNO_DIR")
    if not interno:
        print("⛔ ODI_INTERNO_DIR ausente")
        return 1
    priv = Path(interno) / "casos" / "018"
    agora_rows = list(csv.DictReader(gzip.open(priv / "itens.csv.gz", "rt", encoding="utf-8"), delimiter=";")) if (priv / "itens.csv.gz").exists() else []
    yt = list(csv.DictReader(gzip.open(priv / "youtube_comentarios.csv.gz", "rt", encoding="utf-8"), delimiter=";")) if (priv / "youtube_comentarios.csv.gz").exists() else []
    cfg = next(c for c in json.loads(Path("data/config/casos.json").read_text(encoding="utf-8"))["casos"] if c["id"] == "018")
    janelas = {k: (v or {}).get("janela_epoca") for k, v in (cfg.get("episodios") or {}).items()}
    out = {"caso": "018", "gerado_em_utc": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"), "corte_pos_eleicao": CORTE,
           "metodo": __doc__.split("\n\n")[1].strip(), "episodios": {}}
    textos_sent, por_ep_ids = {}, {}
    for ep, e in EP.items():
        rx = re.compile(e["pertinente"], re.I | re.S)
        epoca = []
        f = priv / f"x_epoca_{ep}.jsonl.gz"
        if f.exists():
            for l in gzip.open(f, "rt", encoding="utf-8"):
                x = json.loads(l)
                r = norm("x", x, f"época {ep}", "")
                if r and rx.search(r["texto"]):
                    r["resposta"] = bool(x.get("isReply"))
                    epoca.append(r)
        ag = [r for r in agora_rows if any(t.lower() in (r["termo"] or "").lower() for t in e["termos_agora"]) and rx.search(r["texto"] or "")]
        ag_x = [r for r in ag if r["rede"] == "x"]
        dep = {"x_epoca": resumo(epoca) if f.exists() else None, "x_agora": resumo(ag_x),
               "instagram_agora": resumo([r for r in ag if r["rede"] == "instagram"]), "facebook_agora": resumo([r for r in ag if r["rede"] == "facebook"]),
               "epoca_instagram_facebook": "⛔ sem busca retroativa no Instagram e no Facebook",
               "janela_epoca": janelas.get(ep), "filtro_pertinencia": e["pertinente"]}
        if f.exists():
            dep["x_epoca"]["respostas_entre_publicacoes"] = sum(1 for r in epoca if r.get("resposta"))
            contas_a = {(r["conta"] or "").lower() for r in epoca}
            ambos = [r for r in ag_x if (r["conta"] or "").lower() in contas_a]
            dep["contas_nos_dois_periodos"] = len({r["conta"].lower() for r in ambos})
            dep["contas_10mil_nos_dois"] = sorted({(r["conta"], int(r.get("seguidores") or 0)) for r in ambos if int(r.get("seguidores") or 0) >= 10000}, key=lambda t: -t[1])[:10]
            ta, tb = tipicas([r["texto"] for r in epoca], [r["texto"] for r in ag])
            dep["palavras_tipicas"] = {"epoca": ta, "agora": tb}
        # YouTube: comentários datados dos vídeos originais, na janela da época × depois do corte
        if e["youtube"]:
            cs = [c for c in yt if c["video_id"] in e["youtube"]]
            jn = janelas.get(ep) or [None, None]
            na_epoca = [c for c in cs if jn[0] and jn[0] <= c["publicado_em"][:10] <= (jn[1] or "9999")]
            depois = [c for c in cs if c["publicado_em"][:10] >= CORTE]
            meses = Counter(c["publicado_em"][:7] for c in cs)
            dep["youtube_comentarios"] = {"videos": e["youtube"], "lidos": len(cs), "na_janela_da_epoca": len(na_epoca), "depois_de_25_10_2026": len(depois),
                                          "por_mes": dict(sorted(meses.items())), "palavras_tipicas": dict(zip(("epoca", "depois"), tipicas([c["texto"] for c in na_epoca], [c["texto"] for c in depois], 10)))}
            for c in na_epoca:
                textos_sent[f"yt:{c['comment_id']}"] = c["texto"]
            for c in depois:
                textos_sent[f"yt:{c['comment_id']}"] = c["texto"]
            por_ep_ids[(ep, "yt_epoca")] = [f"yt:{c['comment_id']}" for c in na_epoca]
            por_ep_ids[(ep, "yt_depois")] = [f"yt:{c['comment_id']}" for c in depois]
        for nome, rs in (("x_epoca", epoca), ("x_agora", ag_x), ("instagram_agora", [r for r in ag if r["rede"] == "instagram"]),
                         ("facebook_agora", [r for r in ag if r["rede"] == "facebook"])):
            ids = []
            for r in rs:
                k = f"{r['rede']}:{r['item_id']}"
                textos_sent[k] = r["texto"]
                ids.append(k)
            por_ep_ids[(ep, nome)] = ids
        out["episodios"][ep] = dep
    rot, erro = sentimento(textos_sent, priv / "sentimento_comparacao.csv.gz")
    for (ep, nome), ids in por_ep_ids.items():
        out["episodios"][ep].setdefault("sentimento", {})[nome] = dist([rot[i] for i in ids if i in rot])
    out["sentimento_modelo"] = "pysentimiento/bertweet-pt-sentiment (o mesmo dos comentários do Atlas; textos em português)"
    out["sentimento_erro"] = erro
    Path("data/casos/018/comparacao.json").write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    for ep, d in out["episodios"].items():
        xe, xa = d.get("x_epoca") or {}, d["x_agora"]
        print(f"018 {ep}: X época {xe.get('publicacoes')} pub · {xe.get('contas')} contas · pico {xe.get('pico')} | X agora {xa['publicacoes']} · "
              f"IG agora {d['instagram_agora']['publicacoes']} · FB agora {d['facebook_agora']['publicacoes']} · contas nos dois {d.get('contas_nos_dois_periodos')}")
    print("sentimento:", erro or "ok")
    return 0


if __name__ == "__main__":
    sys.exit(main())
