#!/usr/bin/env python3
"""Frente de intolerância dos casos — triagem automática (piloto).

Pedido do responsável (02/11/2026, 02h29: "pode aplicar"), sobre a proposta "Frente de intolerância e desinformação nos casos do
ODI Atlas" (piloto nos casos 014, 021 e 022).
- Textos: publicações coletadas do caso (ODI_INTERNO_DIR/casos/<id>/itens.csv.gz) e, se houver, comentários do YouTube do caso
  (youtube_comentarios.csv.gz). Textos repetidos são lidos uma vez.
- Modelos (Hugging Face, pesos públicos): cada um é tentado; o que não carregar fica ⛔ com o motivo. Os rótulos vêm da
  configuração do próprio modelo (id2label), sem renomear. Limiar 0,5 por rótulo.
- O modelo é TRIAGEM, não resultado: estado "processado". Nada vira "validado" sem a amostra codificada por duas pessoas
  (kappa ≥ 0,61), como na proposta.
- Universo: as plataformas não informam o total de publicações por termo (⛔ desconhecido); o JSON diz quantos textos foram lidos
  por rede e a fonte de cada contagem.
- Privacidade: escores por texto e amostra de validação só no repositório privado; no público, só contagens e percentuais.
Saídas: privado casos/<id>/intolerancia/escores.csv.gz e amostra_validacao_v1.csv (nunca sobrescrita);
público data/casos/<id>/intolerancia.json.
Uso: python scripts/intolerancia.py --caso 014 [--caso 021 ...]
"""
from __future__ import annotations

import csv
import datetime as dt
import gzip
import json
import os
import random
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MODELOS = [
    ("ofensividade_hatebr", "ruanchaves/bert-large-portuguese-cased-hatebr",
     "HateBR (Vargas et al., LREC 2022): comentários do Instagram em perfis de políticos; ofensivo × não ofensivo"),
    ("odio_alvos_bertabaporu", "pysentimiento/bertabaporu-pt-hate-speech",
     "pysentimiento (Pérez et al.), BERTabaporu: ódio por alvo; métricas não publicadas no cartão do modelo"),
]
LIMIAR = 0.5
SEMENTE = 20261102
N_VALIDACAO = 200  # 100 sinalizados + 100 não sinalizados pelo modelo de ofensividade, estratificados por rede


def ler_textos(priv: Path) -> list[dict]:
    out = []
    p = priv / "itens.csv.gz"
    if p.exists():
        for r in csv.DictReader(gzip.open(p, "rt", encoding="utf-8"), delimiter=";"):
            out.append({"rede": r["rede"], "id": r["item_id"], "texto": r.get("texto") or "", "dia": (r.get("publicado_em") or "")[:10],
                        "tipo": "publicação"})
    p = priv / "youtube_comentarios.csv.gz"
    if p.exists():
        for r in csv.DictReader(gzip.open(p, "rt", encoding="utf-8"), delimiter=";"):
            out.append({"rede": "youtube", "id": r["comment_id"], "texto": r.get("texto") or "", "dia": (r.get("publicado_em") or "")[:10],
                        "tipo": "comentário"})
    return [r for r in out if len(r["texto"].split()) >= 3]


def classificar(textos: list[str], modelo: str) -> tuple[list[dict], dict]:
    from transformers import AutoModelForSequenceClassification, AutoTokenizer
    import torch
    tok = AutoTokenizer.from_pretrained(modelo)
    mod = AutoModelForSequenceClassification.from_pretrained(modelo).eval()
    rot = {int(k): str(v) for k, v in mod.config.id2label.items()}  # o modelo do HateBR usa True/False (booleanos) como rótulo
    multi = mod.config.problem_type == "multi_label_classification"
    out = []
    with torch.inference_mode():
        for i in range(0, len(textos), 32):
            enc = tok(textos[i:i + 32], truncation=True, max_length=128, padding=True, return_tensors="pt")
            lg = mod(**enc).logits
            pr = torch.sigmoid(lg) if multi else torch.softmax(lg, -1)
            out += [{rot[j]: round(float(p[j]), 4) for j in range(len(rot))} for p in pr]
    return out, {"rotulos": [rot[j] for j in sorted(rot)], "multirrotulo": multi}


def positivo(rotulo: str) -> bool:
    """Rótulo que indica ofensa/ódio (o oposto de 'não ofensivo', 'LABEL_0', 'non-hateful' etc.)."""
    r = str(rotulo).lower()
    return not (r in ("label_0", "0", "false") or r.startswith(("non", "não", "nao", "not")) or "non-" in r or "neutral" in r)


def amostra(rows: list[dict], n: int, rnd: random.Random) -> list[dict]:
    est = defaultdict(list)
    for r in rows:
        est[r["rede"]].append(r)
    n = min(n, len(rows))
    if not n:
        return []
    br = {k: n * len(v) / len(rows) for k, v in est.items()}
    cot = {k: int(b) for k, b in br.items()}
    for k in sorted(est, key=lambda k: -(br[k] - cot[k]))[:n - sum(cot.values())]:
        cot[k] += 1
    out = []
    for k in sorted(est):
        out += rnd.sample(est[k], min(cot[k], len(est[k])))
    return out


def main(argv: list[str]) -> int:
    casos = [argv[i + 1] for i, a in enumerate(argv) if a == "--caso"]
    interno = os.environ.get("ODI_INTERNO_DIR")
    if not interno:
        print("⛔ ODI_INTERNO_DIR ausente: os textos ficam só no repositório privado")
        return 1
    agora = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    for caso in casos:
        priv = Path(interno) / "casos" / caso
        rows = ler_textos(priv)
        vistos, unicos = set(), []
        for r in rows:
            k = " ".join(r["texto"].lower().split())
            if k not in vistos:
                vistos.add(k)
                unicos.append(r)
        print(f"caso {caso}: {len(rows)} textos com 3+ palavras, {len(unicos)} únicos")
        res = {"caso": caso, "gerado_em_utc": agora, "estado": "processado",
               "aviso": "Triagem automática, NÃO validada: percentuais do modelo sobre a amostra lida. ⛔ Validação humana (duas pessoas, kappa ≥ 0,61) pendente.",
               "metodo": " ".join(__doc__.split("Saídas:")[0].split()[2:]), "limiar": LIMIAR,
               "lidos": {"textos_com_3_ou_mais_palavras": len(rows), "textos_unicos": len(unicos),
                         "por_rede": dict(Counter(r["rede"] for r in unicos)),
                         "fonte": "itens.csv.gz (publicações coletadas por termo) e youtube_comentarios.csv.gz do caso, repositório privado"},
               "universo": "⛔ desconhecido: as plataformas não informam o total de publicações por termo; ver o bloco de cada rede no dossiê do caso",
               "modelos": {}}
        esc = {r["id"]: {"rede": r["rede"]} for r in unicos}
        for nome, mid, desc in MODELOS:
            cache = priv / "intolerancia" / f"cache_{nome}.json.gz"  # 02/11/2026: a 1ª rodada perdeu ~2 h de CPU num erro depois do modelo
            try:
                guardado = json.loads(gzip.open(cache, "rt", encoding="utf-8").read()) if cache.exists() else None
                if guardado and guardado.get("ids") == [r["id"] for r in unicos]:
                    ps, info = guardado["ps"], guardado["info"]
                else:
                    ps, info = classificar([r["texto"] for r in unicos], mid)
                    cache.parent.mkdir(parents=True, exist_ok=True)
                    with gzip.open(cache, "wt", encoding="utf-8") as fh:
                        fh.write(json.dumps({"ids": [r["id"] for r in unicos], "ps": ps, "info": info}))
            except Exception as e:  # noqa: BLE001
                res["modelos"][nome] = {"modelo": mid, "situacao": f"⛔ não carregou: {type(e).__name__}: {str(e)[:160]}"}
                print(nome, res["modelos"][nome]["situacao"])
                continue
            pos = [l for l in info["rotulos"] if positivo(l)]
            por_rede = defaultdict(Counter)
            for r, p in zip(unicos, ps):
                esc[r["id"]].update({f"{nome}:{k}": v for k, v in p.items()})
                por_rede[r["rede"]]["n"] += 1
                for l in pos:
                    if p[l] >= LIMIAR:
                        por_rede[r["rede"]][l] += 1
                if any(p[l] >= LIMIAR for l in pos):
                    por_rede[r["rede"]]["algum"] += 1
                r[f"_{nome}"] = any(p[l] >= LIMIAR for l in pos)
            tab = {rede: {"lidos": c["n"], "sinalizados_algum_rotulo": c["algum"], "pct_algum": round(100 * c["algum"] / c["n"], 1) if c["n"] else None,
                          "por_rotulo": {l: {"n": c[l], "pct": round(100 * c[l] / c["n"], 1) if c["n"] else None} for l in pos}}
                   for rede, c in sorted(por_rede.items())}
            tot = sum(c["n"] for c in por_rede.values())
            alg = sum(c["algum"] for c in por_rede.values())
            res["modelos"][nome] = {"modelo": mid, "descricao": desc, "rotulos_do_modelo": info["rotulos"], "rotulos_contados_como_sinal": pos,
                                    "multirrotulo": info["multirrotulo"], "total": {"lidos": tot, "sinalizados": alg, "pct": round(100 * alg / tot, 1) if tot else None},
                                    "por_rede": tab}
            print(nome, "ok:", res["modelos"][nome]["total"])
        # privado: escores e amostra de validação (nunca sobrescrita)
        d = priv / "intolerancia"
        d.mkdir(parents=True, exist_ok=True)
        campos = sorted({k for v in esc.values() for k in v})
        with gzip.open(d / "escores.csv.gz", "wt", encoding="utf-8", newline="") as fh:
            w = csv.DictWriter(fh, ["id"] + campos, delimiter=";")
            w.writeheader()
            for k, v in esc.items():
                w.writerow({"id": k, **v})
        am = d / "amostra_validacao_v1.csv"
        if not am.exists() and "_ofensividade_hatebr" in (unicos[0] if unicos else {}):
            rnd = random.Random(SEMENTE)
            sim = amostra([r for r in unicos if r["_ofensividade_hatebr"]], N_VALIDACAO // 2, rnd)
            nao = amostra([r for r in unicos if not r["_ofensividade_hatebr"]], N_VALIDACAO - len(sim), rnd)
            sel = sim + nao
            rnd.shuffle(sel)  # a ordem não revela o que o modelo marcou
            with open(am, "w", encoding="utf-8", newline="") as fh:
                w = csv.writer(fh, delimiter=";")
                w.writerow(["n", "rede", "id", "dia", "texto", "cod_A_ofensivo(s/n)", "cod_A_odio(s/n)", "cod_A_alvo", "cod_A_acao(s/n)",
                            "cod_B_ofensivo(s/n)", "cod_B_odio(s/n)", "cod_B_alvo", "cod_B_acao(s/n)", "observacao"])
                for i, r in enumerate(sel, 1):
                    w.writerow([i, r["rede"], r["id"], r["dia"], r["texto"]] + [""] * 9)
            with open(d / "amostra_validacao_v1_chave.csv", "w", encoding="utf-8", newline="") as fh:  # o que o modelo disse, separado
                w = csv.writer(fh, delimiter=";")
                w.writerow(["n", "id", "modelo_ofensivo"])
                for i, r in enumerate(sel, 1):
                    w.writerow([i, r["id"], "s" if r["_ofensividade_hatebr"] else "n"])
            res["validacao"] = {"amostra": len(sel), "sinalizados": len(sim), "nao_sinalizados": len(nao),
                                "desenho": "metade marcada e metade não marcada pelo modelo de ofensividade, cada metade estratificada por rede (maior resto); a chave fica num arquivo separado",
                                "situacao": "⛔ aguardando codificação por duas pessoas"}
        elif am.exists():
            res["validacao"] = {"situacao": "⛔ aguardando codificação por duas pessoas", "amostra": "já gerada (v1, não sobrescrita)"}
        pub = ROOT / "data/casos" / caso / "intolerancia.json"
        pub.parent.mkdir(parents=True, exist_ok=True)
        pub.write_text(json.dumps(res, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
