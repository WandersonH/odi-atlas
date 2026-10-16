#!/usr/bin/env python3
"""Caderno 05 (Buscas) — o que o Google mostra para cada candidato: 5 primeiros resultados e 3 mais recentes.

Google Custom Search JSON API (Programmable Search). Chave e mecanismo SÓ por variáveis de ambiente (segredos do
GitHub): GOOGLE_CSE_KEY e GOOGLE_CSE_CX. Erros não imprimem URL (contém a chave). 4 consultas por execução
(cota gratuita: 100/dia).
Saída: data/trends/google_busca.json (última coleta) e data/trends/google_busca_historico.csv (uma linha por resultado e dia).
"""
from __future__ import annotations

import csv
import json
import os
import sys
import urllib.error
import urllib.parse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from net import get_json, now_utc  # noqa: E402

API = "https://www.googleapis.com/customsearch/v1"
HCOLS = ["coletado_em", "candidate_id", "lista", "posicao", "titulo", "link", "dominio", "data_publicacao"]


def data_pub(item: dict) -> str:
    """Data de publicação quando a página informa (metatags de artigo); vazio se não houver."""
    for m in (item.get("pagemap") or {}).get("metatags") or []:
        for k in ("article:published_time", "og:published_time", "datepublished", "date", "publishdate", "pubdate", "dc.date"):
            if m.get(k):
                return str(m[k])[:25]
    return ""


def resultado(item: dict, pos: int) -> dict:
    return {"posicao": pos, "titulo": item.get("title", ""), "link": item.get("link", ""), "dominio": item.get("displayLink", ""),
            "trecho": (item.get("snippet") or "").replace("\n", " ")[:220], "data_publicacao": data_pub(item)}


def consultar(key: str, cx: str, q: str, n: int, extra: dict) -> tuple[list[dict], str | None]:
    params = {"key": key, "cx": cx, "q": q, "num": n, "gl": "br", "cr": "countryBR", "lr": "lang_pt", "hl": "pt-BR", **extra}
    try:
        d = get_json(f"{API}?{urllib.parse.urlencode(params)}", timeout=40)
    except urllib.error.HTTPError as e:
        corpo = ""
        try:
            corpo = json.loads(e.read().decode("utf-8", "replace")).get("error", {}).get("message", "")[:200]
        except Exception:  # noqa: BLE001
            pass
        return [], f"HTTP {e.code} {corpo}".strip()
    except Exception as e:  # noqa: BLE001 — a mensagem pode conter a URL com a chave
        return [], type(e).__name__
    return [resultado(it, i + 1) for i, it in enumerate(d.get("items") or [])], None


def main(argv=None) -> int:
    root = Path(".")
    cfg = json.loads((root / "data/config/google_busca.json").read_text(encoding="utf-8"))
    # a chave pode ser a mesma do YouTube (mesmo projeto do Google Cloud, com a Custom Search API ativada)
    key, cx = os.environ.get("GOOGLE_CSE_KEY") or os.environ.get("YOUTUBE_API_KEY"), (os.environ.get("GOOGLE_CSE_CX") or cfg.get("cx"))
    agora = now_utc()
    out = {"schema_version": 1, "coletado_em_utc": agora, "nota": cfg["nota"], "candidatos": {}, "erros": {}}
    d = root / "data/trends"
    if not key or not cx:
        falta = [n for n, v in (("chave (GOOGLE_CSE_KEY ou YOUTUBE_API_KEY)", key), ("ID do mecanismo de busca (GOOGLE_CSE_CX)", cx)) if not v]
        out["status"] = "⛔ falta no GitHub: " + " e ".join(falta)
        (d / "google_busca.json").write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
        print(out["status"])
        return 1
    for cid, c in cfg["consultas"].items():
        top, e1 = consultar(key, cx, c["q"], cfg["primeiros"], {})
        rec, e2 = consultar(key, cx, c["q"], cfg["recentes"], {"sort": "date", "dateRestrict": cfg["recentes_janela"]})
        out["candidatos"][cid] = {"nome": c["nome"], "consulta": c["q"], "primeiros": top, "recentes": rec}
        for lista, e in (("primeiros", e1), ("recentes", e2)):
            if e:
                out["erros"][f"{c['nome']} · {lista}"] = e
        print(f"{c['nome']}: {len(top)} primeiros, {len(rec)} recentes {e1 or ''} {e2 or ''}")
    ok = any(v["primeiros"] or v["recentes"] for v in out["candidatos"].values())
    out["status"] = "ok" if ok and not out["erros"] else ("⚠️ parcial" if ok else "⛔ nenhum resultado")
    (d / "google_busca.json").write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    hist = d / "google_busca_historico.csv"
    novo = not hist.exists()
    with open(hist, "a", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, HCOLS, delimiter=";", lineterminator="\n", extrasaction="ignore")
        if novo:
            w.writeheader()
        for cid, v in out["candidatos"].items():
            for lista in ("primeiros", "recentes"):
                for r in v[lista]:
                    w.writerow({"coletado_em": agora, "candidate_id": cid, "lista": lista, **r})
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
