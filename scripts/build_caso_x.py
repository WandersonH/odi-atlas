#!/usr/bin/env python3
"""Caso com conversa no X a partir de coletas do Apify já importadas (scripts/importar_apify_runs.py): unifica, remove
duplicados e agrega no padrão dos casos (redes de respostas e de palavras, classes estilo IRaMuTeQ).

Caso 006 (pedido de 22/10/2026): post de Marco Rubio (x.com/SecRubio/status/2060119225176404134, 28/05/2026) que anuncia a
classificação do PCC e do CV como organizações terroristas. As coletas de 23–24/09 (atores xquik) trouxeram respostas,
citações, o fio e quem repostou, em execuções que se repetem: o mesmo post aparece em várias delas.

Unificação: posts por `id` (fica a versão com mais campos; tipo = resposta, citação ou fio, pela marca do ator e pelo
`inReplyToId`); quem repostou, por `id` do perfil. Nada é estimado: as contagens são do que as coletas devolveram.

Entrada: ODI_INTERNO_DIR/casos/<caso>/apify/*.json.
Saída privada: ODI_INTERNO_DIR/casos/<caso>/x_posts.csv.gz, x_repostadores.csv.gz, corpus_iramuteq_x.txt.
Saída pública: data/casos/<caso>/x.json (agregados; nome só de perfis com 10 mil seguidores ou mais; demais como código).
Uso: python scripts/build_caso_x.py --caso 006
"""
from __future__ import annotations

import csv
import glob
import gzip
import json
import os
import re
import statistics
import sys
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from net import now_utc  # noqa: E402

MIN_PUBLICO = 10000
CASOS = {
    "006": {"post": "2060119225176404134", "autor": "SecRubio",
            "titulo": "PCC e CV como organizações terroristas (post de Marco Rubio, 28/05/2026)",
            "categorias": {
                "apoia a designação": r"\b(finalmente|parab[eé]ns|obrigad[oa]|thank you|thanks|well done|great job|excelente|até que enfim|ate que enfim|muito bem|god bless)\b",
                "soberania ou intervenção": r"soberan|interven|imperiali|ingerên|ingeren|invas[aã]o|col[oô]nia|quintal|sovereign",
                "cita Lula ou o governo": r"\blula\b|petista|\bpt\b|governo federal|lulopet|descondenad",
                "cita Bolsonaro ou família": r"bolsonaro|\beduardo\b|fl[aá]vio|\bbozo",
                "cita Moraes ou STF": r"moraes|\bxand|\bstf\b|supremo",
                "cita Trump ou EUA": r"\btrump|\beua\b|estados unidos|\bamerica|\busa\b",
                "narcoterrorismo e crime": r"narco|terror|fac[cç][aã]o|crime organizado|tr[aá]fico|cartel|mil[ií]cia",
            }},
}
CAMPOS_POST = ["id", "tipo", "criado_em_utc", "idioma", "texto", "autor_id", "autor_usuario", "autor_nome", "autor_seguidores", "autor_verificado",
               "em_resposta_a_id", "em_resposta_a_usuario", "curtidas", "reposts", "respostas", "citacoes", "visualizacoes", "url", "runs"]
CAMPOS_RT = ["id", "usuario", "nome", "seguidores", "verificado", "local", "criado_em", "runs"]


def data_x(s: str | None) -> str | None:
    """'Thu May 28 22:01:13 +0000 2026' → '2026-05-28T22:01:13Z'."""
    if not s:
        return None
    for fmt in ("%a %b %d %H:%M:%S %z %Y", "%Y-%m-%dT%H:%M:%S.%f%z", "%Y-%m-%dT%H:%M:%S%z"):
        try:
            return datetime.strptime(s.replace("Z", "+0000") if fmt != "%a %b %d %H:%M:%S %z %Y" else s, fmt).strftime("%Y-%m-%dT%H:%M:%SZ")
        except ValueError:
            continue
    return None


def autor(x: dict) -> dict:
    a = x.get("author") or {}
    return {"id": str(a.get("id") or x.get("authorId") or ""), "usuario": a.get("userName") or a.get("username") or x.get("authorUsername") or "",
            "nome": a.get("name") or x.get("authorName") or "", "seguidores": a.get("followers") if a.get("followers") is not None else x.get("authorFollowers"),
            "verificado": bool(a.get("isBlueVerified") or a.get("isVerified") or x.get("authorIsBlueVerified") or x.get("authorVerified"))}


def tipo_post(x: dict, post: str) -> str:
    if str(x.get("id")) == post:
        return "original"
    rt = (x.get("resultType") or "").lower()
    if rt == "thread":
        return "fio"
    if rt == "quotes" or (x.get("isQuoteStatus") and not x.get("inReplyToId")):
        return "citação"
    return "resposta"


def unificar(arquivos: list[Path], post: str) -> tuple[dict, dict, dict]:
    posts, rts, stats = {}, {}, {"itens_brutos": 0, "runs": 0}
    for f in arquivos:
        d = json.loads(f.read_text(encoding="utf-8"))
        if "items" not in d:
            continue
        stats["runs"] += 1
        for x in d.get("items") or []:
            stats["itens_brutos"] += 1
            if not x.get("text") and (x.get("resultType") in ("retweeters", "user") or x.get("engagementMode") == "retweeters" or "followers" in x):
                k = str(x.get("id") or "")
                if not k:
                    continue
                r = rts.setdefault(k, {"id": k, "usuario": x.get("username") or x.get("userName") or "", "nome": x.get("name") or "",
                                       "seguidores": x.get("followers"), "verificado": bool(x.get("isBlueVerified") or x.get("isVerified") or x.get("verified")),
                                       "local": x.get("location") or "", "criado_em": data_x(x.get("createdAt")), "runs": set()})
                r["runs"].add(d["run_id"])
                continue
            k = str(x.get("id") or "")
            if not k or not x.get("text"):
                continue
            a = autor(x)
            novo = {"id": k, "tipo": tipo_post(x, post), "criado_em_utc": data_x(x.get("createdAt")), "idioma": x.get("lang") or "",
                    "texto": " ".join(str(x.get("text") or "").split()), "autor_id": a["id"], "autor_usuario": a["usuario"], "autor_nome": a["nome"],
                    "autor_seguidores": a["seguidores"], "autor_verificado": a["verificado"], "em_resposta_a_id": str(x.get("inReplyToId") or ""),
                    "em_resposta_a_usuario": x.get("inReplyToUsername") or "", "curtidas": x.get("likeCount"), "reposts": x.get("retweetCount"),
                    "respostas": x.get("replyCount"), "citacoes": x.get("quoteCount"), "visualizacoes": x.get("viewCount"), "url": x.get("url") or ""}
            velho = posts.get(k)
            if velho:
                for c, v in novo.items():  # mantém o que já havia; completa campos vazios; métricas: o maior valor visto
                    if c in ("curtidas", "reposts", "respostas", "citacoes", "visualizacoes"):
                        velho[c] = max([v for v in (velho[c], v) if isinstance(v, (int, float))], default=velho[c])
                    elif velho.get(c) in (None, "") and v not in (None, ""):
                        velho[c] = v
                if velho["tipo"] == "resposta" and novo["tipo"] in ("citação", "fio"):
                    velho["tipo"] = novo["tipo"]
                velho["runs"].add(d["run_id"])
            else:
                novo["runs"] = {d["run_id"]}
                posts[k] = novo
    stats.update(posts_unicos=len(posts), repostadores_unicos=len(rts))
    return posts, rts, stats


def publico(usuario: str, seguidores, codigos: dict, chave: str) -> str:
    if isinstance(seguidores, (int, float)) and seguidores >= MIN_PUBLICO:
        return "@" + usuario
    codigos.setdefault(chave, f"P{len(codigos) + 1:04d}")
    return codigos[chave]


def agregar(posts: dict, rts: dict, stats: dict, cfg: dict) -> dict:
    orig = posts.get(cfg["post"]) or {}
    conv = [p for p in posts.values() if p["tipo"] != "original"]
    cats = {k: re.compile(v, re.I) for k, v in cfg["categorias"].items()}
    por_tipo = Counter(p["tipo"] for p in conv)
    dia = defaultdict(Counter)
    for p in conv:
        if p["criado_em_utc"]:
            dia[p["criado_em_utc"][:10]][p["tipo"]] += 1
    codigos = {}
    publicos = sorted((p for p in conv if isinstance(p["autor_seguidores"], (int, float)) and p["autor_seguidores"] >= MIN_PUBLICO),
                      key=lambda p: -(p["curtidas"] or 0))
    autores = {p["autor_id"] for p in conv}
    seg = [r["seguidores"] for r in rts.values() if isinstance(r["seguidores"], (int, float))]
    pt = [p for p in conv if p["idioma"] == "pt"]
    out = {"original": {k: orig.get(k) for k in ("criado_em_utc", "texto", "curtidas", "reposts", "respostas", "citacoes", "visualizacoes", "url")}
           | {"autor": "@" + cfg["autor"]},
           "unificacao": {**stats, "duplicados_removidos": stats["itens_brutos"] - stats["posts_unicos"] - stats["repostadores_unicos"],
                          "posts_por_tipo": dict(por_tipo), "autores_unicos": len(autores),
                          "cobertura": {"respostas_coletadas": por_tipo.get("resposta", 0), "respostas_informadas_pelo_x": orig.get("respostas"),
                                        "citacoes_coletadas": por_tipo.get("citação", 0), "citacoes_informadas_pelo_x": orig.get("citacoes"),
                                        "repostadores_coletados": len(rts), "reposts_informados_pelo_x": orig.get("reposts")}},
           "por_idioma": Counter(p["idioma"] or "?" for p in conv).most_common(10),
           "por_dia": [[d, dict(c)] for d, c in sorted(dia.items())],
           "categorias_pct": {k: round(100 * sum(bool(rx.search(p["texto"])) for p in conv) / len(conv), 1) if conv else None for k, rx in cats.items()},
           "categorias_pct_pt": {k: round(100 * sum(bool(rx.search(p["texto"])) for p in pt) / len(pt), 1) if pt else None for k, rx in cats.items()},
           "verificados_pct": round(100 * sum(1 for p in conv if p["autor_verificado"]) / len(conv), 1) if conv else None,
           "mais_curtidos_publicos": [{"autor": "@" + p["autor_usuario"], "seguidores": p["autor_seguidores"], "tipo": p["tipo"], "criado_em_utc": p["criado_em_utc"],
                                       "texto": p["texto"][:280], "curtidas": p["curtidas"], "visualizacoes": p["visualizacoes"], "url": p["url"]} for p in publicos[:15]],
           "posts_de_perfis_pequenos": sum(1 for p in conv if not (isinstance(p["autor_seguidores"], (int, float)) and p["autor_seguidores"] >= MIN_PUBLICO)),
           "repostadores": {"total": len(rts), "verificados_pct": round(100 * sum(1 for r in rts.values() if r["verificado"]) / len(rts), 1) if rts else None,
                            "seguidores_mediana": statistics.median(seg) if seg else None,
                            "maiores": [{"perfil": "@" + r["usuario"], "seguidores": r["seguidores"]} for r in
                                        sorted((r for r in rts.values() if isinstance(r["seguidores"], (int, float)) and r["seguidores"] >= MIN_PUBLICO),
                                               key=lambda r: -r["seguidores"])[:15]]},
           "min_seguidores_publico": MIN_PUBLICO}
    return out


def main(argv=None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    caso = argv[argv.index("--caso") + 1] if "--caso" in argv else "006"
    cfg = CASOS[caso]
    interno = os.environ.get("ODI_INTERNO_DIR")
    if not interno:
        print("⛔ sem repositório privado")
        return 1
    pv = Path(interno) / f"casos/{caso}"
    arqs = [Path(f) for f in sorted(glob.glob(str(pv / "apify/*.json"))) if not f.endswith("manifesto.json")]
    if not arqs:
        print(f"⛔ caso {caso}: nenhuma coleta importada em {pv / 'apify'}")
        return 1
    posts, rts, stats = unificar(arqs, cfg["post"])
    with gzip.open(pv / "x_posts.csv.gz", "wt", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, CAMPOS_POST, delimiter=";", lineterminator="\n")
        w.writeheader()
        w.writerows({**p, "runs": "|".join(sorted(p["runs"]))} for p in sorted(posts.values(), key=lambda p: p["criado_em_utc"] or ""))
    with gzip.open(pv / "x_repostadores.csv.gz", "wt", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, CAMPOS_RT, delimiter=";", lineterminator="\n")
        w.writeheader()
        w.writerows({**r, "runs": "|".join(sorted(r["runs"]))} for r in rts.values())
    out = {"schema_version": 1, "caso": caso, "plataforma": "X", "titulo": cfg["titulo"], "gerado_em_utc": now_utc(), **agregar(posts, rts, stats, cfg),
           "nota": "Coletas do X feitas no Apify em 23 e 24/09/2026 (atores xquik), importadas do Apify sem nova execução e unificadas: "
                   "o mesmo post e o mesmo perfil aparecem em várias execuções e contam uma vez. É o que as coletas devolveram, não o total "
                   "da conversa (ver cobertura). Categorias = pré-codificação por dicionário, não decisão. Nome só de perfis com 10 mil "
                   "seguidores ou mais; texto e autor dos demais ficam no repositório privado."}
    # redes e classes no padrão dos casos (sem numpy/networkx a agregação continua)
    conv = [p for p in posts.values() if p["tipo"] != "original"]
    pasta = Path("data/casos") / caso
    pasta.mkdir(parents=True, exist_ok=True)
    try:
        import redes_caso as rc
        rows = [{"comment_id": p["id"], "parent_id": p["em_resposta_a_id"], "tipo": "resposta" if p["em_resposta_a_id"] else "comentario",
                 "autor_canal": p["autor_id"]} for p in posts.values()]
        n, a, r = rc.respostas(rows)
        rc.gexf(n, a, pasta / "rede_respostas_x.gexf", dirigida=True)
        textos_pt = [p["texto"] for p in conv if p["idioma"] == "pt"]
        n2, a2, d2 = rc.palavras(textos_pt)
        rc.gexf(n2, a2, pasta / "rede_palavras_x.gexf")
        out["redes"] = {"respostas": {**r, "o_que_e": "quem responde a quem na conversa do post no X; autores sempre como código (A0001…)",
                                      "gexf": "rede_respostas_x.gexf"},
                        "palavras": {"desenho": d2, "o_que_e": "palavras que aparecem juntas no mesmo post do X em português (3+ vezes); cor = comunidade",
                                     "gexf": "rede_palavras_x.gexf"}}
        out["classes"] = rc.classes(textos_pt, [(p["criado_em_utc"] or "0000")[:4] for p in conv if p["idioma"] == "pt"])
        (pv / "corpus_iramuteq_x.txt").write_text(rc.corpus_iramuteq([{"video_id": p["tipo"], "publicado_em": p["criado_em_utc"] or "", "tipo": p["tipo"],
                                                                      "texto": p["texto"]} for p in conv if p["idioma"] == "pt"]), encoding="utf-8")
    except Exception as e:  # noqa: BLE001
        out["redes"] = {"erro": f"{type(e).__name__}: {str(e)[:200]}"}
    (pasta / "x.json").write_text(json.dumps(out, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    u = out["unificacao"]
    print(f"caso {caso}: {u['runs']} execuções · {u['itens_brutos']} itens brutos → {u['posts_unicos']} posts únicos {u['posts_por_tipo']} + "
          f"{u['repostadores_unicos']} perfis que repostaram · duplicados removidos {u['duplicados_removidos']} · autores {u['autores_unicos']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
