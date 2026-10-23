#!/usr/bin/env python3
"""Caderno 04 — o que a audiência diz nos comentários do YouTube, por candidato. Só AGREGADOS vão para o público.

Entrada: arquivo bruto de collect_comentarios_youtube.py (privado ou temporário), data/youtube/conteudo.json (temas
de cada vídeo), data/config/temas_youtube.json, livros de códigos de populismo e de intolerância.
Saída pública: data/youtube/comentarios/analise.json — contagens, termos, percentuais por categoria, classes da CHD
(só formas, sem trechos), série diária. Nenhum texto de comentário, nome ou canal de autor.
Saída privada (só com ODI_INTERNO_DIR): amostra para codificação humana (uma vez, nunca sobrescrita), pré-codificação
da amostra, corpus IRaMuTeQ e trechos característicos de cada classe da CHD.

Uso: python scripts/build_comentarios.py [caminho/comentarios.csv.gz]
"""
from __future__ import annotations

import csv
import datetime as dt
import gzip
import json
import os
import random
import re
import statistics
import sys
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import build_conteudo as bc  # noqa: E402
import chd_reinert as chd  # noqa: E402
import corpus_populismo as cp  # noqa: E402
from collect_comentarios_youtube import destino, plataforma  # noqa: E402

DESDE = "2026-07-20"  # pré-campanha
SEMENTE = 42
MIN_REPETIDO_AUTORES = 3
MIN_REPETIDO_CHARS = 25
CHD_AMOSTRA = 4000
CHD_MIN_TOKENS = 8
CHD_MIN_FREQ = 15
RISO = re.compile(r"\b(?:k{3,}|(?:ha){2,}|(?:rs){2,}|kk)\b", re.I)
EXCLUIR = set(bc.norm("vc voce voces q ta tá ne né tb tbm pq porque ai aí ja já so só sim nao não ate até la lá ser ter vai vou "
                      "faz fazer tem ter esta está isso esse essa aqui agora hoje ainda nunca sempre tudo todo toda todos "
                      "kkk kkkk kkkkk kkkkkk").split())
INTOLERANCIA = ["desumanizacao", "odio_genero", "odio_lgbt", "odio_raca_origem", "odio_religiao", "ameaca_violencia"]
INCIVILIDADE = ["incivilidade", "rotulo_pejorativo_politico"]


ARROBA = re.compile(r"(?<![\w.])@[A-Za-z0-9_.]{2,30}")


def limpo(t: str) -> str:
    """Sem links, risadas e @perfis: quem comenta costuma marcar outras pessoas, e o @ não pode virar termo publicado
    (nuvem, rede de palavras, CHD) — perfil de pessoa comum não aparece no público (23/10/2026)."""
    return RISO.sub(" ", ARROBA.sub(" ", bc.URL.sub(" ", t or ""))).strip()


def chave_texto(t: str) -> str:
    return " ".join(bc.norm(t).split())


def repetidos(rows: list[dict]) -> tuple[set[str], int]:
    """Textos (≥ MIN_REPETIDO_CHARS) publicados por MIN_REPETIDO_AUTORES+ autores diferentes: 'copiar e colar'.
    Devolve os comment_id marcados e o número de textos distintos."""
    autores = defaultdict(set)
    for r in rows:
        k = chave_texto(r["texto"])
        if len(k) >= MIN_REPETIDO_CHARS:
            autores[k].add(r["autor_canal"] or r["autor_nome"])
    rep = {k for k, a in autores.items() if len(a) >= MIN_REPETIDO_AUTORES}
    return {r["comment_id"] for r in rows if chave_texto(r["texto"]) in rep}, len(rep)


def concentracao(rows: list[dict]) -> dict:
    por = Counter(r["autor_canal"] or r["autor_nome"] for r in rows)
    n = sum(por.values())
    if not n:
        return {}
    vals = sorted(por.values(), reverse=True)
    top = lambda f: round(100 * sum(vals[:max(1, int(len(vals) * f))]) / n, 1)  # noqa: E731
    return {"autores_unicos": len(vals), "comentarios_por_autor_mediana": statistics.median(vals),
            "pct_dos_comentarios_top1pct_autores": top(0.01), "pct_dos_comentarios_top10pct_autores": top(0.10),
            "max_comentarios_de_um_autor": vals[0]}


def codificar(textos: list[str], regs: dict) -> list[set[str]]:
    return [set(cp.precodificar(t, regs)) for t in textos]


def pct(n, d):
    return round(100 * n / d, 2) if d else None


def chd_candidato(textos: list[str], ids: list[str], semente: int = SEMENTE) -> tuple[dict, list[dict]]:
    """CHD de Reinert sobre uma amostra de comentários longos. Devolve (público: classes e formas; privado: trechos)."""
    idx = [i for i, t in enumerate(textos) if len(chd.tokens(t)) >= CHD_MIN_TOKENS]
    random.Random(semente).shuffle(idx)
    idx = sorted(idx[:CHD_AMOSTRA])
    if len(idx) < 200:
        return {"status": f"⛔ só {len(idx)} comentários com {CHD_MIN_TOKENS}+ palavras"}, []
    segs = [textos[i] for i in idx]
    X, voc = chd.matriz(segs, min_freq=CHD_MIN_FREQ)
    X = X.astype(np.float32)
    ativos = int((X.sum(1) > 0).sum())
    mc = max(chd.MIN_CLASSE, int(chd.MIN_CLASSE_PCT * ativos))
    rot, _ = chd.chd(X, min_classe=mc)
    cl = rot > 0
    n = int(cl.sum())
    tot = X[cl].sum(0)
    classes, privados = [], []
    for k in sorted(set(rot[cl].tolist())):
        m = rot == k
        nk = int(m.sum())
        ch = chd.chi2_assoc(X[m].sum(0), tot, nk, n)
        top = [j for j in np.argsort(-ch)[:20] if ch[j] >= chd.CHI_CRIT]
        classes.append({"classe": int(k), "comentarios": nk, "pct": round(100 * nk / n, 1),
                        "formas": [[voc[j], round(float(ch[j]), 1)] for j in top], "nome": None})
        peso = {j: ch[j] for j in range(len(voc)) if ch[j] > 0}
        sc = sorted(((sum(peso.get(j, 0) for j in np.nonzero(X[i])[0]), i) for i in np.where(m)[0]), reverse=True)[:8]
        privados += [{"classe": int(k), "comment_id": ids[idx[i]], "texto": segs[i][:400], "score": round(float(s), 1)} for s, i in sc]
    return {"amostra": len(idx), "classificados": n, "pct_classificados": round(100 * n / len(idx), 1),
            "formas_ativas": len(voc), "min_classe": mc, "classes": classes}, privados


def amostra_humana(rows: list[dict], n: int, semente: int = SEMENTE) -> list[dict]:
    """Estratificada por semana (proporcional), semente fixa."""
    por = defaultdict(list)
    for r in rows:
        por[cp.semana(r["publicado_em"])].append(r)
    rnd = random.Random(semente)
    total = len(rows)
    out = []
    for s in sorted(por):
        g = sorted(por[s], key=lambda r: r["comment_id"])
        k = max(1, round(n * len(g) / total))
        out += rnd.sample(g, min(k, len(g)))
    return sorted(out, key=lambda r: r["comment_id"])[:n]


def main(argv=None) -> int:
    root = Path(".")
    plat, argv = plataforma(argv)
    dest, modo = destino(plat)
    bruto = Path(argv[0]) if argv else dest / "comentarios.csv.gz"
    pub = root / f"data/{plat}/comentarios"
    pub.mkdir(parents=True, exist_ok=True)
    if not bruto.exists():
        print(f"⛔ sem arquivo bruto de comentários ({bruto})")
        return 1
    rows = [r for r in csv.DictReader(gzip.open(bruto, "rt", encoding="utf-8"), delimiter=";") if (r["publicado_em"][:10] or DESDE) >= DESDE]
    cfg = json.loads((root / "data/config/temas_youtube.json").read_text(encoding="utf-8"))
    temas, cands = bc.compile_cfg(cfg)
    pop = json.loads((root / "data/config/livro_codigos_populismo.json").read_text(encoding="utf-8"))
    intol = json.loads((root / "data/config/livro_codigos_intolerancia.json").read_text(encoding="utf-8"))
    r_pop, r_int = cp.compilar(pop), cp.compilar(intol)
    conteudo = json.loads((root / f"data/{plat}/conteudo.json").read_text(encoding="utf-8"))
    tema_video = {v["video_id"]: set(v["temas"]) - {"sem_tema"} for c in conteudo["candidatos"].values() for v in c["videos"]}
    out = {"schema_version": 1, "gerado_em_utc": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
           "coletado_em_utc": max((r["coletado_em"] for r in rows), default=None), "modo": modo,
           "plataforma": plat,
           "metodo": (("Comentários públicos dos vídeos do Kwai das campanhas desde 20/07/2026, via Apify (zen-studio/kwai-comments-scraper): "
                       "até 50 comentários por vídeo, na ordem que o Kwai entrega, sem respostas. Não é o universo de " if plat == "kwai" else
                       "Comentários públicos dos posts das páginas de Facebook das campanhas desde 20/07/2026, via Apify "
                       "(dami_studio/facebook-comments-scraper): cota igual por candidato, de 5 a 50 por post, por relevância, sem respostas. "
                       "Não é o universo de " if plat == "facebook" else
                       "Comentários públicos dos posts dos perfis principais de Instagram das campanhas (@lulaoficial e @flaviobolsonaro) desde "
                       "16/08/2026, via Apify (datadoping/instagram-comments-and-replies-scraper): cota igual por candidato (3.000), de 5 a 50 por "
                       "post a partir dos posts com mais comentários, ordem 'populares' do Instagram; em 23/10, respostas aos 5 comentários mais populares dos 40 posts com mais respostas (até 6 cada) e as prévias de respostas que vieram na coleta. Não é o universo de " if plat == "instagram" else
                       "Comentários públicos dos vídeos de TikTok das campanhas (perfis declarados ao TSE e o do vice indicado pelo responsável) desde "
                       "16/08/2026, via Apify (clockworks/tiktok-comments-scraper): cota igual por candidato (3.000), de 5 a 50 por vídeo a partir "
                       "dos vídeos com mais comentários, sem respostas; depois, 30 por vídeo novo a cada dia. Não é o universo de " if plat == "tiktok" else
                       "Comentários públicos dos vídeos das campanhas desde 20/07/2026, pela API oficial: até 100 conversas por "
                       "relevância e 100 mais recentes por vídeo, com as respostas que a API devolve junto. Não é o universo de ") +
                      "comentários nem amostra do eleitorado. Pré-codificação por dicionário (livros de códigos de populismo e de "
                      "intolerância/incivilidade): indica candidatos a cada categoria; a validação é humana (kappa). "
                      f"'Copiar e colar' = mesmo texto ({MIN_REPETIDO_CHARS}+ caracteres) publicado por {MIN_REPETIDO_AUTORES}+ "
                      "autores diferentes. CHD de Reinert sobre amostra aleatória (semente 42) de comentários com "
                      f"{CHD_MIN_TOKENS}+ palavras; formas com {CHD_MIN_FREQ}+ ocorrências. Nada de texto, nome ou canal de "
                      "autor é publicado: só contagens, termos e percentuais."),
           "livros": {"populismo": {k: c["nome"] for k, c in pop["categorias"].items()},
                      "intolerancia": {k: {"nome": c["nome"], "definicao": c["definicao"]} for k, c in intol["categorias"].items()},
                      "grupos": {"intolerancia": INTOLERANCIA, "incivilidade": INCIVILIDADE}},
           "temas": list(cfg["temas"]), "candidatos": {}}
    privado = {"chd": {}, "amostras": {}}
    for cid, cand in cands.items():
        meus = [r for r in rows if r["candidate_id"] == cid]
        if not meus:
            out["candidatos"][cid] = {"nome": cand["nome"], "comentarios": 0}
            continue
        marcados, n_rep = repetidos(meus)
        textos = [limpo(r["texto"]) for r in meus]
        com_texto = [i for i, t in enumerate(textos) if len(bc.norm(t).split()) >= 2]
        tx = [textos[i] for i in com_texto]
        rr = [meus[i] for i in com_texto]
        c_int, c_pop = codificar(tx, r_int), codificar(tx, r_pop)
        cls = [bc.classify(t, temas, cand) for t in tx]
        n = len(tx)
        intol_any = [bool(s & set(INTOLERANCIA)) for s in c_int]
        incv_any = [bool(s & set(INCIVILIDADE)) for s in c_int]
        curt = [int(r["curtidas"] or 0) for r in rr]
        # tema do vídeo × tema do comentário: dos comentários em vídeos sobre T, quantos falam de T
        ader = {}
        for t in cfg["temas"]:
            em = [i for i, r in enumerate(rr) if t in tema_video.get(r["video_id"], set())]
            if len(em) >= 30:
                outros = Counter(x for i in em for x in cls[i]["temas"] if x != "sem_tema")
                ader[t] = {"comentarios": len(em), "pct_falam_do_tema": pct(sum(t in cls[i]["temas"] for i in em), len(em)),
                           "pct_sem_tema": pct(sum(cls[i]["temas"] == ["sem_tema"] for i in em), len(em)),
                           "outros_temas": [[k, pct(v, len(em))] for k, v in outros.most_common(4) if k != t]}
        dia = defaultdict(lambda: [0, 0, 0])
        for i, r in enumerate(rr):
            d = dia[r["publicado_em"][:10]]
            d[0] += 1
            d[1] += incv_any[i]
            d[2] += intol_any[i]
        pub_chd, priv_chd = chd_candidato(tx, [r["comment_id"] for r in rr])
        out["candidatos"][cid] = {
            "nome": cand["nome"], "comentarios": sum(r["tipo"] == "comentario" for r in meus),
            "respostas": sum(r["tipo"] == "resposta" for r in meus), "videos": len({r["video_id"] for r in meus}),
            "com_texto_analisavel": n, "so_emoji_link_ou_mencao": len(meus) - n,
            "autores": concentracao(meus),
            "copiar_colar": {"comentarios": len(marcados), "pct": pct(len(marcados), len(meus)), "textos_distintos": n_rep},
            "nuvem": bc.nuvem(tx, EXCLUIR, top=80, minimo=max(10, n // 500)),
            "temas_nos_comentarios": {t: pct(sum(t in c["temas"] for c in cls), n) for t in list(cfg["temas"]) + ["sem_tema"]},
            "cita_adversario_pct": pct(sum(c["cita_adversario"] for c in cls), n),
            "aderencia_ao_tema_do_video": ader,
            "populismo_pct": {k: pct(sum(k in s for s in c_pop), n) for k in pop["categorias"]},
            "intolerancia_pct": {k: pct(sum(k in s for s in c_int), n) for k in intol["categorias"]},
            "qualquer_intolerancia_pct": pct(sum(intol_any), n), "qualquer_incivilidade_pct": pct(sum(incv_any), n),
            "curtidas_medias": {"incivis": round(statistics.mean([c for c, f in zip(curt, incv_any) if f]), 1) if any(incv_any) else None,
                                "civis": round(statistics.mean([c for c, f in zip(curt, incv_any) if not f]), 1) if not all(incv_any) else None},
            "serie_diaria": [[d, v[0], pct(v[1], v[0]), pct(v[2], v[0])] for d, v in sorted(dia.items())],
            "chd": pub_chd}
        privado["chd"][cid] = priv_chd
        privado["amostras"][cid] = (amostra_humana(rr, intol["amostra_humana"]["tamanho_por_candidato"]), c_int, c_pop, rr)
        c = out["candidatos"][cid]
        print(f"{cand['nome']}: {len(meus)} registros ({c['comentarios']} comentários, {c['respostas']} respostas) em {c['videos']} vídeos; "
              f"{c['autores'].get('autores_unicos')} autores; incivilidade {c['qualquer_incivilidade_pct']}%, intolerância "
              f"{c['qualquer_intolerancia_pct']}%; copiar-colar {c['copiar_colar']['pct']}%; CHD {len(pub_chd.get('classes', []))} classes")
    (pub / "analise.json").write_text(json.dumps(out, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    if modo == "interno":
        gravar_privado(dest, privado, cands, intol, pop, plat)
    return 0


def gravar_privado(dest: Path, privado: dict, cands: dict, intol: dict, pop: dict, plat: str = "youtube") -> None:
    """Material de pesquisa que contém texto de comentário: só no repositório privado."""
    cod = dest.parent.parent / "codificacao"
    cod.mkdir(parents=True, exist_ok=True)
    dest.mkdir(parents=True, exist_ok=True)
    (dest / "chd_trechos_caracteristicos.json").write_text(json.dumps(privado["chd"], ensure_ascii=False, indent=1), encoding="utf-8")
    cats = list(intol["categorias"]) + list(pop["categorias"])
    amostra_p = cod / "amostra_comentarios_v1.csv"
    if not amostra_p.exists():  # a amostra é sorteada uma vez e nunca refeita (os codificadores trabalham sobre ela)
        with open(amostra_p, "w", encoding="utf-8", newline="") as f, \
             open(cod / "amostra_comentarios_v1_precodificacao.csv", "w", encoding="utf-8", newline="") as g:
            w = csv.writer(f, delimiter=";", lineterminator="\n")
            wp = csv.writer(g, delimiter=";", lineterminator="\n")
            w.writerow(["comment_id", "candidato", "video_url", "tipo", "publicado_em", "texto"] + cats + ["observacao"])
            wp.writerow(["comment_id"] + cats)
            for cid, (am, c_int, c_pop, rr) in privado["amostras"].items():
                pos = {r["comment_id"]: i for i, r in enumerate(rr)}
                for r in am:
                    i = pos[r["comment_id"]]
                    w.writerow([r["comment_id"], cands[cid]["nome"], (f"https://www.kwai.com/@{r['channel_id']}/video/{r['video_id']}" if plat == "kwai" else f"https://www.instagram.com/p/{r['video_id']}/" if plat == "instagram" else f"https://www.tiktok.com/@{r['channel_id']}/video/{r['video_id']}" if plat == "tiktok" else f"https://www.facebook.com/{r['video_id']}" if plat == "facebook" else f"https://www.youtube.com/watch?v={r['video_id']}"), r["tipo"],
                                r["publicado_em"], r["texto"].replace("\n", " ")] + [""] * len(cats) + [""])
                    wp.writerow([r["comment_id"]] + [int(k in (c_int[i] | c_pop[i])) for k in cats])
    with open(dest / "corpus_iramuteq_comentarios.txt", "w", encoding="utf-8") as f:
        for cid, (_, c_int, _, rr) in privado["amostras"].items():
            nome = cp.var(cands[cid]["nome"].split()[0])
            for r, s in zip(rr, c_int):
                t = cp.limpar_iramuteq(limpo(r["texto"]))
                if len(t.split()) < 3:
                    continue
                f.write(f"**** *cand_{nome} *sem_{cp.semana(r['publicado_em'])} *tipo_{r['tipo']} "
                        f"*incv_{int(bool(s & set(INCIVILIDADE)))} *intol_{int(bool(s & set(INTOLERANCIA)))}\n{t}\n")
    print(f"privado: amostra e corpus IRaMuTeQ em {cod} e {dest}")


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
