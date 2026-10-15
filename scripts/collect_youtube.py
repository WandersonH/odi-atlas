#!/usr/bin/env python3
"""Inscritos dos canais do YouTube declarados ao TSE, pela YouTube Data API v3 (oficial, gratuita).

- Chave SOMENTE pela variável de ambiente YOUTUBE_API_KEY (segredo do GitHub). Nunca gravada nem impressa.
- Resolve cada URL declarada: /channel/UC…, /@handle, /user/nome; /c/ e links de vídeo não têm
  correspondência oficial direta e ficam como "não resolvidos" (registrados, não adivinhados).
- Custo de cota: 1 unidade por chamada channels.list (cota diária padrão: 10.000).
- O YouTube arredonda publicamente o número de inscritos (3 dígitos significativos) e permite ocultá-lo;
  canal com contagem oculta fica sem número (não vira zero).
- Saída: data/seguidores/youtube_latest.csv no formato do caderno 02, histórico e manifesto.
"""
from __future__ import annotations

import csv
import gzip
import json
import os
import re
import sys
import urllib.error
import urllib.parse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from net import with_scheme, get_json, now_utc  # noqa: E402

API = "https://www.googleapis.com/youtube/v3/channels"
CARGOS = {"PRESIDENTE", "VICE-PRESIDENTE"}


def parse_channel(url: str):
    """Devolve (tipo, valor) para a API: ('id', UC…), ('handle', @x) ou ('username', x); None se não der."""
    u = url.strip()
    p = urllib.parse.urlparse(u if "://" in u else "https://" + u)
    host = (p.hostname or "").lower()
    if "youtube.com" not in host:
        return None
    parts = [urllib.parse.unquote(x) for x in p.path.split("/") if x]
    if not parts:
        return None
    if parts[0].lower() == "channel" and len(parts) > 1 and re.fullmatch(r"UC[\w-]{22}", parts[1]):
        return ("id", parts[1])
    if parts[0].startswith("@"):
        return ("handle", parts[0])
    if parts[0].lower() == "user" and len(parts) > 1:
        return ("username", parts[1])
    return None


def load_targets(root: Path, year: str = "2026"):
    src = root / "data" / "tse" / f"redes_sociais_candidatos_{year}.csv.gz"
    out = []
    for r in csv.DictReader(gzip.open(src, "rt", encoding="utf-8"), delimiter=";"):
        if r.get("DS_CARGO", "").upper() in CARGOS and r.get("PLATAFORMA") == "youtube":
            out.append({"candidate_id": r["SQ_CANDIDATO"], "candidate_name": r.get("NM_URNA_CANDIDATO", ""),
                        "url": r["DS_URL"].strip(), "ref": parse_channel(r["DS_URL"])})
    return out


def query(key: str, kind: str, value: str):
    param = {"id": "id", "handle": "forHandle", "username": "forUsername"}[kind]
    q = urllib.parse.urlencode({"part": "id,snippet,statistics", param: value, "key": key})
    return get_json(f"{API}?{q}", timeout=60).get("items") or []


def main(argv=None) -> int:
    root = Path(argv[0]) if argv else Path(".")
    started = now_utc()
    outdir = root / "data" / "seguidores"
    outdir.mkdir(parents=True, exist_ok=True)
    man = {"schema_version": 1, "stage": "seguidores-youtube", "run_started_utc": started,
           "fonte": "YouTube Data API v3 · channels.list (statistics)", "blocked": [], "warnings": [], "canais": []}

    def finish(code: int) -> int:
        man["run_finished_utc"] = now_utc()
        man["status"] = "bloqueado" if man["blocked"] else "ok"
        (outdir / "youtube_manifesto_latest.json").write_text(json.dumps(man, ensure_ascii=False, indent=1), encoding="utf-8")
        print(json.dumps({k: man.get(k) for k in ("status", "blocked", "warnings", "linhas_csv", "cota_usada")}, ensure_ascii=False))
        return code

    key = os.environ.get("YOUTUBE_API_KEY", "").strip()
    if not key:
        man["blocked"].append("YOUTUBE_API_KEY ausente (cadastre o segredo no GitHub)")
        return finish(1)
    targets = load_targets(root)
    man["alvos"] = len(targets)
    man["nao_resolvidos"] = [t["url"] for t in targets if not t["ref"]]
    rows, cache, cota = [], {}, 0
    for t in targets:
        if not t["ref"]:
            continue
        if t["ref"] not in cache:
            try:
                cache[t["ref"]] = query(key, *t["ref"])
                cota += 1
            except urllib.error.HTTPError as e:
                msg = f"HTTP {e.code} em {t['ref'][0]}={t['ref'][1]}"
                if e.code in (400, 403):  # chave inválida, API não habilitada ou cota esgotada: para tudo
                    man["blocked"].append(msg + " (verifique a chave, se a YouTube Data API v3 está ativada e a cota)")
                    return finish(1)
                man["warnings"].append(msg)
                cache[t["ref"]] = []
        items = cache[t["ref"]]
        c = {"url": t["url"], "ref": list(t["ref"]), "encontrado": bool(items)}
        if items:
            it = items[0]
            st, sn = it.get("statistics", {}), it.get("snippet", {})
            c.update(channel_id=it["id"], titulo=sn.get("title"), oculto=st.get("hiddenSubscriberCount"),
                     inscritos=st.get("subscriberCount"), videos=st.get("videoCount"), visualizacoes=st.get("viewCount"))
            if not st.get("hiddenSubscriberCount") and st.get("subscriberCount") is not None:
                rows.append([t["candidate_id"], t["candidate_name"], "YouTube", with_scheme(t["url"]), int(st["subscriberCount"]),
                             started[:10], f"https://www.youtube.com/channel/{it['id']}"])
        man["canais"].append(c)
    man["cota_usada"] = cota
    header = ["candidate_id", "candidate_name", "platform", "url", "followers", "captured_at", "source_url"]
    for name in (f"youtube_{started[:10]}.csv", "youtube_latest.csv"):
        with open(outdir / name, "w", encoding="utf-8", newline="") as f:
            w = csv.writer(f, delimiter=";", lineterminator="\n")
            w.writerow(header)
            w.writerows(rows)
    man["linhas_csv"] = len(rows)
    if targets and not rows:
        man["blocked"].append("nenhum canal retornou número de inscritos")
    return finish(1 if man["blocked"] else 0)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
