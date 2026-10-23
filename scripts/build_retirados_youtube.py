#!/usr/bin/env python3
"""Vídeos das campanhas no YouTube que SAÍRAM DO AR: estavam numa leitura diária do canal e sumiram das seguintes.

Pergunta do responsável (23/10/2026, 18h01): dá para marcar vídeos retirados, e se foi por decisão do TSE?
- Detecção: compara as fotos diárias data/youtube/videos_AAAA-MM-DD.csv.gz. Vídeo publicado desde 20/07 que aparecia e não
  está na foto mais recente, com o canal dele lido nessa foto, é candidato a retirado.
- Confirmação (com YOUTUBE_API_KEY): videos.list por id (1 unidade a cada 50 ids). Se a API ainda devolve o vídeo, ele só
  saiu da janela da lista; se não devolve, fica "retirado do ar ou tornado privado". A API não diz qual dos dois nem o motivo.
- Decisão judicial: o YouTube não informa o motivo e o processual do TSE não traz o link do vídeo. Por isso o Atlas NÃO marca
  "retirado por decisão" automaticamente: lista os processos do TSE em que o candidato do canal é parte, com assunto de
  internet ou redes sociais e decisão a partir de 7 dias antes da última vez em que o vídeo foi visto, como pistas a
  conferir. Só vira "decisão" com a peça ou a notícia que cite o vídeo (campo manual em data/config/retirados_confirmados.json).
Saída: data/youtube/retirados.json.
"""
from __future__ import annotations

import csv
import datetime as dt
import glob
import gzip
import json
import os
import sys
import urllib.parse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from net import get_json, now_utc  # noqa: E402

DESDE = "2026-07-20"


def fotos(root: Path) -> dict[str, dict[str, dict]]:
    out = {}
    for f in sorted(glob.glob(str(root / "data/youtube/videos_2026-*.csv.gz"))):
        out[Path(f).name[7:17]] = {r["video_id"]: r for r in csv.DictReader(gzip.open(f, "rt", encoding="utf-8"), delimiter=";")}
    return out


def candidatos_a_retirado(F: dict[str, dict[str, dict]]) -> dict[str, dict]:
    datas = sorted(F)
    if len(datas) < 2:
        return {}
    ult = F[datas[-1]]
    canais_lidos = {r["channel_id"] for r in ult.values()}
    out = {}
    for d in datas[:-1]:
        for vid, r in F[d].items():
            if vid in ult or (r.get("publicado_em") or "") < DESDE or r["channel_id"] not in canais_lidos:
                continue
            out[vid] = {**{k: r.get(k) for k in ("candidate_id", "candidate_name", "channel_id", "canal", "publicado_em", "titulo", "visualizacoes")},
                        "visto_pela_ultima_vez": max(out.get(vid, {}).get("visto_pela_ultima_vez", ""), d)}
    return out


def confirmar(ids: list[str], key: str) -> set[str]:
    """ids que a API ainda devolve (então não saíram do ar)."""
    vivos = set()
    for i in range(0, len(ids), 50):
        q = urllib.parse.urlencode({"part": "id", "id": ",".join(ids[i:i + 50]), "key": key})
        d = get_json(f"https://www.googleapis.com/youtube/v3/videos?{q}", timeout=60)
        vivos |= {x["id"] for x in d.get("items", [])}
    return vivos


def pistas_tse(root: Path, v: dict) -> list[dict]:
    p = root / "data/tse/processual/resumo.json"
    if not p.exists():
        return []
    R = json.loads(p.read_text(encoding="utf-8"))
    nome = (v.get("candidate_name") or "").upper()
    lim = (dt.date.fromisoformat(v["visto_pela_ultima_vez"]) - dt.timedelta(days=7)).isoformat()
    out = []
    for c in R.get("candidatos_presidencia", []):
        if c["nome"].upper() != nome:
            continue
        for x in c.get("lista", []):
            if "Pólo passivo" in x.get("polo", []) and any(k in x.get("assunto", "") for k in ("Internet", "Redes Sociais", "Inteligência Artificial", "Deep Fake")) \
                    and (x.get("ultima_decisao") or x.get("autuacao") or "") >= lim:
                out.append({k: x.get(k) for k in ("processo", "classe", "assunto", "tribunal", "autuacao", "ultima_decisao", "url")})
    return out[:10]


def main(argv=None) -> int:
    root = Path(".")
    F = fotos(root)
    cand = candidatos_a_retirado(F)
    key = os.environ.get("YOUTUBE_API_KEY", "")
    conferido = False
    if cand and key:
        try:
            vivos = confirmar(sorted(cand), key)
            cand = {k: v for k, v in cand.items() if k not in vivos}
            conferido = True
        except Exception as e:  # noqa: BLE001 — a URL tem a chave
            print(f"⚠️ conferência pela API falhou: {type(e).__name__}")
    manual_p = root / "data/config/retirados_confirmados.json"
    manual = json.loads(manual_p.read_text(encoding="utf-8")) if manual_p.exists() else {}
    lista = []
    for vid, v in sorted(cand.items(), key=lambda kv: kv[1]["visto_pela_ultima_vez"], reverse=True):
        m = manual.get(vid) or {}
        lista.append({"video_id": vid, **v, "situacao": "retirado do ar ou tornado privado" + ("" if conferido else " (não conferido na API)"),
                      "motivo": m.get("motivo") or "não informado pelo YouTube", "fonte_motivo": m.get("fonte"),
                      "tag": "retirado por decisão judicial" if m.get("decisao") else "retirado",
                      "pistas_tse": pistas_tse(root, v)})
    datas = sorted(F)
    out = {"gerado_em_utc": now_utc(), "fotos": [datas[0], datas[-1]] if datas else None, "fotos_n": len(datas),
           "conferido_na_api": conferido, "total": len(lista), "videos": lista,
           "metodo": __doc__.split("\n\n", 1)[1].strip()}
    (root / "data/youtube/retirados.json").write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"YouTube retirados: {len(lista)} (fotos de {out['fotos']}, conferido na API: {conferido})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
