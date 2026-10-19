"""Big numbers e comentários do debate no YouTube → data/debate/youtube.json (só agregados).

Entrada: data/debate/youtube_videos.json (collect_debate_youtube.py) e, se houver, o privado
ODI_INTERNO_DIR/debate/youtube_comentarios.csv.gz. Nenhum texto ou autor de comentário vai para o público.
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
import corpus_populismo as cp  # noqa: E402
from net import now_utc  # noqa: E402

PARCEIRAS = re.compile(r"\bband\b|bandnews|bandeirantes|band jornalismo|estad[aã]o|tv cultura|jornalismo tv cultura|tv gazeta|jovem pan", re.I)
VEICULOS = re.compile(r"\bcnn\b|globo|\bg1\b|\buol\b|folha|\bsbt\b|\brecord\b|metr[oó]poles|poder ?360|\bveja\b|\bexame\b|correio|"
                      r"\bo tempo\b|\br7\b|\bcbn\b|\bbbc\b|\bterra\b|brasil de fato|carta ?capital|o antagonista|revista oeste|\bicl\b|"
                      r"brasil 247|\bdcm\b|f[oó]rum|\bjota\b|\bnexo\b|ag[eê]ncia brasil|tv brasil|\bebc\b|\bsic\b|\brtp\b", re.I)
MENCAO = {"Lula": re.compile(r"\blula\b|\bpetista|\blulista|\bmolusco|\bdescondenado|\bpt\b", re.I),
          "Flávio Bolsonaro": re.compile(r"\bfl[aá]vio|\bbolsonaro|\bbolsonarista|\bflavinho|\brachadinha", re.I)}
INTOLERANCIA = ["desumanizacao", "odio_genero", "odio_lgbt", "odio_raca_origem", "odio_religiao", "ameaca_violencia"]
INCIVILIDADE = ["incivilidade", "rotulo_pejorativo_politico"]
EXCLUIR = set(bc.norm("vc voce voces q ta tá ne né tb tbm pq porque ai aí ja já so só sim nao não ate até la lá ser ter vai vou faz fazer "
                      "tem esta está isso esse essa aqui agora hoje ainda nunca sempre tudo todo toda todos kkk kkkk kkkkk kkkkkk debate").split())


def grupo_de(v: dict) -> str:
    if v.get("campanha"):
        return "canais das campanhas"
    if PARCEIRAS.search(v.get("canal") or ""):
        return "emissoras do debate (Band e parceiras)"
    if VEICULOS.search(v.get("canal") or ""):
        return "outros veículos de imprensa"
    return "outros canais (comentaristas, cortes, perfis)"


def soma(vs: list[dict], k: str) -> int:
    return sum(v.get(k) or 0 for v in vs)


def resumo(vs: list[dict]) -> dict:
    return {"videos": len(vs), "canais": len({v["canal_id"] for v in vs}), "visualizacoes": soma(vs, "visualizacoes"),
            "curtidas": soma(vs, "curtidas"), "comentarios": soma(vs, "comentarios"), "horas_de_video": round(soma(vs, "duracao_s") / 3600, 1)}


def pct(n, d):
    return round(100 * n / d, 1) if d else None


def analisar_comentarios(rows: list[dict], vids: dict, root: Path) -> dict:
    intol = json.loads((root / "data/config/livro_codigos_intolerancia.json").read_text(encoding="utf-8"))
    regs = cp.compilar(intol)
    cods = [set(cp.precodificar(r["texto"], regs)) for r in rows]
    def bloco(idx: list[int]) -> dict:
        n = len(idx)
        txt = [rows[i]["texto"] for i in idx]
        return {"comentarios": n, "autores_unicos": len({rows[i]["autor_canal"] or rows[i]["autor_nome"] for i in idx}),
                "respostas_pct": pct(sum(rows[i]["tipo"] == "resposta" for i in idx), n),
                "mencionam_pct": {k: pct(sum(bool(rx.search(t)) for t in txt), n) for k, rx in MENCAO.items()},
                "incivilidade_pct": pct(sum(bool(cods[i] & set(INCIVILIDADE)) for i in idx), n),
                "intolerancia_pct": pct(sum(bool(cods[i] & set(INTOLERANCIA)) for i in idx), n),
                "por_categoria_pct": {k: pct(sum(k in cods[i] for i in idx), n) for k in intol["categorias"]},
                "termos": bc.nuvem(txt, EXCLUIR, top=40, minimo=5)}
    tudo = list(range(len(rows)))
    por_grupo = defaultdict(list)
    por_tipo = defaultdict(list)
    for i, r in enumerate(rows):
        v = vids.get(r["video_id"]) or {}
        por_grupo[v.get("grupo", "?")].append(i)
        por_tipo[v.get("tipo", "?")].append(i)
    return {"total": bloco(tudo), "por_grupo": {g: bloco(ix) for g, ix in por_grupo.items()},
            "por_tipo": {t: bloco(ix) for t, ix in por_tipo.items()},
            "categorias": {k: c["nome"] for k, c in intol["categorias"].items()},
            "nota": "Pré-codificação por dicionário (livro de códigos de intolerância do Atlas): indica candidatos a cada categoria; não é decisão. "
                    "Menção = nome, apelido ou partido no texto. Comentários de pessoas comuns: texto e autor ficam só no repositório privado."}


def main(argv=None) -> int:
    root = Path(argv[0]) if argv else Path(".")
    d = json.loads((root / "data/debate/youtube_videos.json").read_text(encoding="utf-8"))
    vs = d["videos"]
    for v in vs:
        v["grupo"] = grupo_de(v)
    por_tipo = defaultdict(list)
    por_grupo = defaultdict(list)
    for v in vs:
        por_tipo[v["tipo"]].append(v)
        por_grupo[v["grupo"]].append(v)
    canais = Counter()
    for v in vs:
        canais[v["canal"]] += v.get("visualizacoes") or 0
    out = {"schema_version": 1, "gerado_em_utc": now_utc(), "coletado_em_utc": d["coletado_em_utc"], "desde_utc": d["desde_utc"],
           "consultas": d["consultas"], "erros": d["erros"], "chat_ao_vivo": d["chat_ao_vivo"],
           "total": resumo(vs), "por_tipo": {k: resumo(x) for k, x in por_tipo.items()}, "por_grupo": {k: resumo(x) for k, x in por_grupo.items()},
           "canais_mais_vistos": canais.most_common(15),
           "lives": [{k: v.get(k) for k in ("id", "titulo", "canal", "visualizacoes", "curtidas", "comentarios", "comentarios_abertos", "live_inicio", "live_fim", "duracao_s")}
                     for v in vs if v["tipo"] == "transmissão ao vivo"],
           "videos": [{k: v.get(k) for k in ("id", "titulo", "canal", "grupo", "tipo", "publicado_em", "duracao_s", "visualizacoes", "curtidas",
                                             "comentarios", "comentarios_lidos", "campanha")} for v in vs],
           "comentarios": None}
    interno = os.environ.get("ODI_INTERNO_DIR")
    arq = Path(interno) / "debate/youtube_comentarios.csv.gz" if interno else None
    if arq and arq.exists():
        rows = list(csv.DictReader(gzip.open(arq, "rt", encoding="utf-8"), delimiter=";"))
        out["comentarios"] = {**analisar_comentarios(rows, {v["id"]: v for v in vs}, root), "videos_lidos": d["videos_com_comentarios_lidos"],
                              "metodo": "Até 100 conversas por relevância e 100 pelas mais recentes (com as respostas que a API traz) nos "
                                        f"{d['videos_com_comentarios_lidos']} vídeos mais vistos com comentários abertos."}
    (root / "data/debate/youtube.json").write_text(json.dumps(out, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    t = out["total"]
    c = (out["comentarios"] or {}).get("total") or {}
    print(f"debate no YouTube: {t['videos']} vídeos · {t['canais']} canais · {t['visualizacoes']:,} visualizações · {t['curtidas']:,} curtidas · "
          f"{t['comentarios']:,} comentários (API) · lidos {c.get('comentarios')} · incivilidade {c.get('incivilidade_pct')}% · intolerância {c.get('intolerancia_pct')}%")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
