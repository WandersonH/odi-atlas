#!/usr/bin/env python3
"""Análise geral de comentários de um caso (padrão dos casos do Atlas), usada pelos casos 011 e 012.

Pedido do responsável (27/10/2026, 03h04): "quero circulação e uma análise geral dos comentários".
Entrada: linhas no formato de collect_comentarios_youtube.CAMPOS. Saída pública: só agregados e redes com autores em código.
  - volume: comentários, autores, respostas, por dia (Brasília);
  - temas: percentual por expressão regular (dicionário passado por quem chama; um comentário pode ter vários);
  - palavras mais frequentes e rede de coocorrência (redes_caso.palavras);
  - quem responde a quem (redes_caso.respostas; autores como código);
  - classes no estilo IRaMuTeQ (CHD de Reinert, redes_caso.classes) e corpus no privado;
  - circulação: canal × termo/tema com peso em visualizações (redes_caso.circulacao), quando houver vídeos.
"""
from __future__ import annotations

import random
import re
from collections import Counter
from datetime import datetime, timedelta
from pathlib import Path

MAX_CHD = 5000
ARROBA = re.compile(r"@\S+|https?://\S+")
STOP = set("a o e de da do das dos que em um uma para pra por com não nao na no nas nos se é eu você vc ele ela isso esse essa mais mas "
           "vai seu sua aqui está esta foi tem estão como ser pelo pela pode isso essa esse eles elas nós já quando também muito tudo nada "
           "sobre até sem só todos todo toda são era ter vamos agora porque pois onde quem qual aos às ao me te lhe meu minha nosso nossa "
           "the to and of you is in for on it this that are be".split())


def dia_brt(iso: str) -> str | None:
    try:
        return (datetime.fromisoformat(iso.replace("Z", "+00:00")) - timedelta(hours=3)).strftime("%Y-%m-%d")
    except (ValueError, AttributeError):
        return None


def temas_pct(textos: list[str], temas: dict) -> dict:
    n = len(textos)
    c = Counter(t for x in textos for t, rx in temas.items() if re.search(rx, ARROBA.sub(" ", x or ""), re.I))
    return {t: {"n": c.get(t, 0), "pct": round(100 * c.get(t, 0) / n, 1) if n else None} for t in temas}


def analisar(rows: list[dict], temas: dict, pub: Path, priv: Path, prefixo: str = "") -> dict:
    textos = [r.get("texto") or "" for r in rows]
    autores = {r.get("autor_canal") or r.get("autor_nome") for r in rows} - {None, ""}
    dias = Counter(d for d in (dia_brt(r.get("publicado_em") or "") for r in rows) if d)
    palavras = Counter(w for t in textos for w in re.findall(r"[a-zà-úç]{3,}", ARROBA.sub(" ", t).lower()) if w not in STOP)
    out = {"comentarios": len(rows), "autores": len(autores), "respostas": sum(1 for r in rows if r.get("tipo") == "resposta"),
           "por_dia": dict(sorted(dias.items())), "temas": temas_pct(textos, temas), "temas_regex": temas,
           "palavras": [[w, n] for w, n in palavras.most_common(40) if n >= 5]}  # só palavras com 5+ ocorrências (nada de trecho único)
    try:
        import redes_caso as rc
        if rows:
            n, a, d = rc.palavras(textos)
            rc.gexf(n, a, pub / f"rede_palavras_comentarios{prefixo}.gexf")
            out["rede_palavras"] = {"desenho": d, "gexf": f"rede_palavras_comentarios{prefixo}.gexf",
                                    "o_que_e": "palavras que aparecem juntas no mesmo comentário (3+ vezes); cor = comunidade"}
            n, a, r = rc.respostas(rows)
            rc.gexf(n, a, pub / f"rede_respostas_comentarios{prefixo}.gexf", dirigida=True)
            out["rede_respostas"] = {**r, "gexf": f"rede_respostas_comentarios{prefixo}.gexf",
                                     "o_que_e": "quem responde a quem nos comentários; autores sempre como código (A0001…)"}
            # CHD com mais de ~6 mil comentários estoura a memória (27/10/2026, caso 011 com 22 mil): amostra aleatória fixa
            amostra = rows if len(rows) <= MAX_CHD else random.Random(42).sample(rows, MAX_CHD)
            out["classes"] = rc.classes([r.get("texto") or "" for r in amostra], [(r.get("publicado_em") or "0000")[:4] for r in amostra])
            if out["classes"] is not None:
                out["classes"]["amostra"] = {"comentarios": len(amostra), "de": len(rows), "semente": 42}
            priv.mkdir(parents=True, exist_ok=True)
            (priv / f"corpus_iramuteq_comentarios{prefixo}.txt").write_text(rc.corpus_iramuteq(rows), encoding="utf-8")
    except Exception as e:  # noqa: BLE001 — sem numpy/networkx a análise de volume e temas continua
        out["erro_redes"] = f"{type(e).__name__}: {str(e)[:200]}"
    return out


def circulacao(videos: list[dict], pub: Path, nome: str = "rede_circulacao.gexf") -> dict:
    """videos: dicts com canal, canal_id, inscritos, visualizacoes e consulta (termo ou tema que liga o vídeo)."""
    try:
        import redes_caso as rc
        n, a, d = rc.circulacao(videos, [], [])
        rc.gexf(n, a, pub / nome)
        return {"desenho": d, "gexf": nome, "o_que_e": "canais do YouTube ligados ao termo ou tema que os trouxe; peso = visualizações; "
                "canais com menos de 10 mil inscritos aparecem como código"}
    except Exception as e:  # noqa: BLE001
        return {"erro": f"{type(e).__name__}: {str(e)[:200]}"}
