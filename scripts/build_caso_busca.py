"""Casos de busca → data/casos/<id>/busca.json (público, só agregados e conteúdo de canais/veículos públicos).

Entrada: ODI_INTERNO_DIR/casos/<id>/busca_coleta.json e youtube_comentarios.csv.gz (collect_caso_busca.py).
Para o caso 005, também as falas do debate de 18/10 que citam o caso (transcrição privada + turnos codificados).
Uso: python scripts/build_caso_busca.py --caso 002|005
"""
from __future__ import annotations

import csv
import gzip
import json
import os
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import build_conteudo as bc  # noqa: E402
import collect_caso_busca as cb  # noqa: E402
from net import now_utc  # noqa: E402

DEBATE_RX = {"005": re.compile(r"crian[çc]a de 5 anos|bala de fuzil|ana clara", re.I)}
EXCLUIR = set(bc.norm("vc voce voces q ta tá ne né tb tbm pq porque ai aí ja já so só sim nao não ate até la lá ser ter vai vou faz fazer "
                      "tem esta está isso esse essa aqui agora hoje ainda nunca sempre tudo todo toda todos kkk kkkk kkkkk").split())


def pct(n, d):
    return round(100 * n / d, 1) if d else None


def youtube(y: dict | None) -> dict | None:
    if not y:
        return None
    vs = y["videos"]
    soma = lambda xs, k: sum(v.get(k) or 0 for v in xs)  # noqa: E731
    ano = defaultdict(list)
    for v in vs:
        ano[(v["publicado_em"] or "?")[:4]].append(v)
    publicos = [v for v in vs if (v.get("inscritos") or 0) >= cb.MIN_PUBLICO]
    return {"videos": len(vs), "canais": len({v["canal_id"] for v in vs}), "visualizacoes": soma(vs, "visualizacoes"),
            "curtidas": soma(vs, "curtidas"), "comentarios": soma(vs, "comentarios"),
            "por_ano": {a: {"videos": len(x), "visualizacoes": soma(x, "visualizacoes"), "comentarios": soma(x, "comentarios")} for a, x in sorted(ano.items())},
            "mais_vistos": [{k: v.get(k) for k in ("id", "titulo", "canal", "inscritos", "publicado_em", "visualizacoes", "curtidas", "comentarios")}
                            for v in publicos[:25]],
            "videos_de_canais_pequenos": len(vs) - len(publicos), "min_inscritos_publico": cb.MIN_PUBLICO,
            "nota": f"Busca da YouTube Data API (até 100 vídeos por consulta) filtrada pelo título/descrição. Só aparecem com nome canais com "
                    f"{cb.MIN_PUBLICO:,} inscritos ou mais; os demais entram nas somas. A busca não garante todos os vídeos: o total é um piso.".replace(",", ".")}


def comentarios(arq: Path, vids: set) -> dict | None:
    if not arq.exists():
        return None
    # só comentários de vídeos que estão na lista atual do caso (o arquivo privado acumula leituras anteriores, inclusive de vídeos
    # que um filtro mais estrito tirou do caso; eles continuam guardados, mas não entram na conta)
    rows = [r for r in csv.DictReader(gzip.open(arq, "rt", encoding="utf-8"), delimiter=";") if not vids or r["video_id"] in vids]
    if not rows:
        return None
    txt = [r["texto"] for r in rows]
    ano = Counter((r["publicado_em"] or "?")[:4] for r in rows)
    cats = {k: pct(sum(bool(rx.search(t)) for t in txt), len(txt)) for k, rx in cb.CATEGORIAS.items()}
    return {"comentarios": len(rows), "autores_unicos": len({r["autor_canal"] or r["autor_nome"] for r in rows}),
            "videos": len({r["video_id"] for r in rows}), "por_ano": dict(sorted(ano.items())), "categorias_pct": cats,
            "termos": bc.nuvem(txt, EXCLUIR, top=40, minimo=5),
            "nota": "Pré-codificação por dicionário (relato de teste, mudança percebida, contestação, cita Lula): indica candidatos, não decide. "
                    "Texto e autor ficam só no repositório privado."}


def debate(caso: str) -> list[dict] | None:
    rx = DEBATE_RX.get(caso)
    interno = os.environ.get("ODI_INTERNO_DIR")
    if not rx or not interno:
        return None
    arq = Path(interno) / "debate/transcricao.json"
    if not arq.exists():
        return None
    import build_debate_transcricao as bd
    segs = json.loads(arq.read_text(encoding="utf-8"))["segmentos"]
    pc = Path("data/config/debate_turnos.json")
    turnos = json.loads(pc.read_text(encoding="utf-8")).get("turnos", {}) if pc.exists() else {}
    quem = bd.orador_por_deixas(segs, turnos)
    out, ult = [], -999
    for i, (s, q) in enumerate(zip(segs, quem)):
        if rx.search(s["texto"]) and s["ini"] - ult > 30:
            ult = s["ini"]
            mesmos = [segs[j]["texto"] for j in range(i, min(i + 6, len(segs))) if quem[j] == q]  # só a fala de quem citou
            trecho = " ".join(" ".join(mesmos).replace(">>", " ").split()[:25])
            out.append({"minuto_do_programa": round(s["ini"] / 60, 1), "orador": bd.ORADORES.get(q, q), "trecho": trecho + "…"})
    return out


def main(argv=None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    caso = argv[argv.index("--caso") + 1] if "--caso" in argv else "002"
    cb.configurar(caso)
    pv = cb.priv_dir()
    col = pv / "busca_coleta.json"
    if not col.exists():
        print(f"⛔ coleta do caso {caso} não encontrada no privado")
        return 1
    c = json.loads(col.read_text(encoding="utf-8"))
    y = youtube(c.get("youtube"))
    out = {"schema_version": 1, "caso": caso, "gerado_em_utc": now_utc(), "coletado_em_utc": c["coletado_em_utc"],
           "variantes": c["variantes"], "controles": c["controles"], "trends": c.get("trends"), "youtube": y,
           "comentarios": comentarios(pv / "youtube_comentarios.csv.gz", {v["id"] for v in (c.get("youtube") or {}).get("videos", [])}), "noticias": c.get("noticias"),
           "checagens": [{k: x.get(k) for k in ("data_checagem", "agencia", "rotulo", "titulo", "afirmacao", "url")} for x in c.get("checagens") or []],
           "arquivo_web": c.get("arquivo_web"), "debate": debate(caso), "erros": c.get("erros")}
    pasta = Path("data/casos") / caso
    pasta.mkdir(parents=True, exist_ok=True)
    (pasta / "busca.json").write_text(json.dumps(out, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    cm = out["comentarios"] or {}
    print(f"caso {caso}: YouTube {y and y['videos']} vídeos · {y and y['visualizacoes']} visualizações · comentários lidos {cm.get('comentarios')} · "
          f"notícias {len(out['noticias'] or [])} · checagens {len(out['checagens'])} · falas no debate {len(out['debate'] or [])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
