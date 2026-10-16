#!/usr/bin/env python3
"""Caderno 11 — estratégias discursivas (Bardin) e corpus para IRaMuTeQ.

Entrada: data/youtube/videos_latest.csv.gz, data/config/temas_youtube.json, data/config/livro_codigos_populismo.json
Saídas:
  data/youtube/populismo.json                       pré-codificação automática por vídeo e agregados (sugestão, não decisão)
  data/corpus/youtube_candidatos_iramuteq.txt       corpus no formato IRaMuTeQ (**** *variáveis), um texto por vídeo
  data/corpus/youtube_candidatos_segmentos.csv      mesmo texto em segmentos (~40 palavras) para a CHD (chd_reinert.py)
  data/codificacao/amostra_populismo_v1.csv         planilha da codificação humana (gerada UMA vez; nunca sobrescrita)
  data/codificacao/amostra_populismo_v1_precodificacao.csv  pré-codificação da amostra, separada (codificador não vê)

Unidade de registro: o vídeo (título + descrição útil, sem links, rodapés repetidos nem nome do canal).
"""
from __future__ import annotations

import csv
import datetime as dt
import gzip
import json
import random
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import build_conteudo as bc  # noqa: E402
import plataformas as pl  # noqa: E402

SEMENTE = 42
PALAVRAS_SEGMENTO = 40
DESDE = dt.datetime(2026, 8, 16, tzinfo=dt.timezone.utc)


def compilar(livro: dict) -> dict:
    """{categoria: (indicadores, exclusões)}."""
    return {k: ([bc.term_regex(t) for t in c["indicadores"]], [bc.term_regex(t) for t in c.get("excluir_trechos", [])])
            for k, c in livro["categorias"].items()}


def precodificar(texto: str, regs: dict) -> dict[str, str]:
    """{categoria: trecho que disparou} só para as categorias presentes (pré-codificação, não decisão).
    Os trechos de exclusão da categoria são retirados antes da busca."""
    t0 = bc.norm(texto)
    out = {}
    for cat, (rs, excl) in regs.items():
        t = t0
        for e in excl:
            t = e.sub(" ", t)
        for r in rs:
            m = r.search(t)
            if m:
                out[cat] = t[max(0, m.start() - 50):m.end() + 50].strip()
                break
    return out


def limpar_iramuteq(texto: str) -> str:
    """Remove o que o IRaMuTeQ interpreta como marcação ou quebra o corpus (*, $, %, aspas, apóstrofos, quebras)."""
    t = bc.URL.sub(" ", texto or "")
    t = re.sub(r"[*$%\"'`´“”‘’#@|_\\]", " ", t)
    t = re.sub(r"[\U0001F000-\U0001FAFF☀-➿️]", " ", t)
    return re.sub(r"\s+", " ", t).strip()


def var(s: str) -> str:
    """Valor de variável IRaMuTeQ: minúsculas, sem acento, sem espaço."""
    return re.sub(r"[^a-z0-9]+", "", bc.norm(s))


def semana(iso: str) -> int:
    d = dt.datetime.fromisoformat(iso.replace("Z", "+00:00"))
    return max(0, (d - DESDE).days // 7) + 1


def formato(duracao: str) -> str:
    m = re.fullmatch(r"PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?", duracao or "")
    if not m:
        return "nd"
    seg = int(m[1] or 0) * 3600 + int(m[2] or 0) * 60 + int(m[3] or 0)
    return "short" if seg <= 180 else "longo"


def segmentos(texto: str, n: int = PALAVRAS_SEGMENTO) -> list[str]:
    """Segmentos de ~n palavras, cortando preferencialmente em fim de frase (como o IRaMuTeQ)."""
    frases = [f.strip() for f in re.split(r"(?<=[.!?;])\s+", texto) if f.strip()]
    out, atual = [], []
    for f in frases:
        w = f.split()
        if atual and len(atual) + len(w) > n:
            out.append(" ".join(atual))
            atual = []
        while len(w) > n:  # frase longa demais: corta
            out.append(" ".join(w[:n]))
            w = w[n:]
        atual += w
    if atual:
        out.append(" ".join(atual))
    return out


def amostra_estratificada(vids: list[dict], n: int, semente: int = SEMENTE) -> list[dict]:
    """Proporcional por candidato × mês; arredondamento pelo maior resto; semente fixa."""
    estratos = defaultdict(list)
    for v in vids:
        estratos[(v["cid"], v["publicado_em"][:7])].append(v)
    total = len(vids)
    quotas = {k: n * len(lst) / total for k, lst in estratos.items()}
    base = {k: int(q) for k, q in quotas.items()}
    falta = n - sum(base.values())
    for k in sorted(quotas, key=lambda k: (-(quotas[k] - base[k]), k))[:falta]:
        base[k] += 1
    rng = random.Random(semente)
    out = []
    for k in sorted(estratos):
        lst = sorted(estratos[k], key=lambda v: v["video_id"])
        out += rng.sample(lst, min(base[k], len(lst)))
    return sorted(out, key=lambda v: (v["cid"], v["publicado_em"]))


def main(argv=None) -> int:
    root, plat = pl.args(argv)
    cfg = json.loads((root / "data/config/temas_youtube.json").read_text(encoding="utf-8"))
    livro = json.loads((root / "data/config/livro_codigos_populismo.json").read_text(encoding="utf-8"))
    regs = compilar(livro)
    rows = pl.videos(root, plat)
    padrao = bc.texto_padrao(rows)
    coleta = max((r["coletado_em"] for r in rows), default=None)
    vids = []
    for cid, cand in cfg["candidatos"].items():
        meus = [r for r in rows if r["candidate_id"] == cid and r.get("publicado_em")]
        canais = sorted({r["canal"] for r in meus}, key=len, reverse=True)
        tira = re.compile("|".join(re.escape(c) for c in canais) or "(?!)", re.I)
        for r in meus:
            texto = re.sub(r"\s+", " ", tira.sub(" ", bc.texto_util(r, padrao))).strip()
            pre = precodificar(texto, regs)
            vids.append({"cid": cid, "cand": cand["nome"], "video_id": r["video_id"], "canal": r["canal"],
                         "publicado_em": r["publicado_em"], "titulo": r["titulo"], "texto": texto,
                         "duracao": r["duracao"], "visualizacoes": int(r["visualizacoes"] or 0), "pre": pre})
    vids.sort(key=lambda v: (v["cid"], v["publicado_em"], v["video_id"]))

    # 1) agregados da pré-codificação
    cats = list(livro["categorias"])
    out = {"schema_version": 1, "gerado_em_utc": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
           "coletado_em_utc": coleta, "livro": livro["versao"],
           "aviso": "PRÉ-CODIFICAÇÃO AUTOMÁTICA por indicadores do livro de códigos. É sugestão para a codificação humana, não resultado validado: a precisão de cada categoria só será conhecida depois da amostra codificada por duas pessoas (kappa).",
           "categorias": {k: {"nome": c["nome"], "definicao": c["definicao"], "fonte": c["fonte"]} for k, c in livro["categorias"].items()},
           "candidatos": {}}
    for cid, cand in cfg["candidatos"].items():
        vs = [v for v in vids if v["cid"] == cid]
        por = Counter(c for v in vs for c in v["pre"])
        sem = defaultdict(Counter)
        for v in vs:
            s = semana(v["publicado_em"])
            sem[s]["_total"] += 1
            sem[s].update(v["pre"].keys())
        exemplos = {}
        for c in cats:
            cand_vs = sorted((v for v in vs if c in v["pre"]), key=lambda v: -v["visualizacoes"])[:3]
            exemplos[c] = [{"video_id": v["video_id"], "titulo": v["titulo"], "trecho": v["pre"][c]} for v in cand_vs]
        out["candidatos"][cid] = {"nome": cand["nome"], "videos": len(vs),
                                  "com_alguma": sum(1 for v in vs if v["pre"]),
                                  "por_categoria": {c: por.get(c, 0) for c in cats},
                                  "por_semana": {str(s): dict(sem[s]) for s in sorted(sem)},
                                  "exemplos": exemplos}
    out["plataforma"] = plat
    pl.caminho(root, plat, "populismo").write_text(json.dumps(out, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")

    # 2) corpus IRaMuTeQ e segmentos para a CHD
    cdir = root / "data/corpus"
    cdir.mkdir(parents=True, exist_ok=True)
    nseg = 0
    with open(pl.caminho(root, plat, "corpus"), "w", encoding="utf-8", newline="\n") as f, \
         open(pl.caminho(root, plat, "segmentos"), "w", encoding="utf-8", newline="") as g:
        w = csv.writer(g, lineterminator="\n")
        w.writerow(["seg_id", "video_id", "cand", "semana", "formato", "texto"])
        for v in vids:
            texto = limpar_iramuteq(v["texto"])
            if len(texto.split()) < 3:
                continue
            cab = (f"**** *plat_{plat} *cand_{var(v['cand'].split()[0])} *mes_{v['publicado_em'][5:7]} *sem_{semana(v['publicado_em']):02d}"
                   f" *formato_{formato(v['duracao'])} *canal_{var(v['canal'])[:20]}"
                   + "".join(f" *pop_{c[:10]}_{int(c in v['pre'])}" for c in cats))
            f.write(cab + "\n" + texto + "\n")
            for i, s in enumerate(segmentos(texto)):
                w.writerow([f"{v['video_id']}_{i}", v["video_id"], var(v["cand"].split()[0]), semana(v["publicado_em"]),
                            formato(v["duracao"]), s])
                nseg += 1

    # 3) amostra para a codificação humana (gerada uma única vez)
    kdir = root / "data/codificacao"
    kdir.mkdir(parents=True, exist_ok=True)
    amostra_p = pl.caminho(root, plat, "amostra")
    if not amostra_p.exists():
        amostra = amostra_estratificada(vids, livro["amostra_humana"]["tamanho"])
        with open(amostra_p, "w", encoding="utf-8-sig", newline="") as f:
            w = csv.writer(f, delimiter=";", lineterminator="\n")
            w.writerow(["video_id", "url", "candidato", "publicado_em", "titulo", "texto_util", "codificador"]
                       + cats + ["instituicoes_direcao", "observacao"])
            for v in amostra:
                w.writerow([v["video_id"], f"https://www.youtube.com/watch?v={v['video_id']}", v["cand"], v["publicado_em"][:10],
                            v["titulo"], v["texto"][:1500], ""] + [""] * len(cats) + ["", ""])
        with open(amostra_p.with_name(amostra_p.stem + "_precodificacao.csv"), "w", encoding="utf-8-sig", newline="") as f:
            w = csv.writer(f, delimiter=";", lineterminator="\n")
            w.writerow(["video_id"] + cats)
            for v in amostra:
                w.writerow([v["video_id"]] + [int(c in v["pre"]) for c in cats])
    print(f"populismo [{plat}]: {len(vids)} vídeos; " + "; ".join(
        f"{c['nome']}: {c['com_alguma']} com alguma categoria {c['por_categoria']}" for c in out["candidatos"].values())
        + f" | corpus: {nseg} segmentos")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
