#!/usr/bin/env python3
"""Caso 018 "Antigo como atual": circulação NA ÉPOCA × AGORA de conteúdos antigos recirculados depois do 2º turno.

Pedido do responsável (30/10/2026, 17h33): Haddad em Davos (jan/2023) usado contra as denúncias de listas de boicote; vídeo de greve
de professores em Sergipe apresentado como reação a corte na educação; reportagem da CNN de jul/2024 apresentada como corte de
R$ 6 bilhões depois da eleição. "Os vídeos dessa data devem trazer a visão do vídeo naquele momento"; "repercussão na época e hoje
de forma comparativa"; "acompanhar a veiculação por canal e a visão antes e depois".

O YouTube não informa visualizações passadas de um vídeo (só o total de hoje). O "naquele momento" é reconstruído com o que tem data:
  - vídeos originais (YouTube, grátis): total de hoje + comentários por mês desde a publicação (cada comentário tem data) e quantos
    vieram na época × depois de 25/10/2026; comentários só no privado, público só contagens;
  - vídeos sobre o tema por janela (YouTube, grátis): quantos foram publicados na época × desde 25/10/2026 e quantas visualizações têm hoje;
  - Google Trends (grátis): semanal desde 2023-01-01;
  - Google Notícias (grátis): títulos da época × de agora;
  - X na época (pago, conta 1, teto `teto_epoca_x_usd` do caso): as mesmas buscas na janela da época, para comparar com a coleta de agora.
Saída: data/casos/018/antes_depois.json. Uso: python scripts/caso_antigo_atual.py [--sem-x] [--sem-trends]
"""
from __future__ import annotations

import csv
import gzip
import json
import os
import sys
import urllib.parse
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from caso_joice import detalhes, yt  # noqa: E402
from collect_comentarios_youtube import CAMPOS, linhas_da_conversa  # noqa: E402
from net import now_utc  # noqa: E402

CASO = "018"
CORTE = "2026-10-25"
BUSCAS_YT = {
    "A": {"epoca": ("2023-01-15", "2023-02-28"), "q": ["Haddad boicote", "Haddad Davos palito de fósforo", "Haddad não compro palito"]},
    "B": {"epoca": None, "q": ["greve professores Sergipe"]},
    "C": {"epoca": ("2024-07-29", "2024-08-15"), "q": ["congelamento 15 bilhões saúde educação", "Lula corta 6 bilhões saúde educação"]},
}
X_EPOCA = {
    "A": "Haddad (boicote OR boicotar OR \"palito de fósforo\" OR \"palito de fosforo\" OR Davos OR \"não compro\") since:2023-01-15 until:2023-03-01",
    "C": "(\"15 bilhões\" OR \"15 bi\" OR congelamento OR bloqueio) (saúde OR educação) (Haddad OR Lula OR governo) since:2024-07-29 until:2024-08-16",
}
TRENDS = ["Haddad boicote", "Haddad Davos", "corte saúde educação", "greve professores Sergipe"]


def mes(iso: str) -> str:
    return (iso or "")[:7]


def comentarios(key: str, vid: str, priv: Path, erros: list, paginas: int = 40) -> list[dict]:
    q = lambda **k: {**k, "key": key}  # noqa: E731
    rows, tok, agora = [], None, now_utc()
    meta = {"video_id": vid, "candidate_id": "", "channel_id": ""}
    for _ in range(paginas):
        p = q(part="snippet,replies", videoId=vid, maxResults=100, order="time", textFormat="plainText")
        if tok:
            p["pageToken"] = tok
        try:
            r = yt("commentThreads", **p)
        except RuntimeError as e:
            erros.append(f"comentários {vid}: {e}")
            break
        rows += [l for it in r.get("items", []) for l in linhas_da_conversa(it, meta, "caso018", agora)]
        tok = r.get("nextPageToken")
        if not tok:
            break
    arq = priv / "youtube_comentarios.csv.gz"
    antigos = {r["comment_id"]: r for r in csv.DictReader(gzip.open(arq, "rt", encoding="utf-8"), delimiter=";")} if arq.exists() else {}
    antigos.update({r["comment_id"]: r for r in rows})
    with gzip.open(arq, "wt", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, CAMPOS, delimiter=";", lineterminator="\n", extrasaction="ignore")
        w.writeheader()
        w.writerows(antigos.values())
    return [r for r in antigos.values() if r.get("video_id") == vid]


def busca_yt(key: str, q: str, depois: str, antes: str | None, erros: list) -> dict:
    p = {"part": "snippet", "q": q, "type": "video", "maxResults": 50, "regionCode": "BR", "relevanceLanguage": "pt", "order": "viewCount",
         "publishedAfter": depois + "T00:00:00Z", "key": key}
    if antes:
        p["publishedBefore"] = antes + "T23:59:59Z"
    try:
        r = yt("search", **p)
    except RuntimeError as e:
        erros.append(f"busca {q}: {e}")
        return {"q": q, "erro": str(e)[:120]}
    ids = [it["id"]["videoId"] for it in r.get("items", []) if it.get("id", {}).get("videoId")]
    vs = detalhes(ids, lambda **k: {**k, "key": key}, erros) if ids else []
    vs.sort(key=lambda v: -(v["visualizacoes"] or 0))
    return {"q": q, "janela": [depois, antes], "total_estimado_youtube": (r.get("pageInfo") or {}).get("totalResults"), "lidos": len(vs),
            "visualizacoes_hoje": sum(v["visualizacoes"] or 0 for v in vs),
            "videos": [{k: v[k] for k in ("id", "titulo", "canal", "publicado_em", "visualizacoes", "curtidas", "comentarios")} for v in vs[:15]]}


def x_epoca(caso: dict, priv: Path, erros: list) -> dict:
    from collect_casos import norm
    from collect_meta_apify import run_actor
    tok = os.environ.get(caso["segredo"], "").strip()
    teto = caso.get("teto_epoca_x_usd", 0)
    man_f = priv / "x_epoca_manifesto.json"
    man = json.loads(man_f.read_text(encoding="utf-8")) if man_f.exists() else {"runs": [], "gasto_usd": 0.0}
    out = {}
    for ep, q in X_EPOCA.items():
        if any(r["episodio"] == ep for r in man["runs"]):
            continue  # a janela da época é fixa: lida uma vez só
        sobra = round(teto - man["gasto_usd"], 4)
        n = min(1500, int(sobra * 0.9 / 0.00015 / max(1, len(X_EPOCA)))) if sobra > 0.02 else 0
        if not tok or n < 20:
            erros.append(f"X época {ep}: sem token ou sem teto (sobra US$ {sobra})")
            continue
        try:
            run, itens = run_actor(tok, "xquik~x-tweet-scraper", {"searchTerms": [q], "maxItems": n, "queryType": "Latest"}, round(0.00015 * n * 1.3 + 0.02, 4))
        except Exception as e:  # noqa: BLE001
            erros.append(f"X época {ep}: {type(e).__name__}")
            continue
        gasto = float((run or {}).get("usageTotalUsd") or 0) or round(0.00015 * len(itens or []), 4)
        with gzip.open(priv / f"x_epoca_{ep}.jsonl.gz", "wt", encoding="utf-8") as f:
            for x in itens or []:
                f.write(json.dumps(x, ensure_ascii=False) + "\n")
        man["runs"].append({"episodio": ep, "busca": q, "run": (run or {}).get("id"), "pedidos": n, "itens": len(itens or []), "custo_usd": gasto, "em_utc": now_utc()})
        man["gasto_usd"] = round(man["gasto_usd"] + gasto, 4)
    man_f.write_text(json.dumps(man, ensure_ascii=False, indent=1), encoding="utf-8")
    for r in man["runs"]:
        f = priv / f"x_epoca_{r['episodio']}.jsonl.gz"
        rows = []
        if f.exists():
            for linha in gzip.open(f, "rt", encoding="utf-8"):
                try:
                    x = norm("x", json.loads(linha), r["episodio"], "")
                except ValueError:
                    continue
                if x:
                    rows.append(x)
        num = lambda v: int(v) if str(v or "").isdigit() else 0  # noqa: E731
        por_dia = Counter((x["publicado_em"] or "")[:10] for x in rows)
        grandes = Counter()
        for x in rows:
            if num(x["seguidores"]) >= 10000:
                grandes[(x["conta"], num(x["seguidores"]))] += 1
        out[r["episodio"]] = {"busca": r["busca"], "run": r["run"], "pedidos": r["pedidos"], "lidos": len(rows), "no_limite": r["itens"] >= r["pedidos"],
                              "curtidas": sum(num(x["curtidas"]) for x in rows), "visualizacoes": sum(num(x["visualizacoes"]) for x in rows),
                              "por_dia": dict(sorted(por_dia.items())),
                              "contas_10mil": [{"conta": c, "seguidores": s, "posts": k} for (c, s), k in grandes.most_common(10)]}
    return {"gasto_usd": man["gasto_usd"], "teto_usd": teto, "episodios": out}


def main(argv=None) -> int:
    argv = sys.argv[1:] if argv is None else list(argv)
    caso = next(c for c in json.loads(Path("data/config/casos.json").read_text(encoding="utf-8"))["casos"] if c["id"] == CASO)
    key = os.environ.get("YOUTUBE_API_KEY", "")
    interno = os.environ.get("ODI_INTERNO_DIR")
    priv = Path(interno) / "casos" / CASO if interno else Path(os.environ.get("RUNNER_TEMP", "/tmp")) / "caso018"
    priv.mkdir(parents=True, exist_ok=True)
    erros: list[str] = []
    out = {"caso": CASO, "gerado_em_utc": now_utc(), "corte": CORTE,
           "aviso": "O YouTube só informa as visualizações de hoje; a época é reconstruída por comentários datados, vídeos publicados em cada janela, Trends, notícias e a busca do X na janela da época.",
           "episodios": {}}
    for ep, info in caso["episodios"].items():
        reg = {"titulo": info["titulo"], "janela_epoca": info.get("janela_epoca"), "fontes": info.get("fontes", [])}
        if key:
            vids = []
            for v in detalhes(info.get("videos_youtube", []), lambda **k: {**k, "key": key}, erros):
                cs = comentarios(key, v["id"], priv, erros)
                pm = Counter(mes(c.get("publicado_em")) for c in cs)
                pub_mes = mes(v["publicado_em"])
                vids.append({**{k: v[k] for k in ("id", "titulo", "canal", "publicado_em", "visualizacoes", "curtidas", "comentarios")},
                             "comentarios_lidos": len(cs), "comentarios_por_mes": dict(sorted(pm.items())),
                             "comentarios_na_epoca": sum(n for m, n in pm.items() if pub_mes <= m <= _mais(pub_mes, 1)),
                             "comentarios_desde_corte": sum(1 for c in cs if (c.get("publicado_em") or "") >= CORTE)})
            reg["videos_originais"] = vids
            bq = BUSCAS_YT.get(ep, {})
            reg["youtube_por_janela"] = {"agora": [busca_yt(key, q, CORTE, None, erros) for q in bq.get("q", [])]}
            if bq.get("epoca"):
                a, b = bq["epoca"]
                reg["youtube_por_janela"]["epoca"] = [busca_yt(key, q, a, b, erros) for q in bq.get("q", [])]
        out["episodios"][ep] = reg
    if "--sem-trends" not in argv:
        try:
            from collect_trends import Trends
            import datetime as dt
            t = Trends(pause=5)
            janela = f"2023-01-01 {now_utc()[:10]}"
            ws = {w["id"]: w for w in t.explore(TRENDS, janela, "BR")}
            ts = t.widget("multiline", ws["TIMESERIES"])
            out["trends"] = {"janela": janela, "termos": TRENDS, "pontos": [{"t": dt.datetime.fromtimestamp(int(p["time"]), dt.timezone.utc).strftime("%Y-%m-%d"),
                                                                            "v": dict(zip(TRENDS, p.get("value") or []))} for p in ts["default"]["timelineData"]]}
        except Exception as e:  # noqa: BLE001
            out["trends"] = {"erro": f"{type(e).__name__}: {str(e)[:160]}"}
    out["noticias"] = noticias()
    if "--sem-x" not in argv:
        out["x_epoca"] = x_epoca(caso, priv, erros)
    out["erros"] = erros
    dest = Path("data/casos") / CASO
    dest.mkdir(parents=True, exist_ok=True)
    (dest / "antes_depois.json").write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    for ep, r in out["episodios"].items():
        print(f"{ep}: " + " · ".join(f"{v['id']} {v['visualizacoes']} vis, comentários época {v['comentarios_na_epoca']} × desde 25/10 {v['comentarios_desde_corte']}" for v in r.get("videos_originais", []))
              + " · " + " · ".join(f"{k}: " + ", ".join(f"{b['q']} {b.get('lidos')} vídeos {b.get('visualizacoes_hoje')} vis" for b in v) for k, v in (r.get("youtube_por_janela") or {}).items()))
    print("X época:", json.dumps({k: (v["lidos"], v["no_limite"]) for k, v in (out.get("x_epoca") or {}).get("episodios", {}).items()}), "· trends:", "ok" if (out.get("trends") or {}).get("pontos") else out.get("trends"),
          "· notícias:", {k: len(v) for k, v in out["noticias"].items()}, "· erros:", erros[:5])
    return 0


def _mais(m: str, k: int) -> str:
    a, b = int(m[:4]), int(m[5:7]) + k
    while b > 12:
        a, b = a + 1, b - 12
    return f"{a:04d}-{b:02d}"


def noticias() -> dict:
    from collect_google_busca import RSS, parse_rss
    from net import open_url, read_body
    consultas = {"A_epoca": "Haddad Davos boicote after:2023-01-15 before:2023-03-01", "A_agora": "Haddad boicote Davos after:2026-10-24",
                 "B_agora": "vídeo greve professores Sergipe after:2026-10-24", "C_epoca": "congelamento 15 bilhões saúde educação after:2024-07-28 before:2024-08-16",
                 "C_agora": "corte 6 bilhões saúde educação falso after:2026-10-24"}
    out = {}
    for k, q in consultas.items():
        try:
            with open_url(RSS + "?" + urllib.parse.urlencode({"q": q, "hl": "pt-BR", "gl": "BR", "ceid": "BR:pt-419"}), timeout=40) as r:
                its = parse_rss(read_body(r))
            out[k] = [{x: i.get(x) for x in ("titulo", "link", "veiculo", "data_publicacao")} for i in its][:40]
        except Exception as e:  # noqa: BLE001
            out[k] = [{"erro": type(e).__name__}]
    return out


if __name__ == "__main__":
    sys.exit(main())
