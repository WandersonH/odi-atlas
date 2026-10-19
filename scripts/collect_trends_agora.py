#!/usr/bin/env python3
"""Google Trends "Em alta agora" (trends.google.com.br/trending, Brasil) para acompanhar o debate do 2º turno.

Pedido do usuário (18/10/2026, 22h24): página sobre o debate (Band/Estadão, 18/10, 20h), "cópia do Trends mais precisa", com as
tendências das últimas horas e a categoria Política; janela de 24 h antes e 24 h depois do debate.

Fontes (grátis, os mesmos endereços que a página do Trends usa; sem API oficial):
- lista "Em alta agora": RPC i0OFE do batchexecute (Brasil, pt-BR, últimas 4 h e 24 h) — termo, volume de buscas aproximado,
  aumento, início, se segue ativo, categorias e termos agrupados ("detalhamento"). Categoria Política = id 14 (rótulo do Trends).
- RSS de tendências do Brasil (trends.google.com/trending/rss?geo=BR): volume aproximado e notícias ligadas a cada termo.
- curva de interesse por termo nas últimas 24 h e 7 dias (explore, a cada 8 min / hora): Lula, Flávio Bolsonaro, "debate".
Cada execução grava um retrato (data/trends/agora/retratos/AAAAMMDD-HHMM.json) e atualiza o consolidado
data/trends/agora/debate.json: cada termo com primeira e última vez visto, maior volume, categorias e notícias.
Os números do Trends são aproximados (faixas: "2 mil+", "50 mil+") e a lista muda a cada atualização da página.
"""
from __future__ import annotations

import datetime as dt
import email.utils
import json
import re
import sys
import time
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from collect_trends import Trends  # noqa: E402
from net import now_utc, open_url, read_body  # noqa: E402

BATCH = "https://trends.google.com/_/TrendsUi/data/batchexecute"
RSS = "https://trends.google.com/trending/rss?geo=BR"
# ids da página "Em alta agora"; nomes conferidos pelos termos de cada id no retrato de 19/10 01h26 UTC (ex.: 17 = futebol,
# 20 = previsão do tempo, 9 = Unicamp/OAB, 10 = locais de votação); 12 e 13 não apareceram e ficam sem nome
CATEGORIAS = {1: "Veículos", 2: "Beleza e moda", 3: "Negócios e finanças", 4: "Entretenimento", 5: "Comida e bebida", 6: "Jogos",
              7: "Saúde", 8: "Hobbies e lazer", 9: "Empregos e educação", 10: "Lei e governo", 11: "Outros", 14: "Política",
              15: "Ciência", 16: "Compras", 17: "Esportes", 18: "Tecnologia", 19: "Viagens e transporte", 20: "Clima"}
POLITICA = 14
DEBATE = {"inicio": "2026-10-18T23:00:00Z", "rotulo": "Debate Band/Estadão · 2º turno · 18/10 às 20h (Brasília)",
          "janela_de": "2026-10-17T23:00:00Z", "janela_ate": "2026-10-19T23:00:00Z"}
TERMOS_CURVA = ["Lula", "Flávio Bolsonaro", "debate"]


def batch(horas: int, get=None) -> list:
    req = json.dumps([[["i0OFE", json.dumps([None, None, "BR", 0, "pt-BR", horas, 1]), None, "generic"]]])
    body = urllib.parse.urlencode({"f.req": req}).encode()
    if get:
        txt = get(horas)
    else:
        r = urllib.request.Request(BATCH + "?hl=pt-BR&gl=BR", data=body,
                                   headers={"Content-Type": "application/x-www-form-urlencoded;charset=UTF-8",
                                            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124 Safari/537.36"})
        with urllib.request.urlopen(r, timeout=60) as resp:
            txt = resp.read().decode("utf-8")
    for linha in txt.splitlines():
        if linha.startswith('[["wrb.fr"'):
            env = json.loads(linha)
            dados = json.loads(env[0][2])
            return dados[1] if isinstance(dados, list) and len(dados) > 1 and isinstance(dados[1], list) else []
    return []


def ts(v) -> str | None:
    if isinstance(v, list) and v and isinstance(v[0], (int, float)):
        v = v[0]
    if isinstance(v, (int, float)) and v > 1e9:
        return dt.datetime.fromtimestamp(v, dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    return None


def termo(t: list) -> dict:
    """Uma tendência do i0OFE. Posições conferidas na resposta da página (manifesto guarda o 1º item bruto)."""
    def at(i):
        return t[i] if len(t) > i else None
    cats = at(10) if isinstance(at(10), list) else []
    rel = at(9) if isinstance(at(9), list) else []
    return {"termo": at(0), "inicio": ts(at(3)), "fim": ts(at(4)), "ativo": at(4) in (None, [], 0),
            "volume": at(6) if isinstance(at(6), int) else None, "aumento_pct": at(8) if isinstance(at(8), (int, float)) else None,
            "categorias": [c for c in cats if isinstance(c, int)], "relacionados": [x for x in rel if isinstance(x, str)][:15]}


def rss(get=None) -> dict:
    xml = get() if get else read_body(open_url(RSS, timeout=60))
    root = ET.fromstring(xml)
    ns = {"ht": "https://trends.google.com/trending/rss"}
    out = {}
    for it in root.iter("item"):
        nome = (it.findtext("title") or "").strip()
        pub = it.findtext("pubDate") or ""
        try:
            pub = email.utils.parsedate_to_datetime(pub).astimezone(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        except (TypeError, ValueError):
            pub = ""
        trafego = None
        noticias = []
        for el in it:
            tag = el.tag.split("}")[-1]
            if tag == "approx_traffic":
                trafego = (el.text or "").strip()
            if tag == "news_item":
                n = {c.tag.split("}")[-1]: (c.text or "").strip() for c in el}
                noticias.append({"titulo": n.get("news_item_title"), "url": n.get("news_item_url"), "veiculo": n.get("news_item_source")})
        out[nome.lower()] = {"termo": nome, "trafego": trafego, "publicado": pub, "noticias": noticias[:5]}
    _ = ns
    return out


def curvas() -> dict:
    t = Trends(pause=3)
    out = {}
    for janela in ("now 1-d", "now 7-d"):
        ws = {w["id"]: w for w in t.explore(TERMOS_CURVA, janela, "BR")}
        ts_ = t.widget("multiline", ws["TIMESERIES"])
        out[janela] = [{"t": dt.datetime.fromtimestamp(int(p["time"]), dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                        "v": dict(zip(TERMOS_CURVA, p.get("value") or []))} for p in ts_["default"]["timelineData"]]
    return out


def main(argv=None, get_batch=None, get_rss=None, get_curvas=None) -> int:
    root = Path(next((a for a in (argv or []) if not a.startswith("--")), "."))
    pasta = root / "data/trends/agora"
    (pasta / "retratos").mkdir(parents=True, exist_ok=True)
    agora = now_utc()
    if "--sempre" not in (argv or []) and agora > DEBATE["janela_ate"]:
        print(f"fora da janela do debate (até {DEBATE['janela_ate']}): nada coletado")
        return 0
    ret = {"coletado_em_utc": agora, "erros": {}, "listas": {}}
    for h in (4, 24):
        try:
            brutos = batch(h, get_batch)
            ret["listas"][f"{h}h"] = [termo(t) for t in brutos if isinstance(t, list) and t and isinstance(t[0], str)]
            if brutos:
                ret.setdefault("amostra_bruta", json.dumps(brutos[0], ensure_ascii=False)[:1500])
        except Exception as e:  # noqa: BLE001
            ret["erros"][f"lista_{h}h"] = f"{type(e).__name__}: {str(e)[:200]}"
    try:
        ret["rss"] = rss(get_rss)
    except Exception as e:  # noqa: BLE001
        ret["erros"]["rss"] = f"{type(e).__name__}: {str(e)[:200]}"
        ret["rss"] = {}
    try:
        ret["curvas"] = (get_curvas or curvas)()
    except Exception as e:  # noqa: BLE001
        ret["erros"]["curvas"] = f"{type(e).__name__}: {str(e)[:200]}"
    (pasta / "retratos" / f"{agora[:16].replace('-', '').replace(':', '').replace('T', '-')}.json").write_text(json.dumps(ret, ensure_ascii=False), encoding="utf-8")
    # consolidado: todos os retratos
    cons = {}
    retratos = []
    ultima_curva = None
    for f in sorted((pasta / "retratos").glob("*.json")):
        r = json.loads(f.read_text(encoding="utf-8"))
        retratos.append({"t": r["coletado_em_utc"], "n24": len(r["listas"].get("24h", [])), "erros": list(r.get("erros", {}))})
        if r.get("curvas"):
            ultima_curva = r["curvas"]
        for janela in ("4h", "24h"):
            for x in r["listas"].get(janela, []):
                k = (x["termo"] or "").lower()
                if not k:
                    continue
                c = cons.setdefault(k, {"termo": x["termo"], "primeira_vez_visto": r["coletado_em_utc"], "categorias": x["categorias"],
                                        "inicio": x["inicio"], "volume_max": None, "retratos": 0, "relacionados": []})
                c["ultima_vez_visto"] = r["coletado_em_utc"]
                c["retratos"] += 1
                c["inicio"] = min(filter(None, [c["inicio"], x["inicio"]]), default=None)
                c["fim"] = x["fim"]
                c["ativo"] = x["ativo"]
                if x["volume"] is not None and (c["volume_max"] is None or x["volume"] > c["volume_max"]):
                    c["volume_max"] = x["volume"]
                c["relacionados"] = sorted(set(c["relacionados"]) | set(x["relacionados"]))[:20]
                c["categorias"] = sorted(set(c["categorias"]) | set(x["categorias"]))
        for k, v in (r.get("rss") or {}).items():
            if k in cons:
                cons[k]["trafego_rss"] = v["trafego"]
                if v["noticias"]:
                    cons[k]["noticias"] = v["noticias"]
    for c in cons.values():
        c["politica"] = POLITICA in c["categorias"]
        c["rotulos"] = [CATEGORIAS.get(i, str(i)) for i in c["categorias"]]
        ini = c.get("inicio")
        c["momento"] = None if not ini else "antes do debate" if ini < DEBATE["inicio"] else "durante/depois do debate"
    termos = sorted(cons.values(), key=lambda c: (-(c["volume_max"] or 0), c["termo"]))
    out = {"schema_version": 1, "gerado_em_utc": agora, "debate": DEBATE, "categorias": CATEGORIAS, "politica_id": POLITICA,
           "retratos": retratos, "ultimo_retrato": {"t": agora, "erros": ret["erros"],
                                                       "lista_4h": [x["termo"] for x in ret["listas"].get("4h", [])][:60]},
           "termos": termos, "curvas": ultima_curva,
           "metodo": "Lista 'Em alta agora' do Google Trends (Brasil, pt-BR), lida a cada execução; volumes são as faixas aproximadas "
                     "que o Trends mostra. 'Primeira vez visto' é o primeiro retrato do Atlas em que o termo apareceu; 'início' é o "
                     "horário que o próprio Trends informa. Categoria Política = rótulo do Trends (id 14). Curvas: interesse relativo "
                     "(0–100) por termo, mesma consulta para os três termos."}
    (pasta / "debate.json").write_text(json.dumps(out, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    n = {k: len(v) for k, v in ret["listas"].items()}
    pol = sum(1 for c in termos if c["politica"])
    print(f"retrato {agora}: listas {n} · rss {len(ret.get('rss') or {})} · termos acumulados {len(termos)} (política {pol}) · erros {ret['erros']}")
    if ret.get("amostra_bruta"):
        print("1º item bruto: " + ret["amostra_bruta"][:800])
    return 0 if any(ret["listas"].values()) or ret.get("rss") else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
