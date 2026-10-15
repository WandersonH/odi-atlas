#!/usr/bin/env python3
"""Google Trends: interesse de busca pelos nomes das candidaturas.

Lê os grupos de termos de data/config/trends.json e, para cada grupo e período, grava:
  - a série temporal (interesse ao longo do tempo, Brasil);
  - o recorte por UF (interesse por região).

Cuidados metodológicos (registrados também no manifesto):
  - O Google Trends não dá volume de buscas. Os valores vão de 0 a 100 e são
    RELATIVOS dentro de cada consulta: só compare termos do mesmo grupo e período.
  - Cada consulta é uma amostra; repetir a mesma consulta pode dar números um pouco
    diferentes. Por isso cada coleta é guardada com data/hora, sem sobrescrever.
  - Palavras soltas são ambíguas ("lula" também é o molusco). Por isso a configuração
    usa TÓPICOS (entidades) do Trends sempre que possível; o tópico escolhido fica no manifesto.
  - Não há API oficial aberta. O coletor usa os mesmos endereços que a página do
    Trends usa; o Google pode limitar (HTTP 429) e isso é registrado como bloqueio.
"""
from __future__ import annotations

import argparse
import csv
import http.cookiejar
import json
import sys
import time
import urllib.error
import urllib.parse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from net import now_utc, open_url  # noqa: E402

BASE = "https://trends.google.com/trends"
HL, TZ = "pt-BR", "180"  # fuso de Brasília (UTC-3) em minutos


def _strip(txt: str):
    """As respostas do Trends começam com um prefixo anti-JSON-hijacking, ex.: )]}',"""
    return json.loads(txt[txt.index("{"):])


class Trends:
    def __init__(self, pause: float = 4.0, tries: int = 4):
        self.jar = http.cookiejar.CookieJar()
        self.pause, self.tries = pause, tries
        self._get(f"{BASE}/?geo=BR&hl={HL}", raw=True)  # obtém o cookie NID

    def _get(self, url: str, raw: bool = False):
        delay = self.pause
        for i in range(self.tries):
            try:
                with open_url(url, cookies=self.jar, timeout=60,
                              headers={"Accept-Language": "pt-BR,pt;q=0.9"}) as r:
                    body = r.read().decode("utf-8")
                time.sleep(self.pause)
                return body if raw else _strip(body)
            except urllib.error.HTTPError as e:
                if e.code != 429 or i == self.tries - 1:
                    raise
                time.sleep(delay)
                delay *= 2.5

    def explore(self, termos: list[str], periodo: str, geo: str):
        req = {"comparisonItem": [{"keyword": t, "geo": geo, "time": periodo} for t in termos],
               "category": 0, "property": ""}
        q = urllib.parse.urlencode({"hl": HL, "tz": TZ, "req": json.dumps(req, ensure_ascii=False)})
        return self._get(f"{BASE}/api/explore?{q}")["widgets"]

    def autocomplete(self, termo: str) -> list[dict]:
        q = urllib.parse.quote(termo)
        return self._get(f"{BASE}/api/autocomplete/{q}?hl={HL}&tz={TZ}")["default"]["topics"]

    def widget(self, endpoint: str, w: dict):
        q = urllib.parse.urlencode({"hl": HL, "tz": TZ, "req": json.dumps(w["request"], ensure_ascii=False),
                                    "token": w["token"]})
        return self._get(f"{BASE}/api/widgetdata/{endpoint}?{q}")


def resolver(t: "Trends", item) -> dict:
    """Converte um item da configuração no que será consultado.

    - texto simples ("Lula") → busca pela palavra, com o aviso de ambiguidade;
    - {"rotulo", "busca", "tipo_contem"} → tópico do Trends (entidade), escolhido no
      autocomplete pelo tipo esperado. Se nenhum tópico tiver esse tipo, é bloqueio:
      não cair em silêncio para a palavra solta.
    """
    if isinstance(item, str):
        return {"rotulo": item, "consulta": item, "modo": "palavra"}
    tops = t.autocomplete(item["busca"])
    alvos = item["tipo_contem"] if isinstance(item["tipo_contem"], list) else [item["tipo_contem"]]
    alvos = [a.lower() for a in alvos]
    hits = [x for x in tops if any(a in x.get("type", "").lower() for a in alvos)]
    if not hits:
        raise ValueError(f"tópico não encontrado para {item['busca']!r} com tipo contendo {item['tipo_contem']!r}; "
                         f"opções: {[(x.get('title'), x.get('type')) for x in tops]}")
    h = hits[0]
    return {"rotulo": item["rotulo"], "consulta": h["mid"], "modo": "topico",
            "topico_titulo": h.get("title"), "topico_tipo": h.get("type")}


def write_timeline(data: dict, termos: list[str], path: Path) -> int:
    rows = data["default"]["timelineData"]
    with open(path, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f, delimiter=";", lineterminator="\n")
        w.writerow(["timestamp_utc", "rotulo"] + termos + ["parcial"])
        for r in rows:
            ts = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(int(r["time"])))
            w.writerow([ts, r.get("formattedTime", "")] + r["value"] + [int(bool(r.get("isPartial")))])
    return len(rows)


def write_geo(data: dict, termos: list[str], path: Path) -> int:
    rows = data["default"]["geoMapData"]
    with open(path, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f, delimiter=";", lineterminator="\n")
        w.writerow(["geo_code", "geo_nome"] + termos)
        for r in rows:
            w.writerow([r.get("geoCode"), r.get("geoName")] + r["value"])
    return len(rows)


def resolver_periodo(periodo: str, cfg: dict, hoje: str | None = None) -> str:
    """'eleitoral' = das convenções partidárias até o 2º turno (ou até hoje, se antes): 'AAAA-MM-DD AAAA-MM-DD'.
    Outros valores ('now 7-d', 'today 3-m') vão direto para o Trends."""
    if periodo != "eleitoral":
        return periodo
    e = cfg["periodo_eleitoral"]
    hoje = hoje or time.strftime("%Y-%m-%d", time.gmtime())
    return f"{e['inicio']} {min(hoje, e['fim'])}"


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--config", default="data/config/trends.json")
    p.add_argument("--root", default=".")
    a = p.parse_args(argv)
    root = Path(a.root)
    cfg = json.loads((root / a.config).read_text(encoding="utf-8"))
    started = now_utc()
    outdir = root / "data" / "trends" / started[:10] / started[11:19].replace(":", "")
    outdir.mkdir(parents=True, exist_ok=True)
    man = {"schema_version": 1, "stage": "coleta-trends", "run_started_utc": started, "config": cfg,
           "aviso_metodologico": "Valores 0-100 relativos dentro de cada consulta (grupo x período). "
                                 "Não são volumes; não compare entre consultas diferentes.",
           "consultas": [], "blocked": []}
    try:
        t = Trends(pause=cfg.get("pausa_segundos", 4))
    except Exception as e:
        man["blocked"].append(f"sessão Trends: {type(e).__name__}: {e}")
        t = None
    for g in cfg["grupos"] if t else []:
        try:
            itens = [resolver(t, x) for x in g["termos"]]
        except Exception as e:
            man["blocked"].append(f"grupo {g['nome']}: {type(e).__name__}: {e}")
            continue
        termos = [i["rotulo"] for i in itens]
        consultas = [i["consulta"] for i in itens]
        if len(termos) > 5:
            man["blocked"].append(f"grupo {g['nome']}: o Trends aceita no máximo 5 termos por consulta")
            continue
        for periodo in cfg["periodos"]:
            janela = resolver_periodo(periodo, cfg)
            c = {"grupo": g["nome"], "termos": termos, "itens": itens, "periodo": periodo, "janela_trends": janela,
                 "geo": cfg.get("geo", "BR")}
            man["consultas"].append(c)
            tag = f"{g['nome']}__{periodo.replace(' ', '_')}"
            try:
                ws = {w["id"]: w for w in t.explore(consultas, janela, c["geo"])}
                ts = t.widget("multiline", ws["TIMESERIES"])
                (outdir / f"{tag}__serie.json").write_text(json.dumps(ts, ensure_ascii=False), encoding="utf-8")
                c["serie_pontos"] = write_timeline(ts, termos, outdir / f"{tag}__serie.csv")
                geo_w = next((w for k, w in ws.items() if k.startswith("GEO_MAP")), None)
                if geo_w:
                    gm = t.widget("comparedgeo", geo_w)
                    (outdir / f"{tag}__uf.json").write_text(json.dumps(gm, ensure_ascii=False), encoding="utf-8")
                    c["uf_linhas"] = write_geo(gm, termos, outdir / f"{tag}__uf.csv")
                c["status"] = "ok"
            except Exception as e:
                c["status"] = "erro"
                c["error"] = f"{type(e).__name__}: {e}"
                man["blocked"].append(f"{tag}: {c['error']}")
    man["run_finished_utc"] = now_utc()
    man["status"] = "bloqueado" if man["blocked"] else "ok"
    txt = json.dumps(man, ensure_ascii=False, indent=2)
    (outdir / "manifesto.json").write_text(txt, encoding="utf-8")
    (root / "data" / "manifest").mkdir(parents=True, exist_ok=True)
    (root / "data" / "manifest" / "trends_latest.json").write_text(txt, encoding="utf-8")
    print(txt)
    return 1 if man["blocked"] else 0


if __name__ == "__main__":
    sys.exit(main())
