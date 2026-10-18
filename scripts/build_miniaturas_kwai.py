#!/usr/bin/env python3
"""Miniaturas (capas) dos vídeos do Kwai para a página: JPEG pequeno em data/kwai/miniaturas/<video_id>.jpg.

Seleção (data/config/kwai.json → miniaturas): todos os vídeos publicados desde `desde` + os `top_por_perfil` de maior
audiência de cada perfil em todo o acervo. A capa vem de `capa_url` (coverUrl do ator); URLs da CDN do Kwai expiram,
por isso o passo roda logo após a coleta. Não rebaixa o que já existe. Índice: data/kwai/miniaturas.json.
"""
from __future__ import annotations

import csv
import gzip
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import build_criativos_meta as bcm  # noqa: E402


def selecionar(rows: list[dict], desde: str, top: int) -> list[dict]:
    escolhidos = {r["video_id"]: r for r in rows if r.get("publicado_em", "") >= desde}
    por_perfil: dict[str, list[dict]] = {}
    for r in rows:
        por_perfil.setdefault(r["perfil"], []).append(r)
    for lst in por_perfil.values():
        lst.sort(key=lambda r: int(r.get("visualizacoes") or 0), reverse=True)
        for r in lst[:top]:
            escolhidos[r["video_id"]] = r
    return [r for r in escolhidos.values() if r.get("capa_url")]


def main(argv=None, baixar=None) -> int:
    argv = list(argv or [])
    plat = "facebook" if "--facebook" in argv else "kwai"  # Facebook: mesmas regras, capa do post
    argv = [a for a in argv if a != "--facebook"]
    root = Path(argv[0]) if argv else Path(".")
    cfg = json.loads((root / "data/config/kwai.json").read_text(encoding="utf-8"))["miniaturas"]
    src = root / f"data/{plat}/videos.csv.gz"
    if not src.exists():
        print(f"⛔ sem acervo ({plat})")
        return 1
    rows = list(csv.DictReader(gzip.open(src, "rt", encoding="utf-8"), delimiter=";"))
    pasta = root / f"data/{plat}/miniaturas"
    pasta.mkdir(parents=True, exist_ok=True)
    bcm.LARGURA = cfg["largura_px"]
    baixar = baixar or bcm.miniatura
    novas = falhas = 0
    for r in selecionar(rows, cfg["desde"], cfg["top_por_perfil"]):
        dest = pasta / f"{r['video_id']}.jpg"
        if dest.exists():
            continue
        if baixar(r["capa_url"], dest):
            novas += 1
        else:
            falhas += 1
    ids = sorted(p.stem for p in pasta.glob("*.jpg"))
    sem_capa = sum(1 for r in rows if not r.get("capa_url"))
    (root / f"data/{plat}/miniaturas.json").write_text(json.dumps({"ids": ids, "sem_capa_url": sem_capa}, separators=(",", ":")), encoding="utf-8")
    print(f"miniaturas {plat}: {novas} novas, {falhas} falhas, {len(ids)} no total; {sem_capa} vídeos do acervo sem URL de capa")
    return 0 if ids else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
