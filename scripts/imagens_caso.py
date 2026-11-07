#!/usr/bin/env python3
"""Imagens dos posts de um caso (TikTok, Instagram, Facebook), para a galeria visual da página — protótipo no caso 030.

Pedido do responsável (07/11/2026, 18h40): "assim como mostra os tweets, que pudesse mostrar as imagens dos posts em
outras redes; caso aprovado, aplicaremos em tudo".

Regras:
- Só posts de contas públicas pela regra do Atlas: 10 mil+ seguidores ou perfil declarado ao TSE (o selo não basta,
  C19.353). Conta pequena nunca tem imagem publicada, porque a imagem mostra rosto, nome e texto de pessoa comum.
- Instagram e Facebook: os coletores não devolvem seguidores. Sem a leitura de perfil (arquivo privado perfil_*.json
  ou coluna seguidores), o post não entra e a página diz quantos ficaram de fora por isso (⛔).
- Os endereços de imagem das plataformas expiram (horas ou dias). A imagem é baixada no dia e guardada em
  data/casos/<id>/imagens/ (miniatura de até 480 px, JPEG), com sha256 do arquivo original, data e fonte.
- TikTok: a capa vem do oEmbed público do TikTok (https://www.tiktok.com/oembed), que devolve a miniatura atual do
  vídeo sem login; grátis.
- Instagram/Facebook: usa o endereço de imagem gravado na coleta (capa_url) se ainda responder; senão, ⛔ expirado.
Saída pública: data/casos/<id>/imagens.json + data/casos/<id>/imagens/*.jpg.
Uso: ODI_INTERNO_DIR=… python scripts/imagens_caso.py --caso 030 [--max 24]
"""
from __future__ import annotations

import csv
import gzip
import hashlib
import io
import json
import os
import sys
import urllib.parse
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from build_casos import declarados, num  # noqa: E402
from net import now_utc  # noqa: E402

UA = {"User-Agent": "Mozilla/5.0 (ODI Atlas; pesquisa acadêmica PPGCOM/UNIP)"}
REDES = ("tiktok", "instagram", "facebook")


def baixar(url: str, timeout: int = 20) -> bytes | None:
    try:
        with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=timeout) as r:
            return r.read() if r.status == 200 else None
    except Exception:
        return None


def oembed_tiktok(url: str) -> dict | None:
    b = baixar("https://www.tiktok.com/oembed?url=" + urllib.parse.quote(url, safe=""))
    try:
        return json.loads(b) if b else None
    except ValueError:
        return None


def miniatura(dados: bytes) -> bytes:
    try:
        from PIL import Image
        im = Image.open(io.BytesIO(dados)).convert("RGB")
        im.thumbnail((480, 480))
        out = io.BytesIO()
        im.save(out, "JPEG", quality=82, optimize=True)
        return out.getvalue()
    except Exception:
        return dados


def perfis_privados(interno: Path, caso: str) -> dict:
    out = {}
    for f in interno.glob(f"casos/{caso}/perfil_*.json"):
        try:
            x = json.loads(f.read_text(encoding="utf-8"))
        except ValueError:
            continue
        for p in (x if isinstance(x, list) else x.get("perfis") or [x]):
            if p.get("usuario") and p.get("seguidores") is not None:
                out[(f.stem.split("_", 1)[1], p["usuario"].lower())] = int(p["seguidores"])
    return out


def main(argv=None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    caso = argv[argv.index("--caso") + 1]
    maximo = int(argv[argv.index("--max") + 1]) if "--max" in argv else 24
    interno = Path(os.environ.get("ODI_INTERNO_DIR") or "")
    arq = interno / "casos" / caso / "itens.csv.gz"
    if not arq.exists():
        print(f"⛔ {arq} não existe")
        return 1
    root = Path(".")
    cfg = json.loads((root / "data/config/casos.json").read_text(encoding="utf-8"))
    minimo = cfg.get("min_seguidores_publico", 10000)
    dec = declarados(root)
    perf = perfis_privados(interno, caso)
    itens = list(csv.DictReader(gzip.open(arq, "rt", encoding="utf-8"), delimiter=";"))
    resumo = {r: {"lidos": 0, "publicos": 0, "sem_seguidores": 0, "pequenas": 0, "com_imagem": 0, "falhas": 0} for r in REDES}
    candidatos = []
    for r in itens:
        rede = r["rede"]
        if rede not in REDES:
            continue
        s = resumo[rede]
        s["lidos"] += 1
        k = (rede, (r["conta"] or "").lower())
        seg = num(r.get("seguidores")) or perf.get(k)
        if k in dec or (seg or 0) >= minimo:
            s["publicos"] += 1
            candidatos.append({**r, "_seg": seg, "_tse": k in dec})
        elif not r.get("seguidores") and k not in perf:
            s["sem_seguidores"] += 1
        else:
            s["pequenas"] += 1
    # os de maior alcance primeiro, no máximo `maximo` no total e metade por rede, para a galeria não ser só de uma rede
    candidatos.sort(key=lambda r: (num(r["visualizacoes"]), num(r["curtidas"])), reverse=True)
    pasta = root / "data/casos" / caso / "imagens"
    pasta.mkdir(parents=True, exist_ok=True)
    pecas, por_rede, vistos = [], {}, set()
    tentativas = 0
    for r in candidatos:
        if tentativas >= 4 * maximo:  # não insiste além disso quando a fonte de imagem falha
            break
        if len(pecas) >= maximo or por_rede.get(r["rede"], 0) >= max(1, maximo // 2) or r["url"] in vistos:
            continue
        vistos.add(r["url"])
        tentativas += 1
        fonte, img = None, None
        if r["rede"] == "tiktok":
            o = oembed_tiktok(r["url"])
            if o and o.get("thumbnail_url"):
                img, fonte = baixar(o["thumbnail_url"]), "oEmbed público do TikTok (miniatura do vídeo)"
        elif r.get("capa_url"):
            img, fonte = baixar(r["capa_url"]), f"endereço de imagem gravado na coleta de {r.get('coletado_em', '')[:10]}"
        if not img:
            resumo[r["rede"]]["falhas"] += 1
            continue
        nome = f"{r['rede']}_{hashlib.sha1(r['url'].encode()).hexdigest()[:12]}.jpg"
        (pasta / nome).write_bytes(miniatura(img))
        resumo[r["rede"]]["com_imagem"] += 1
        por_rede[r["rede"]] = por_rede.get(r["rede"], 0) + 1
        pecas.append({"rede": {"tiktok": "TikTok", "instagram": "Instagram", "facebook": "Facebook"}[r["rede"]],
                      "conta": ("@" if r["rede"] != "facebook" else "") + r["conta"], "seguidores": r["_seg"], "declarado_tse": r["_tse"],
                      "publicado_em": r["publicado_em"], "texto": (r["texto"] or "")[:220], "url": r["url"],
                      "visualizacoes": num(r["visualizacoes"]) or None, "curtidas": num(r["curtidas"]) or None,
                      "imagem": f"data/casos/{caso}/imagens/{nome}", "sha256_original": hashlib.sha256(img).hexdigest(),
                      "obtida_em_utc": now_utc(), "fonte_imagem": fonte})
    out = {"gerado_em_utc": now_utc(), "caso": caso, "pecas": pecas, "resumo_por_rede": resumo,
           "regra": f"Só contas com {minimo:,} seguidores ou mais, ou perfil declarado ao TSE (o selo não basta). Ordem: visualizações, depois curtidas. "
                    f"Até {maximo} peças, no máximo {max(1, maximo // 2)} por rede.".replace(",", "."),
           "universo": "⛔ desconhecido: as buscas das plataformas não informam o total de posts; a galeria é uma seleção das peças de maior alcance dentro da amostra lida."}
    (root / "data/casos" / caso / "imagens.json").write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"imagens {caso}: {len(pecas)} peças ·", " · ".join(f"{k} {v}" for k, v in resumo.items()))
    return 0


if __name__ == "__main__":
    sys.exit(main())
