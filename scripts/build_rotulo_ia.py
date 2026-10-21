"""Rótulo de IA nas campanhas → data/ia/rotulo.json (agregados e listas de conteúdo de contas públicas).

Entradas: ODI_INTERNO_DIR/ia/rotulo_coleta.json (collect_rotulo_ia.py; privado) e data/checagens/checagens.json (checagens que tratam de IA).
"""
from __future__ import annotations

import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from net import now_utc  # noqa: E402

MIN_PUBLICO = 10000  # mesma regra dos casos: abaixo disso, perfil de pessoa comum (LGPD)
ORDEM = ["Lula", "Flávio Bolsonaro"]  # Lula primeiro por padrão do Atlas
# "IA" só em maiúsculas: em minúsculas, "ia" é o verbo ir ("ia votar") e trazia checagens sem relação com IA (19/10)
TERMOS_IA = {"IA ou inteligência artificial": re.compile(r"\bIA\b|[Ii]ntelig[eê]ncia [Aa]rtificial"),
             "deepfake": re.compile(r"deep ?fake", re.I),
             "montagem, manipulação ou edição": re.compile(r"\bmontage|\bmanipula|\beditad|\balterad", re.I)}


def pct(n, d):
    return round(100 * n / d, 1) if d else None


def ordenar(d: dict) -> dict:
    return {k: d[k] for k in sorted(d, key=lambda k: (k not in ORDEM, ORDEM.index(k) if k in ORDEM else 0, k))}


def youtube(y: dict | None) -> dict | None:
    if not y:
        return None
    vs = y["videos"]
    camp = [v for v in vs if v["origem"] == "canal da candidatura"]
    por = defaultdict(list)
    for v in camp:
        por[v["candidato"]].append(v)
    res = {c: {"videos": len(x), "campo_presente": sum(v["campo_presente"] for v in x), "declarados": sum(bool(v["sintetico_declarado"]) for v in x),
               "pct": pct(sum(bool(v["sintetico_declarado"]) for v in x), len(x))} for c, x in por.items()}
    deb = [v for v in vs if v["origem"] == "vídeo sobre o debate"]
    lista = sorted([{k: v[k] for k in ("id", "candidato", "canal", "titulo", "publicado_em", "origem")} for v in vs if v["sintetico_declarado"]],
                   key=lambda v: v["publicado_em"] or "", reverse=True)
    return {"lidos": len(vs), "campo_presente": sum(v["campo_presente"] for v in vs), "declarados": sum(bool(v["sintetico_declarado"]) for v in vs),
            "por_candidato": ordenar(res),
            "debate": {"videos": len(deb), "declarados": sum(bool(v["sintetico_declarado"]) for v in deb)},
            "lista": lista,
            "nota": "Campo status.containsSyntheticMedia da YouTube Data API: declaração do próprio canal ao publicar. Vídeo sem a "
                    "declaração não quer dizer vídeo sem IA; quer dizer que o canal não declarou."}


def tiktok(t: dict | None) -> dict | None:
    if not t:
        return None
    vs = t["videos"]
    por = defaultdict(list)
    for v in vs:
        por[v["candidato"] or "vídeos de qualquer conta nas hashtags " + ", ".join(sorted({o.split(" ", 1)[1] for o in (x.get("origem") or "" for x in vs) if o.startswith("hashtag")}))].append(v)
    campos = Counter(c for v in vs for c in v["campos_ia"])
    return {"videos": len(vs), "rotulados": sum(v["rotulo_ia"] for v in vs),
            "por_candidato": ordenar({c: {"videos": len(x), "perfis": len({v["perfil"] for v in x}), "rotulados": sum(v["rotulo_ia"] for v in x),
                                          "pct": pct(sum(v["rotulo_ia"] for v in x), len(x))} for c, x in por.items()}),
            "perfis": t["perfis"], "campos_vistos": campos.most_common(),
            # só contas com MIN_PUBLICO+ seguidores aparecem com nome e link; as demais (pessoas comuns) entram só na contagem
            "lista": sorted([{k: v.get(k) for k in ("id", "perfil", "candidato", "origem", "publicado_em", "legenda", "url", "campos_ia", "seguidores", "capa_url")}
                             for v in vs if v["rotulo_ia"] and (v.get("seguidores") or 0) >= MIN_PUBLICO],
                            key=lambda v: v["publicado_em"] or "", reverse=True),
            "rotulados_contas_pequenas": sum(1 for v in vs if v["rotulo_ia"] and (v.get("seguidores") or 0) < MIN_PUBLICO),
            "min_seguidores_publico": MIN_PUBLICO,
            "nota": "Campos lidos do JSON que a página pública do TikTok entrega (sem login). O TikTok não documenta esses campos; "
                    "a lista de campos vistos fica no arquivo para conferência."}


def capas(root: Path, lista: list[dict], baixar=None) -> None:
    """Miniatura de cada vídeo rotulado de conta pública: data/ia/miniaturas/tiktok_<id>.jpg (320 px). A capa vem da URL que a
    página da hashtag entregou (expira em horas; por isso o build roda logo após a coleta) ou, se faltar ou falhar, do oEmbed
    público do TikTok (thumbnail_url). Não rebaixa o que já existe. Sem capa: o campo fica vazio e a página mostra ⛔."""
    import urllib.parse
    if baixar is None:
        import build_criativos_meta as bcm
        baixar = bcm.miniatura
    pasta = root / "data/ia/miniaturas"
    pasta.mkdir(parents=True, exist_ok=True)
    for v in lista:
        arq = pasta / f"tiktok_{v['id']}.jpg"
        if not arq.exists():
            urls = [v.get("capa_url")]
            try:
                from net import get_json
                urls.append((get_json("https://www.tiktok.com/oembed?url=" + urllib.parse.quote(v["url"], safe="")) or {}).get("thumbnail_url"))
            except Exception:  # noqa: BLE001
                pass
            for u in [u for u in urls if u]:
                if baixar(u, arq):
                    break
        v["miniatura"] = f"data/ia/miniaturas/{arq.name}" if arq.exists() else None
        v.pop("capa_url", None)


def checagens(root: Path) -> dict | None:
    p = root / "data/checagens/checagens.json"
    if not p.exists():
        return None
    d = json.loads(p.read_text(encoding="utf-8"))
    hits = []
    for x in d["itens"]:
        t = f"{x.get('afirmacao') or ''} {x.get('titulo') or ''}"
        termos = [k for k, rx in TERMOS_IA.items() if rx.search(t)]
        if termos:
            hits.append({**x, "termos_ia": termos})
    por_cand = {c: sum(c in x["candidatos"] for x in hits) for c in ORDEM}
    mes = Counter((x.get("data_checagem") or "sem data")[:7] for x in hits)
    return {"total_base": len(d["itens"]), "sobre_ia": len(hits), "pct": pct(len(hits), len(d["itens"])),
            "por_termo": {k: sum(k in x["termos_ia"] for x in hits) for k in TERMOS_IA}, "citam_candidato": por_cand,
            "por_agencia": Counter(x["agencia"] for x in hits).most_common(), "por_mes": sorted(mes.items()),
            "por_rotulo": Counter(x.get("grupo_rotulo") or x.get("rotulo") for x in hits).most_common(),
            "lista": [{k: x.get(k) for k in ("data_checagem", "agencia", "rotulo", "titulo", "afirmacao", "url", "candidatos", "termos_ia")} for x in hits],
            "coletado_em_utc": d.get("coletado_em_utc"),
            "nota": "Checagens da base do Google Fact Check (60 dias) cujo título ou afirmação cita IA, deepfake, montagem, manipulação ou edição. "
                    "Busca por palavras: uma checagem pode citar 'montagem' sem envolver IA."}


def main(argv=None) -> int:
    root = Path(argv[0]) if argv else Path(".")
    from collect_rotulo_ia import arquivo_coleta
    col = arquivo_coleta()
    c = json.loads(col.read_text(encoding="utf-8")) if col.exists() else {}
    out = {"schema_version": 1, "gerado_em_utc": now_utc(), "coletado_em_utc": c.get("coletado_em_utc"),
           "youtube": youtube(c.get("youtube")), "tiktok": tiktok(c.get("tiktok")), "instagram": c.get("instagram"),
           "checagens": checagens(root), "erros": c.get("erros", []),
           "regra_tse": "Res. TSE nº 23.610/2019, alterada pela Res. nº 23.755/2026: conteúdo sintético na propaganda, quando permitido, "
                        "deve ser informado de modo explícito (art. 9º-B)."}
    (root / "data/ia").mkdir(parents=True, exist_ok=True)
    if out["tiktok"]:
        capas(root, out["tiktok"]["lista"])
    (root / "data/ia/rotulo.json").write_text(json.dumps(out, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    y, t, k = out["youtube"] or {}, out["tiktok"] or {}, out["checagens"] or {}
    print(f"rótulo de IA: YouTube {y.get('declarados')} declarados de {y.get('lidos')} (campo presente em {y.get('campo_presente')}) · "
          f"TikTok {t.get('rotulados')} rotulados de {t.get('videos')} · checagens sobre IA {k.get('sobre_ia')} de {k.get('total_base')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
