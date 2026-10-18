#!/usr/bin/env python3
"""Caderno 04 — sentimento (polaridade) dos comentários do YouTube, por candidato, fase e vídeo.

Entrada (repositório privado, ODI_INTERNO_DIR): youtube/comentarios/comentarios.csv.gz (collect_comentarios_youtube.py)
Cache  (privado): youtube/comentarios/sentimento.csv.gz — comment_id; rótulo; probabilidades; modelo e revisão.
         Só comentários ainda não classificados passam pelo modelo (até max_por_execucao por run; o resto, no dia seguinte).
Saída  (pública, só agregados): data/youtube/comentarios/sentimento.json
Modelo e regras em data/config/sentimento_comentarios.json. Sem ODI_INTERNO_DIR, grava ⛔ e sai (não há texto público).
"""
from __future__ import annotations

import csv
import gzip
import json
import os
import re
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from net import now_utc  # noqa: E402

CAMPOS_CACHE = ["comment_id", "rotulo", "p_pos", "p_neg", "p_neu", "modelo", "revisao", "classificado_em"]


def preparar(t: str) -> str:
    """Normalização no estilo do pysentimiento: links, menções, emojis por extenso, letras repetidas."""
    import emoji
    t = re.sub(r"https?://\S+|www\.\S+", "url", t or "")
    t = re.sub(r"@[\w.\-]+", "@usuario", t)
    t = emoji.demojize(t, language="pt", delimiters=(" emoji ", " emoji "))
    t = re.sub(r"(.)\1{3,}", r"\1\1\1", t)
    return re.sub(r"\s+", " ", t).replace("_", " ").strip()


def classificador(modelo: str, max_tokens: int, lote: int):
    import torch
    from transformers import AutoModelForSequenceClassification, AutoTokenizer
    tok = AutoTokenizer.from_pretrained(modelo)
    m = AutoModelForSequenceClassification.from_pretrained(modelo).eval()
    torch.set_num_threads(os.cpu_count() or 2)
    rot = {i: l for i, l in m.config.id2label.items()}
    revisao = getattr(m.config, "_commit_hash", "") or ""

    def f(textos: list[str]) -> list[dict]:
        out = []
        with torch.inference_mode():
            for i in range(0, len(textos), lote):
                enc = tok([preparar(t) for t in textos[i:i + lote]], padding=True, truncation=True,
                          max_length=max_tokens, return_tensors="pt")
                pr = torch.softmax(m(**enc).logits, dim=-1).tolist()
                for p in pr:
                    d = {rot[j]: p[j] for j in range(len(p))}
                    out.append({"rotulo": max(d, key=d.get), "p_pos": round(d.get("POS", 0), 4),
                                "p_neg": round(d.get("NEG", 0), 4), "p_neu": round(d.get("NEU", 0), 4)})
        return out
    return f, revisao


def distrib(rotulos: list[str]) -> dict:
    c = Counter(rotulos)
    n = sum(c.values())
    if not n:
        return {"n": 0}
    pc = {k: round(c[k] / n * 100, 1) for k in ("POS", "NEG", "NEU")}
    return {"n": n, "positivo": pc["POS"], "negativo": pc["NEG"], "neutro": pc["NEU"],
            "saldo": round(pc["POS"] - pc["NEG"], 1)}


def fase_de(data: str, fases: list[dict]) -> str | None:
    for f in fases:
        if f["de"] <= data[:10] <= f["ate"]:
            return f["id"]
    return None


def semana_de(iso: str, fases: list[dict]) -> str | None:
    """Semana de campanha (segunda a domingo), rotulada pela segunda-feira; só dentro das fases."""
    import datetime as _dt
    d = (iso or "")[:10]
    if not fases or not d or d < fases[0]["de"] or d > fases[-1]["ate"]:
        return None
    dia = _dt.date.fromisoformat(d)
    return (dia - _dt.timedelta(days=dia.weekday())).isoformat()


def agregar(rows: list[dict], rot: dict[str, str], fases: list[dict], min_n: int, nomes: dict) -> dict:
    por_cand, por_fase, por_video, total = defaultdict(list), defaultdict(list), defaultdict(list), Counter()
    por_semana = defaultdict(list)
    for r in rows:
        total[r["candidate_id"]] += 1
        lab = rot.get(r["comment_id"])
        if not lab:
            continue
        por_cand[r["candidate_id"]].append(lab)
        f = fase_de(r.get("publicado_em", ""), fases)
        if f:
            por_fase[(r["candidate_id"], f)].append(lab)
            sem = semana_de(r.get("publicado_em", ""), fases)
            if sem:
                por_semana[(r["candidate_id"], f, sem)].append(lab)
        por_video[(r["candidate_id"], r["video_id"])].append(lab)
    out = {}
    for c in sorted(total):
        vids = {}
        for (cc, v), labs in por_video.items():
            if cc != c:
                continue
            vids[v] = distrib(labs) if len(labs) >= min_n else {"n": len(labs), "insuficiente": True}
        out[c] = {"nome": nomes.get(c, c), "coletados": total[c], **distrib(por_cand[c]),
                  "cobertura_pct": round(len(por_cand[c]) / total[c] * 100, 1),
                  "fases": [{"id": f["id"], "rotulo": f["rotulo"], "de": f["de"], "ate": f["ate"],
                             **distrib(por_fase[(c, f["id"])]),
                             "semanas": [{"semana": w, **distrib(por_semana[(c, f["id"], w)])}
                                         for w in sorted({k[2] for k in por_semana if k[0] == c and k[1] == f["id"]})]} for f in fases],
                  "videos": vids}
    return out


def ler_csv(p: Path) -> list[dict]:
    if not p.exists():
        return []
    with gzip.open(p, "rt", encoding="utf-8") as f:
        return list(csv.DictReader(f, delimiter=";"))


def main(argv=None, classificar=None) -> int:
    from collect_comentarios_youtube import plataforma
    plat, argv = plataforma(argv)
    root = Path(argv[0]) if argv else Path(".")
    cfg = json.loads((root / "data/config/sentimento_comentarios.json").read_text(encoding="utf-8"))
    fases = json.loads((root / "data/config/trends.json").read_text(encoding="utf-8")).get("fases", [])
    saida = root / f"data/{plat}/comentarios/sentimento.json"
    saida.parent.mkdir(parents=True, exist_ok=True)
    base = {"schema_version": 1, "gerado_em_utc": now_utc(), "modelo": cfg["modelo"], "metodo": cfg["nota"],
            "min_comentarios_video": cfg["min_comentarios_video"]}
    interno = os.environ.get("ODI_INTERNO_DIR")
    if not interno:
        saida.write_text(json.dumps({**base, "status": "⛔ sem acesso ao repositório privado (ODI_INTERNO_DIR): nada classificado"},
                                    ensure_ascii=False, indent=1), encoding="utf-8")
        print("⛔ ODI_INTERNO_DIR ausente")
        return 1
    d = Path(interno) / plat / ("respostas" if plat == "x" else "comentarios")
    rows = ler_csv(d / ("respostas.csv.gz" if plat == "x" else "comentarios.csv.gz"))
    cache = {r["comment_id"]: r for r in ler_csv(d / "sentimento.csv.gz") if r.get("modelo") == cfg["modelo"]}
    pend = [r for r in rows if r["comment_id"] not in cache and (r.get("texto") or "").strip()]
    pend.sort(key=lambda r: r.get("publicado_em", ""), reverse=True)  # mais recentes primeiro
    pend = pend[:cfg["max_por_execucao"]]
    revisao, feitos, t0 = "", 0, time.monotonic()
    if pend:
        if classificar is None:
            classificar, revisao = classificador(cfg["modelo"], cfg["max_tokens"], cfg["lote"])
        bloco = cfg.get("bloco_gravacao", 2000)
        for i in range(0, len(pend), bloco):  # grava a cada bloco: um run interrompido não perde o que já fez
            if time.monotonic() - t0 > cfg.get("tempo_max_minutos", 80) * 60:
                print(f"tempo máximo atingido: {feitos} classificados neste run, o resto fica para o próximo")
                break
            parte = pend[i:i + bloco]
            agora = now_utc()
            for r, s in zip(parte, classificar([r["texto"] for r in parte])):
                cache[r["comment_id"]] = {"comment_id": r["comment_id"], **s, "modelo": cfg["modelo"], "revisao": revisao, "classificado_em": agora}
            feitos += len(parte)
            with gzip.open(d / "sentimento.csv.gz", "wt", encoding="utf-8", newline="") as f:
                w = csv.DictWriter(f, CAMPOS_CACHE, delimiter=";", lineterminator="\n")
                w.writeheader()
                w.writerows(cache.values())
            print(f"  {feitos} classificados ({time.monotonic() - t0:.0f} s)", flush=True)
    rot = {k: v["rotulo"] for k, v in cache.items()}
    nomes = {}
    cj = root / f"data/{plat}/conteudo.json"
    if cj.exists():
        nomes = {k: v.get("nome", k) for k, v in json.loads(cj.read_text(encoding="utf-8"))["candidatos"].items()}
    cand = agregar(rows, rot, fases, cfg["min_comentarios_video"], nomes)
    faltam = sum(1 for r in rows if r["comment_id"] not in rot and (r.get("texto") or "").strip())
    revs = sorted({v.get("revisao", "") for v in cache.values()} - {""})
    out = {**base, "status": "ok" if not faltam else f"parcial: faltam {faltam} comentários (próximos runs)",
           "revisoes_modelo": revs, "classificados_neste_run": feitos, "classificados_total": len(rot),
           "comentarios_coletados": len(rows), "candidatos": cand}
    saida.write_text(json.dumps(out, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    for c in cand.values():
        print(f"{c['nome']}: {c.get('n')} classificados ({c['cobertura_pct']}%) · positivo {c.get('positivo')}% · negativo {c.get('negativo')}% · neutro {c.get('neutro')}%")
    print(f"sentimento: {feitos} classificados neste run, {faltam} pendentes")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
