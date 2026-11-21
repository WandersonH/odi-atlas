#!/usr/bin/env python3
"""Caso 039: retransmissões das lives de Lula com Janones em outros canais do YouTube (API oficial, grátis).

Pedido do responsável (21/11/2026, 12h53): "quero pegar retransmissões também".

Para cada live do caso (videos_youtube em data/config/casos.json):
  1. lê o vídeo original (início e fim reais da transmissão, duração);
  2. busca no YouTube vídeos de OUTROS canais publicados entre 6 h antes e 72 h depois do início (BUSCAS + o título da live),
     a cada execução enquanto a live tem menos de 7 dias; depois só atualiza os números dos vídeos já achados (a lista de
     achados fica no privado; sem o privado, a busca é refeita sempre);
  3. fica só com vídeos cujo título tem "Lula" e ("Janones" ou "Exército");
  4. classifica: "ao vivo simultânea" (transmissão ao vivo que começou até 3 h antes ou depois do original e dura ao menos metade
     dele), "transmissão ao vivo em outro horário" ou "outro vídeo sobre a live" (vídeo comum);
  5. lê inscritos de cada canal. Canal com menos de 10 mil inscritos (ou que esconde o número) aparece só como código, sem
     título nem link (regra do Atlas para contas comuns).
Comentários das retransmissões: só quando há repositório privado ($ODI_INTERNO_DIR), até PAGINAS páginas de 100 conversas nos
MAX_VIDEOS_COMENTARIOS vídeos com mais comentários; texto e autor ficam em casos/039/retransmissoes_comentarios.csv.gz (privado).
Universo: a busca do YouTube não informa quantos vídeos existem e devolve até 50 por consulta — ⛔ desconhecido. O que se
publica é o que a busca devolveu, quanto passou no filtro e o critério.
Uso: YOUTUBE_API_KEY=… [ODI_INTERNO_DIR=…] python scripts/caso_lives_retransmissoes.py
"""
from __future__ import annotations

import csv
import gzip
import json
import os
import re
import sys
import time
import unicodedata
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from collect_caso_busca import yt as yt_api  # noqa: E402
from collect_comentarios_youtube import CAMPOS, linhas_da_conversa  # noqa: E402

CASO = "039"
BUSCAS = ["Lula Janones ao vivo", "live Exército do Lula Janones"]
MIN_INSCRITOS = 10_000
DIAS_DE_BUSCA = 7
PAGINAS = 3
MAX_VIDEOS_COMENTARIOS = 40
ISO = "%Y-%m-%dT%H:%M:%SZ"


def agora() -> str:
    return datetime.now(timezone.utc).strftime(ISO)


def t(iso: str | None):
    return datetime.strptime(iso[:19] + "Z", ISO).replace(tzinfo=timezone.utc) if iso else None


def sem_acento(s: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", (s or "").lower()) if unicodedata.category(c) != "Mn")


def titulo_serve(titulo: str) -> bool:
    s = sem_acento(titulo)
    return "lula" in s and ("janones" in s or "exercito" in s)


def segundos(dur: str | None) -> int | None:
    m = re.fullmatch(r"P(?:(\d+)D)?T?(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?", dur or "")
    if not m or not any(m.groups()):
        return None
    d, h, mi, s = (int(x or 0) for x in m.groups())
    return d * 86400 + h * 3600 + mi * 60 + s


def classificar(v: dict, orig: dict) -> str:
    if not v.get("inicio_ao_vivo"):
        return "outro vídeo sobre a live"
    perto = abs((t(v["inicio_ao_vivo"]) - t(orig["inicio"])).total_seconds()) <= 3 * 3600
    longo = (v.get("segundos") or 0) >= 0.5 * (orig.get("segundos") or 0) if orig.get("segundos") else True
    return "ao vivo simultânea" if perto and longo else "transmissão ao vivo em outro horário"


def quando(v: dict) -> str:
    return v.get("inicio_ao_vivo") or v.get("publicado_em") or ""


def na_janela(v: dict, orig: dict) -> bool:
    q = t(quando(v))
    return bool(q) and t(orig["inicio"]) - timedelta(hours=6) <= q <= t(orig["inicio"]) + timedelta(hours=72)


def mais_proxima(v: dict, inicios: dict[str, str]) -> str | None:
    """Live de início mais próximo do vídeo: cada vídeo conta em uma live só."""
    q = t(quando(v))
    return min(inicios, key=lambda i: abs((q - t(inicios[i])).total_seconds())) if q and inicios else None


def yt(rota, **q):
    for k in range(3):
        try:
            return yt_api(rota, **q)
        except RuntimeError as e:
            if "429" in str(e) and k < 2:
                time.sleep(20 * (k + 1))
                continue
            raise


def detalhes(ids: list[str], key: str, erros: list) -> dict[str, dict]:
    out = {}
    for i in range(0, len(ids), 50):
        try:
            r = yt("videos", part="snippet,statistics,contentDetails,liveStreamingDetails", id=",".join(ids[i:i + 50]), key=key)
        except RuntimeError as e:
            erros.append(f"vídeos: {e}")
            continue
        for it in r.get("items", []):
            sn, st, lv = it.get("snippet", {}), it.get("statistics", {}), it.get("liveStreamingDetails") or {}
            num = lambda k: int(st[k]) if str(st.get(k, "")).isdigit() else None  # noqa: E731
            out[it["id"]] = {"id": it["id"], "titulo": sn.get("title"), "canal_id": sn.get("channelId"), "canal": sn.get("channelTitle"),
                             "publicado_em": sn.get("publishedAt"), "duracao": it.get("contentDetails", {}).get("duration"),
                             "segundos": segundos(it.get("contentDetails", {}).get("duration")),
                             "inicio_ao_vivo": lv.get("actualStartTime"), "fim_ao_vivo": lv.get("actualEndTime"),
                             "visualizacoes": num("viewCount"), "curtidas": num("likeCount"), "comentarios_informados": num("commentCount")}
    return out


def inscritos(canais: list[str], key: str, erros: list) -> dict[str, int | None]:
    out = {}
    for i in range(0, len(canais), 50):
        try:
            for it in yt("channels", part="statistics", id=",".join(canais[i:i + 50]), key=key).get("items", []):
                s = it.get("statistics", {})
                out[it["id"]] = int(s["subscriberCount"]) if not s.get("hiddenSubscriberCount") and str(s.get("subscriberCount", "")).isdigit() else None
        except RuntimeError as e:
            erros.append(f"canais: {e}")
    return out


def buscar(orig: dict, key: str, erros: list) -> tuple[dict[str, str], list[dict]]:
    ini = t(orig["inicio"])
    de, ate = (ini - timedelta(hours=6)).strftime(ISO), (ini + timedelta(hours=72)).strftime(ISO)
    achados, consultas = {}, []
    for b in [orig["titulo"]] + BUSCAS:
        try:
            r = yt("search", part="snippet", q=b, type="video", maxResults=50, publishedAfter=de, publishedBefore=ate, regionCode="BR",
                   relevanceLanguage="pt", order="relevance", key=key)
        except RuntimeError as e:
            erros.append(f"busca '{b}': {e}")
            consultas.append({"busca": b, "devolvidos": None, "erro": str(e)[:200]})
            continue
        its = r.get("items", [])
        for it in its:
            achados.setdefault(it["id"]["videoId"], b)
        consultas.append({"busca": b, "devolvidos": len(its), "de": de, "ate": ate,
                          "total_estimado_pela_api": (r.get("pageInfo") or {}).get("totalResults")})
        time.sleep(1)
    return achados, consultas


def publicar(v: dict, n_codigo: int) -> dict:
    """O que vai ao público: canal com menos de 10 mil inscritos (ou número oculto) vira código, sem título nem link."""
    base = {k: v.get(k) for k in ("tipo", "publicado_em", "inicio_ao_vivo", "duracao", "visualizacoes", "curtidas", "comentarios_informados",
                                  "comentarios_lidos", "achado_pela_busca")}
    if (v.get("inscritos_canal") or 0) >= MIN_INSCRITOS:
        return {**base, "id": v["id"], "url": f"https://www.youtube.com/watch?v={v['id']}", "titulo": v["titulo"], "canal": v["canal"],
                "inscritos_canal": v["inscritos_canal"], "identificado": True}
    return {**base, "canal": f"canal_{n_codigo:03d}", "inscritos_canal": None, "identificado": False}


def comentarios(videos: list[dict], key: str, priv: Path, erros: list) -> dict[str, int]:
    alvo = sorted([v for v in videos if v.get("comentarios_informados")], key=lambda v: -v["comentarios_informados"])[:MAX_VIDEOS_COMENTARIOS]
    rows, quando = [], agora()
    for v in alvo:
        meta, tok = {"video_id": v["id"], "candidate_id": "", "channel_id": v["canal_id"]}, None
        for _ in range(PAGINAS):
            p = dict(part="snippet,replies", videoId=v["id"], maxResults=100, order="time", textFormat="plainText", key=key)
            if tok:
                p["pageToken"] = tok
            try:
                r = yt("commentThreads", **p)
            except RuntimeError as e:
                erros.append(f"comentários {v['id']}: {str(e)[:160]}")
                break
            rows += [l for it in r.get("items", []) for l in linhas_da_conversa(it, meta, "caso039", quando)]
            tok = r.get("nextPageToken")
            if not tok:
                break
    priv.mkdir(parents=True, exist_ok=True)
    arq = priv / "retransmissoes_comentarios.csv.gz"
    todos = {r["comment_id"]: r for r in csv.DictReader(gzip.open(arq, "rt", encoding="utf-8"), delimiter=";")} if arq.exists() else {}
    todos.update({r["comment_id"]: r for r in rows})  # só acrescenta ou atualiza; nunca apaga o que já foi lido
    with gzip.open(arq, "wt", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, CAMPOS, delimiter=";", lineterminator="\n", extrasaction="ignore")
        w.writeheader()
        w.writerows(todos.values())
    n: dict[str, int] = {}
    for r in todos.values():
        n[r["video_id"]] = n.get(r["video_id"], 0) + 1
    return n


def main(argv=None) -> int:
    key = os.environ.get("YOUTUBE_API_KEY", "")
    if not key:
        print("⛔ falta YOUTUBE_API_KEY no ambiente")
        return 1
    cfg = next(c for c in json.load(open("data/config/casos.json", encoding="utf-8"))["casos"] if c["id"] == CASO)
    ids = cfg["videos_youtube"]
    pub = Path("data/casos") / CASO
    pub.mkdir(parents=True, exist_ok=True)
    # estado (ids já achados) só no privado: ele traz vídeos de canais pequenos, que não podem ter link no público.
    # Sem o privado não há estado: a busca é refeita a cada execução (300 unidades de cota por live).
    interno = os.environ.get("ODI_INTERNO_DIR") or ""
    tem_priv = bool(interno) and (Path(interno) / "casos").is_dir()
    est_arq = Path(interno) / "casos" / CASO / "retransmissoes_estado.json" if tem_priv else None
    estado = json.load(open(est_arq, encoding="utf-8")) if est_arq and est_arq.exists() else {}
    erros: list[str] = []
    originais = detalhes(ids, key, erros)
    canais_lula = {o["canal_id"] for o in originais.values()}
    saida, todos_videos = [], []
    inicios = {i: (o["inicio_ao_vivo"] or o["publicado_em"]) for i, o in originais.items()}
    for i in ids:
        o = originais.get(i)
        if not o:
            saida.append({"live": i, "situacao": "⛔ vídeo original não devolvido pela API"})
            continue
        orig = {"id": i, "titulo": o["titulo"], "inicio": o["inicio_ao_vivo"] or o["publicado_em"], "fim": o["fim_ao_vivo"], "segundos": o["segundos"],
                "foi_ao_vivo": bool(o["inicio_ao_vivo"]), "visualizacoes": o["visualizacoes"], "comentarios_informados": o["comentarios_informados"]}
        e = estado.setdefault(i, {"achados": {}, "consultas": [], "buscas_em": []})
        recente = (datetime.now(timezone.utc) - t(orig["inicio"])) <= timedelta(days=DIAS_DE_BUSCA)
        if recente or not e["buscas_em"]:
            achados, consultas = buscar(orig, key, erros)
            for vid, b in achados.items():
                e["achados"].setdefault(vid, b)
            e["consultas"], e["buscas_em"] = consultas, (e["buscas_em"] + [agora()])[-30:]
        det = detalhes([v for v in e["achados"] if v not in ids], key, erros)
        fora = [v for v in det.values() if v["canal_id"] not in canais_lula]
        vs = [v for v in fora if titulo_serve(v["titulo"]) and na_janela(v, orig) and mais_proxima(v, inicios) == i]
        for v in vs:
            v["tipo"], v["achado_pela_busca"], v["live"] = classificar(v, orig), e["achados"].get(v["id"]), i
        saida.append({"live": i, "original": orig, "consultas": e["consultas"], "buscas_em": e["buscas_em"], "achados_na_busca": len(e["achados"]),
                      "de_outros_canais": len(fora), "passaram_no_filtro": len(vs), "_videos": vs})
        todos_videos += vs
    insc = inscritos(sorted({v["canal_id"] for v in todos_videos}), key, erros)
    for v in todos_videos:
        v["inscritos_canal"] = insc.get(v["canal_id"])
    lidos = None
    if tem_priv:
        lidos = comentarios(todos_videos, key, Path(interno) / "casos" / CASO, erros)
    else:
        erros.append("⛔ sem repositório privado: comentários das retransmissões não lidos nesta execução")
    codigos: dict[str, int] = {}
    for s in saida:
        vs = sorted(s.pop("_videos", []), key=lambda v: -(v.get("visualizacoes") or 0))
        for v in vs:
            v["comentarios_lidos"] = (lidos or {}).get(v["id"]) if lidos is not None else None
        s["videos"] = [publicar(v, codigos.setdefault(v["canal_id"], len(codigos) + 1)) for v in vs]
        s["canais"] = len({v["canal_id"] for v in vs})
        s["canais_identificados"] = len({v["canal_id"] for v in vs if (v.get("inscritos_canal") or 0) >= MIN_INSCRITOS})
        s["por_tipo"] = {k: sum(1 for v in vs if v["tipo"] == k) for k in ("ao vivo simultânea", "transmissão ao vivo em outro horário", "outro vídeo sobre a live")}
        s["soma_visualizacoes"] = sum(v.get("visualizacoes") or 0 for v in vs)
        s["soma_comentarios_informados"] = sum(v.get("comentarios_informados") or 0 for v in vs)
        s["comentarios_lidos"] = sum((lidos or {}).get(v["id"], 0) for v in vs) if lidos is not None else None
    uni_c = sum(s.get("soma_comentarios_informados") or 0 for s in saida)
    lid_c = sum(s.get("comentarios_lidos") or 0 for s in saida) if lidos is not None else None
    out = {"caso": CASO, "gerado_em_utc": agora(), "lives": saida,
           "universo": [
               {"conjunto": "Retransmissões e reenvios em outros canais", "videos": sum(s.get("passaram_no_filtro") or 0 for s in saida), "universo": None,
                "fonte_universo": "⛔ desconhecido: a busca do YouTube não informa quantos vídeos existem e devolve até 50 por consulta",
                "amostra": sum(s.get("passaram_no_filtro") or 0 for s in saida), "pct": None,
                "criterio": f"busca pelo título da live e por {', '.join(repr(b) for b in BUSCAS)}, de 6 h antes a 72 h depois do início; só outros canais; "
                            "título com 'Lula' e ('Janones' ou 'Exército')"},
               {"conjunto": "Comentários das retransmissões", "videos": sum(s.get("passaram_no_filtro") or 0 for s in saida), "universo": uni_c or None,
                "fonte_universo": "contagem de comentários informada pelo YouTube nos vídeos achados (inclui respostas)", "amostra": lid_c,
                "pct": round(100 * lid_c / uni_c, 1) if lid_c is not None and uni_c else None,
                "criterio": f"até {PAGINAS * 100} conversas mais recentes nos {MAX_VIDEOS_COMENTARIOS} vídeos com mais comentários"
                            + ("" if lidos is not None else " · ⛔ não lidos: sem repositório privado")}],
           "privacidade": f"Canal com menos de {MIN_INSCRITOS:,} inscritos, ou que esconde o número, aparece como código, sem título nem link.".replace(",", "."),
           "erros": erros}
    (pub / "retransmissoes.json").write_text(json.dumps(out, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    if est_arq:
        est_arq.parent.mkdir(parents=True, exist_ok=True)
        est_arq.write_text(json.dumps(estado, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    for s in saida:
        print(f"{s['live']}: achados {s.get('achados_na_busca')} · outros canais {s.get('de_outros_canais')} · no filtro {s.get('passaram_no_filtro')} · "
              f"canais {s.get('canais')} · {s.get('por_tipo')} · visualizações {s.get('soma_visualizacoes')} · comentários lidos {s.get('comentarios_lidos')}")
    for e in erros:
        print(e)
    return 0


if __name__ == "__main__":
    sys.exit(main())
