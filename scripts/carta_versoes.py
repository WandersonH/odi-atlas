#!/usr/bin/env python3
"""Caso 017: as versões da carta de Flávio Bolsonaro no X (post editado) e os arquivos públicos de cada versão.

Pedido do responsável (29/10/2026, 21h51): "cartas e suas versões: a carta de Flávio teve 3 versões; quero um dossiê completo de mídia
e, se conseguirmos, as 2 outras versões"; "ele começa se autoproclamando presidente e na última versão entra como líder".
Post indicado: https://x.com/flaviobolsonaro/status/2115538982012682337

Grátis, sem login:
  - X, endpoint público de incorporação (cdn.syndication.twimg.com/tweet-result): texto, data, imagens, curtidas, respostas e
    a cadeia de edição (edit_control.edit_tweet_ids: cada versão de um post editado tem o próprio id);
  - Internet Archive (CDX): capturas de cada versão, com data, para conferência independente.
Imagens das versões (a carta é publicada como imagem) vão para data/casos/017/midia/ (post público de figura pública).
Se o endpoint não responder, o resultado é ⛔ (nada inventado) e a busca paga do X (caso 017, from:flaviobolsonaro) cobre o texto.
Saída: data/casos/017/versoes.json.
Uso: python scripts/carta_versoes.py 2115538982012682337 [outros ids]
"""
from __future__ import annotations

import json
import sys
import urllib.parse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from net import download, get_json, now_utc  # noqa: E402

SYN = "https://cdn.syndication.twimg.com/tweet-result?id={id}&token={tok}&lang=pt"
CDX = "https://web.archive.org/cdx/search/cdx?"
DEST = Path("data/casos/017")


def token(tid: str) -> str:
    """Mesmo cálculo do widget oficial: ((id / 1e15) * π) em base 36, sem zeros e sem ponto (Node, quando há; senão aproximação)."""
    import math
    import subprocess
    try:
        return subprocess.run(["node", "-e", f"console.log(((Number('{int(tid)}')/1e15)*Math.PI).toString(36).replace(/(0+|\\.)/g,''))"],
                              capture_output=True, text=True, timeout=20, check=True).stdout.strip()
    except Exception:  # noqa: BLE001
        pass
    x = (int(tid) / 1e15) * math.pi
    inteiro, frac, dig = int(x), x - int(x), "0123456789abcdefghijklmnopqrstuvwxyz"
    s = ""
    while inteiro:
        s = dig[inteiro % 36] + s
        inteiro //= 36
    s = (s or "0") + "."
    for _ in range(12):
        frac *= 36
        s += dig[int(frac)]
        frac -= int(frac)
    return s.replace(".", "").replace("0", "")


def ler(tid: str) -> dict:
    reg = {"id": tid, "url": f"https://x.com/flaviobolsonaro/status/{tid}"}
    try:
        d = get_json(SYN.format(id=tid, tok=token(tid)), timeout=40)
    except Exception as e:  # noqa: BLE001
        return {**reg, "status": f"⛔ {type(e).__name__}: {str(e)[:160]}"}
    if not d or d.get("__typename") == "TweetTombstone" or "text" not in d:
        return {**reg, "status": "⛔ sem conteúdo no endpoint (apagado, restrito ou tombstone)", "bruto_tipo": d.get("__typename") if d else None}
    ec = d.get("edit_control") or {}
    ini = ec.get("edit_control_initial") or ec
    return {**reg, "status": "ok", "criado_em_utc": d.get("created_at"), "texto": d.get("text"), "conta": (d.get("user") or {}).get("screen_name"),
            "curtidas": d.get("favorite_count"), "respostas": d.get("conversation_count"),
            "edicao": {"ids": ini.get("edit_tweet_ids") or ec.get("edit_tweet_ids"), "editavel_ate_ms": ini.get("editable_until_msecs"),
                       "edicoes_restantes": ini.get("edits_remaining"), "inicial": ec.get("initial_tweet_id")},
            "imagens": [m.get("media_url_https") for m in d.get("mediaDetails") or [] if m.get("type") == "photo"],
            "citado": (d.get("quoted_tweet") or {}).get("id_str")}


def arquivo(tid: str) -> list[dict]:
    out = []
    for dom in ("x.com", "twitter.com"):
        q = {"url": f"{dom}/flaviobolsonaro/status/{tid}", "output": "json", "fl": "timestamp,original,statuscode,digest"}
        try:
            rows = get_json(CDX + urllib.parse.urlencode(q), timeout=60)
        except Exception as e:  # noqa: BLE001
            out.append({"dominio": dom, "erro": type(e).__name__})
            continue
        for r in (rows or [])[1:]:
            out.append({"dominio": dom, "captura": r[0], "status_http": r[2], "link": f"https://web.archive.org/web/{r[0]}/{r[1]}"})
    return out


def main(argv=None) -> int:
    argv = sys.argv[1:] if argv is None else list(argv)
    ids = [a for a in argv if a.isdigit()] or ["2115538982012682337"]
    vistos, fila, versoes = set(), list(ids), []
    while fila:
        tid = fila.pop(0)
        if tid in vistos:
            continue
        vistos.add(tid)
        v = ler(tid)
        for outro in (v.get("edicao") or {}).get("ids") or []:
            if str(outro) not in vistos:
                fila.append(str(outro))
        v["arquivo_internet_archive"] = arquivo(tid)
        versoes.append(v)
    (DEST / "midia").mkdir(parents=True, exist_ok=True)
    for v in versoes:
        v["imagens_locais"] = []
        for i, u in enumerate(v.get("imagens") or []):
            nome = f"versao_{v['id']}_{i + 1}.jpg"
            try:
                download(u + ("&name=large" if "?" in u else "?name=large"), DEST / "midia" / nome, timeout=60)
                v["imagens_locais"].append(f"midia/{nome}")
            except Exception as e:  # noqa: BLE001
                v.setdefault("erros_imagem", []).append(f"{u}: {type(e).__name__}")
    versoes.sort(key=lambda v: v.get("criado_em_utc") or "9")
    out = {"gerado_em_utc": now_utc(), "pedido": "Responsável em 29/10/2026, 21h51: \"a carta de Flávio teve 3 versões; quero um dossiê completo de mídia e, se conseguirmos, as 2 outras versões\"",
           "fonte": "X, endpoint público de incorporação (cdn.syndication.twimg.com) e Internet Archive (CDX)", "ids_pedidos": ids, "versoes": versoes,
           "nota": "No X, cada edição de um post ganha um id novo; o endpoint informa a cadeia (edit_tweet_ids). Versões apagadas ou restritas ficam ⛔."}
    DEST.mkdir(parents=True, exist_ok=True)
    (DEST / "versoes.json").write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    for v in versoes:
        print(f"versão {v['id']}: {v['status']} · {v.get('criado_em_utc')} · imagens {len(v.get('imagens') or [])} · capturas {len(v['arquivo_internet_archive'])} · "
              f"cadeia {(v.get('edicao') or {}).get('ids')} · {(v.get('texto') or '')[:160]!r}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
