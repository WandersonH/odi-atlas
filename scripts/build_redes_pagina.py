#!/usr/bin/env python3
"""Tipo e métricas de cada rede, para a página do Atlas (bloco "Redes do caso").

Pedido do responsável (07/11/2026, 21h48): "queria que as métricas e o tipo de rede fossem informados em algum lugar no ODI".
Entradas (todas públicas): data/redes/estatisticas_redes.csv (Python, todas as redes), data/redes/gephi/gephi_resumo.csv
(Gephi Toolkit, as redes já desenhadas), data/redes/rede_candidatos_resumo.csv e os arquivos em data/casos/<id>/*.gexf.
Saída: data/redes/redes_pagina.json — por caso, uma linha por rede com o tipo (o que é nó, aresta e para que serve), as
métricas e os links (GEXF, prints do ForceAtlas 2, OpenOrd e lado a lado, pontes). Universo: as redes são da amostra lida.
"""
from __future__ import annotations

import csv
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from net import now_utc  # noqa: E402

TIPOS = {
    "rede": ("Contas × hashtags e menções", "conta (X, TikTok, Instagram, Facebook) e hashtag ou @ citado", "a conta usou a hashtag ou citou o @; peso = nº de posts", "quem se agrupa em torno de quais marcadores"),
    "rede_circulacao": ("Circulação", "fonte (canal do YouTube, veículo, conta do TikTok) e termo de busca", "a fonte apareceu na busca do termo; peso = visualizações (YouTube, TikTok) ou 1 (notícia)", "por onde o tema circula e com que audiência"),
    "rede_respostas_comentarios": ("Respostas nos comentários do YouTube", "autor de comentário (código)", "A respondeu no fio aberto por B; peso = nº de respostas", "quem conversa com quem; sem reciprocidade na API do YouTube"),
    "rede_palavras_comentarios": ("Palavras dos comentários do YouTube", "palavra", "duas palavras no mesmo comentário (3+ comentários)", "temas e enquadramentos"),
    "rede_respostas_comentarios_posts": ("Respostas nos comentários das redes sociais", "autor de comentário (código)", "A respondeu a B; peso = nº de respostas", "quem conversa com quem no X, Instagram e TikTok"),
    "rede_candidatos": ("Influência dos candidatos", "candidato (conta declarada ao TSE) e conta que cita o @", "a conta citou o @ do candidato num post do caso; peso = citações", "quem puxa cada candidato para a conversa"),
    "rede_palavras_comentarios_posts": ("Palavras dos comentários das redes sociais", "palavra", "duas palavras no mesmo comentário (3+ comentários)", "temas e enquadramentos no X, Instagram e TikTok"),
}
CAMPOS = ["nos", "arestas", "dirigida", "densidade", "grau_medio", "componentes", "nos_maior_componente", "pct_nos_maior_componente",
          "gc_densidade", "modularidade_q", "gc_modularidade_q", "gc_comunidades_1pct_ou_mais", "gc_pct_maior", "gc_pct_segunda",
          "gc_polarizacao_ei_2_maiores", "assortatividade_grau", "reciprocidade", "clustering_medio", "diametro_maior_componente",
          "caminho_medio_maior_componente", "calculado_em_utc"]


def ler(p: str) -> list[dict]:
    return list(csv.DictReader(open(p, encoding="utf-8"))) if os.path.exists(p) else []


def tipo_de(rede: str) -> tuple:
    if rede.startswith("rede_video_"):
        return ("Respostas e menções de um vídeo", "autor de comentário (código)", "resposta ao fio ou @ citado; tipo gravado na aresta", "recorte pequeno: perfil muito mencionado × grupo que se menciona")
    return TIPOS.get(rede, (rede.replace("rede_", "").replace("_", " ").capitalize(), "—", "—", "—"))


def main() -> int:
    est = ler("data/redes/estatisticas_redes.csv")
    gep = {(r["caso"], r["rede"]): r for r in ler("data/redes/gephi/gephi_resumo.csv")}
    casos = {}
    for r in est:
        caso, rede = r["caso"], r["rede"]
        nome, no, aresta, serve = tipo_de(rede)
        base = f"data/redes/gephi/{caso}_{rede}"
        g = gep.get((caso, rede), {})
        lin = {"rede": rede, "tipo": nome, "no": no, "aresta": aresta, "serve_para": serve, "gexf": f"data/casos/{caso}/{rede}.gexf",
               **{k: r.get(k) for k in CAMPOS if r.get(k) not in (None, "")},
               "gephi": {k: g.get(k) for k in ("gc_modularidade_q", "gc_comunidades", "separacao_openord_2_maiores", "separacao_openord_edgecut0",
                                               "estabilidade_fa2_corr_distancias_top50", "pct_arestas_cruzando", "inferencia_estatistica_classes") if g.get(k)} or None,
               "imagens": {k: f"{base}_{k}.png" for k in ("forceatlas2", "openord", "comparacao", "fruchterman", "yifanhu") if os.path.exists(f"{base}_{k}.png")},
               "pontes": f"{base}_pontes.csv" if os.path.exists(f"{base}_pontes.csv") else None}
        casos.setdefault(caso, []).append(lin)
    cand = ler("data/redes/rede_candidatos_resumo.csv")
    gc = gep.get(("redes", "rede_candidatos"), {})
    out = {"gerado_em_utc": now_utc(), "casos": casos,
           "candidatos": {"tipo": "Influência dos candidatos na circulação", "no": "candidato (conta declarada ao TSE), caso e conta que cita candidato",
                          "aresta": "candidato → caso (publicou; peso = publicações) e conta → candidato (citou o @; peso = citações)",
                          "gexf": "data/redes/rede_candidatos.gexf", "top": cand[:20], "total_candidatos": len(cand), "gephi": gc or None,
                          "imagens": {k: f"data/redes/gephi/redes_rede_candidatos_{k}.png" for k in ("forceatlas2", "openord", "comparacao")
                                      if os.path.exists(f"data/redes/gephi/redes_rede_candidatos_{k}.png")}},
           "nota": "Métricas calculadas sobre a amostra lida em cada caso (universo das plataformas ⛔ não informado). Desenho e "
                   "percentuais no componente gigante; Q da rede inteira ao lado. Método: documento \"Método de avaliação das redes do ODI Atlas\"."}
    Path("data/redes/redes_pagina.json").write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"redes_pagina: {sum(len(v) for v in casos.values())} redes em {len(casos)} casos; {len(cand)} candidatos")
    return 0


if __name__ == "__main__":
    sys.exit(main())
