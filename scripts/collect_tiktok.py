#!/usr/bin/env python3
"""TikTok das chapas 13 (Lula) e 22 (Flávio Bolsonaro): vídeos públicos dos perfis declarados ao TSE, via yt-dlp (grátis).

- Perfis: data/tse/redes_sociais_candidatos_2026.csv.gz, plataforma tiktok, cargos PRESIDENTE e VICE-PRESIDENTE,
  números das chapas em data/config/temas_youtube.json (o vice entra na chapa do titular).
- Sem login, sem chave: lê a lista pública de vídeos do perfil (metadados: legenda, visualizações, curtidas,
  comentários, compartilhamentos). Não baixa vídeo e não coleta texto de comentários.
- O TikTok bloqueia de forma intermitente IPs de servidor: cada perfil tem até TENTATIVAS tentativas com espera.
  Perfil que falha fica ⛔ no manifesto e os dados anteriores dele são PRESERVADOS (não viram zero nem somem).
- Data de publicação: o ID do vídeo do TikTok carrega o instante de criação nos 32 bits mais altos.
- Acumula em data/tiktok/videos.csv.gz (atualiza métricas de vídeos já vistos) e grava foto do dia.
"""
from __future__ import annotations

import csv
import datetime as dt
import gzip
import json
import re
import sys
import time
import urllib.parse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from net import now_utc  # noqa: E402

DESDE = "2026-07-20"  # pré-campanha (fases em data/config/trends.json)
TENTATIVAS = 3
ESPERA_S = 20
LIMITE_POR_PERFIL = 300
COLS = ["candidate_id", "candidate_name", "perfil", "declarado_por", "video_id", "url", "publicado_em", "legenda",
        "duracao_s", "visualizacoes", "curtidas", "comentarios", "compartilhamentos", "primeira_coleta", "ultima_coleta"]


def handle(url: str) -> str | None:
    u = url.strip()
    p = urllib.parse.urlparse(u if "://" in u else "https://" + u)
    if "tiktok.com" not in (p.hostname or "").lower():
        return None
    parts = [x for x in p.path.split("/") if x]
    if not parts:
        return None
    h = parts[0].lstrip("@").lower()
    return h if re.fullmatch(r"[a-z0-9._]{2,30}", h) else None


def data_do_id(video_id: str) -> str | None:
    """IDs do TikTok: os 32 bits mais altos são o Unix time de criação."""
    try:
        ts = int(video_id) >> 32
    except (TypeError, ValueError):
        return None
    if not 1_400_000_000 < ts < 2_500_000_000:
        return None
    return dt.datetime.fromtimestamp(ts, dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def alvos(root: Path) -> list[dict]:
    cfg = json.loads((root / "data/config/temas_youtube.json").read_text(encoding="utf-8"))
    por_numero = {c["numero"]: (cid, c["nome"]) for cid, c in cfg["candidatos"].items()}
    out, vistos = [], set()
    src = root / "data/tse/redes_sociais_candidatos_2026.csv.gz"
    for r in csv.DictReader(gzip.open(src, "rt", encoding="utf-8"), delimiter=";"):
        if r.get("PLATAFORMA") != "tiktok" or r.get("DS_CARGO", "").upper() not in ("PRESIDENTE", "VICE-PRESIDENTE"):
            continue
        nr = r.get("NR_CANDIDATO", "")
        if nr not in por_numero:
            continue
        h = handle(r["DS_URL"])
        if not h or h in vistos:
            continue
        vistos.add(h)
        cid, nome = por_numero[nr]
        out.append({"candidate_id": cid, "candidate_name": nome, "perfil": h,
                    "declarado_por": r.get("NM_URNA_CANDIDATO", ""), "url_tse": r["DS_URL"]})
    return sorted(out, key=lambda a: (a["candidate_id"], a["perfil"]))


def listar(perfil: str, limite: int = LIMITE_POR_PERFIL, desde: str = DESDE) -> tuple[list[dict], str | None]:
    """Lê a lista de vídeos página a página (preguiçosa). Se uma página seguinte falhar, devolve o que já chegou
    e o erro (antes, um erro em qualquer página descartava tudo). Para depois de 8 vídeos seguidos anteriores a `desde`
    (vídeos fixados no topo podem ser antigos, por isso não para no primeiro)."""
    import yt_dlp  # importado aqui para os testes rodarem sem a dependência
    opts = {"quiet": True, "no_warnings": True, "skip_download": True, "extract_flat": True, "lazy_playlist": True}
    out, antigos, erro = [], 0, None
    with yt_dlp.YoutubeDL(opts) as y:
        info = y.extract_info(f"https://www.tiktok.com/@{perfil}", download=False, process=False)
        try:
            for e in info.get("entries") or []:
                out.append(e)
                pub = data_do_id(str(e.get("id") or "")) or ""
                antigos = antigos + 1 if pub and pub < desde else 0
                if antigos >= 8 or len(out) >= limite:
                    break
        except Exception as ex:  # página seguinte bloqueada: mantém as anteriores
            erro = f"{type(ex).__name__}: {str(ex)[:160]}"
    if not out and erro:
        raise RuntimeError(erro)
    return out, erro


def linha(alvo: dict, e: dict, agora: str) -> dict | None:
    vid = str(e.get("id") or "")
    if not vid.isdigit():
        return None
    pub = data_do_id(vid)
    if e.get("timestamp"):
        pub = dt.datetime.fromtimestamp(int(e["timestamp"]), dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    leg = re.sub(r"\s+", " ", str(e.get("description") or e.get("title") or "")).strip()[:2000]
    num = lambda k: "" if e.get(k) is None else int(e[k])  # noqa: E731
    return {"candidate_id": alvo["candidate_id"], "candidate_name": alvo["candidate_name"], "perfil": alvo["perfil"],
            "declarado_por": alvo["declarado_por"], "video_id": vid,
            "url": f"https://www.tiktok.com/@{alvo['perfil']}/video/{vid}", "publicado_em": pub or "", "legenda": leg,
            "duracao_s": num("duration"), "visualizacoes": num("view_count"), "curtidas": num("like_count"),
            "comentarios": num("comment_count"), "compartilhamentos": num("repost_count"), "ultima_coleta": agora}


def mesclar(antigo: dict[str, dict], novas: list[dict]) -> dict[str, dict]:
    """Atualiza métricas dos vídeos vistos de novo; mantém os que não vieram (perfil bloqueado hoje)."""
    out = dict(antigo)
    for r in novas:
        chave = f"{r['perfil']}|{r['video_id']}"
        r["primeira_coleta"] = antigo.get(chave, {}).get("primeira_coleta") or r["ultima_coleta"]
        out[chave] = r
    return out


def ler_acervo(p: Path) -> dict[str, dict]:
    if not p.exists():
        return {}
    return {f"{r['perfil']}|{r['video_id']}": r for r in csv.DictReader(gzip.open(p, "rt", encoding="utf-8"), delimiter=";")}


def gravar(p: Path, rows: list[dict]):
    with gzip.open(p, "wt", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=COLS, delimiter=";", lineterminator="\n", extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)


def main(argv=None) -> int:
    root = Path(argv[0]) if argv else Path(".")
    outdir = root / "data/tiktok"
    outdir.mkdir(parents=True, exist_ok=True)
    agora = now_utc()
    try:
        import yt_dlp
        versao = yt_dlp.version.__version__
    except Exception:
        versao = None
    man = {"schema_version": 1, "stage": "coleta-tiktok", "run_started_utc": agora, "ferramenta": f"yt-dlp {versao}",
           "desde": DESDE, "perfis": [], "blocked": [], "warnings": [], "status": "ok"}
    novas = []
    for a in alvos(root):
        reg = {**a, "status": None, "tentativas": 0, "videos_lidos": 0, "videos_desde_inicio_campanha": 0}
        for t in range(1, TENTATIVAS + 1):
            reg["tentativas"] = t
            try:
                ents, parcial = listar(a["perfil"])
                if parcial:
                    reg["aviso"] = f"lista interrompida após {len(ents)} vídeos ({parcial})"
                rows = [r for r in (linha(a, e, agora) for e in ents) if r]
                reg["videos_lidos"] = len(rows)
                rows = [r for r in rows if r["publicado_em"] >= DESDE]
                reg["videos_desde_inicio_campanha"] = len(rows)
                novas += rows
                reg["status"] = "ok"
                break
            except Exception as e:  # bloqueio intermitente: espera e tenta de novo
                msg = str(e)
                reg["status"] = f"⛔ {type(e).__name__}: {msg[:200]}"
                if "does not have any videos" in msg:
                    reg["status"] = "sem vídeos públicos"  # perfil existe, mas vazio: não é bloqueio
                    break
                if t < TENTATIVAS:
                    time.sleep(ESPERA_S * t)
        if reg["status"] not in ("ok", "sem vídeos públicos"):
            man["blocked"].append(f"@{a['perfil']}: {reg['status']} (dados anteriores preservados)")
        man["perfis"].append(reg)
        time.sleep(3)
    acervo = mesclar(ler_acervo(outdir / "videos.csv.gz"), novas)
    rows = sorted(acervo.values(), key=lambda r: (r["publicado_em"], r["video_id"]), reverse=True)
    gravar(outdir / "videos.csv.gz", rows)
    gravar(outdir / f"videos_{agora[:10]}.csv.gz", [r for r in rows if r["ultima_coleta"] == agora])
    ok = sum(1 for p in man["perfis"] if p["status"] == "ok")
    man.update({"perfis_ok": ok, "perfis_total": len(man["perfis"]), "videos_novos_ou_atualizados": len(novas),
                "videos_acervo": len(rows)})
    if ok == 0:
        man["status"] = "bloqueado"
    elif man["blocked"]:
        man["status"] = "parcial"
    (outdir / "manifesto_latest.json").write_text(json.dumps(man, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({k: man[k] for k in ("status", "ferramenta", "perfis_ok", "perfis_total", "videos_novos_ou_atualizados",
                                          "videos_acervo", "blocked")}, ensure_ascii=False))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
