#!/usr/bin/env python3
"""Caderno 13 — vídeos do YouTube de Lula e Flávio Bolsonaro classificados por tema (dicionário aberto).

Entrada: data/youtube/videos_latest.csv.gz (coleta diária) + data/config/temas_youtube.json
Saída:   data/youtube/conteudo.json

Para cada vídeo, sobre título + descrição normalizados:
  - temas: todos os temas do dicionário com pelo menos um termo encontrado ("sem_tema" se nenhum);
  - cita_adversario: algum termo do adversário aparece;
  - pede_voto: alguma expressão de pedido de voto com o próprio número (ou referência ao 2º turno).
Inspirado nos níveis do Flaviômetro (0 não cita / 1 cita / 2 pede voto), mas com regras publicadas.
"""
from __future__ import annotations

import csv
import datetime as dt
import gzip
import json
import re
import sys
import unicodedata
from collections import Counter
from pathlib import Path


def norm(s: str) -> str:
    s = unicodedata.normalize("NFKD", s or "").lower()
    s = "".join(c for c in s if not unicodedata.combining(c))
    return " " + re.sub(r"[^a-z0-9#]+", " ", s).strip() + " "


def term_regex(term: str) -> re.Pattern:
    prefixo = term.strip().endswith("*")  # checar antes de norm(), que remove o "*"
    t = norm(term.strip().rstrip("*")).strip()
    body = re.escape(t).replace(r"\ ", " ")
    return re.compile(r"(?<![a-z0-9])" + body + (r"[a-z0-9]*" if prefixo else r"(?![a-z0-9])"))


def compile_cfg(cfg: dict):
    temas = {k: [term_regex(t) for t in v] for k, v in cfg["temas"].items()}
    cands = {}
    for cid, c in cfg["candidatos"].items():
        cands[cid] = {"adv": [term_regex(t) for t in c["adversario"]],
                      "voto": [term_regex(t.replace("{n}", c["numero"])) for t in cfg["pede_voto"]], **c}
    return temas, cands


URL = re.compile(r"(https?://\S+|www\.\S+|\S+\.(com|br|me|app|org|net)(/\S*)?)", re.I)
SEG = re.compile(r"(?<=[.!?])\s+|\s[|•]\s|\s-\s|\s*[\U0001F300-\U0001FAFF☀-➿]+\s*|\n")  # emojis também separam trechos
LIMIAR_REPETICAO = 10  # trecho presente em 10+ vídeos do mesmo canal = texto padrão (rodapé, institucional)


def segmentos(desc: str) -> list[str]:
    return [x.strip() for x in SEG.split(URL.sub(" ", desc or "")) if x.strip()]


def texto_padrao(rows: list[dict]) -> dict[str, set]:
    """Por canal, os trechos de descrição repetidos em LIMIAR_REPETICAO ou mais vídeos."""
    cont: dict[str, Counter] = {}
    for r in rows:
        cont.setdefault(r["channel_id"], Counter()).update(set(segmentos(r.get("descricao", ""))))
    return {ch: {s for s, n in c.items() if n >= LIMIAR_REPETICAO} for ch, c in cont.items()}


def texto_util(r: dict, padrao: dict[str, set]) -> str:
    fora = padrao.get(r["channel_id"], set())
    return r["titulo"] + " " + " ".join(s for s in segmentos(r.get("descricao", "")) if s not in fora)


# Nuvem de palavras: frequência por documento (em quantos vídeos o termo aparece), sobre o mesmo texto útil.
STOP = set(norm("""a o e é de da do das dos em no na nos nas um uma uns umas para pra pro por pelo pela pelos pelas com sem
que se não nao mais mas ou como ao aos à às já ja foi ser são sao está esta estão estao isso essa esse este esta isto
aquele aquela ele ela eles elas nós nos você voce vocês voces eu me meu minha meus minhas seu sua seus suas nosso nossa
nossos nossas lhe te tu dele dela deles delas quem qual quais quando onde porque porquê sobre entre até ate também tambem
muito muita muitos muitas pouco todo toda todos todas tudo nada aqui ali lá la agora hoje ontem amanhã amanha vai vão vao
vamos ter tem têm tinha teve fazer faz fez feito ver vê vou estou estamos são sou era eram será sera seria há ha pode podem
dia dias ano anos vez vezes cada outro outra outros outras mesmo mesma só so ainda então entao assim bem sim também
https http www com br youtube video vídeo vídeos videos canal inscreva inscrevase inscreva-se ative sininho link bio
shorts short live ao vivo assista confira acompanhe veja siga redes sociais instagram facebook tiktok twitter kwai
whatsapp telegram x clique aqui completo íntegra integra parte episódio episodio programa acesse site conheça conheca
obrigado obrigada pronto fim gente quer quero precisa contra lado enquanto nunca sempre grande novo nova tempo seguir bora
propaganda eleitoral horário horario gratuito janeiro fevereiro março marco abril maio junho julho agosto setembro outubro
novembro dezembro segunda terça terca quarta quinta sexta sábado sabado domingo
""").split())
NUVEM_TOP = 60
NUVEM_MIN_VIDEOS = 3
TOKEN = re.compile(r"[#]?[0-9a-zà-ÿ][0-9a-zà-ÿ]*(?:x[0-9]+)?", re.I)


def _valido(t: str, excluir: set) -> bool:
    return len(t.lstrip("#")) >= 3 and t.lstrip("#") not in STOP and t.lstrip("#") not in excluir and not t.lstrip("#").isdigit()


def termos(text: str, excluir: set) -> set[str]:
    """Termos (palavras, hashtags e pares de palavras) normalizados sem acento; um termo conta 1x por vídeo.
    Hashtags não formam pares."""
    toks = [t for t in (norm(x).strip() for x in TOKEN.findall((text or "").lower())) if t]
    out = set()
    for i, t in enumerate(toks):
        ok = _valido(t, excluir)
        if ok:
            out.add(t)
        if ok and not t.startswith("#") and i + 1 < len(toks):
            u = toks[i + 1]
            if not u.startswith("#") and _valido(u, excluir):
                out.add(t + " " + u)
    return out


def nuvem(textos: list[str], excluir: set, top: int = NUVEM_TOP, minimo: int = NUVEM_MIN_VIDEOS) -> list[list]:
    df = Counter()
    for tx in textos:
        df.update(termos(tx, excluir))
    df = {t: n for t, n in df.items() if n >= minimo}
    # par de palavras absorve a palavra solta quando cobre 80%+ das ocorrências dela
    for t, n in list(df.items()):
        if " " in t:
            for w in t.split():
                if w in df and n >= 0.8 * df[w]:
                    df.pop(w, None)
    return [[t, n] for t, n in sorted(df.items(), key=lambda x: (-x[1], x[0]))[:top]]


def classify(text: str, temas, cand) -> dict:
    t = norm(text)
    found = [k for k, regs in temas.items() if any(r.search(t) for r in regs)]
    return {"temas": found or ["sem_tema"],
            "cita_adversario": any(r.search(t) for r in cand["adv"]),
            "pede_voto": any(r.search(t) for r in cand["voto"])}


def main(argv=None) -> int:
    root = Path(argv[0]) if argv else Path(".")
    cfg = json.loads((root / "data/config/temas_youtube.json").read_text(encoding="utf-8"))
    temas, cands = compile_cfg(cfg)
    src = root / "data/youtube/videos_latest.csv.gz"
    rows = list(csv.DictReader(gzip.open(src, "rt", encoding="utf-8"), delimiter=";"))
    padrao = texto_padrao(rows)
    coletado = max((r["coletado_em"] for r in rows), default=None)
    out = {"schema_version": 1, "gerado_em_utc": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
           "coletado_em_utc": coletado, "fonte": "YouTube Data API v3 (canais declarados ao TSE)",
           "metodo_nuvem": f"Nuvem: em quantos vídeos cada palavra ou par de palavras aparece (título + descrição útil), mínimo {NUVEM_MIN_VIDEOS} vídeos, top {NUVEM_TOP}; excluídas palavras funcionais, meses, termos de formato (propaganda eleitoral, acesse, inscreva-se), o nome do próprio candidato e o nome e a hashtag do próprio canal. Hashtags aparecem com #.",
           "metodo": cfg["nota"] + f" Antes de classificar, links são removidos e trechos de descrição repetidos em {LIMIAR_REPETICAO}+ vídeos do mesmo canal (rodapés, textos institucionais) são descartados.", "temas": list(cfg["temas"]) + ["sem_tema"], "candidatos": {}}
    for cid, cand in cands.items():
        vids, textos = [], []
        nomes_canais = sorted({r["canal"] for r in rows if r["candidate_id"] == cid}, key=len, reverse=True)
        tira_canal = re.compile("|".join(re.escape(n) for n in nomes_canais) or "(?!)", re.I)
        nome = norm(cand["nome"]).split()
        excluir = set(nome) | {"".join(nome)} | set(norm(" ".join(cand.get("excluir_nuvem", []))).split())
        for r in rows:
            if r["candidate_id"] != cid:
                continue
            txt = texto_util(r, padrao)
            textos.append(tira_canal.sub(" ", txt))  # nome do canal não é assunto
            excluir.add(norm(r["canal"]).replace(" ", ""))  # hashtag do próprio canal (#tvcelular)
            c = classify(txt, temas, cand)
            vids.append({"video_id": r["video_id"], "canal": r["canal"], "titulo": r["titulo"],
                         "publicado_em": r["publicado_em"], "duracao": r["duracao"],
                         "visualizacoes": int(r["visualizacoes"]) if r["visualizacoes"] else None,
                         "curtidas": int(r["curtidas"]) if r["curtidas"] else None,
                         "comentarios": int(r["comentarios"]) if r["comentarios"] else None, **c})
        vids.sort(key=lambda v: v["publicado_em"] or "", reverse=True)
        por_tema = Counter(t for v in vids for t in v["temas"])
        views_tema = Counter()
        for v in vids:
            for t in v["temas"]:
                views_tema[t] += v["visualizacoes"] or 0
        out["candidatos"][cid] = {"nome": cand["nome"], "numero": cand["numero"], "total_videos": len(vids),
                                  "canais": sorted({v["canal"] for v in vids}),
                                  "por_tema": dict(por_tema.most_common()), "visualizacoes_por_tema": dict(views_tema.most_common()),
                                  "cita_adversario": sum(v["cita_adversario"] for v in vids),
                                  "pede_voto": sum(v["pede_voto"] for v in vids),
                                  "nuvem": nuvem(textos, excluir),
                                  "videos": vids}
        print(cand["nome"], len(vids), "vídeos | temas:", dict(por_tema.most_common(6)),
              "| cita adversário:", out["candidatos"][cid]["cita_adversario"], "| pede voto:", out["candidatos"][cid]["pede_voto"])
    (root / "data/youtube/conteudo.json").write_text(json.dumps(out, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
