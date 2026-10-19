"""Checagens publicadas (ClaimReview) sobre os candidatos e o debate — Google Fact Check Tools API (grátis).

Fonte: https://factchecktools.googleapis.com/v1alpha1/claims:search — agrega as checagens que as agências publicam
no formato ClaimReview (schema.org). O Atlas não dá veredito: mostra o que cada agência checou, com o rótulo dela
("falso", "enganoso"…), a data e o link. Chave do Google Cloud por segredo (FACTCHECK_API_KEY; se faltar, a mesma
chave do YouTube — vale se a API estiver ativa no mesmo projeto e a chave não for restrita a outra API).

Saída pública: data/checagens/checagens.json (texto da afirmação como a agência publicou; quem disse é figura
pública ou "redes sociais"). Uso: python scripts/collect_checagens.py [--dias 60]
"""
from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.parse
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from net import get_json, now_utc  # noqa: E402

URL = "https://factchecktools.googleapis.com/v1alpha1/claims:search"
CONSULTAS = ["Lula", "Flávio Bolsonaro", "debate Band", "debate presidencial", "eleições 2026", "urna eletrônica"]
DEBATE_INICIO = "2026-10-18"  # dia do debate do 2º turno (Band/Estadão, 20h)
MAX_PAGINAS = 5


def norm(s: str) -> str:
    import unicodedata
    return "".join(c for c in unicodedata.normalize("NFD", (s or "").lower()) if unicodedata.category(c) != "Mn")


def candidato(texto: str, quem: str) -> list[str]:
    t = norm(f"{texto} {quem}")
    out = []
    if "lula" in t:
        out.append("Lula")
    if "flavio" in t:
        out.append("Flávio Bolsonaro")
    return out


def achatar(claims: list[dict], consulta: str) -> list[dict]:
    out = []
    for c in claims or []:
        for r in c.get("claimReview") or []:
            pub = r.get("publisher") or {}
            out.append({"afirmacao": " ".join(str(c.get("text") or "").split()), "quem_disse": c.get("claimant"),
                        "data_afirmacao": (c.get("claimDate") or "")[:10] or None,
                        "agencia": pub.get("name") or pub.get("site"), "site": pub.get("site"),
                        "titulo": r.get("title"), "url": r.get("url"), "data_checagem": (r.get("reviewDate") or "")[:10] or None,
                        "rotulo": r.get("textualRating"), "idioma": r.get("languageCode"), "consulta": [consulta]})
    return out


def buscar(chave: str, consulta: str, dias: int, erros: list[str]) -> list[dict]:
    itens, token = [], None
    for _ in range(MAX_PAGINAS):
        q = {"query": consulta, "languageCode": "pt", "maxAgeDays": dias, "pageSize": 100, "key": chave}
        if token:
            q["pageToken"] = token
        try:
            d = get_json(URL + "?" + urllib.parse.urlencode(q))
        except urllib.error.HTTPError as e:
            corpo = e.read().decode("utf-8", "replace")[:300] if hasattr(e, "read") else ""
            erros.append(f"{consulta}: HTTP {e.code} {corpo}")
            break
        except Exception as e:  # noqa: BLE001
            erros.append(f"{consulta}: {type(e).__name__} {str(e)[:200]}")
            break
        itens += achatar(d.get("claims"), consulta)
        token = d.get("nextPageToken")
        if not token:
            break
    return itens


def juntar(itens: list[dict]) -> list[dict]:
    por = {}
    for x in itens:
        k = x["url"] or (x["agencia"], x["afirmacao"])
        if k in por:
            por[k]["consulta"] = sorted(set(por[k]["consulta"]) | set(x["consulta"]))
        else:
            por[k] = dict(x)
    out = list(por.values())
    for x in out:
        x["candidatos"] = candidato(x["afirmacao"] + " " + (x["titulo"] or ""), x["quem_disse"] or "")
        x["desde_o_debate"] = bool(x["data_checagem"] and x["data_checagem"] >= DEBATE_INICIO)
    out.sort(key=lambda x: (x["data_checagem"] or "", x["agencia"] or ""), reverse=True)
    return out


def main(argv=None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    dias = int(argv[argv.index("--dias") + 1]) if "--dias" in argv else 60
    chave = (os.environ.get("FACTCHECK_API_KEY") or os.environ.get("YOUTUBE_API_KEY") or "").strip()
    pasta = Path("data/checagens")
    pasta.mkdir(parents=True, exist_ok=True)
    if not chave:
        print("⛔ falta a chave do Google Cloud (FACTCHECK_API_KEY ou YOUTUBE_API_KEY)")
        return 1
    erros, brutos = [], []
    for c in CONSULTAS:
        r = buscar(chave, c, dias, erros)
        print(f"consulta '{c}': {len(r)} checagens")
        brutos += r
    itens = juntar(brutos)
    ag = Counter(x["agencia"] for x in itens)
    rot = Counter(norm(x["rotulo"] or "") for x in itens)
    out = {"schema_version": 1, "coletado_em_utc": now_utc(), "fonte": "Google Fact Check Tools API (claims:search, ClaimReview)",
           "consultas": CONSULTAS, "idioma": "pt", "janela_dias": dias, "debate_inicio": DEBATE_INICIO,
           "total": len(itens), "desde_o_debate": sum(x["desde_o_debate"] for x in itens),
           "por_agencia": ag.most_common(), "rotulos": rot.most_common(30), "erros": erros,
           "status": "ok" if itens else ("⛔ " + erros[0] if erros else "⛔ nenhuma checagem encontrada"),
           "nota": "Rótulos e textos são das agências de checagem; o Atlas não dá veredito. A API só traz checagens marcadas em ClaimReview.",
           "itens": itens}
    (pasta / "checagens.json").write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"checagens: {len(itens)} (desde o debate {out['desde_o_debate']}) · agências {ag.most_common(8)} · erros {erros[:2]}")
    return 0 if itens else 1


if __name__ == "__main__":
    raise SystemExit(main())
