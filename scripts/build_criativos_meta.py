#!/usr/bin/env python3
"""Criativos dos anúncios da Meta com maior alcance, com miniatura (página "Anúncios pagos").

Entrada: o bruto mais recente da coleta via Apify no repositório privado (ODI_INTERNO_DIR/meta/anuncios/apify_*.jsonl.gz).
Para cada busca (candidato), os N anúncios de maior alcance (piso de impressões) da última coleta: baixa a imagem de prévia
(imagem, primeiro quadro do vídeo ou primeiro cartão), reduz para 320 px de largura (JPEG) e grava em
data/meta/miniaturas/<id>.jpg — os links da Meta (fbcdn) expiram em dias, por isso a cópia reduzida.
Saída: data/meta/criativos.json (texto até 400 caracteres, título, página, quem pagou, datas, faixas, link da Biblioteca).
Anúncios políticos são públicos na Biblioteca de Anúncios; a cópia reduzida serve à documentação da pesquisa.
"""
from __future__ import annotations

import glob
import gzip
import io
import json
import os
import sys
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from collect_meta_anuncios_apify import faixa_de, iso  # noqa: E402
from net import now_utc  # noqa: E402

POR_CONSULTA = 24
LARGURA = 320


def previa(snap: dict) -> str | None:
    for im in snap.get("images") or []:
        u = im.get("resized_image_url") or im.get("original_image_url")
        if u:
            return u
    for v in snap.get("videos") or []:
        if v.get("video_preview_image_url"):
            return v["video_preview_image_url"]
    for c in snap.get("cards") or []:
        u = c.get("resized_image_url") or c.get("video_preview_image_url") or c.get("original_image_url")
        if u:
            return u
    return None


def texto(snap: dict) -> str:
    b = snap.get("body") or {}
    t = b.get("text") if isinstance(b, dict) else str(b or "")
    if not t or "{{" in t:  # DCO: texto em cartões
        t = next(((c.get("body") or "") for c in snap.get("cards") or [] if c.get("body")), t or "")
    return " ".join(str(t or "").split())[:400]


def piso_impressoes(x: dict) -> int:
    f = faixa_de((x.get("impressions_with_index") or {}).get("impressions_text")) or {}
    return int(f.get("lower_bound") or 0)


def miniatura(url: str, destino: Path) -> bool:
    from PIL import Image
    try:
        with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"}), timeout=30) as r:
            im = Image.open(io.BytesIO(r.read())).convert("RGB")
    except Exception:  # noqa: BLE001
        return False
    if im.width > LARGURA:
        im = im.resize((LARGURA, round(im.height * LARGURA / im.width)))
    im.save(destino, "JPEG", quality=72, optimize=True)
    return True


def main(argv=None) -> int:
    root = Path(".")
    interno = os.environ.get("ODI_INTERNO_DIR")
    arqs = sorted(glob.glob(str(Path(interno or "/nao-existe") / "meta/anuncios/apify_*.jsonl.gz")))
    if not arqs:
        print("⛔ sem bruto da coleta da Meta no repositório privado")
        return 1
    xs = [json.loads(l) for l in gzip.open(arqs[-1], "rt", encoding="utf-8")]
    pasta = root / "data/meta/miniaturas"
    pasta.mkdir(parents=True, exist_ok=True)
    out = {"schema_version": 1, "gerado_em_utc": now_utc(), "fonte_bruto": Path(arqs[-1]).name,
           "metodo": (f"Os {POR_CONSULTA} anúncios de maior alcance (piso da faixa de impressões informada pela Meta) de cada busca na "
                      "última coleta. Miniatura: cópia reduzida da prévia (imagem ou primeiro quadro do vídeo); texto até 400 caracteres. "
                      "Link para o anúncio na Biblioteca de Anúncios da Meta."), "consultas": {}}
    usados = set()
    for q in sorted({x.get("_consulta") for x in xs if x.get("_consulta")}):
        cand = sorted((x for x in xs if x.get("_consulta") == q and x.get("ad_archive_id")), key=lambda x: -piso_impressoes(x))
        lista, vistos = [], set()
        for x in cand:
            if len(lista) >= POR_CONSULTA:
                break
            aid = str(x["ad_archive_id"])
            if aid in vistos:
                continue
            vistos.add(aid)
            snap = x.get("snapshot") or {}
            u = previa(snap)
            arq = pasta / f"{aid}.jpg"
            ok = arq.exists() or (bool(u) and miniatura(u, arq))
            if ok:
                usados.add(arq.name)
            g = faixa_de(x.get("spend")) or {}
            i = faixa_de((x.get("impressions_with_index") or {}).get("impressions_text")) or {}
            lista.append({"id": aid, "pagina": x.get("page_name") or snap.get("page_name") or "", "pago_por": snap.get("byline") or "",
                          "formato": snap.get("display_format") or "", "titulo": " ".join(str(snap.get("title") or "").split())[:140],
                          "texto": texto(snap), "inicio": iso(x.get("start_date"))[:10], "fim": iso(x.get("end_date"))[:10],
                          "ativo": bool(x.get("is_active")), "gasto": g, "impressoes": i,
                          "plataformas": [str(p).lower() for p in x.get("publisher_platform") or []],
                          "miniatura": f"data/meta/miniaturas/{aid}.jpg" if ok else None,
                          "link": f"https://www.facebook.com/ads/library/?id={aid}"})
        out["consultas"][q] = lista
        print(f"{q}: {len(lista)} criativos, {sum(1 for c in lista if c['miniatura'])} com miniatura")
    for f in pasta.glob("*.jpg"):  # mantém só as miniaturas em uso
        if f.name not in usados:
            f.unlink()
    (root / "data/meta/criativos.json").write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
