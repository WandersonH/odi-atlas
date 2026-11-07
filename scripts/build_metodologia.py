#!/usr/bin/env python3
"""Metodologia de cada caso + tabela universo × amostra, para o bloco "Como a amostra foi feita" da página.

Entrada:
- data/config/metodologia_casos.json: texto da metodologia (pergunta, recorte, famílias de termos e justificativas,
  exclusões, fontes, controles, limites), redigido à mão;
- data/config/casos.json: os termos efetivamente usados em cada rede (para a página mostrar a busca real, não um resumo);
- data/casos/<id>/manifesto-*.json, caso.json, busca.json e canais_whatsapp.json: os números.
Saída: data/casos/<id>/metodologia.json (só para os casos com texto redigido).

Regra (CLAUDE.md, 9): toda amostra aparece com o universo. Universo é o total que a plataforma informa para a mesma
busca; quando ela não informa, fica "⛔ desconhecido" e não é estimado. Nenhum número é digitado aqui: todos vêm dos
arquivos de coleta, com o caminho de origem.
Uso: python scripts/build_metodologia.py [--caso 030]
"""
from __future__ import annotations

import glob
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from net import now_utc  # noqa: E402

ROT = {"x": "X", "tiktok": "TikTok", "instagram": "Instagram", "facebook": "Facebook", "kwai": "Kwai"}
SEM_UNIVERSO = {
    "x": "⛔ desconhecido: a busca do X (via Apify) não informa o total de posts",
    "tiktok": "⛔ desconhecido: a busca do TikTok não informa o total de vídeos",
    "instagram": "⛔ desconhecido: a busca de reels e a página da hashtag do Instagram (via Apify) não devolvem o total",
    "facebook": "⛔ desconhecido: a busca de posts do Facebook (via Apify) não informa o total",
    "kwai": "⛔ desconhecido: a busca do Kwai não informa o total",
    "youtube": "⛔ desconhecido: a YouTube Data API não informa o total exato (devolve até 100 vídeos por consulta)",
    "noticias": "⛔ desconhecido: o RSS do Google Notícias devolve até 100 títulos por consulta e não informa o total",
    "trends": "não se aplica: o Google Trends dá índice relativo (0–100), não volume",
}


def termos_por_rede(c: dict) -> dict:
    out = {}
    x = [f"{q.get('termo')}: {q.get('busca')}" for q in c.get("complementos_x", [])]
    if c.get("hashtags"):
        x = [f"#{h}" for h in c["hashtags"]] + x
    out["x"] = x
    out["tiktok"] = [f"#{h}" for h in c.get("hashtags", [])] + list(c.get("buscas_tiktok", []))
    ig = [f"#{h}" for h in c.get("hashtags_instagram", [])] + [f"reels: {q}" for q in c.get("buscas_instagram", [])]
    fb = list(c.get("buscas_facebook", []))
    for k, v in c.items():
        if k.startswith("buscas_instagram_r"):
            ig += [f"reels (rodada {k.rsplit('_r', 1)[1]}): {q}" for q in v]
        if k.startswith("buscas_facebook_r"):
            fb += [f"{q} (rodada {k.rsplit('_r', 1)[1]})" for q in v]
    out["instagram"], out["facebook"] = ig, fb
    out["google_trends"] = list(c.get("termos_trends", []))
    out["google_noticias"] = list(c.get("termos_noticias", []))
    return {k: v for k, v in out.items() if v}


def amostra(root: Path, cid: str, c: dict) -> list[dict]:
    pasta = root / "data/casos" / cid
    linhas, por = [], {}
    for f in sorted(glob.glob(str(pasta / "manifesto-2*.json"))):
        m = json.loads(Path(f).read_text(encoding="utf-8"))
        for r in m.get("redes", []):
            rede = r.get("rede")
            if rede not in ROT:
                continue
            a = por.setdefault(rede, {"lidos": 0, "no_periodo": 0, "termos": 0, "no_limite": [], "manifestos": [], "status": []})
            ts = r.get("termos")
            if isinstance(ts, list):
                for t in ts:
                    a["termos"] += 1
                    a["lidos"] += int(t.get("lidos") or t.get("itens") or 0)
                    a["no_periodo"] += int(t.get("no_periodo") or 0)
                    if t.get("no_limite"):
                        a["no_limite"].append(t.get("termo"))
            elif isinstance(ts, dict):  # TikTok pela página pública (dicionário por termo)
                for t in ts.values():
                    a["termos"] += 1
                    a["lidos"] += int(t.get("videos") or 0)
                    a["no_periodo"] += int(t.get("videos") or 0)
            a["manifestos"].append(Path(f).name)
            if r.get("status") and r["status"] != "ok":
                a["status"].append(r["status"])
    cj = pasta / "caso.json"
    caso = json.loads(cj.read_text(encoding="utf-8")) if cj.exists() else {}
    for rede, a in por.items():
        final = ((caso.get("redes") or {}).get(ROT[rede]) or {}).get("publicacoes")
        linhas.append({"fonte": ROT[rede], "universo": SEM_UNIVERSO[rede], "lidos": a["lidos"], "no_periodo": a["no_periodo"],
                       "na_analise": final, "pct": None, "termos_buscados": a["termos"],
                       "termos_no_limite": sorted(set(filter(None, a["no_limite"]))),
                       "como": "busca por termo na plataforma (Apify ou página pública), na ordem que a plataforma devolve, até o limite por termo; "
                               "depois, filtro de período e de termo; duplicados unidos",
                       "avisos": sorted(set(a["status"])), "origem": a["manifestos"][-3:] and f"data/casos/{cid}/" + ", ".join(a["manifestos"][-3:])})
    bj = pasta / "busca.json"
    if bj.exists():
        b = json.loads(bj.read_text(encoding="utf-8"))
        y = b.get("youtube") or {}
        if y.get("videos") is not None:
            linhas.append({"fonte": "YouTube", "universo": SEM_UNIVERSO["youtube"], "lidos": y.get("videos"), "no_periodo": y.get("videos"),
                           "na_analise": y.get("videos"), "pct": None, "como": "busca da YouTube Data API por consulta, desde a data do caso, "
                           "filtrada pelo título e descrição; " + (y.get("nota") or ""), "origem": f"data/casos/{cid}/busca.json (youtube)",
                           "coletado_em": b.get("coletado_em_utc")})
        n = b.get("noticias") or []
        linhas.append({"fonte": "Google Notícias", "universo": SEM_UNIVERSO["noticias"], "lidos": len(n), "no_periodo": len(n), "na_analise": len(n),
                       "pct": None, "como": "RSS do Google Notícias por consulta e edição de país, filtrado pelo título; duplicados unidos",
                       "origem": f"data/casos/{cid}/busca.json (noticias)", "coletado_em": b.get("coletado_em_utc")})
        tr = (b.get("trends") or {}).get("variantes") or {}
        if tr.get("termos"):
            janelas = [k for k, v in tr.items() if isinstance(v, list) and v and isinstance(v[0], dict) and "t" in v[0]]
            linhas.append({"fonte": "Google Trends", "universo": SEM_UNIVERSO["trends"], "lidos": None, "no_periodo": None, "na_analise": None,
                           "pct": None, "como": f"índice semanal/diário por janela ({', '.join(janelas)}), termos: {', '.join(tr['termos'])}",
                           "avisos": [e for e in b.get("erros") or [] if e.startswith("trends")],
                           "origem": f"data/casos/{cid}/busca.json (trends)", "coletado_em": b.get("coletado_em_utc")})
    wj = pasta / "canais_whatsapp.json"
    if wj.exists():
        w = json.loads(wj.read_text(encoding="utf-8"))
        ult = {}
        for x in w.get("leituras", []):
            if x.get("seguidores") is not None:
                ult[x["canal"]] = x
        if ult:
            linhas.append({"fonte": "Canais de WhatsApp (página pública)", "universo": "informado pela plataforma: seguidores de cada canal (número arredondado pelo WhatsApp)",
                           "lidos": len(ult), "no_periodo": len(ult), "na_analise": len(ult), "pct": None,
                           "como": f"{len(ult)} canais lidos todo dia; é censo dos canais listados (não amostra), mas a lista de canais é aberta",
                           "seguidores_ultima_leitura": {k: [v["seguidores"], v["lido_em_utc"]] for k, v in ult.items()},
                           "origem": f"data/casos/{cid}/canais_whatsapp.json", "coletado_em": w.get("atualizado_em_utc")})
    return linhas


def main(argv=None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    root = Path(".")
    so = argv[argv.index("--caso") + 1] if "--caso" in argv else None
    met = json.loads((root / "data/config/metodologia_casos.json").read_text(encoding="utf-8"))
    casos = {c["id"]: c for c in json.loads((root / "data/config/casos.json").read_text(encoding="utf-8"))["casos"]}
    feitos = []
    for cid, m in met.items():
        if cid.startswith("_") or (so and cid != so) or cid not in casos:
            continue
        out = {"gerado_em_utc": now_utc(), "caso": cid, "titulo": casos[cid]["titulo"], **m, "comum": met["_comum"],
               "termos_por_rede": termos_por_rede(casos[cid]), "amostra": amostra(root, cid, casos[cid])}
        (root / "data/casos" / cid).mkdir(parents=True, exist_ok=True)
        (root / "data/casos" / cid / "metodologia.json").write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
        feitos.append(cid)
    print("metodologia:", ", ".join(feitos) or "nenhum caso", f"· sem texto ainda: {len([c for c in casos if c not in met])} casos")
    return 0


if __name__ == "__main__":
    sys.exit(main())
