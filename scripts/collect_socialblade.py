#!/usr/bin/env python3
"""Série diária retroativa de seguidores via Social Blade, pela Apify (rl1987/social-blade-lookup; US$ 0,01 por evento).

O Social Blade bloqueia acesso direto de robôs (Cloudflare); o ator usa o backend do app oficial. Plataformas: Instagram,
TikTok e YouTube (o ator não cobre X nem Facebook). Contas 3 a 7 (a conta 1 não é usada).

--teste: 1 perfil (Instagram @lulaoficial).
sem opção: perfis de TikTok e YouTube declarados ao TSE por todas as chapas que foram às urnas no 1º turno (titular e vice;
o vice conta na chapa do titular). Perfis com série lida nos últimos 2 dias são pulados (a série é de ~30 dias; repetir a
coleta a cada 2 a 4 semanas emenda a série).
Tetos: US$ 3 (18/10, chapas 13 e 22) + US$ 5 (18/10, pedido "use até $5" para estender a todos os candidatos e vices).
Saída: data/seguidores/socialblade_historico.csv (plataforma; perfil; candidate_id; url_tse; data; seguidores; seguindo; posts;
visualizações quando houver) e socialblade_manifesto_latest.json. Bruto no privado.
"""
from __future__ import annotations

import csv
import gzip
import json
import os
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from collect_kwai_apify import g, inteiro  # noqa: E402
from collect_meta_anuncios_apify import custo_run  # noqa: E402
from collect_meta_apify import escolher_conta, run_actor  # noqa: E402
from net import now_utc  # noqa: E402

ATOR = "rl1987~social-blade-lookup"
SEGREDOS = ["APIFY_TOKEN_3", "APIFY_TOKEN_4", "APIFY_TOKEN_5", "APIFY_TOKEN_6", "APIFY_TOKEN_7"] + [f"APIFY_TOKEN_{i}" for i in range(8, 16)]
PADROES = {"instagram": r"instagram\.com/([A-Za-z0-9._]+)", "tiktok": r"tiktok\.com/@?([A-Za-z0-9._]+)",
           "youtube": r"youtube\.com/(?:@|c/|user/|channel/)?([A-Za-z0-9._-]+)"}
COLS = ["plataforma", "perfil", "candidate_id", "url_tse", "data", "seguidores", "seguindo", "posts", "visualizacoes", "coletado_em"]
TETO_TOTAL = 8.0


def titulares(root: Path) -> dict[str, str]:
    """número → SQ do titular, para as chapas que foram às urnas no 1º turno."""
    urna = json.loads((root / "data/elections.json").read_text(encoding="utf-8"))["candidates"]["2026"]
    out = {}
    for r in csv.DictReader(gzip.open(root / "data/tse/redes_sociais_candidatos_2026.csv.gz", "rt", encoding="utf-8"), delimiter=";"):
        nr = r.get("NR_CANDIDATO")
        if r.get("DS_CARGO", "").upper() == "PRESIDENTE" and nr in urna and (nr not in out or r.get("NM_URNA_CANDIDATO") == urna[nr]):
            out[nr] = r["SQ_CANDIDATO"]
    return out


def alvos(root: Path) -> list[dict]:
    out, vistos = [], set()
    IDS = titulares(root)
    pc = root / "data/config/youtube_correcoes.json"
    corr = json.loads(pc.read_text(encoding="utf-8")).get("correcoes", {}) if pc.exists() else {}
    for x in json.loads((root / "data/tse/redes_presidencia_2026.json").read_text(encoding="utf-8")):
        if x["url"] in corr:  # canal declarado que não funciona (ID todo em maiúsculas): usa o corrigido
            x = {**x, "url": corr[x["url"]]["usar"]}
        if x["plataforma"] not in PADROES or x["plataforma"] == "instagram" or x["nr"] not in IDS:  # Instagram: série bloqueada pelo Social Blade (README do ator)
            continue
        m = re.search(PADROES[x["plataforma"]], x["url"], re.I)
        if not m or m.group(1).lower() in ("p", "reel", "watch", "share"):
            continue
        k = (x["plataforma"], m.group(1).lower())
        if k in vistos:
            continue
        vistos.add(k)
        out.append({"plataforma": x["plataforma"], "perfil": m.group(1), "url_tse": x["url"], "candidate_id": IDS[x["nr"]]})
    return out


def pontos(item: dict) -> list[dict]:
    """Histórico diário: procura a lista de pontos (data + contagem) em qualquer chave do item."""
    for k in ("history", "historyData", "daily", "data.history", "history.data"):
        v = g(item, k)
        if isinstance(v, list) and v and isinstance(v[0], dict):
            return v
    for v in item.values():
        if isinstance(v, list) and v and isinstance(v[0], dict) and any(c in v[0] for c in ("date", "day", "timestamp")):
            return v
    return []


def main(argv=None, executar=None) -> int:
    argv = list(argv or [])
    root = Path(".")
    teste = "--teste" in argv
    agora = now_utc()
    seg = root / "data/seguidores"
    seg.mkdir(parents=True, exist_ok=True)
    manp = seg / "socialblade_manifesto_latest.json"
    hist_man = [json.loads(p.read_text(encoding="utf-8")) for p in seg.glob("socialblade_manifesto-*.json")]
    ja = round(sum(float(m.get("custo_usd") or 0) for m in hist_man), 4)
    man = {"run_started_utc": agora, "ferramenta": f"Apify · {ATOR.replace('~', '/')}", "modo": "teste" if teste else "carga",
           "teto_total_usd": TETO_TOTAL, "gasto_antes_usd": ja, "perfis": []}

    def fim(status, code):
        man["status"] = status
        stamp = agora.replace(":", "").replace("-", "")
        for p in (seg / f"socialblade_manifesto-{stamp}.json", manp):
            p.write_text(json.dumps(man, ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"social blade: {status}")
        return code

    al = alvos(root)
    arq0 = seg / "socialblade_historico.csv"
    if arq0.exists() and not teste:  # série lida há menos de 2 dias: pula (economia; a série do ator é de ~30 dias)
        import datetime as dt
        limite = (dt.date.fromisoformat(agora[:10]) - dt.timedelta(days=2)).isoformat()
        recentes = {(r["plataforma"], r["perfil"].lower()) for r in csv.DictReader(open(arq0, encoding="utf-8"), delimiter=";") if r["coletado_em"][:10] >= limite}
        man["pulados_coleta_recente"] = sorted(f"{p}:{h}" for p, h in recentes if any((a["plataforma"], a["perfil"].lower()) == (p, h) for a in al))
        al = [a for a in al if (a["plataforma"], a["perfil"].lower()) not in recentes]
    if teste:
        al = [a for a in al if a["plataforma"] == "tiktok" and a["perfil"].lower() == "lulaoficial"][:1]
    custo_est = 0.03 * len(al) + 0.01
    if ja + custo_est > TETO_TOTAL:
        return fim(f"⛔ teto de US$ {TETO_TOTAL} (gasto US$ {ja}; esta carga ≈ US$ {round(custo_est, 2)})", 1)
    nome, token, saldo = escolher_conta(SEGREDOS, custo_est) if executar is None else ("teste", "x", None)
    man.update(conta=nome, saldo_conta_antes_usd=saldo)
    if not token:
        return fim("⛔ nenhuma conta Apify dos outros pesquisadores com saldo", 1)
    executar = executar or (lambda pl, cap: run_actor(token, ATOR, pl, cap))
    arq = seg / "socialblade_historico.csv"
    linhas = {}
    if arq.exists():
        for r in csv.DictReader(open(arq, encoding="utf-8"), delimiter=";"):
            linhas[(r["plataforma"], r["perfil"].lower(), r["data"])] = r
    custo, brutos = 0.0, []
    for plat in sorted({a["plataforma"] for a in al}):
        grupo = [a for a in al if a["plataforma"] == plat]
        pl = {"platform": plat, "resultType": "profile", "queries": [a["perfil"] for a in grupo], "includeHistory": True, "includeGrowth": False,
              "historyLimit": 365}
        try:
            run, itens = executar(pl, max(0.1, round(0.03 * len(grupo) + 0.02, 3)))  # a Apify exige teto mínimo de US$ 0,10 por execução neste ator
        except Exception as e:  # noqa: BLE001 — o token vai no cabeçalho
            corpo = ""
            try:
                corpo = e.read().decode("utf-8", "replace")[:300]
            except Exception:  # noqa: BLE001
                pass
            man["perfis"].append({"plataforma": plat, "erro": f"{type(e).__name__} {getattr(e, 'code', '')} {corpo}".strip()})
            print(f"{plat}: erro {type(e).__name__} {corpo}")
            continue
        itens = itens or []
        custo += max(custo_run(run or {}) or 0, 0.02 * len(itens))
        # o modo "profile" pode vir sem a série; nesse caso, pede o histórico pelo id da plataforma (exigência do ator)
        # o modo "profile" traz ~30 dias; o pedido de histórico pelo id (historyLimit 365) devolveu os mesmos 30 dias
        # (teste de 18/10), então só é feito para perfil que veio sem série
        sem = {str(x.get("id")): x for x in itens if x.get("id") and not pontos(x)}
        if sem:
            try:
                run2, hist = executar({"platform": plat, "resultType": "history", "queries": list(sem), "historyLimit": 365}, max(0.1, round(0.01 * len(sem) + 0.02, 3)))
                custo += max(custo_run(run2 or {}) or 0, 0.01 * len(hist or []))
                for hx in hist or []:
                    alvo = sem.get(str(g(hx, "id", "query", "user.id") or ""))
                    if alvo is not None:
                        alvo["_history"] = (alvo.get("_history") or pontos(alvo)) + (pontos(hx) or ([hx] if g(hx, "date") else []))
                    else:
                        man.setdefault("historico_sem_par", []).append(sorted(hx.keys())[:20])
                brutos += hist or []
            except Exception as e:  # noqa: BLE001
                man["perfis"].append({"plataforma": plat, "erro_historico": f"{type(e).__name__} {getattr(e, 'code', '')}"})
        brutos += itens
        por = {a["perfil"].lower(): a for a in grupo}
        for x in itens:
            h = str(g(x, "query", "input", "username", "handle", "profile.username", "user.username") or "").lstrip("@").lower()
            a = por.get(h)
            pts = x.get("_history") or pontos(x)
            man["perfis"].append({"plataforma": plat, "perfil": h, "casou": bool(a), "pontos": len(pts),
                                  "chaves": sorted(x.keys())[:25], "chaves_ponto": sorted(pts[0].keys())[:15] if pts else None})
            if not a:
                continue
            for p in pts:
                d = str(g(p, "date", "day", "timestamp") or "")[:10]
                if not re.match(r"\d{4}-\d{2}-\d{2}", d):
                    continue
                linhas[(plat, a["perfil"].lower(), d)] = {"plataforma": plat, "perfil": a["perfil"], "candidate_id": a["candidate_id"], "url_tse": a["url_tse"],
                                                         "data": d, "seguidores": inteiro(g(p, "followers", "subscribers", "followerCount")),
                                                         "seguindo": inteiro(g(p, "following")), "posts": inteiro(g(p, "media", "posts", "videos", "uploads")),
                                                         "visualizacoes": inteiro(g(p, "views", "likes")), "coletado_em": agora}
        print(f"{plat}: {len(itens)} itens para {len(grupo)} perfis")
    interno = os.environ.get("ODI_INTERNO_DIR")
    if interno and brutos:
        d = Path(interno) / "socialblade"
        d.mkdir(parents=True, exist_ok=True)
        with gzip.open(d / f"apify_{agora.replace(':', '').replace('-', '')}.jsonl.gz", "wt", encoding="utf-8") as f:
            for x in brutos:
                f.write(json.dumps(x, ensure_ascii=False) + "\n")
    with open(arq, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, COLS, delimiter=";", lineterminator="\n", extrasaction="ignore")
        w.writeheader()
        w.writerows(sorted(linhas.values(), key=lambda r: (r["plataforma"], r["perfil"].lower(), r["data"])))
    man.update(custo_usd=round(custo, 4), linhas=len(linhas), datas=sorted({k[2] for k in linhas})[:1] + sorted({k[2] for k in linhas})[-1:])
    print(f"série: {len(linhas)} pontos · {man['datas']} · US$ {round(custo, 4)}")
    if brutos:
        print("chaves do 1º item: " + ", ".join(sorted(brutos[0].keys()))[:700])
    return fim("ok" if linhas else "⛔ nenhum ponto de série lido", 0 if linhas else 1)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
