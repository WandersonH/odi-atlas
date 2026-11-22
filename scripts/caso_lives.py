#!/usr/bin/env python3
"""Caso 039: "Nova forma de se comunicar" — as lives de Lula com André Janones no canal oficial de Lula no YouTube.

Pedido do responsável (21/11/2026, 12h27): "preciso de uma nova coleta de caso de YouTube: Presidente Lula e Janones falam com o
Exército; canal oficial dele e todos os vídeos [do] canal e comentários; foi uma live"; nome do caso: "nova forma de se comunicar".

Este script NÃO chama a API. Ele lê o que as coletas diárias do Atlas já guardam:
  - público: data/youtube/conteudo.json — todos os vídeos dos canais de Lula declarados ao TSE desde 20/07/2026, com
    visualizações, curtidas e a contagem de comentários informada pelo YouTube (o universo);
  - privado ($ODI_INTERNO_DIR/youtube/comentarios/comentarios.csv.gz) — os comentários lidos pela coleta "Comentários YouTube".
Saídas:
  - público data/casos/039/lives.json: só contagens (nenhum texto, nenhum autor);
  - privado casos/039/youtube_comentarios.csv.gz: os comentários das lives (texto e autor), para emojis, Iramuteq e área do pesquisador.
Medidas:
  1. cada live: visualizações, curtidas, comentários informados (universo) × lidos (amostra), autores;
  2. a live no canal: posição entre todos os vídeos do canal e comparação com a mediana dos demais;
  3. público novo: de quem comentou na live, quantos já tinham comentado ANTES dela nos canais de Lula, de Flávio, nos dois ou em
     nenhum (acervo do Atlas, só canais das campanhas; indício de público, não prova de voto);
  4. retorno: autores em comum entre as lives.
Live sem comentário lido aparece como ⛔ (nunca zero).
Uso: ODI_INTERNO_DIR=… python scripts/caso_lives.py
"""
from __future__ import annotations

import csv
import gzip
import json
import os
import statistics
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

csv.field_size_limit(10**9)
CASO = "039"
LULA, FLAVIO = "280002542548", "280002551544"
CAMPOS = ["comment_id", "parent_id", "tipo", "video_id", "candidate_id", "channel_id", "ordem", "autor_canal", "autor_nome", "texto",
          "curtidas", "respostas", "publicado_em", "atualizado_em", "coletado_em"]


def agora() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def cfg_caso(caminho: str = "data/config/casos.json") -> dict:
    d = json.load(open(caminho, encoding="utf-8"))
    return next(c for c in d["casos"] if c["id"] == CASO)


def inteiro(v) -> int | None:
    try:
        return int(v)
    except (TypeError, ValueError):
        return None


def pct(a, b, casas=1):
    return round(100 * a / b, casas) if b else None


def canal_publico(conteudo: dict, ids_lives: list[str]) -> tuple[list[dict], dict]:
    """Vídeos do canal (público) e o resumo de comparação lives × demais vídeos."""
    vs = conteudo["candidatos"][LULA]["videos"]
    por_id = {v["video_id"]: v for v in vs}
    outros = [v for v in vs if v["video_id"] not in ids_lives]
    ordem = {k: [v["video_id"] for v in sorted(vs, key=lambda v: -(inteiro(v.get(k)) or 0))] for k in ("visualizacoes", "comentarios")}

    def med(k):
        xs = [inteiro(v.get(k)) for v in outros if inteiro(v.get(k)) is not None]
        return int(statistics.median(xs)) if xs else None

    lives = []
    for i in ids_lives:
        v = por_id.get(i)
        if not v:
            lives.append({"id": i, "url": f"https://www.youtube.com/watch?v={i}", "no_canal": False,
                          "situacao": "⛔ vídeo ainda não apareceu na coleta de vídeos do canal"})
            continue
        lives.append({"id": i, "url": f"https://www.youtube.com/watch?v={i}", "no_canal": True, "titulo": v["titulo"], "canal": v.get("canal"),
                      "publicado_em": v["publicado_em"], "duracao": v.get("duracao"), "visualizacoes": inteiro(v.get("visualizacoes")),
                      "curtidas": inteiro(v.get("curtidas")), "comentarios_informados": inteiro(v.get("comentarios")),
                      "posicao_visualizacoes": ordem["visualizacoes"].index(i) + 1, "posicao_comentarios": ordem["comentarios"].index(i) + 1})
    resumo = {"videos_no_canal": len(vs), "desde": min(v["publicado_em"] for v in vs)[:10], "ate": max(v["publicado_em"] for v in vs)[:10],
              "mediana_visualizacoes_demais": med("visualizacoes"), "mediana_comentarios_demais": med("comentarios"),
              "soma_visualizacoes_canal": sum(inteiro(v.get("visualizacoes")) or 0 for v in vs),
              "soma_visualizacoes_lives": sum(x.get("visualizacoes") or 0 for x in lives),
              "soma_comentarios_canal": sum(inteiro(v.get("comentarios")) or 0 for v in vs),
              "soma_comentarios_lives": sum(x.get("comentarios_informados") or 0 for x in lives),
              "mais_vistos": [{"id": i, "titulo": por_id[i]["titulo"], "publicado_em": por_id[i]["publicado_em"][:10],
                               "visualizacoes": inteiro(por_id[i].get("visualizacoes")), "comentarios": inteiro(por_id[i].get("comentarios")),
                               "live_do_caso": i in ids_lives} for i in ordem["visualizacoes"][:10]]}
    return lives, resumo


def ler_acervo(interno: Path, ids_lives: set[str]):
    """Uma passada no acervo: linhas das lives e, por autor, a primeira data em que comentou em cada lado (fora das lives)."""
    f = interno / "youtube" / "comentarios" / "comentarios.csv.gz"
    linhas, primeiro = defaultdict(list), {LULA: {}, FLAVIO: {}}
    total = 0
    with gzip.open(f, "rt", encoding="utf-8", errors="ignore") as h:
        for r in csv.DictReader(h, delimiter=";"):
            total += 1
            a, v, t = r.get("autor_canal") or "", r.get("video_id"), r.get("publicado_em") or ""
            if v in ids_lives:
                linhas[v].append(r)
            if a and r.get("candidate_id") in primeiro and v not in ids_lives:
                p = primeiro[r["candidate_id"]]
                if a not in p or t < p[a]:
                    p[a] = t
    return linhas, primeiro, total


def analisar(lives: list[dict], linhas: dict, primeiro: dict) -> dict:
    autores = {}
    for x in lives:
        rs = linhas.get(x["id"], [])
        x["comentarios_lidos"] = len(rs)
        if not rs:
            x["situacao"] = x.get("situacao") or "⛔ nenhum comentário lido ainda (coleta de comentários do YouTube parada)"
            x["pct_lido"] = None
            continue
        aut = {r["autor_canal"] for r in rs if r.get("autor_canal")}
        autores[x["id"]] = aut
        marco = x.get("publicado_em") or ""
        lado = Counter()
        for a in aut:
            l, f = primeiro[LULA].get(a), primeiro[FLAVIO].get(a)
            l, f = bool(l and l < marco), bool(f and f < marco)
            lado["ambos" if l and f else "lula" if l else "flavio" if f else "nenhum"] += 1
        dias = Counter((r.get("publicado_em") or "")[:10] for r in rs)
        inf = x.get("comentarios_informados")
        if inf is not None and len(rs) > inf:  # a contagem do YouTube foi lida antes dos comentários (vídeo recente ainda crescendo)
            x["nota"] = "mais comentários lidos do que a contagem informada: a contagem do YouTube é de uma leitura anterior à dos comentários; % não calculado"
        x.update({"pct_lido": None if inf is not None and len(rs) > inf else pct(len(rs), inf), "autores": len(aut),
                  "respostas_lidas": sum(1 for r in rs if r.get("parent_id")),
                  "primeiro_comentario_lido": min(r["publicado_em"] for r in rs if r.get("publicado_em")),
                  "ultimo_comentario_lido": max(r["publicado_em"] for r in rs if r.get("publicado_em")),
                  "lido_ate": max((r.get("coletado_em") or "") for r in rs) or None,
                  "comentarios_no_dia_da_live": dias.get(marco[:10], 0),
                  "publico": {k: lado.get(k, 0) for k in ("lula", "ambos", "flavio", "nenhum")},
                  "publico_pct": {k: pct(lado.get(k, 0), len(aut)) for k in ("lula", "ambos", "flavio", "nenhum")}})
    ids = [x["id"] for x in lives if x["id"] in autores]
    retorno = [{"a": a, "b": b, "em_comum": len(autores[a] & autores[b]), "pct_de_a": pct(len(autores[a] & autores[b]), len(autores[a])),
                "pct_de_b": pct(len(autores[a] & autores[b]), len(autores[b]))} for i, a in enumerate(ids) for b in ids[i + 1:]]
    todos = set().union(*autores.values()) if autores else set()
    vezes = Counter(n for n in Counter(a for s in autores.values() for a in s).values())
    return {"retorno": retorno, "autores_distintos": len(todos), "autores_por_numero_de_lives": {str(k): v for k, v in sorted(vezes.items())}}


def main(argv=None) -> int:
    cfg = cfg_caso()
    ids = cfg["videos_youtube"]
    conteudo = json.load(open("data/youtube/conteudo.json", encoding="utf-8"))
    lives, canal = canal_publico(conteudo, ids)
    interno = Path(os.environ.get("ODI_INTERNO_DIR", ""))
    acervo = interno / "youtube" / "comentarios" / "comentarios.csv.gz"
    pub = Path("data/casos") / CASO
    pub.mkdir(parents=True, exist_ok=True)
    erros, extra, total_acervo = [], {"retorno": [], "autores_distintos": None, "autores_por_numero_de_lives": {}}, None
    if os.environ.get("ODI_INTERNO_DIR") and acervo.exists():
        linhas, primeiro, total_acervo = ler_acervo(interno, set(ids))
        extra = analisar(lives, linhas, primeiro)
        priv = interno / "casos" / CASO
        priv.mkdir(parents=True, exist_ok=True)
        with gzip.open(priv / "youtube_comentarios.csv.gz", "wt", encoding="utf-8", newline="") as h:
            w = csv.DictWriter(h, fieldnames=CAMPOS, delimiter=";", extrasaction="ignore")
            w.writeheader()
            for i in ids:
                w.writerows(linhas.get(i, []))
    else:
        erros.append("⛔ sem repositório privado: comentários não lidos nesta execução")
        ant = pub / "lives.json"
        if ant.exists():  # não trocar análise real por vazio: mantém a anterior e só atualiza os números públicos
            velho = json.load(open(ant, encoding="utf-8"))
            vp = {x["id"]: x for x in velho.get("lives", [])}
            for x in lives:
                for k, v in vp.get(x["id"], {}).items():
                    x.setdefault(k, v)
            extra = {k: velho.get(k) for k in extra}
            total_acervo = velho.get("acervo_comentarios")
        else:
            for x in lives:
                x.update({"comentarios_lidos": None, "pct_lido": None, "situacao": "⛔ comentários não lidos (sem repositório privado)"})
    # universo e amostra somam só as lives em que a contagem informada é igual ou posterior à leitura (lidos ≤ informados)
    comparaveis = [x for x in lives if not x.get("nota")]
    uni_c = sum(x.get("comentarios_informados") or 0 for x in comparaveis)
    lidos = sum(x.get("comentarios_lidos") or 0 for x in comparaveis)
    fora = len(lives) - len(comparaveis)
    out = {"caso": CASO, "gerado_em_utc": agora(), "videos_lidos_em_utc": conteudo.get("coletado_em_utc"), "lives": lives, "canal": canal,
           **extra, "acervo_comentarios": total_acervo,
           "universo": [
               {"conjunto": "Comentários das lives" + (f" ({len(comparaveis)} de {len(lives)}; a mais recente fica fora: contagem do YouTube anterior à leitura)" if fora else ""),
                "videos": len(comparaveis), "universo": uni_c or None,
                "fonte_universo": "contagem de comentários informada pelo YouTube em cada vídeo (inclui respostas)", "amostra": lidos,
                "pct": pct(lidos, uni_c), "criterio": "o que a coleta diária de comentários do YouTube já leu de cada live (API oficial)"},
               {"conjunto": "Vídeos do canal", "videos": canal["videos_no_canal"], "universo": None,
                "fonte_universo": "⛔ o total de vídeos do canal não está no arquivo de vídeos; a lista cobre os envios desde 20/07/2026",
                "amostra": canal["videos_no_canal"], "pct": None, "criterio": "todos os envios dos canais de Lula declarados ao TSE desde 20/07/2026"},
               {"conjunto": "Acervo do Atlas (público anterior)", "videos": None, "universo": None,
                "fonte_universo": "⛔ não há universo: o acervo cobre só comentários nos canais das campanhas", "amostra": total_acervo, "pct": None,
                "criterio": "autor conta como público anterior de um lado se comentou naquele lado antes da data da live"}],
           "nota": "Percentuais valem para os comentários lidos. 'Público anterior' usa só o acervo do Atlas (canais das campanhas): é indício "
                   "de público, não prova de voto. Quem aparece em 'nenhum' não tinha comentário anterior no acervo.",
           "erros": erros}
    (pub / "lives.json").write_text(json.dumps(out, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    for x in lives:
        print(f"{x['id']} · {x.get('titulo', '—')[:50]} · informados {x.get('comentarios_informados')} · lidos {x.get('comentarios_lidos')} · {x.get('situacao', 'ok')}")
    for e in erros:
        print(e)
    return 0


if __name__ == "__main__":
    sys.exit(main())
