#!/usr/bin/env python3
"""Seguidores de canais de WhatsApp — página pública do canal (whatsapp.com/channel/<id>), uma leitura por dia.

Só o número público exibido na página (ex.: "12,3 mil seguidores" / "12.3K followers") e o nome do canal.
Mensagens do canal não são lidas aqui. O WhatsApp arredonda o número (mil / mi); o texto original fica gravado
ao lado do número convertido, para conferência.

Entrada: data/config/whatsapp_canais.json
Saída:   data/whatsapp/seguidores.csv (histórico, uma linha por dia e canal: a última leitura do dia — abre no Excel/Sheets),
         data/whatsapp/seguidores_horario.csv (toda leitura, uma por hora desde 21/10/2026),
         data/whatsapp/seguidores_latest.csv e data/whatsapp/manifesto_latest.json
"""
from __future__ import annotations

import csv
import datetime as dt
import html
import json
import re
import sys
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from net import now_utc  # noqa: E402

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
CAMPOS = ["data", "canal_id", "nome", "lado", "seguidores", "texto_original", "url", "coletado_em_utc"]
NUM = re.compile(r"(\d+(?:[.,]\d+)*)\s*(mil|mi|milhão|milhões|milhao|milhoes|k|m|thousand|million)?\s*(seguidores|seguidor|followers|follower)\b", re.I)
MULT = {"mil": 1e3, "k": 1e3, "thousand": 1e3, "mi": 1e6, "milhão": 1e6, "milhões": 1e6, "milhao": 1e6, "milhoes": 1e6,
        "m": 1e6, "million": 1e6}


def numero(txt: str, sufixo: str | None) -> int:
    """'12,3' + 'mil' → 12300; '1.234' (sem sufixo) → 1234; '12.3' + 'K' → 12300."""
    s = txt
    if sufixo:
        s = s.replace(".", ",") if s.count(".") == 1 and len(s.split(".")[1]) <= 2 else s
        s = s.replace(".", "").replace(",", ".")
        return int(round(float(s) * MULT[sufixo.lower()]))
    return int(re.sub(r"[.,]", "", s))


def extrair(pagina: str) -> dict:
    """Nome e seguidores a partir do HTML público. Procura no texto visível e nas meta tags."""
    texto = html.unescape(re.sub(r"<[^>]+>", " ", re.sub(r"(?is)<(script|style)[^>]*>.*?</\1>", " ", pagina)))
    metas = " ".join(html.unescape(m) for m in re.findall(r'<meta[^>]+content="([^"]*)"', pagina))
    out = {}
    for fonte in (texto, metas):
        m = NUM.search(" ".join(fonte.split()))
        if m:
            out["seguidores"] = numero(m.group(1), m.group(2))
            out["texto_original"] = m.group(0)
            break
    t = re.search(r'<meta property="og:title" content="([^"]*)"', pagina) or re.search(r"<title>([^<]*)</title>", pagina)
    if t:
        nome = html.unescape(t.group(1)).strip()
        out["nome"] = re.sub(r"^(WhatsApp Channel|Canal do WhatsApp)\s*[:|·-]?\s*", "", nome, flags=re.I).strip() or nome
    return out


def baixar(url: str, idioma: str) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept-Language": idioma})
    with urllib.request.urlopen(req, timeout=40) as r:
        return r.read().decode("utf-8", "replace")


def main(argv=None) -> int:
    root = Path(argv[0]) if argv else Path(".")
    cfg = json.loads((root / "data/config/whatsapp_canais.json").read_text(encoding="utf-8"))
    hoje = dt.datetime.now(dt.timezone(dt.timedelta(hours=-3))).date().isoformat()  # data de Brasília
    agora = now_utc()
    linhas, man = [], {"schema_version": 1, "run_started_utc": agora, "fonte": "página pública whatsapp.com/channel", "canais": []}
    for c in cfg["canais"]:
        url = f"https://www.whatsapp.com/channel/{c['id']}"
        reg = {"canal_id": c["id"], "nome_config": c.get("nome"), "url": url}
        try:
            info = {}
            for idioma in ("pt-BR,pt;q=0.9", "en-US,en;q=0.9"):
                info = extrair(baixar(url, idioma))
                if "seguidores" in info:
                    break
            reg.update(info)
            reg["status"] = "ok" if "seguidores" in info else "⛔ número de seguidores não encontrado na página"
            if "seguidores" not in info:  # diagnóstico: começo do texto visível da página pública
                pg = baixar(url, "pt-BR,pt;q=0.9")
                reg["trecho_pagina"] = " ".join(re.sub(r"<[^>]+>", " ", re.sub(r"(?is)<(script|style)[^>]*>.*?</\1>", " ", pg)).split())[:400]
        except Exception as e:  # noqa: BLE001
            reg["status"] = f"⛔ {type(e).__name__} {getattr(e, 'code', '')}".strip()
        man["canais"].append(reg)
        if reg.get("seguidores") is not None:
            linhas.append({"data": hoje, "canal_id": c["id"], "nome": reg.get("nome") or c.get("nome", ""), "lado": c.get("lado", ""),
                           "seguidores": reg["seguidores"], "texto_original": reg["texto_original"], "url": url, "coletado_em_utc": agora})
        print(f"{c.get('nome') or c['id']}: {reg['status']} · {reg.get('nome')} · {reg.get('seguidores')} ({reg.get('texto_original')})")
    d = root / "data/whatsapp"
    d.mkdir(parents=True, exist_ok=True)
    hist = d / "seguidores.csv"
    antigas = list(csv.DictReader(open(hist, encoding="utf-8"), delimiter=";")) if hist.exists() else []
    novas_chaves = {(l["data"], l["canal_id"]) for l in linhas}
    todas = [r for r in antigas if (r["data"], r["canal_id"]) not in novas_chaves] + linhas
    todas.sort(key=lambda r: (r["data"], r["canal_id"]))
    hora = d / "seguidores_horario.csv"  # toda leitura (coleta de hora em hora, pedido de 21/10/2026)
    ant_h = list(csv.DictReader(open(hora, encoding="utf-8"), delimiter=";")) if hora.exists() else []
    vistas = {(r["coletado_em_utc"], r["canal_id"]) for r in ant_h}
    toda_hora = ant_h + [l for l in linhas if (l["coletado_em_utc"], l["canal_id"]) not in vistas]
    toda_hora.sort(key=lambda r: (r["coletado_em_utc"], r["canal_id"]))
    for p, rows in ((hist, todas), (d / "seguidores_latest.csv", linhas), (hora, toda_hora)):
        with open(p, "w", encoding="utf-8", newline="") as f:
            w = csv.DictWriter(f, CAMPOS, delimiter=";", lineterminator="\n")
            w.writeheader()
            w.writerows(rows)
    man["status"] = "ok" if len(linhas) == len(cfg["canais"]) else f"⚠️ {len(linhas)} de {len(cfg['canais'])} canais lidos"
    (d / "manifesto_latest.json").write_text(json.dumps(man, ensure_ascii=False, indent=1), encoding="utf-8")
    return 0 if linhas else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
