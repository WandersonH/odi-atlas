#!/usr/bin/env python3
"""Carga diária do corpus na área do pesquisador (Supabase, tabela public.corpus) — C19.374, 10/11/2026.

Lê do privado ($ODI_INTERNO_DIR/casos/<id>/): itens.csv.gz (posts), youtube_comentarios.csv.gz e
instagram_comentarios.csv.gz. Envia por PostgREST (upsert por caso+fonte+item_id) com a chave de serviço, que vem
SÓ do ambiente (secret SUPABASE_SERVICE_ROLE_KEY no GitHub; nunca no código).

Proteções:
  - autor: só @conta com 10 mil seguidores ou mais; pessoa comum fica sem autor (e comentários nunca levam autor);
  - casos com anonimizar_publico_regex (020, criança): o texto vai com "[…]" no lugar do que identifica a criança;
  - nenhum link nem id de conta comum é enviado.
Triagem automática (não validada): ofensivo (HateBR ≥ 0,5) e ódio (BERTabaporu ≥ 0,5, alvo), quando o caso tem escores.

Uso: ODI_INTERNO_DIR=… SUPABASE_URL=… SUPABASE_SERVICE_ROLE_KEY=… python scripts/carregar_area_pesquisador.py [--caso 001] [--seco]
  --seco: não envia nada; só conta o que seria enviado.
"""
from __future__ import annotations

import argparse
import csv
import gzip
import json
import os
import re
import sys
import time
import urllib.request
from pathlib import Path

import emoji

csv.field_size_limit(10**9)
VAR = re.compile("[️\U0001F3FB-\U0001F3FF]")
LOTE = 500
MIN_SEG = 10_000


def casos_cfg() -> dict:
    d = json.load(open("data/config/casos.json", encoding="utf-8"))
    d = d if isinstance(d, list) else d.get("casos", list(d.values()))
    return {str(c["id"]): c for c in d}


def ler(f: Path):
    with gzip.open(f, "rt", encoding="utf-8", errors="ignore") as h:
        yield from csv.DictReader(h, delimiter=";")


def triagem(pasta: Path) -> dict:
    f = pasta / "intolerancia" / "escores.csv.gz"
    out = {}
    if not f.exists():
        return out
    for r in ler(f):
        alvos = [k.split(":", 1)[1] for k, v in r.items() if k.startswith("odio_") and v and float(v) >= 0.5]
        out[r["id"]] = (float(r.get("ofensividade_hatebr:True") or 0) >= 0.5, ", ".join(alvos) or None)
    return out


def emojis_de(t: str) -> list[str]:
    return sorted({VAR.sub("", e["emoji"]) for e in emoji.emoji_list(t)})


def linhas(cid: str, interno: Path, cfg: dict):
    pasta = interno / "casos" / cid
    mascara = re.compile(cfg["anonimizar_publico_regex"], re.I) if cfg.get("anonimizar_publico_regex") else None
    tri = triagem(pasta)
    limpa = (lambda t: mascara.sub("[…]", t)) if mascara else (lambda t: t)

    def base(item, rede, fonte, data, texto, autor=None, candidato=None):
        of, od = tri.get(item, (None, None))
        return {"caso": cid, "rede": rede, "fonte": fonte, "item_id": item, "publicado_em": data or None, "autor": autor,
                "texto": limpa(texto), "emojis": emojis_de(texto), "candidato": candidato, "ofensivo": of, "odio": od}

    f = pasta / "itens.csv.gz"
    if f.exists():
        for r in ler(f):
            t = (r.get("texto") or "").strip()
            if not t or not r.get("item_id"):
                continue
            try:
                seg = int(float(r.get("seguidores") or 0))
            except ValueError:
                seg = 0
            autor = f"@{r['conta']}" if seg >= MIN_SEG and r.get("conta") else None
            if autor and mascara and mascara.search(autor):
                autor = None
            yield base(r["item_id"], (r.get("rede") or "?").lower(), "post", r.get("publicado_em"), t, autor)
    f = pasta / "youtube_comentarios.csv.gz"
    if f.exists():
        for r in ler(f):
            t = (r.get("texto") or "").strip()
            if t and r.get("comment_id"):
                yield base(r["comment_id"], "youtube", "comentario", r.get("publicado_em"), t, candidato=r.get("candidate_id") or None)
    f = pasta / "instagram_comentarios.csv.gz"
    if f.exists():
        for r in ler(f):
            t = (r.get("texto") or "").strip()
            if t and r.get("id"):
                yield base(r["id"], "instagram", "comentario", r.get("criado_em_utc"), t)


def enviar(url: str, chave: str, lote: list[dict]):
    req = urllib.request.Request(f"{url}/rest/v1/corpus?on_conflict=caso,fonte,item_id", data=json.dumps(lote).encode(), method="POST",
                                 headers={"apikey": chave, "Authorization": f"Bearer {chave}", "Content-Type": "application/json",
                                          "Prefer": "resolution=merge-duplicates,return=minimal"})
    for tentativa in range(4):
        try:
            urllib.request.urlopen(req, timeout=120).read()
            return
        except Exception as e:  # noqa: BLE001
            if tentativa == 3:
                raise
            print(f"   nova tentativa ({e})")
            time.sleep(5 * (tentativa + 1))


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--caso")
    ap.add_argument("--seco", action="store_true")
    a = ap.parse_args(argv)
    interno = Path(os.environ.get("ODI_INTERNO_DIR", ""))
    if not (interno / "casos").is_dir():
        print("⛔ ODI_INTERNO_DIR sem casos/"); return 1
    url, chave = os.environ.get("SUPABASE_URL", "").rstrip("/"), os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")
    if not a.seco and not (url and chave):
        print("⛔ faltam SUPABASE_URL e SUPABASE_SERVICE_ROLE_KEY no ambiente (secrets do GitHub)"); return 1
    cfg = casos_cfg()
    ids = [a.caso] if a.caso else sorted(p.name for p in (interno / "casos").iterdir() if re.fullmatch(r"\d{3}", p.name))
    total = 0
    for cid in ids:
        lote, n, vistos = [], 0, set()
        for r in linhas(cid, interno, cfg.get(cid, {})):
            k = (r["fonte"], r["item_id"])
            if k in vistos:
                continue
            vistos.add(k)
            lote.append(r)
            n += 1
            if len(lote) >= LOTE:
                if not a.seco:
                    enviar(url, chave, lote)
                lote = []
        if lote and not a.seco:
            enviar(url, chave, lote)
        total += n
        print(f"{cid}: {n} textos {'contados' if a.seco else 'enviados'}")
    print(f"total: {total}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
