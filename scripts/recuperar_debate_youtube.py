#!/usr/bin/env python3
"""Recupera do histórico do git os vídeos e comentários do debate no YouTube que coletas anteriores substituíram.

Por quê (22/10/2026): até hoje cada execução de collect_debate_youtube.py reescrevia a lista de vídeos e o arquivo de
comentários só com o que a busca daquele dia devolveu. Em 22/10 a busca falhou por cota (HTTP 429) e a lista caiu de 426
para 69 vídeos. O coletor agora acumula; este script junta, sem apagar nada, todas as versões já commitadas:

  vídeos (repositório público, data/debate/youtube_videos.json): união por id; vale a versão mais recente de cada vídeo,
    com o campo numeros_lidos_em = data da coleta daquela versão (números de visualização não são atualizados aqui);
  comentários (repositório privado, debate/youtube_comentarios.csv.gz): união por comment_id; vale a leitura mais recente.

Só leitura do histórico (git show); grava os dois arquivos atuais. Uso: ODI_INTERNO_DIR=... python scripts/recuperar_debate_youtube.py
"""
from __future__ import annotations

import csv
import gzip
import io
import json
import os
import subprocess
from collections import Counter
from pathlib import Path

ARQ = "data/debate/youtube_videos.json"
COM = "debate/youtube_comentarios.csv.gz"


def versoes(repo: str, caminho: str) -> list[str]:
    """Commits que tocaram o arquivo, do mais antigo para o mais recente."""
    return subprocess.check_output(["git", "-C", repo, "log", "--reverse", "--format=%h", "--", caminho], text=True).split()


def mostrar(repo: str, commit: str, caminho: str) -> bytes:
    return subprocess.check_output(["git", "-C", repo, "show", f"{commit}:{caminho}"])


def unir_videos(listas: list[tuple[str, list[dict]]]) -> dict[str, dict]:
    """listas = [(coletado_em, vídeos)] do mais antigo ao mais recente; a última leitura de cada id vence."""
    por = {}
    for quando, vids in listas:
        for v in vids:
            por[v["id"]] = {**v, "numeros_lidos_em": v.get("numeros_lidos_em") or quando}
    return por


def unir_comentarios(listas: list[list[dict]]) -> list[dict]:
    por = {}
    for rows in listas:
        for r in rows:
            por[r["comment_id"]] = r
    return list(por.values())


def main() -> int:
    atual = json.loads(Path(ARQ).read_text(encoding="utf-8"))
    hist = [json.loads(mostrar(".", c, ARQ)) for c in versoes(".", ARQ)]
    por = unir_videos([(d.get("coletado_em_utc"), d.get("videos") or []) for d in hist] + [(atual.get("coletado_em_utc"), atual.get("videos") or [])])
    antes = (atual.get("recuperado_do_historico") or {}).get("videos_antes") or len(atual.get("videos") or [])
    atual["videos"] = sorted(por.values(), key=lambda v: -(v.get("visualizacoes") or 0))
    atual["recuperado_do_historico"] = {"versoes_lidas": len(hist), "videos_antes": antes, "videos_depois": len(atual["videos"]),
                                        "nota": "vídeos que coletas anteriores substituíram, recuperados do histórico do git (22/10/2026)"}
    Path(ARQ).write_text(json.dumps(atual, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"vídeos: {antes} → {len(atual['videos'])} (de {len(hist)} versões)")
    interno = os.environ.get("ODI_INTERNO_DIR")
    if interno:
        p = Path(interno) / COM
        listas = []
        for c in versoes(interno, COM):
            listas.append(list(csv.DictReader(io.StringIO(gzip.decompress(mostrar(interno, c, COM)).decode("utf-8")), delimiter=";")))
        if p.exists():
            listas.append(list(csv.DictReader(gzip.open(p, "rt", encoding="utf-8"), delimiter=";")))
        rows = unir_comentarios(listas)
        campos = list(dict.fromkeys(k for r in listas[-1][:1] for k in r)) or list(rows[0])
        with gzip.open(p, "wt", encoding="utf-8", newline="") as f:
            w = csv.DictWriter(f, fieldnames=campos, delimiter=";", extrasaction="ignore")
            w.writeheader()
            w.writerows(rows)
        print(f"comentários: {len(listas[-1])} → {len(rows)} (de {len(listas)} versões)")
        n = Counter(r["video_id"] for r in rows)
        for v in atual["videos"]:
            v["comentarios_lidos"] = n.get(v["id"], 0)
        atual["comentarios_lidos"] = len(rows)
        atual["videos_com_comentarios_lidos"] = sum(1 for v in atual["videos"] if v["comentarios_lidos"])
        Path(ARQ).write_text(json.dumps(atual, ensure_ascii=False, indent=1), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
