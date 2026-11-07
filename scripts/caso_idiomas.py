#!/usr/bin/env python3
"""Caso 037 ("Faz o L"): contagem por família de termo e língua, e uso do bordão nos vídeos (só contagens).

Pedido do responsável (07/11/2026, 18h40): gráfico sobre os termos em outros idiomas ("Do the L", "Haz la L", "Fais le L",
"Mach das L", L.U.L.A.) e o "L" de "loser" no inglês, que pode ser ruído ou uso irônico e deve ficar separado.

Entrada: data/casos/037/busca.json (notícias, Trends) e, para os títulos dos vídeos, ODI_INTERNO_DIR/casos/037/busca_coleta.json.
Saída pública: data/casos/037/idiomas.json, só com contagens (nenhum título de canal pequeno sai do privado).
As regras de classificação estão no próprio arquivo de saída, para quem for citar poder reproduzir.
"""
from __future__ import annotations

import json
import os
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from net import now_utc  # noqa: E402

FAMILIAS = [  # (id, rótulo, língua, regex)
    ("pt_canonica", "\"faz o L\" / #FazOL", "português", r"\bfa[zs] o l\b|#fazol\b"),
    ("pt_ironica", "grafias irônicas (fazueli, fazuele, fazoele)", "português", r"fazu[eé]l+i|fazuele|fazoel[ei]"),
    ("pt_primeira", "\"fiz o L\" / \"fez o L\"", "português", r"\bfi[zs] o l\b|\bfez o l\b"),
    ("es", "\"haz la L\" / \"hace la L\" / \"haz el L\"", "espanhol", r"\bha(z|ce|cer) (la|el) l\b"),
    ("en", "\"do the L\" / \"make the L\"", "inglês", r"\b(do|make|doing|making) the l\b"),
    ("fr", "\"fais le L\" / \"faites le L\"", "francês", r"\bfai(s|tes) le l\b"),
    ("de", "\"mach das L\"", "alemão", r"\bmach das l\b"),
    ("lula_acronimo", "L.U.L.A. (Liga Universal da Luta Antifascista)", "várias", r"l\.u\.l\.a|liga universal da luta antifascista"),
]
LOSER = r"\bloser\b|\btake (an|the) l\b|\btook (an|the) l\b|\bl on (the|your) forehead"
USOS = [  # ordem importa: a primeira regra que casa define o uso
    ("internacional", "difusão internacional (o \"L\" no mundo)", r"mundo|global|world|internacional|esquerda pelo mundo|lenda global|exterior"),
    ("ironia", "ironia / oposição", r"fazu[eé]l+i|fazuele|fazoel|#?foralula|lula ?dr[aã]o|ladr[aã]o|arrependid|picanha|militont|comuna|chora|#direita|patriota|sosbrasil|#bolsonaro|leitoa|petista!|kkk"),
    ("campanha", "campanha / apoio (jingle, música)", r"jingle|m[uú]sica|lula 13|\b13\b|vira voto|cora[cç][aã]o grand|desenrola|faz o l e vem|lula livre|pra continuar"),
    ("noticia", "notícia / análise", r"'faz o l'|“faz o l”|\"faz o l\"|vereadora|imposto|ator|s[ií]mbolo|diz|afirma"),
]


def familia_de(txt: str) -> list[str]:
    t = txt.lower()
    return [f for f, _, _, rx in FAMILIAS if re.search(rx, t)]


def uso_de(txt: str) -> str:
    t = txt.lower()
    for u, _, rx in USOS:
        if re.search(rx, t):
            return u
    return "outro"


def main() -> int:
    root = Path(".")
    b = json.loads((root / "data/casos/037/busca.json").read_text(encoding="utf-8"))
    interno = os.environ.get("ODI_INTERNO_DIR")
    videos = []
    if interno and (Path(interno) / "casos/037/busca_coleta.json").exists():
        videos = (json.loads((Path(interno) / "casos/037/busca_coleta.json").read_text(encoding="utf-8")).get("youtube") or {}).get("videos") or []
    fam = {f: {"youtube": 0, "noticias": 0} for f, *_ in FAMILIAS}
    loser = {"youtube": 0, "noticias": 0}
    usos = defaultdict(Counter)
    for v in videos:
        txt = f"{v.get('titulo', '')} {v.get('descricao', '')}"
        for f in familia_de(txt):
            fam[f]["youtube"] += 1
        loser["youtube"] += bool(re.search(LOSER, txt.lower()))
        usos[(v.get("publicado_em") or "")[:4]][uso_de(v.get("titulo", ""))] += 1
    for n in b.get("noticias") or []:
        for f in familia_de(n.get("titulo", "")):
            fam[f]["noticias"] += 1
        loser["noticias"] += bool(re.search(LOSER, n.get("titulo", "").lower()))
    tr = (b.get("trends") or {}).get("variantes") or {}
    serie = tr.get("today 5-y") or []
    trends = {t: {"pico": max((p["v"].get(t, 0) for p in serie), default=None),
                  "semanas_com_interesse": sum(1 for p in serie if p["v"].get(t, 0) > 0), "semanas": len(serie)} for t in tr.get("termos", [])}
    out = {
        "gerado_em_utc": now_utc(), "caso": "037",
        "amostra": {"videos_youtube": len(videos), "noticias": len(b.get("noticias") or []),
                    "youtube_coletado_em": b.get("coletado_em_utc"), "universo": "⛔ desconhecido (YouTube e Google Notícias não informam o total)"},
        "familias": [{"id": f, "rotulo": r, "lingua": lg, "regex": rx, **fam[f]} for f, r, lg, rx in FAMILIAS],
        "loser": {"regex": LOSER, **loser, "nota": "Em inglês, \"take an L\" e o gesto do L na testa significam derrota (\"loser\"). "
                  "Contado à parte para não misturar com o L de Lula; nas buscas pagas, as traduções só entram com Lula/Brasil/Brazil."},
        "trends_brasil_5_anos": {"termos": trends, "nota": "Google Trends, Brasil, semanal, índice 0–100 relativo ao pico da consulta "
                                 "(os cinco termos na mesma consulta, então se comparam entre si). Por país: ⛔ (HTTP 429 na leitura de 06–07/11)."},
        "usos_youtube_por_ano": {a: dict(c) for a, c in sorted(usos.items())},
        "usos_regras": [{"id": u, "rotulo": r, "regex": rx} for u, r, rx in USOS] + [{"id": "outro", "rotulo": "outro / sem marca no título", "regex": ""}],
        "nota_usos": "Classificação automática pelo título do vídeo, por regras explícitas (a primeira que casa vale). É uma triagem: "
                     "a leitura manual dos vídeos de maior alcance confere o sentido antes de qualquer conclusão.",
        "fontes": ["data/casos/037/busca.json", "ODI_INTERNO_DIR/casos/037/busca_coleta.json (privado: títulos)"],
    }
    (root / "data/casos/037/idiomas.json").write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print("037 idiomas:", {f["id"]: (f["youtube"], f["noticias"]) for f in out["familias"]}, "loser", loser, dict(Counter(u for c in usos.values() for u in c.elements())))
    return 0


if __name__ == "__main__":
    sys.exit(main())
