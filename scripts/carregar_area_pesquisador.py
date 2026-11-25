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

Acervos gerais (24/11/2026): comentários e respostas nos canais das campanhas ("campanhas") e nos debates ("debate").
Uso: ODI_INTERNO_DIR=… SUPABASE_URL=… SUPABASE_SERVICE_ROLE_KEY=… python scripts/carregar_area_pesquisador.py [--caso 001|campanhas|debate] [--completo] [--seco]
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
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

import emoji

csv.field_size_limit(10**9)
VAR = re.compile("[️\U0001F3FB-\U0001F3FF]")
LOTE = 500
MIN_SEG = 10_000
# Limite de segurança do banco, em MB. Até 24/11/2026 o plano era o gratuito (500 MB) e a carga parava em 430 (C19.375).
# Em 24/11/2026 o responsável assinou o plano Pro ("assinatura supabase feita pode levar tudo pra lá tem espaço agora");
# o Pro inclui 8 GB de disco. O teto fica em 6.000 MB e pode ser mudado pela variável ODI_AREA_LIMITE_MB.
LIMITE_MB = int(os.environ.get("ODI_AREA_LIMITE_MB") or 6000)
# Acervos gerais (fora dos casos), levados ao banco a pedido do responsável em 24/11/2026. Entram como "casos" com nome
# próprio. Todos os arquivos têm as mesmas colunas da coleta de comentários do YouTube. Comentário nunca leva autor.
ACERVOS = {
    "campanhas": [("youtube", "youtube/comentarios/comentarios.csv.gz"), ("facebook", "facebook/comentarios/comentarios.csv.gz"),
                  ("instagram", "instagram/comentarios/comentarios.csv.gz"), ("tiktok", "tiktok/comentarios/comentarios.csv.gz"),
                  ("kwai", "kwai/comentarios/comentarios.csv.gz"), ("x", "x/respostas/respostas.csv.gz")],
    "debate": [("youtube", "debate/youtube_comentarios.csv.gz"), ("youtube", "debate/globo/youtube_comentarios.csv.gz")],
}
ACERVO_DIAS = 3  # carga diária dos acervos: só o que foi coletado nos últimos dias (o resto já está no banco); --completo manda tudo


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


def data_iso(v: str | None) -> str | None:
    """Data do acervo no formato do banco. A coleta de comentários do Instagram grava parte das datas como segundos desde 1970
    ("1792064145"); o banco recusou o lote inteiro (HTTP 400, run 45624468428). Valor que não é data vira vazio, nunca chute."""
    v = (v or "").strip()
    if not v:
        return None
    if re.fullmatch(r"\d{9,10}", v):
        return datetime.fromtimestamp(int(v), timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    if re.fullmatch(r"\d{12,13}", v):
        return datetime.fromtimestamp(int(v) / 1000, timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    return v if re.match(r"\d{4}-\d{2}-\d{2}", v) else None


def linhas_acervo(nome: str, interno: Path, desde: str | None = None):
    """Comentários e respostas dos acervos gerais. Sem autor, sem link, sem id de conta. `desde`: só coletados a partir dessa data."""
    for rede, rel in ACERVOS[nome]:
        f = interno / rel
        if not f.exists():
            print(f"⛔ {nome}: arquivo ausente no privado: {rel}")
            continue
        for r in ler(f):
            t = (r.get("texto") or "").strip()
            if not t or not r.get("comment_id"):
                continue
            if desde and (r.get("coletado_em") or "") < desde:
                continue
            # o id do YouTube é único por si; nas outras redes é numérico e pode repetir entre redes
            item = r["comment_id"] if rede == "youtube" else f"{rede}:{r['comment_id']}"
            yield {"caso": nome, "rede": rede, "fonte": "comentario", "item_id": item, "publicado_em": data_iso(r.get("publicado_em")), "autor": None,
                   "texto": t, "emojis": emojis_de(t), "candidato": r.get("candidate_id") or None, "ofensivo": None, "odio": None}


def enviar(url: str, chave: str, lote: list[dict], manter: bool = False):
    """manter=True: texto que já está no banco não é regravado (acervos; comentário não muda e não tem triagem a atualizar)."""
    req = urllib.request.Request(f"{url}/rest/v1/corpus?on_conflict=caso,fonte,item_id", data=json.dumps(lote).encode(), method="POST",
                                 headers={"apikey": chave, "Authorization": f"Bearer {chave}", "Content-Type": "application/json",
                                          "Prefer": f"resolution={'ignore' if manter else 'merge'}-duplicates,return=minimal"})
    for tentativa in range(4):
        try:
            urllib.request.urlopen(req, timeout=120).read()
            return
        except Exception as e:  # noqa: BLE001
            corpo = e.read().decode("utf-8", "replace")[:300] if isinstance(e, urllib.error.HTTPError) else ""
            if tentativa == 3 or (isinstance(e, urllib.error.HTTPError) and 400 <= e.code < 500 and e.code != 429):
                print(f"⛔ lote recusado pelo banco ({e}): {corpo}")  # erro de dado não melhora repetindo: mostra o motivo
                raise
            print(f"   nova tentativa ({e}) {corpo}")
            time.sleep(5 * (tentativa + 1))


def tamanho_mb(url: str, chave: str) -> float:
    req = urllib.request.Request(f"{url}/rest/v1/rpc/tamanho_banco_mb", data=b"{}", method="POST",
                                 headers={"apikey": chave, "Authorization": f"Bearer {chave}", "Content-Type": "application/json"})
    return float(json.loads(urllib.request.urlopen(req, timeout=60).read()))


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--caso")
    ap.add_argument("--seco", action="store_true")
    ap.add_argument("--completo", action="store_true", help="acervos gerais inteiros (padrão: só o coletado nos últimos dias)")
    a = ap.parse_args(argv)
    interno = Path(os.environ.get("ODI_INTERNO_DIR", ""))
    if not (interno / "casos").is_dir():
        print("⛔ ODI_INTERNO_DIR sem casos/"); return 1
    url, chave = os.environ.get("SUPABASE_URL", "").rstrip("/"), os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")
    if not a.seco and not (url and chave):
        print("⛔ faltam SUPABASE_URL e SUPABASE_SERVICE_ROLE_KEY no ambiente (secrets do GitHub)"); return 1
    cfg = casos_cfg()
    ids = [a.caso] if a.caso else sorted(p.name for p in (interno / "casos").iterdir() if re.fullmatch(r"\d{3}", p.name)) + list(ACERVOS)
    desde = None if a.completo else (datetime.now(timezone.utc) - timedelta(days=ACERVO_DIAS)).strftime("%Y-%m-%dT%H:%M:%SZ")
    total, falhas = 0, 0
    for cid in ids:
        if not a.seco:
            mb = tamanho_mb(url, chave)
            if mb >= LIMITE_MB:
                print(f"⛔ banco com {mb} MB (limite de segurança {LIMITE_MB} MB): carga parada antes do caso {cid}")
                return 1
        lote, n, vistos = [], 0, set()
        for r in (linhas_acervo(cid, interno, desde) if cid in ACERVOS else linhas(cid, interno, cfg.get(cid, {}))):
            k = (r["fonte"], r["item_id"])
            if k in vistos:
                continue
            vistos.add(k)
            lote.append(r)
            n += 1
            if len(lote) >= LOTE:
                if not a.seco:
                    enviar(url, chave, lote, manter=cid in ACERVOS)
                lote = []
        if lote and not a.seco:
            enviar(url, chave, lote, manter=cid in ACERVOS)
        total += n
        if not a.seco:
            # amostra de validação (se o caso é novo), resumo e nuvens DESTE caso (C19.385: por caso, para caber no tempo)
            req = urllib.request.Request(f"{url}/rest/v1/rpc/preparar_area", data=json.dumps({"p_caso": cid}).encode(), method="POST",
                                         headers={"apikey": chave, "Authorization": f"Bearer {chave}", "Content-Type": "application/json"})
            try:
                preparo = urllib.request.urlopen(req, timeout=900).read().decode()
            except Exception as e:  # noqa: BLE001
                preparo, falhas = f"⛔ preparo não rodou ({e})", falhas + 1
        print(f"{cid}: {n} textos {'contados' if a.seco else 'enviados'}" + (f" (coletados desde {desde})" if cid in ACERVOS and desde else "") + ("" if a.seco else f" · {preparo}"))
    print(f"total: {total}" + ("" if a.seco else f" · banco com {tamanho_mb(url, chave)} MB"))
    return 1 if falhas else 0


if __name__ == "__main__":
    sys.exit(main())
