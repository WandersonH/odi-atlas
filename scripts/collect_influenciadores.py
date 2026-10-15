#!/usr/bin/env python3
"""Canais do YouTube que citam Lula ou Flávio Bolsonaro (rede de influenciadores do caderno 13).

- Chave SOMENTE por YOUTUBE_API_KEY (segredo do GitHub). Nunca gravada nem impressa.
- search.list (100 unidades/página) com as buscas de data/config/influenciadores_youtube.json, depois
  videos.list e channels.list (1 unidade por 50). Teto de cota por execução no config.
- Um vídeo só conta como citação se o nome aparece no título ou na descrição (a busca do YouTube é
  ampla); categorias e termos de exclusão afastam o molusco ("lula") e conteúdo fora de política.
- Canais declarados ao TSE por qualquer chapa presidencial ficam fora (são campanha, não influenciador).
- Canais com menos de min_inscritos ou contagem oculta ficam fora (não são tratados como influenciador).
- Acumula: data/youtube/influenciadores/videos.csv.gz e canais.csv (atualiza números a cada coleta).
- Não coleta comentários nem dados de quem assiste.
"""
from __future__ import annotations

import csv
import datetime as dt
import gzip
import json
import os
import re
import sys
import urllib.parse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from net import get_json, now_utc  # noqa: E402
from build_conteudo import norm, term_regex  # noqa: E402

BASE = "https://www.googleapis.com/youtube/v3"
VCOLS = ["video_id", "channel_id", "canal", "publicado_em", "titulo", "descricao", "categoria", "visualizacoes",
         "curtidas", "comentarios", "cita_280002542548", "cita_280002551544", "excluido", "primeira_coleta", "ultima_coleta"]
CCOLS = ["channel_id", "canal", "handle", "inscritos", "videos_total", "pais", "atualizado_em"]


class Cota:
    def __init__(self, teto: int):
        self.teto, self.usada = teto, 0

    def gastar(self, n: int) -> bool:
        if self.usada + n > self.teto:
            return False
        self.usada += n
        return True


def iso(d: dt.datetime) -> str:
    return d.strftime("%Y-%m-%dT%H:%M:%SZ")


def janelas(cfg: dict, agora: dt.datetime) -> list[dict]:
    out = []
    for b in cfg["buscas_por_execucao"]:
        desde = cfg["desde"] + "T00:00:00Z" if b.get("janela") == "desde" else iso(agora - dt.timedelta(days=b["janela_dias"]))
        out.append({"ordem": b["ordem"], "desde": desde, "paginas": b["paginas"]})
    return out


def compilar(cfg: dict):
    men = {cid: [term_regex(t) for t in c["mencao"]] for cid, c in cfg["candidatos"].items()}
    excl = [term_regex(t) for t in cfg["excluir_termos"]]
    return men, excl


def avaliar(v: dict, men, excl, cats: dict) -> dict:
    """cita_<cid> por menção no título/descrição; excluido = motivo (ou vazio)."""
    t = norm(v["titulo"] + " " + v["descricao"])
    out = {f"cita_{cid}": int(any(r.search(t) for r in regs)) for cid, regs in men.items()}
    motivo = ""
    if v["categoria"] in cats:
        motivo = "categoria " + v["categoria"]
    elif any(r.search(t) for r in excl):
        motivo = "termo de exclusão"
    elif not any(out.values()):
        motivo = "sem menção no título/descrição"
    out["excluido"] = motivo
    return out


def buscar(key, q, ordem, desde, paginas, cota: Cota) -> list[str]:
    ids, page = [], None
    for _ in range(paginas):
        if not cota.gastar(100):
            break
        p = {"part": "id", "type": "video", "q": q, "order": ordem, "publishedAfter": desde, "regionCode": "BR",
             "relevanceLanguage": "pt", "maxResults": 50, "key": key}
        if page:
            p["pageToken"] = page
        d = get_json(f"{BASE}/search?{urllib.parse.urlencode(p)}", timeout=60)
        ids += [it["id"]["videoId"] for it in d.get("items", []) if it.get("id", {}).get("videoId")]
        page = d.get("nextPageToken")
        if not page:
            break
    return ids


def em_lotes(key, recurso, part, ids, cota: Cota) -> list[dict]:
    out = []
    for i in range(0, len(ids), 50):
        if not cota.gastar(1):
            break
        q = urllib.parse.urlencode({"part": part, "id": ",".join(ids[i:i + 50]), "key": key})
        out += get_json(f"{BASE}/{recurso}?{q}", timeout=60).get("items", [])
    return out


def ler_csv(path: Path, gz: bool) -> dict[str, dict]:
    if not path.exists():
        return {}
    f = gzip.open(path, "rt", encoding="utf-8") if gz else open(path, encoding="utf-8")
    with f:
        k = "video_id" if gz else "channel_id"
        return {r[k]: r for r in csv.DictReader(f, delimiter=";")}


def gravar_csv(path: Path, cols, rows, gz: bool):
    f = gzip.open(path, "wt", encoding="utf-8", newline="") if gz else open(path, "w", encoding="utf-8", newline="")
    with f:
        w = csv.DictWriter(f, fieldnames=cols, delimiter=";", lineterminator="\n", extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)


def canais_de_campanha(root: Path) -> set[str]:
    p = root / "data/youtube/videos_latest.csv.gz"
    if not p.exists():
        return set()
    return {r["channel_id"] for r in csv.DictReader(gzip.open(p, "rt", encoding="utf-8"), delimiter=";")}


def main(argv=None) -> int:
    root = Path(argv[0]) if argv else Path(".")
    cfg = json.loads((root / "data/config/influenciadores_youtube.json").read_text(encoding="utf-8"))
    outdir = root / "data/youtube/influenciadores"
    outdir.mkdir(parents=True, exist_ok=True)
    started = now_utc()
    man = {"schema_version": 1, "stage": "coleta-influenciadores-youtube", "run_started_utc": started,
           "config": cfg, "buscas": [], "blocked": [], "warnings": [], "status": "ok"}
    key = os.environ.get("YOUTUBE_API_KEY", "").strip()
    if not key:
        man["status"] = "bloqueado"
        man["blocked"].append("YOUTUBE_API_KEY ausente (cadastre o segredo no GitHub)")
        (outdir / "manifesto_latest.json").write_text(json.dumps(man, ensure_ascii=False, indent=2), encoding="utf-8")
        print(json.dumps({k: man[k] for k in ("status", "blocked")}, ensure_ascii=False))
        return 1
    cota = Cota(cfg["cota_maxima_por_execucao"])
    agora = dt.datetime.now(dt.timezone.utc)
    achados: list[str] = []
    for cid, c in cfg["candidatos"].items():
        for q in c["buscas"]:
            for j in janelas(cfg, agora):
                try:
                    ids = buscar(key, q, j["ordem"], j["desde"], j["paginas"], cota)
                except Exception as e:  # registra e segue
                    man["warnings"].append(f"busca '{q}' {j['ordem']}: {type(e).__name__}: {e}")
                    ids = []
                man["buscas"].append({"candidato": c["nome"], "q": q, **j, "videos": len(ids)})
                achados += ids
    novos_ids = list(dict.fromkeys(achados))
    vids = em_lotes(key, "videos", "snippet,statistics", novos_ids, cota)
    men, excl = compilar(cfg)
    hist = ler_csv(outdir / "videos.csv.gz", gz=True)
    campanha = canais_de_campanha(root)
    for v in vids:
        sn, st = v.get("snippet", {}), v.get("statistics", {})
        row = {"video_id": v["id"], "channel_id": sn.get("channelId", ""), "canal": sn.get("channelTitle", ""),
               "publicado_em": sn.get("publishedAt", ""), "titulo": sn.get("title", ""),
               "descricao": re.sub(r"\s+", " ", sn.get("description", ""))[:600], "categoria": sn.get("categoryId", ""),
               "visualizacoes": st.get("viewCount", ""), "curtidas": st.get("likeCount", ""),
               "comentarios": st.get("commentCount", ""), "ultima_coleta": started}
        if row["publicado_em"] < cfg["desde"]:
            continue
        row.update(avaliar(row, men, excl, cfg["excluir_categorias"]))
        if row["channel_id"] in campanha:
            row["excluido"] = "canal de campanha (declarado ao TSE)"
        row["primeira_coleta"] = hist.get(v["id"], {}).get("primeira_coleta") or started
        hist[v["id"]] = row
    validos = {r["channel_id"] for r in hist.values() if not r["excluido"]}
    canais = ler_csv(outdir / "canais.csv", gz=False)
    for ch in em_lotes(key, "channels", "snippet,statistics", sorted(validos), cota):
        sn, st = ch.get("snippet", {}), ch.get("statistics", {})
        canais[ch["id"]] = {"channel_id": ch["id"], "canal": sn.get("title", ""), "handle": sn.get("customUrl", ""),
                            "inscritos": "" if st.get("hiddenSubscriberCount") else st.get("subscriberCount", ""),
                            "videos_total": st.get("videoCount", ""), "pais": sn.get("country", ""), "atualizado_em": started}
    gravar_csv(outdir / "videos.csv.gz", VCOLS, sorted(hist.values(), key=lambda r: r["publicado_em"], reverse=True), gz=True)
    gravar_csv(outdir / "canais.csv", CCOLS, sorted(canais.values(), key=lambda r: r["channel_id"]), gz=False)
    from collections import Counter
    man.update({"cota_usada": cota.usada, "videos_retornados": len(novos_ids), "videos_detalhados": len(vids),
                "videos_acumulados": len(hist), "videos_validos": sum(1 for r in hist.values() if not r["excluido"]),
                "exclusoes": dict(Counter(r["excluido"] for r in hist.values() if r["excluido"])),
                "canais_validos": len(validos), "canais_com_dados": len(canais)})
    if not vids:
        man["status"] = "bloqueado"
        man["blocked"].append("nenhum vídeo retornado pela busca")
    (outdir / "manifesto_latest.json").write_text(json.dumps(man, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({k: man[k] for k in ("status", "cota_usada", "videos_retornados", "videos_acumulados",
                                          "videos_validos", "exclusoes", "canais_validos")}, ensure_ascii=False))
    return 0 if man["status"] == "ok" else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
