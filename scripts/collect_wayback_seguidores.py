#!/usr/bin/env python3
"""Seguidores retroativos pelo Internet Archive (Wayback Machine): o número que aparecia na página do perfil em cada
captura arquivada. Grátis; teste pedido junto com o Social Blade (18/10/2026).

Para cada perfil declarado ao TSE (todas as chapas do 1º turno; Instagram, TikTok, YouTube e X), consulta o índice CDX do
Internet Archive entre `DESDE` e hoje, escolhe até 1 captura por mês (status 200) e lê o número na página arquivada:
- TikTok: "followerCount" no JSON embutido;
- YouTube: texto de inscritos ("1,2 mi de inscritos", "1.2M subscribers");
- Instagram: meta og:description ("1M Followers", "1 mi seguidores");
- X: "followers_count" quando a captura tem o JSON (páginas recentes do X são só JavaScript e costumam vir sem número).
Cada ponto guarda o endereço da captura (conferível). Captura sem número fica registrada no manifesto, sem ponto.
Saída: data/seguidores/wayback_historico.csv e wayback_manifesto_latest.json.
"""
from __future__ import annotations

import csv
import gzip
import html
import json
import re
import sys
import time
import urllib.parse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from collect_whatsapp_canais import numero  # noqa: E402
from net import now_utc, open_url, read_body  # noqa: E402

DESDE = "20260101"
CDX = "https://web.archive.org/cdx/search/cdx"
COLS = ["plataforma", "perfil", "numero_chapa", "candidate_name", "data", "seguidores", "captura", "coletado_em"]
PLATS = ("tiktok", "youtube", "instagram", "x")


def endereco(plat: str, url: str) -> str | None:
    """Endereço canônico do perfil para o CDX."""
    u = url.strip()
    if plat == "tiktok":
        m = re.search(r"tiktok\.com/@([A-Za-z0-9._]+)", u, re.I)
        return f"tiktok.com/@{m.group(1).lower()}" if m else None
    if plat == "instagram":
        m = re.search(r"instagram\.com/([A-Za-z0-9._]+)", u, re.I)
        return f"instagram.com/{m.group(1).lower()}/" if m and m.group(1).lower() not in ("p", "reel") else None
    if plat == "x":
        m = re.search(r"(?:x|twitter)\.com/@?([A-Za-z0-9_]+)", u, re.I)
        return f"x.com/{m.group(1)}" if m else None
    if plat == "youtube":
        m = re.search(r"youtube\.com/(@[^/?#]+|channel/UC[\w-]{22}|c/[^/?#]+|user/[^/?#]+)", u, re.I)
        return f"youtube.com/{m.group(1)}" if m else None
    return None


def alvos(root: Path) -> list[dict]:
    urna = json.loads((root / "data/elections.json").read_text(encoding="utf-8"))["candidates"]["2026"]
    pc = root / "data/config/youtube_correcoes.json"
    corr = json.loads(pc.read_text(encoding="utf-8")).get("correcoes", {}) if pc.exists() else {}
    out, vistos = [], set()
    for r in csv.DictReader(gzip.open(root / "data/tse/redes_sociais_candidatos_2026.csv.gz", "rt", encoding="utf-8"), delimiter=";"):
        if r.get("DS_CARGO", "").upper() not in ("PRESIDENTE", "VICE-PRESIDENTE") or r.get("NR_CANDIDATO") not in urna or r.get("PLATAFORMA") not in PLATS:
            continue
        url = corr.get(r["DS_URL"], {}).get("usar", r["DS_URL"])
        e = endereco(r["PLATAFORMA"], url)
        if not e or (r["PLATAFORMA"], e.lower()) in vistos:
            continue
        vistos.add((r["PLATAFORMA"], e.lower()))
        out.append({"plataforma": r["PLATAFORMA"], "perfil": e, "numero_chapa": r["NR_CANDIDATO"], "candidate_name": r.get("NM_URNA_CANDIDATO", "")})
    return out


def mil(txt: str) -> int | None:
    """'1,2 mi de inscritos' / '1.2M subscribers' / '35,4 mil' → inteiro."""
    t = html.unescape(txt).replace("\xa0", " ")
    m = re.search(r"([\d][\d.,]*)\s*(mil|mi|milhões|milhão|[KkMm])?\b", t)
    if not m:
        return None
    n, suf = m.group(1), (m.group(2) or "").lower()
    mult = {"mil": 1e3, "k": 1e3, "mi": 1e6, "milhões": 1e6, "milhão": 1e6, "m": 1e6}.get(suf)
    if mult:
        n = n.replace(".", "").replace(",", ".") if "," in n else n
        try:
            return int(round(float(n) * mult))
        except ValueError:
            return None
    return int(re.sub(r"[.,]", "", n))


def extrair(plat: str, pag: str) -> int | None:
    if plat == "tiktok":
        m = re.search(r'"followerCount"\s*:\s*(\d+)', pag)
        return int(m.group(1)) if m else None
    if plat == "youtube":
        m = re.search(r'"subscriberCountText"\s*:\s*\{[^{}]*?"simpleText"\s*:\s*"([^"]+)"', pag) or \
            re.search(r'"subscriberCountText"\s*:\s*\{"accessibility"[^}]*\}\}\s*,\s*"simpleText"\s*:\s*"([^"]+)"', pag) or \
            re.search(r'"content"\s*:\s*"([\d.,]+\s*(?:mil|mi|[KM])?\s*(?:de\s*)?(?:inscritos|subscribers))"', pag)
        return mil(m.group(1)) if m else None
    if plat == "instagram":
        m = re.search(r'<meta[^>]+(?:property|name)="(?:og:)?description"[^>]+content="([^"]*)"', pag) or \
            re.search(r'<meta[^>]+content="([^"]*)"[^>]+(?:property|name)="(?:og:)?description"', pag)
        return numero(m.group(1).lower()) if m else None
    if plat == "x":
        m = re.search(r'"followers_count"\s*:\s*(\d+)', pag)
        return int(m.group(1)) if m else None
    return None


def capturas(perfil: str, ate: str, get=None) -> list[tuple[str, str]]:
    """(timestamp, url original) — a primeira captura com status 200 de cada mês."""
    q = urllib.parse.urlencode({"url": perfil, "from": DESDE, "to": ate, "output": "json", "filter": "statuscode:200",
                                "collapse": "timestamp:6", "fl": "timestamp,original"})
    get = get or (lambda u: json.loads(read_body(open_url(u, timeout=60)) or b"[]"))
    linhas = get(f"{CDX}?{q}")
    return [(t, o) for t, o in linhas[1:]] if linhas else []


def main(argv=None, get=None, pagina=None) -> int:
    root = Path(argv[0]) if argv else Path(".")
    agora = now_utc()
    seg = root / "data/seguidores"
    seg.mkdir(parents=True, exist_ok=True)
    arq = seg / "wayback_historico.csv"
    linhas = {(r["plataforma"], r["perfil"].lower(), r["data"]): r for r in csv.DictReader(open(arq, encoding="utf-8"), delimiter=";")} if arq.exists() else {}
    pagina = pagina or (lambda u: read_body(open_url(u, timeout=60)).decode("utf-8", "replace"))
    man = {"run_started_utc": agora, "fonte": "Internet Archive (CDX + capturas arquivadas)", "desde": DESDE, "perfis": []}
    for a in alvos(root):
        reg = {"plataforma": a["plataforma"], "perfil": a["perfil"], "capturas": 0, "com_numero": 0, "erro": None}
        try:
            caps = capturas(a["perfil"], agora[:10].replace("-", ""), get)
            reg["capturas"] = len(caps)
            for ts, orig in caps:
                link = f"https://web.archive.org/web/{ts}id_/{orig}"
                try:
                    n = extrair(a["plataforma"], pagina(link))
                except Exception as e:  # noqa: BLE001
                    reg.setdefault("falhas", []).append(f"{ts}: {type(e).__name__}")
                    continue
                time.sleep(1)
                if n is None:
                    continue
                d = f"{ts[:4]}-{ts[4:6]}-{ts[6:8]}"
                reg["com_numero"] += 1
                linhas[(a["plataforma"], a["perfil"].lower(), d)] = {**{k: a[k] for k in ("plataforma", "perfil", "numero_chapa", "candidate_name")},
                                                                       "data": d, "seguidores": n, "captura": f"https://web.archive.org/web/{ts}/{orig}", "coletado_em": agora}
        except Exception as e:  # noqa: BLE001
            reg["erro"] = f"{type(e).__name__}: {str(e)[:120]}"
        man["perfis"].append(reg)
        print(f"{a['plataforma']} {a['perfil']}: {reg['capturas']} capturas, {reg['com_numero']} com número{' · ' + reg['erro'] if reg['erro'] else ''}")
        time.sleep(1)
    with open(arq, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, COLS, delimiter=";", lineterminator="\n", extrasaction="ignore")
        w.writeheader()
        w.writerows(sorted(linhas.values(), key=lambda r: (r["plataforma"], r["perfil"].lower(), r["data"])))
    man.update(pontos=len(linhas), perfis_com_ponto=len({(k[0], k[1]) for k in linhas}), status="ok" if linhas else "⛔ nenhuma captura com número")
    (seg / "wayback_manifesto_latest.json").write_text(json.dumps(man, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"wayback: {len(linhas)} pontos em {man['perfis_com_ponto']} perfis")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
