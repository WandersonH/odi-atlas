"""Complemento da linha do tempo de bolhas de cada caso (pedido do responsável, 02/11/2026, 16h32: "porque vc não incluiu o
youtube e kwai aqui nesses gráficos?").

- YouTube: os vídeos da busca do caso (privado casos/<id>/busca_coleta.json, YouTube Data API) viram pontos
  [hora UTC, visualizações, canal, url]; canal e link só com 10 mil+ inscritos (regra do projeto). Vídeos não passam pela
  pré-codificação de Bardin (que lê as publicações das redes), então entram sem categoria.
- Redes coletadas sem nenhuma publicação lida (em geral Kwai): a situação da última tentativa de cada uma, lida dos
  manifestos públicos data/casos/<id>/manifesto-*.json, para o gráfico mostrar a faixa vazia com o motivo em vez de sumir com ela.
Saída: data/casos/<id>/bolhas_extra.json. Grátis; não coleta nada. Uso: ODI_INTERNO_DIR=... python scripts/build_bolhas_extra.py [--caso 016 ...]
"""
from __future__ import annotations

import csv
import gzip
import json
import os
import re
import sys
import unicodedata
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from net import now_utc  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
MIN_PUBLICO = 10000


def num(v) -> int:
    try:
        return int(float(v))
    except (TypeError, ValueError):
        return 0


def youtube(priv_caso: Path, desde: str) -> dict | None:
    p = priv_caso / "busca_coleta.json"
    if not p.exists():
        return None
    vs = ((json.loads(p.read_text(encoding="utf-8")).get("youtube") or {}).get("videos")) or []
    vs = list({v["id"]: v for v in vs if v.get("id")}.values())
    no_periodo = [v for v in vs if (v.get("publicado_em") or "")[:10] >= desde]
    pts = []
    for v in sorted(no_periodo, key=lambda v: v.get("publicado_em") or ""):
        grande = num(v.get("inscritos")) >= MIN_PUBLICO
        pts.append([(v.get("publicado_em") or "")[:16], num(v.get("visualizacoes")), v.get("canal") if grande else None,
                    f"https://www.youtube.com/watch?v={v['id']}" if grande else None])
    return {"videos_lidos": len(vs), "videos_no_periodo": len(no_periodo), "pontos": pts,
            "fonte": "YouTube Data API, busca por termo do caso (até 100 vídeos por consulta); o total é um piso",
            "universo": "⛔ desconhecido: a busca do YouTube não informa o total de vídeos por termo de forma exata"}


PARADAS = set("a o as os de da do das dos e em no na nos nas um uma para por com que se seu sua ou ao".split())


def sem_acento(t: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", (t or "").lower()) if unicodedata.category(c) != "Mn")


def regras(termos: list[str]) -> list[tuple[str, list[list[list[str]]]]]:
    """Termo do caso → grupos (separados por '+') de alternativas (separadas por '/') de palavras que precisam aparecer todas.
    '#tag' vira a própria hashtag; 'reels: ' sai; termos genéricos da coleta ('o caso (busca por termo)', 'posts de …') ficam de fora."""
    out = []
    for t in termos:
        b = re.sub(r"^(reels|diário|diario|posts?)\s*:\s*", "", t.strip(), flags=re.I)
        if not b or "(" in b or b.lower().startswith(("posts de", "menções a", "mencoes a")):
            continue
        grupos = []
        for parte in b.split("+"):
            alts = [[w for w in re.findall(r"#?[\w]+", sem_acento(a)) if w not in PARADAS] for a in parte.split("/")]
            alts = [a for a in alts if a]
            if alts:
                grupos.append(alts)
        if grupos:
            out.append((t, grupos))
    return out


def casa(texto: str, rg) -> str | None:
    tx = sem_acento(texto)
    palavras = set(re.findall(r"#?\w+", tx)) | {w.lstrip("#") for w in re.findall(r"#\w+", tx)}
    for termo, grupos in rg:
        if all(any(all((w in palavras) if w.startswith("#") else (w in palavras or ("#" + w) in palavras) for w in alt) for alt in g) for g in grupos):
            return termo
    return None


def outras_coletas(desde: str, termos: list[str], interno: str | None) -> dict:
    """Vídeos que o Atlas já coleta por outros caminhos e que citam um termo do caso no período (pedido de 02/11/2026, 16h38:
    "Kwai vc tá coletando ele mesmo"): perfis das campanhas no Kwai e no TikTok e a série de hashtags do TikTok."""
    rg = regras(termos)
    fontes = [("kwai", "perfis das campanhas no Kwai (data/kwai/videos.csv.gz)", ROOT / "data/kwai/videos.csv.gz", True),
              ("tiktok", "perfis das campanhas no TikTok (data/tiktok/videos.csv.gz)", ROOT / "data/tiktok/videos.csv.gz", True)]
    priv_h = Path(interno) / "tiktok/hashtags/videos_todos.csv.gz" if interno else None
    fontes.append(("tiktok", "série Vídeos por hashtag do TikTok", priv_h if priv_h and priv_h.exists() else ROOT / "data/tiktok/hashtags/videos.csv.gz", False))
    out = {"pontos": [], "fontes": [], "regra": "o texto do vídeo contém todas as palavras de um termo do caso (sem acento; '#' exige a hashtag; '+' e '/' do termo viram E e OU)"}
    for rede, nome, arq, oficial in fontes:
        if not arq.exists():
            out["fontes"].append({"rede": rede, "fonte": nome, "status": "⛔ arquivo ausente"})
            continue
        lidos = casados = 0
        vistos = set()
        for r in csv.DictReader(gzip.open(arq, "rt", encoding="utf-8"), delimiter=";"):
            if (r.get("publicado_em") or "")[:10] < desde or r.get("video_id") in vistos:
                continue
            vistos.add(r.get("video_id"))
            lidos += 1
            termo = casa((r.get("legenda") or "") + " " + " ".join("#" + h for h in (r.get("hashtags") or "").split("|") if h), rg)
            if not termo:
                continue
            casados += 1
            pub = oficial or num(r.get("seguidores")) >= MIN_PUBLICO
            out["pontos"].append([(r.get("publicado_em") or "")[:16], rede, num(r.get("visualizacoes")),
                                  (r.get("perfil") or r.get("conta")) if pub else None, r.get("url") if pub else None, nome, termo])
        out["fontes"].append({"rede": rede, "fonte": nome, "videos_no_periodo": lidos, "citam_termo_do_caso": casados})
    out["pontos"].sort(key=lambda p: p[0])
    return out


def vazias(pub_caso: Path) -> dict:
    caso = json.loads((pub_caso / "caso.json").read_text(encoding="utf-8")) if (pub_caso / "caso.json").exists() else {}
    zero = [r for r, v in (caso.get("redes") or {}).items() if v.get("coletada") and not v.get("publicacoes")]
    out = {}
    for f in sorted(pub_caso.glob("manifesto-*.json")):
        try:
            m = json.loads(f.read_text(encoding="utf-8"))
        except Exception:  # noqa: BLE001
            continue
        for r in m.get("redes", []):
            nome = {"kwai": "Kwai", "tiktok": "TikTok", "x": "X", "instagram": "Instagram", "facebook": "Facebook"}.get(r.get("rede"), r.get("rede"))
            if nome in zero:
                out[nome] = {"ultima_tentativa": f.stem.replace("manifesto-", ""), "status": r.get("status"),
                             "itens_do_ator": sum((t.get("itens") or 0) for t in (r.get("termos") or []) if isinstance(t, dict))}
    for r in zero:
        out.setdefault(r, {"status": "coletada sem nenhuma publicação no período"})
    # "teto da rede esgotado" com teto 0 quer dizer que nunca houve verba autorizada para a rede, não que ela foi gasta
    try:
        cfg = json.loads((ROOT / "data/config/casos.json").read_text(encoding="utf-8"))
        conf = next((x for x in (cfg.get("casos") if isinstance(cfg, dict) and "casos" in cfg else cfg) if x.get("id") == pub_caso.name), {})
    except Exception:  # noqa: BLE001
        conf = {}
    for r, v in out.items():
        teto = (conf.get("teto_usd") or {}).get(r.lower())
        if teto is not None:
            v["teto_usd_do_caso"] = teto
            if v.get("status") == "ok":
                v["status"] = "lida, mas nenhuma publicação no período do caso"
            if not teto and "teto" in str(v.get("status")):
                v["status"] = "⛔ sem verba autorizada para esta rede neste caso (teto US$ 0)"
    return out


def main(argv: list[str]) -> int:
    interno = os.environ.get("ODI_INTERNO_DIR")
    pedidos = [argv[i + 1] for i, a in enumerate(argv) if a == "--caso"]
    casos = pedidos or sorted(p.parent.name for p in (ROOT / "data/casos").glob("*/caso.json"))
    for c in casos:
        pub = ROOT / "data/casos" / c
        desde = (json.loads((pub / "caso.json").read_text(encoding="utf-8")).get("desde") or "") if (pub / "caso.json").exists() else ""
        yt = youtube(Path(interno) / "casos" / c, desde) if interno else None
        termos = (json.loads((pub / "caso.json").read_text(encoding="utf-8")).get("termos") or []) if (pub / "caso.json").exists() else []
        oc = outras_coletas(desde, termos, interno) if desde else None
        out = {"caso": c, "gerado_em_utc": now_utc(), "youtube": yt, "outras_coletas": oc, "redes_sem_publicacoes": vazias(pub)}
        (pub / "bolhas_extra.json").write_text(json.dumps(out, ensure_ascii=False, separators=(",", ":")) + "\n", encoding="utf-8")
        print(c, "YouTube:", (yt or {}).get("videos_no_periodo"), "no período · outras coletas:", [(f["fonte"][:22], f.get("citam_termo_do_caso")) for f in (oc or {}).get("fontes", [])], "·", "vazias:", {k: v.get("status") for k, v in out["redes_sem_publicacoes"].items()})
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
