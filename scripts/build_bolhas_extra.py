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

import json
import os
import sys
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
        out = {"caso": c, "gerado_em_utc": now_utc(), "youtube": yt, "redes_sem_publicacoes": vazias(pub)}
        (pub / "bolhas_extra.json").write_text(json.dumps(out, ensure_ascii=False, separators=(",", ":")) + "\n", encoding="utf-8")
        print(c, "YouTube:", (yt or {}).get("videos_no_periodo"), "no período ·", "vazias:", {k: v.get("status") for k, v in out["redes_sem_publicacoes"].items()})
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
