#!/usr/bin/env python3
"""Caso com comentários do Instagram a partir de coletas do Apify já importadas (scripts/importar_apify_runs.py): unifica,
remove duplicados e agrega no padrão dos casos (rede de palavras e classes estilo IRaMuTeQ).

Caso 007 (pedido de 22/10/2026, 01h09): fake news "Lula amassa a bandeira no dia da eleição". As coletas de 06–07/10
(atores datadoping/instagram-comments-and-replies-scraper e apify/instagram-comment-scraper, e o apify/instagram-reel-scraper
para os números do vídeo) são do mesmo reel, publicado em 04/10/2026, dia do 1º turno. Os mesmos comentários aparecem em
várias execuções e contam uma vez (por id do comentário).

Privacidade: quem comenta nunca aparece com nome no público. O perfil que publicou o reel só aparece com nome, link e o
vídeo incorporado se tiver 10 mil seguidores ou mais, conforme a leitura em ODI_INTERNO_DIR/casos/<caso>/perfil_instagram.json
(scripts/checar_seguidores_perfil.py); sem essa leitura, fica sem nome e sem link (⛔).

Entrada: ODI_INTERNO_DIR/casos/<caso>/apify/*.json.
Saída privada: ODI_INTERNO_DIR/casos/<caso>/instagram_comentarios.csv.gz e corpus_iramuteq_instagram.txt.
Saída pública: data/casos/<caso>/instagram.json.
Uso: python scripts/build_caso_instagram.py --caso 007
"""
from __future__ import annotations

import csv
import glob
import gzip
import json
import os
import re
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from net import now_utc  # noqa: E402

MIN_PUBLICO = 10000
CASOS = {
    "007": {"shortcode": "DeFBlCfM1vy",
            "titulo": "Fake news: \"Lula amassa a bandeira no dia da eleição\" (reel do Instagram, 04/10/2026)",
            "categorias": {
                "aponta montagem, IA ou fake": r"\bfake\b|montag|mentira|editad|\bia\b|intelig[eê]ncia artificial|deep ?fake|falso|manipula|corta(do|ram)|contexto",
                "ataca Lula": r"vergonha|desrespeit|lixo|ladr[aã]o|bandido|nojo|cachaceiro|descondenad|nove dedos|9 dedos|molusco",
                "defende Lula": r"\blula ?13\b|faz o l|\bfazol|\bfaz o eli\b|lula presidente|lula l[aá]|#lula|❤️ ?lula|lula ?❤",
                "cita Bolsonaro ou família": r"bolsonaro|fl[aá]vio|\beduardo\b|\bbozo|\bmito\b",
                "bandeira e pátria": r"bandeira|p[aá]tria|brasil acima|verde e amarelo|s[ií]mbolo nacional|hino",
                "eleição e voto": r"elei[cç]|\bvot|urna|\b22\b|\b13\b|1º turno|primeiro turno|2º turno|segundo turno",
            },
            "nota_coleta": "Coletas de comentários do Instagram feitas no Apify em 06 e 07/10/2026, importadas sem nova execução e unificadas por id do comentário.",
            "marco": "dia do 1º turno"},
    # 22/10/2026 (18h48): reel sobre camisas do PT em Piracicaba; coleta nova (scripts/coletar_caso_instagram.py), teto US$ 3,00
    "008": {"shortcode": "DewwdGCR_Qn",
            "titulo": "Camisetas do PT em Piracicaba: reel de Guilherme Derrite (Instagram, 21/10/2026)",
            "categorias": {
                "aponta montagem, armação ou fake": r"\bfake\b|montag|mentira|arma[cç][aã]o|plantad|falso|manipula|\bia\b|encena",
                "acusa crime eleitoral ou compra de voto": r"crime|compra de voto|comprando voto|boca de urna|propaganda irregular|ilegal|\btse\b|justi[cç]a eleitoral|den[uú]nci|pol[ií]cia|pres[oa]",
                "ataca o PT ou Lula": r"ladr[aã]o|ladr[oõ]es|bandid|vergonha|nojo|corrup|petralha|cachaceiro|descondenad|nove dedos|9 dedos|molusco|quadrilha",
                "defende o PT ou Lula": r"\blula ?13\b|faz o l|\bfazol|lula presidente|lula l[aá]|#lula|❤️ ?lula|vamos de 13|\b13\b ?confirma",
                "cita Bolsonaro ou família": r"bolsonaro|fl[aá]vio|\beduardo\b|\bbozo|\bmito\b|\b22\b",
                "cita camisas": r"camis",
                "cita Piracicaba": r"piracicaba|piraci",
            },
            "nota_coleta": "Coleta nova do Atlas no Apify em 22/10/2026 (conta 1, teto autorizado de US$ 3,00), comentários unificados por id.",
            "marco": "início do caso"},
}
CAMPOS = ["id", "criado_em_utc", "texto", "curtidas", "respostas", "autor_id", "autor_usuario", "autor_nome", "autor_verificado", "runs"]


def data_ig(x: dict) -> str | None:
    v = x.get("created_at_utc") or x.get("created_at") or x.get("timestamp")
    if isinstance(v, (int, float)) or (isinstance(v, str) and v.isdigit()):
        return datetime.fromtimestamp(int(v), timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    if isinstance(v, str) and len(v) >= 19:
        return v[:19] + "Z"
    return None


def comentario(x: dict) -> dict | None:
    cid = str(x.get("comment_id") or x.get("pk") or x.get("id") or "")
    texto = " ".join(str(x.get("text") or "").split())
    if not cid or not texto:
        return None
    u = x.get("user") if isinstance(x.get("user"), dict) else x.get("owner") if isinstance(x.get("owner"), dict) else {}
    return {"id": cid, "criado_em_utc": data_ig(x), "texto": texto,
            "curtidas": x.get("comment_like_count") if x.get("comment_like_count") is not None else x.get("likesCount"),
            "respostas": x.get("child_comment_count") if x.get("child_comment_count") is not None else x.get("repliesCount"),
            "autor_id": str(u.get("id") or x.get("user_id") or ""), "autor_usuario": u.get("username") or x.get("username") or x.get("ownerUsername") or "",
            "autor_nome": u.get("full_name") or "", "autor_verificado": bool(u.get("is_verified"))}


def unificar(arquivos: list[Path], shortcode: str) -> tuple[dict, dict, dict]:
    coms, reel, stats = {}, {}, {"itens_brutos": 0, "runs": 0, "runs_sem_itens": 0}
    for f in arquivos:
        d = json.loads(f.read_text(encoding="utf-8"))
        if "items" not in d:
            continue
        stats["runs"] += 1
        itens = d.get("items") or []
        if not itens:
            stats["runs_sem_itens"] += 1
        for x in itens:
            stats["itens_brutos"] += 1
            if x.get("shortCode") == shortcode or ("videoPlayCount" in x and "ownerUsername" in x and "commentsCount" in x):
                reel = {k: x.get(k) for k in ("timestamp", "likesCount", "commentsCount", "videoPlayCount", "sharesCount", "videoDuration", "ownerUsername", "ownerFullName", "url")}
                reel["lido_em_utc"] = d.get("inicio_utc")
                continue
            c = comentario(x)
            if not c:
                continue
            velho = coms.get(c["id"])
            if velho:
                for k in ("curtidas", "respostas"):
                    vs = [v for v in (velho[k], c[k]) if isinstance(v, (int, float))]
                    velho[k] = max(vs) if vs else velho[k]
                for k, v in c.items():
                    if velho.get(k) in (None, "") and v not in (None, ""):
                        velho[k] = v
                velho["runs"].add(d["run_id"])
            else:
                c["runs"] = {d["run_id"]}
                coms[c["id"]] = c
    stats["comentarios_unicos"] = len(coms)
    return coms, reel, stats


def autor_publico(perfil: dict | None, shortcode: str) -> dict:
    """Nome, link e incorporação do reel só com 10 mil+ seguidores lidos; senão, ⛔ e nada que identifique o perfil."""
    if perfil and isinstance(perfil.get("seguidores"), int) and perfil["seguidores"] >= MIN_PUBLICO:
        return {"autor": f"@{perfil['usuario']}" + (f" ({perfil['nome']})" if perfil.get("nome") else ""), "autor_seguidores": perfil["seguidores"],
                "autor_verificado": bool(perfil.get("verificado")), "autor_seguidores_lido_em_utc": perfil.get("lido_em_utc"),
                "url": f"https://www.instagram.com/p/{shortcode}/", "embed": f"https://www.instagram.com/p/{shortcode}/embed"}
    if perfil and isinstance(perfil.get("seguidores"), int):
        return {"autor": f"perfil com menos de {MIN_PUBLICO:,} seguidores".replace(",", "."), "autor_seguidores": None}
    return {"autor": "⛔ perfil pessoal sem número de seguidores coletado: nome e link ficam no repositório privado"}


def agregar(coms: dict, reel: dict, stats: dict, cfg: dict, perfil: dict | None = None) -> dict:
    cats = {k: re.compile(v, re.I) for k, v in cfg["categorias"].items()}
    cs = list(coms.values())
    hora = Counter((c["criado_em_utc"] or "")[:13] for c in cs if c["criado_em_utc"])
    dia = Counter((c["criado_em_utc"] or "")[:10] for c in cs if c["criado_em_utc"])
    curt = sorted((c["curtidas"] or 0 for c in cs), reverse=True)
    return {"reel": {"publicado_em_utc": reel.get("timestamp"), "reproducoes": reel.get("videoPlayCount"), "curtidas": reel.get("likesCount"),
                     "comentarios_informados": reel.get("commentsCount"), "compartilhamentos": reel.get("sharesCount"), "duracao_s": reel.get("videoDuration"),
                     "lido_em_utc": reel.get("lido_em_utc"), "marco": cfg.get("marco"), **autor_publico(perfil, cfg["shortcode"])},
            "unificacao": {**stats, "duplicados_removidos": stats["itens_brutos"] - stats["comentarios_unicos"] - (1 if reel else 0),
                           "autores_unicos": len({c["autor_id"] or c["autor_usuario"] for c in cs}),
                           "cobertura": {"comentarios_coletados": len(cs), "comentarios_informados_pelo_instagram": reel.get("commentsCount")}},
            "por_dia": sorted(dia.items()), "por_hora_utc": sorted(hora.items())[:72],
            "categorias_pct": {k: round(100 * sum(bool(rx.search(c["texto"])) for c in cs) / len(cs), 1) if cs else None for k, rx in cats.items()},
            "verificados_pct": round(100 * sum(1 for c in cs if c["autor_verificado"]) / len(cs), 1) if cs else None,
            "curtidas_nos_comentarios": {"soma": sum(curt), "top10_pct": round(100 * sum(curt[:10]) / sum(curt), 1) if sum(curt) else None},
            "min_seguidores_publico": MIN_PUBLICO}


def main(argv=None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    caso = argv[argv.index("--caso") + 1] if "--caso" in argv else "007"
    cfg = CASOS[caso]
    interno = os.environ.get("ODI_INTERNO_DIR")
    if not interno:
        print("⛔ sem repositório privado")
        return 1
    pv = Path(interno) / f"casos/{caso}"
    arqs = [Path(f) for f in sorted(glob.glob(str(pv / "apify/*.json"))) if not f.endswith(("manifesto.json", "manifesto_coleta.json"))]
    if not arqs:
        print(f"⛔ caso {caso}: nenhuma coleta importada")
        return 1
    coms, reel, stats = unificar(arqs, cfg["shortcode"])
    arq_perfil = pv / "perfil_instagram.json"
    perfil = json.loads(arq_perfil.read_text(encoding="utf-8")) if arq_perfil.exists() else None
    with gzip.open(pv / "instagram_comentarios.csv.gz", "wt", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, CAMPOS, delimiter=";", lineterminator="\n")
        w.writeheader()
        w.writerows({**c, "runs": "|".join(sorted(c["runs"]))} for c in sorted(coms.values(), key=lambda c: c["criado_em_utc"] or ""))
    out = {"schema_version": 1, "caso": caso, "plataforma": "Instagram", "titulo": cfg["titulo"], "gerado_em_utc": now_utc(), **agregar(coms, reel, stats, cfg, perfil),
           "nota": cfg["nota_coleta"] + " É o que as coletas devolveram (ordem 'populares' do Instagram), não o total. Categorias = pré-codificação por "
                   "dicionário, não decisão. Quem comenta nunca aparece com nome; texto e autor ficam no repositório privado."}
    pasta = Path("data/casos") / caso
    pasta.mkdir(parents=True, exist_ok=True)
    try:
        import redes_caso as rc
        textos = [c["texto"] for c in coms.values()]
        n, a, d = rc.palavras(textos)
        rc.gexf(n, a, pasta / "rede_palavras_instagram.gexf")
        out["redes"] = {"palavras": {"desenho": d, "o_que_e": "palavras que aparecem juntas no mesmo comentário do reel (3+ vezes); cor = comunidade",
                                     "gexf": "rede_palavras_instagram.gexf"}}
        out["classes"] = rc.classes(textos, [(c["criado_em_utc"] or "0000")[:4] for c in coms.values()])
        (pv / "corpus_iramuteq_instagram.txt").write_text(rc.corpus_iramuteq([{"video_id": cfg["shortcode"], "publicado_em": c["criado_em_utc"] or "",
                                                                              "tipo": "comentario", "texto": c["texto"]} for c in coms.values()]), encoding="utf-8")
    except Exception as e:  # noqa: BLE001
        out["redes"] = {"erro": f"{type(e).__name__}: {str(e)[:200]}"}
    (pasta / "instagram.json").write_text(json.dumps(out, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    u = out["unificacao"]
    print(f"caso {caso}: {u['runs']} execuções ({u['runs_sem_itens']} sem itens) · {u['itens_brutos']} itens brutos → {u['comentarios_unicos']} comentários "
          f"únicos · duplicados removidos {u['duplicados_removidos']} · autores {u['autores_unicos']} · reel {out['reel']['reproducoes']} reproduções")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
