#!/usr/bin/env python3
"""Emojis e palavras dos textos de cada caso (posts e comentários) — só contagens no público.

10/11/2026 (C19.373, pedido do responsável: "gerar um mapa de emojis dos comentários … classificados automaticamente
e validados por pesquisadores"). Etapa 1: extração e sugestão automática. A validação humana é etapa seguinte.

Lê do privado ($ODI_INTERNO_DIR/casos/<id>/): itens.csv.gz (posts), youtube_comentarios.csv.gz,
instagram_comentarios.csv.gz, comentarios.csv.gz. Grava data/casos/<id>/emojis.json SEM texto nem autor:
  - fontes: universo informado pela plataforma (quando há), textos lidos, textos com emoji (regra 9);
  - emojis: os 120 mais usados, com variantes unidas (❤ = ❤️; tons de pele somados ao emoji-base);
    por emoji: ocorrências, textos, % dos textos lidos, nome em português (CLDR, biblioteca emoji),
    posição no texto (início, meio, fim, só emoji — Paiva, 2016; Schnoebelen), repetição em sequência
    (intensificador), divisão por fonte e escore de sentimento do Emoji Sentiment Ranking
    (Kralj Novak et al., 2015; data/config/emoji_sentiment_ranking_v1.csv) — fora do ranking: null (⛔);
  - palavras: nuvem (em quantos textos cada palavra ou par aparece), geral e por fonte, com a mesma regra das
    nuvens do YouTube (build_conteudo.nuvem).
Tudo é SUGESTÃO AUTOMÁTICA até a validação dos pesquisadores.

Uso: ODI_INTERNO_DIR=… python scripts/emojis_caso.py [--caso 001]
"""
from __future__ import annotations

import argparse
import csv
import gzip
import json
import os
import re
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

import emoji

sys.path.insert(0, os.path.dirname(__file__))
from build_conteudo import URL, norm as norm_txt, nuvem  # noqa: E402

csv.field_size_limit(10**9)
TOP = 120
MENCAO = re.compile(r"@[\w.]+")
VAR = re.compile("[️\U0001F3FB-\U0001F3FF]")
FONTES = [  # (chave, arquivo, rótulo, coluna da rede ou None)
    ("posts", "itens.csv.gz", None, "rede"),
    ("youtube_comentarios", "youtube_comentarios.csv.gz", "YouTube · comentários", None),
    ("instagram_comentarios", "instagram_comentarios.csv.gz", "Instagram · comentários", None),
    ("comentarios", "comentarios.csv.gz", "Comentários", None),
]
ROT_REDE = {"x": "X", "instagram": "Instagram", "facebook": "Facebook", "tiktok": "TikTok", "kwai": "Kwai",
            "youtube": "YouTube", "threads": "Threads", "bluesky": "Bluesky"}
ROT_POS = ("início", "meio", "fim", "só emoji")


def norm(e: str) -> str:
    return VAR.sub("", e)


def sentimento(caminho: str = "data/config/emoji_sentiment_ranking_v1.csv") -> dict[str, float]:
    out = {}
    for r in csv.DictReader(open(caminho, encoding="utf-8")):
        n = int(r["Occurrences"])
        if n:
            out[norm(r["Emoji"])] = round((int(r["Positive"]) - int(r["Negative"])) / n, 3)
    return out


def casos_cfg() -> dict:
    d = json.load(open("data/config/casos.json", encoding="utf-8"))
    d = d if isinstance(d, list) else d.get("casos", list(d.values()))
    return {str(c["id"]): c for c in d}


def ler(f: Path):
    with gzip.open(f, "rt", encoding="utf-8", errors="ignore") as h:
        yield from csv.DictReader(h, delimiter=";")


def universo(cid: str) -> dict:
    """Universo informado pelas plataformas, quando existe: soma dos comentários que as plataformas informam nos
    vídeos/posts lidos. Busca de posts: as plataformas não informam o total (⛔)."""
    u = {}
    b = Path(f"data/casos/{cid}/busca.json")
    if b.exists():
        y = (json.loads(b.read_text(encoding="utf-8")).get("youtube") or {})
        if isinstance(y.get("comentarios"), int):
            u["youtube_comentarios"] = (y["comentarios"], "soma dos comentários que o YouTube informa nos vídeos lidos (busca.json)")
    return u


def processa(cid: str, interno: Path, esr: dict, cfg: dict) -> dict | None:
    pasta = interno / "casos" / cid
    if not pasta.is_dir():
        return None
    mascara = re.compile(cfg["anonimizar_publico_regex"], re.I) if cfg.get("anonimizar_publico_regex") else None
    univ = universo(cid)
    fontes = {}  # rótulo → {lidos, com_emoji, ocorrencias}
    occ, txts, pos, rep, por_fonte, variantes = Counter(), Counter(), defaultdict(Counter), Counter(), defaultdict(Counter), defaultdict(Counter)
    textos_por_fonte = defaultdict(list)
    for chave, arq, rot, col in FONTES:
        f = pasta / arq
        if not f.exists():
            continue
        for r in ler(f):
            t = r.get("texto") or ""
            fonte = f"{ROT_REDE.get((r.get(col) or '').lower(), r.get(col) or '?')} · posts" if col else rot
            F = fontes.setdefault(fonte, {"chave": chave, "lidos": 0, "com_emoji": 0, "ocorrencias": 0})
            F["lidos"] += 1
            tl = MENCAO.sub(" ", URL.sub(" ", t))  # @ de pessoas comuns e links não entram na nuvem
            textos_por_fonte[fonte].append(mascara.sub(" ", tl) if mascara else tl)
            es = emoji.emoji_list(t)
            if not es:
                continue
            F["com_emoji"] += 1
            F["ocorrencias"] += len(es)
            so = not emoji.replace_emoji(t, "").strip()
            cobre = set()
            for e in es:
                cobre.update(range(e["match_start"], e["match_end"]))
            txt_idx = [i for i, ch in enumerate(t) if i not in cobre and not ch.isspace() and ch != "\ufe0f"]
            pri, ult = (txt_idx[0], txt_idx[-1]) if txt_idx else (-1, -1)
            vistos = set()
            ant, fim_ant = None, -1
            for e in es:
                k = norm(e["emoji"])
                variantes[k][e["emoji"]] += 1
                occ[k] += 1
                por_fonte[k][fonte] += 1
                p = "só emoji" if so else ("fim" if e["match_start"] > ult else ("início" if e["match_end"] <= pri else "meio"))
                pos[k][p] += 1
                if k == ant and e["match_start"] == fim_ant:
                    rep[k] += 1  # ocorrência colada à anterior do mesmo emoji (😂😂): intensificador
                ant, fim_ant = k, e["match_end"]
                if k not in vistos:
                    txts[k] += 1
                    vistos.add(k)
    if not fontes:
        return None
    lidos = sum(F["lidos"] for F in fontes.values())
    com = sum(F["com_emoji"] for F in fontes.values())
    lista = []
    for k, n in occ.most_common(TOP):
        rot = variantes[k].most_common(1)[0][0]
        if "\ufe0f" not in rot and (rot + "\ufe0f") in emoji.EMOJI_DATA:
            rot += "\ufe0f"  # forma colorida (❤ → ❤️) na página
        nome = emoji.demojize(rot, language="pt").strip(":").replace("_", " ")
        lista.append({"e": rot, "nome": nome if not nome.startswith(rot) else None, "ocorrencias": n, "textos": txts[k],
                      "pct_textos_lidos": round(100 * txts[k] / lidos, 2), "posicao": {p: pos[k][p] for p in ROT_POS if pos[k][p]},
                      "repeticao_pct": round(100 * rep[k] / n, 1), "por_fonte": dict(por_fonte[k].most_common()),
                      "sentimento": esr.get(k)})
    pos_tot = Counter()
    for c in pos.values():
        pos_tot.update(c)
    # como nas nuvens do YouTube (que tiram o nome do próprio candidato): os termos de busca do caso não entram
    excluir = set()
    cj = Path(f"data/casos/{cid}/caso.json")
    if cj.exists():
        for t in json.loads(cj.read_text(encoding="utf-8")).get("termos") or []:
            t = t if isinstance(t, str) else (t.get("termo") or "")
            excluir |= {norm_txt(w).strip().lstrip("#") for w in re.split(r"\s+", t.strip('"')) if w}
            excluir.add(norm_txt(t.replace(" ", "")).strip().lstrip("#"))
    palavras = {"Todas": nuvem(sum(textos_por_fonte.values(), []), excluir, top=60, minimo=3)}
    for fonte, ts in textos_por_fonte.items():
        if len(ts) >= 30:
            palavras[fonte] = nuvem(ts, excluir, top=60, minimo=3)
    if mascara:  # 020: nada que remeta à criança nas nuvens
        palavras = {k: [x for x in v if not mascara.search(x[0])] for k, v in palavras.items()}
    soma_occ = sum(occ.values())
    return {
        "schema_version": 1, "caso": cid, "gerado_em_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "fontes": [{"fonte": k, "universo": univ.get(F["chave"], (None, None))[0],
                    "universo_fonte": univ.get(F["chave"], (None, "⛔ a plataforma não informa o total"))[1],
                    "lidos": F["lidos"], "com_emoji": F["com_emoji"], "ocorrencias": F["ocorrencias"]}
                   for k, F in sorted(fontes.items(), key=lambda x: -x[1]["lidos"])],
        "total": {"lidos": lidos, "com_emoji": com, "pct_com_emoji": round(100 * com / lidos, 1) if lidos else 0,
                  "ocorrencias": soma_occ, "distintos": len(occ),
                  "cobertura_sentimento_pct": round(100 * sum(n for k, n in occ.items() if k in esr) / soma_occ, 1) if soma_occ else None},
        "posicao": {p: pos_tot[p] for p in ROT_POS},
        "emojis": lista,
        "palavras": palavras,
        "metodo": ("Emojis extraídos de cada texto lido (posts e comentários) com a biblioteca emoji 2.16 (Unicode/CLDR); variantes "
                   "unidas (seletor de variação e tons de pele somados ao emoji-base). Posição: início, meio, fim do texto ou texto só "
                   "com emoji (Paiva, 2016). Repetição: % das ocorrências coladas a outra do mesmo emoji (😂😂), uso como "
                   "intensificador. Sentimento: escore (positivos − negativos) / ocorrências do Emoji Sentiment Ranking v1.0 "
                   "(Kralj Novak et al., 2015, tweets em 13 línguas europeias, 2013–2015); emoji fora do ranking fica sem escore. "
                   "Palavras: em quantos textos cada palavra ou par aparece (mínimo 3, top 60), sem palavras funcionais."),
        "aviso": ("Classificação automática: SUGESTÃO, ainda não validada pelos pesquisadores. Percentuais valem para a amostra lida, "
                  "não para o universo da plataforma."),
    }


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--caso")
    a = ap.parse_args(argv)
    interno = Path(os.environ.get("ODI_INTERNO_DIR", ""))
    if not (interno / "casos").is_dir():
        print("⛔ ODI_INTERNO_DIR sem casos/"); return 1
    esr, cfg = sentimento(), casos_cfg()
    ids = [a.caso] if a.caso else sorted(p.name for p in Path("data/casos").iterdir() if re.fullmatch(r"\d{3}", p.name))
    for cid in ids:
        out = processa(cid, interno, esr, cfg.get(cid, {}))
        if out is None:
            print(f"{cid}: sem corpus no privado"); continue
        Path(f"data/casos/{cid}/emojis.json").write_text(json.dumps(out, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
        t = out["total"]
        print(f"{cid}: {t['lidos']} textos, {t['com_emoji']} com emoji ({t['pct_com_emoji']}%), {t['distintos']} emojis")
    return 0


if __name__ == "__main__":
    sys.exit(main())
