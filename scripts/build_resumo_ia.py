#!/usr/bin/env python3
"""Resumo compacto dos dados PÚBLICOS do Atlas para o chat com IA (data/ia/resumo.json).

Só agregados que já estão na página (nenhum texto de comentário, nenhum dado de pessoa comum, nenhum custo de coleta).
Cada bloco traz a fonte (arquivo) e a data, para a IA citar. Ordem dos candidatos: Lula primeiro (regra do Atlas).
"""
from __future__ import annotations

import csv
import gzip
import json
import statistics
import sys
from pathlib import Path

L, F = "280002542548", "280002551544"
NOMES = {L: "Lula", F: "Flávio Bolsonaro"}


def ler(p: Path):
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        return None


def conteudo(root: Path, plat: str) -> dict | None:
    d = ler(root / f"data/{plat}/conteudo.json")
    if not d:
        return None
    out = {"fonte": f"data/{plat}/conteudo.json", "coletado_em": d.get("coletado_em_utc"), "desde": d.get("desde"), "candidatos": {}}
    for cid in (L, F):
        c = (d.get("candidatos") or {}).get(cid)
        if not c:
            continue
        vs = c.get("videos") or []
        fases = (ler(root / "data/config/trends.json") or {}).get("fases") or []
        soma = lambda lst, k: sum(v.get(k) or 0 for v in lst)  # noqa: E731
        totais = c.get("totais") or {k: soma(vs, k) for k in ("visualizacoes", "curtidas", "comentarios")}
        por_fase = c.get("por_fase") or {f["id"]: {"rotulo": f["rotulo"], "itens": len(x := [v for v in vs if f["de"] <= (v.get("publicado_em") or "")[:10] <= f["ate"]]),
                                                    "visualizacoes": soma(x, "visualizacoes")} for f in fases}
        top = sorted(vs, key=lambda v: -(v.get("visualizacoes") or 0))[:5]
        out["candidatos"][NOMES[cid]] = {
            "itens": c.get("total_videos"), "perfis": c.get("perfis") or c.get("canais"),
            "totais": totais, "interacao_mediana": c.get("taxa_interacao_mediana"),
            "temas": dict(list((c.get("por_tema") or {}).items())[:8]), "cita_adversario": c.get("cita_adversario"),
            "pede_voto": c.get("pede_voto"), "por_fase": por_fase, "por_mes": c.get("por_mes"),
            "hashtags": (c.get("hashtags") or [])[:10], "palavras": [w for w, _ in (c.get("nuvem") or [])[:15]],
            "mais_vistos": [{"data": (v.get("publicado_em") or "")[:10], "visualizacoes": v.get("visualizacoes"),
                             "texto": (v.get("legenda") or v.get("titulo") or "")[:140], "url": v.get("url")} for v in top]}
    return out


def comentarios(root: Path, plat: str) -> dict | None:
    a = ler(root / f"data/{plat}/comentarios/analise.json")
    s = ler(root / f"data/{plat}/comentarios/sentimento.json")
    if not a:
        return None
    out = {"fonte": f"data/{plat}/comentarios/analise.json", "coletado_em": a.get("coletado_em_utc"), "candidatos": {}}
    for cid in (L, F):
        c = (a.get("candidatos") or {}).get(cid) or {}
        sc = ((s or {}).get("candidatos") or {}).get(cid) or {}
        out["candidatos"][NOMES[cid]] = {"comentarios": c.get("comentarios"), "videos": c.get("videos"),
                                         "incivilidade_pct": c.get("qualquer_incivilidade_pct"), "intolerancia_pct": c.get("qualquer_intolerancia_pct"),
                                         "cita_adversario_pct": c.get("cita_adversario_pct"),
                                         "sentimento": {k: sc.get(k) for k in ("positivo", "neutro", "negativo", "n")} if sc else None,
                                         "palavras": [w for w, _ in (c.get("nuvem") or [])[:12]]}
    return out


def seguidores(root: Path) -> list[dict]:
    out = []
    for arq, origem in (("latest.csv", "Apify (Instagram/Facebook)"), ("youtube_latest.csv", "YouTube API"), ("kwai_latest.csv", "Kwai"),
                        ("x_latest.csv", "X"), ("tiktok_latest.csv", "TikTok"), ("complemento_latest.csv", "Apify (consulta direta ao perfil)")):
        p = root / "data/seguidores" / arq
        if not p.exists():
            continue
        for r in csv.DictReader(open(p, encoding="utf-8"), delimiter=";"):
            if r.get("candidate_id") in (L, F):
                out.append({"candidato": NOMES[r["candidate_id"]], "declarado_por": r.get("candidate_name"), "rede": r.get("platform"),
                            "perfil": r.get("source_url") or r.get("url"), "seguidores": r.get("followers"), "data": r.get("captured_at"), "fonte": f"data/seguidores/{arq}"})
    return out


def main(argv=None) -> int:
    root = Path(argv[0]) if argv else Path(".")
    tr = ler(root / "data/trends/caderno.json") or {}
    q = next((c for c in tr.get("consultas", []) if c.get("grupo") == "segundo_turno_topicos" and c.get("periodo") == "eleitoral"), None)
    xt = ler(root / "data/x/trends/latest.json") or {}
    ads = ler(root / "data/meta/anuncios.json") or {}
    el = ler(root / "data/elections.json") or {}
    voto = None
    if el.get("years", {}).get("2026"):
        vL = vF = val = 0
        for m in el["years"]["2026"].values():
            c = m.get("candidatos") or {}
            vL += c.get("13", 0)
            vF += c.get("22", 0)
            val += m.get("validos_nominais", 0)
        voto = {"Lula_votos": vL, "Flavio_votos": vF, "Lula_pct_validos": round(100 * vL / val, 2) if val else None,
                "Flavio_pct_validos": round(100 * vF / val, 2) if val else None, "fonte": "data/elections.json (TSE, 1º turno 2026)"}
    out = {"gerado_em_utc": __import__("datetime").datetime.now(__import__("datetime").timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
           "regras": ["Ordem: Lula primeiro (candidato à reeleição); não indica preferência.",
                      "Seguidores não são eleitores; interações não são votos; buscas não são intenção de voto.",
                      "Fases: pré-campanha 20/07–15/08, 1º turno 16/08–04/10, 2º turno 05/10–25/10."],
           "fases": tr.get("fases") or (ler(root / "data/config/trends.json") or {}).get("fases"),
           "conteudo": {p: conteudo(root, p) for p in ("youtube", "tiktok", "kwai", "facebook", "x")},
           "comentarios": {p: comentarios(root, p) for p in ("youtube", "kwai", "facebook")},
           "seguidores": seguidores(root),
           "google_trends": {"fonte": "data/trends/caderno.json", "termos": q.get("termos") if q else None,
                             "vegetativo": (q or {}).get("vegetativo"), "uf_mais_buscado": None} if q else None,
           "x_assuntos_do_dia": {"fonte": "data/x/trends/latest.json", "dia": xt.get("dia"), "top": [t["assunto"] for t in (xt.get("top") or [])[:20]],
                                 "citam_candidatos": [t["assunto"] for t in (xt.get("citam_candidatos") or [])[:20]]} if xt else None,
           "anuncios_meta": {"fonte": "data/meta/anuncios.json", "coletado_em": ads.get("coletado_em_utc"),
                             "consultas": [{k: c.get(k) for k in ("candidato", "anuncios", "gasto_min", "gasto_max", "impressoes_min", "impressoes_max") if k in c}
                                           for c in (ads.get("consultas") or [])] if isinstance(ads.get("consultas"), list) else None},
           "voto_1turno": voto}
    d = root / "data/ia"
    d.mkdir(parents=True, exist_ok=True)
    txt = json.dumps(out, ensure_ascii=False, separators=(",", ":"), default=str)
    (d / "resumo.json").write_text(txt, encoding="utf-8")
    print(f"resumo para IA: {len(txt) // 1024} KB")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
