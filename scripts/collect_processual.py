#!/usr/bin/env python3
"""Processos eleitorais de 2026 (PJe) — TSE, Dados Abertos, conjunto processual-2026 (grátis; atualização sob demanda do TSE).

Pedido do responsável (22/10/2026, 01h26). Estrutura conferida pela sonda C19.95 (run 39723264242): processo_eleitoral (99 mil
linhas), assuntos (182 mil), decisões (137 mil), partes (617 mil) e recursos (9 mil), arquivos de 21/10/2026.

Público (só agregados e dados de figuras públicas):
- totais; processos por classe, assunto principal, tribunal (UF e instância), mês de autuação; situação (baixado ou em curso);
  decisões por tipo e por mês; recursos por classe e tribunal;
- recorte de temas de interesse do Observatório pelos assuntos (propaganda, internet e redes, desinformação ou fato
  inverídico, inteligência artificial ou conteúdo sintético, pesquisa eleitoral, abuso de poder), contados por processo;
- processos em que candidatos a presidente ou vice de 2026 são parte (pelo SQ_CANDIDATO da base de candidaturas do TSE):
  número, classe, assunto, tribunal, datas, polo e link público do processo.
Partes que não são candidatos à Presidência nunca aparecem com nome no público; nomes de relatores não são publicados.
Bruto no repositório privado (ODI_INTERNO_DIR/tse/processual/).
Uso: python scripts/collect_processual.py
"""
from __future__ import annotations

import csv
import gzip
import io
import json
import os
import re
import sys
import tempfile
import urllib.request
import zipfile
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from net import now_utc  # noqa: E402

BASE = "https://cdn.tse.jus.br/estatistica/sead/odsele/processual/"
ARQS = {"processo": "processo_eleitoral_2026", "assuntos": "processos_eleitorais_assuntos_2026", "decisoes": "processos_eleitorais_decisoes_2026",
        "partes": "processos_eleitorais_partes_2026", "recursos": "recursos_eleitorais_2026"}
FONTE = "https://dadosabertos.tse.jus.br/dataset/processual-2026"
TEMAS = {
    "propaganda eleitoral": r"propaganda",
    "internet e redes sociais": r"internet|rede social|redes sociais|impulsionamento|aplicativo|mensagem|whatsapp|disparo",
    "desinformação ou fato inverídico": r"desinforma|inver[ií]dic|fake|not[ií]cia falsa|fato sabidamente",
    "inteligência artificial ou conteúdo sintético": r"intelig[eê]ncia artificial|sint[eé]tic|deep ?fake|manipula[cç][aã]o digital",
    "pesquisa eleitoral": r"pesquisa eleitoral|pesquisa",
    "abuso de poder": r"abuso",
    "direito de resposta": r"direito de resposta",
}
LISTAR_TEMAS = ["inteligência artificial ou conteúdo sintético", "desinformação ou fato inverídico"]
csv.field_size_limit(10**9)
UA = {"User-Agent": "Mozilla/5.0 (ODI Atlas; pesquisa acadêmica)"}


def ler(nome: str, pasta: Path) -> tuple[str, list[dict]]:
    destino = pasta / f"{nome}.zip"
    with urllib.request.urlopen(urllib.request.Request(BASE + destino.name, headers=UA), timeout=900) as r:
        destino.write_bytes(r.read())
    z = zipfile.ZipFile(destino)
    arq = next((x for x in z.namelist() if x.lower().endswith(".csv") and "BRASIL" in x.upper()), None) or next(x for x in z.namelist() if x.lower().endswith(".csv"))
    txt = z.read(arq).decode("latin-1")
    return txt, list(csv.DictReader(io.StringIO(txt), delimiter=";"))


def iso(d: str | None) -> str | None:
    d = (d or "").strip()
    m = re.match(r"(\d{2})/(\d{2})/(\d{4})", d)
    return f"{m.group(3)}-{m.group(2)}-{m.group(1)}" if m else (d[:10] if re.match(r"\d{4}-\d{2}-\d{2}", d) else None)


def limpo(v: str | None) -> str:
    v = (v or "").strip()
    return "" if v.upper() in ("", "#NULO", "#NULO#", "#NE", "NÃO INFORMADO") else v


def tribunal(uf: str, inst: str) -> str:
    return "TSE" if str(inst) == "3" else (f"TRE-{uf}" if str(inst) == "2" else f"Zona eleitoral ({uf})")


def candidatos_presidencia(root: Path) -> dict:
    out = {}
    for r in csv.DictReader(gzip.open(root / "data/tse/candidatos_2026.csv.gz", "rt", encoding="utf-8"), delimiter=";"):
        if (r.get("DS_CARGO") or "").upper() in ("PRESIDENTE", "VICE-PRESIDENTE"):
            out[r["SQ_CANDIDATO"]] = {"nome": r.get("NM_URNA_CANDIDATO"), "cargo": r["DS_CARGO"].title(), "numero": r.get("NR_CANDIDATO")}
    return out


def agregar(D: dict, cands: dict) -> dict:
    proc, ass, dec, par, rec = D["processo"], D["assuntos"], D["decisoes"], D["partes"], D["recursos"]
    por_proc_ass = defaultdict(set)
    for a in ass:
        por_proc_ass[a["NR_PROCESSO"]].add(limpo(a.get("DS_ASSUNTO")))
    for p in proc:
        por_proc_ass[p["NR_PROCESSO"]].add(limpo(p.get("DS_ASSUNTO_PRINCIPAL")))
    unicos = {p["NR_PROCESSO"]: p for p in proc}
    temas = {}
    for t, rx in TEMAS.items():
        r = re.compile(rx, re.I)
        ids = [n for n, s in por_proc_ass.items() if n in unicos and any(r.search(x) for x in s if x)]
        temas[t] = {"processos": len(ids), "por_tribunal": Counter(tribunal(unicos[n]["SG_UF_TRIBUNAL"], unicos[n]["NR_INSTANCIA"]) for n in ids).most_common(10),
                    "assuntos": Counter(x for n in ids for x in por_proc_ass[n] if x and r.search(x)).most_common(8)}
    mes = Counter((iso(p.get("DT_AUTUACAO")) or "?")[:7] for p in unicos.values())
    # candidatos à Presidência como parte
    envolv = defaultdict(list)
    chapas_do_proc = defaultdict(set)  # processo → {(nome, cargo, número, polo)}
    for x in par:
        sq = (x.get("SQ_CANDIDATO") or "").strip()
        if sq in cands and x["NR_PROCESSO"] in unicos:
            envolv[sq].append(x)
            c = cands[sq]
            chapas_do_proc[x["NR_PROCESSO"]].add((c["nome"], c["cargo"], c["numero"], limpo(x.get("DS_POLO"))))
    # lista dos processos dos temas de IA e desinformação (pedido de 22/10/2026: levar à página de rótulo de IA) e tema × chapa
    for t in LISTAR_TEMAS:
        r = re.compile(TEMAS[t], re.I)
        ids = [n for n, st in por_proc_ass.items() if n in unicos and any(r.search(x) for x in st if x)]
        lista = []
        for n in ids:
            p = unicos[n]
            lista.append({"processo": n, "classe": limpo(p.get("DS_CLASSE")), "assuntos": sorted(x for x in por_proc_ass[n] if x and r.search(x)),
                          "tribunal": tribunal(p["SG_UF_TRIBUNAL"], p["NR_INSTANCIA"]), "uf": p.get("SG_UF_TRIBUNAL"), "autuacao": iso(p.get("DT_AUTUACAO")),
                          "baixa": iso(p.get("DT_BAIXA")), "decisoes": int(p.get("QT_DECISOES") or 0), "url": limpo(p.get("DS_URL_PROCESSO")),
                          "chapas": sorted({f"{nm} ({cg.lower()}, {nr}) · {pl.replace('Pólo ', 'polo ')}" for nm, cg, nr, pl in chapas_do_proc.get(n, ())})})
        lista.sort(key=lambda x: x["autuacao"] or "", reverse=True)
        temas[t]["lista"] = lista
        temas[t]["por_mes"] = sorted(Counter((x["autuacao"] or "?")[:7] for x in lista).items())
        temas[t]["por_classe"] = Counter(x["classe"] for x in lista).most_common(10)
    tema_chapa = {}
    for t, rx in TEMAS.items():
        r = re.compile(rx, re.I)
        cont = Counter()
        for n, st in por_proc_ass.items():
            if n in unicos and any(r.search(x) for x in st if x):
                for nm, cg, nr, pl in {(a, b, c, "passivo" if "passivo" in d.lower() else "ativo" if "ativo" in d.lower() else "outro") for a, b, c, d in chapas_do_proc.get(n, ())}:
                    cont[(nr, nm, cg, pl)] += 1
        tema_chapa[t] = [{"numero": nr, "nome": nm, "cargo": cg, "polo": pl, "processos": v} for (nr, nm, cg, pl), v in cont.most_common()]
    pres = []
    for sq, xs in envolv.items():
        c = cands[sq]
        lista = []
        for nr in sorted({x["NR_PROCESSO"] for x in xs}):
            p = unicos[nr]
            lista.append({"processo": nr, "classe": limpo(p.get("DS_CLASSE")), "assunto": limpo(p.get("DS_ASSUNTO_PRINCIPAL")),
                          "tribunal": tribunal(p["SG_UF_TRIBUNAL"], p["NR_INSTANCIA"]), "autuacao": iso(p.get("DT_AUTUACAO")), "baixa": iso(p.get("DT_BAIXA")),
                          "polo": sorted({limpo(x.get("DS_POLO")) for x in xs if x["NR_PROCESSO"] == nr} - {""}), "decisoes": int(p.get("QT_DECISOES") or 0),
                          "ultima_decisao": iso(p.get("DT_ULTIMA_DECISAO")), "url": limpo(p.get("DS_URL_PROCESSO"))})
        lista.sort(key=lambda x: x["autuacao"] or "", reverse=True)
        pres.append({**c, "processos": len(lista), "por_polo": Counter(p for x in lista for p in x["polo"]).most_common(), "lista": lista})
    pres.sort(key=lambda x: (x["cargo"] != "Presidente", -x["processos"]))
    return {"totais": {"processos": len(unicos), "linhas_processo": len(proc), "assuntos": len(ass), "decisoes": len(dec), "partes": len(par), "recursos": len(rec),
                       "baixados": sum(1 for p in unicos.values() if iso(p.get("DT_BAIXA"))), "sem_decisao": sum(1 for p in unicos.values() if str(p.get("QT_DECISOES")) == "0"),
                       "partes_candidatos": sum(1 for x in par if (x.get("ST_CANDIDATO") or "").upper() in ("S", "SIM"))},
            "por_classe": Counter(limpo(p.get("DS_CLASSE")) or "não informado" for p in unicos.values()).most_common(20),
            "por_assunto_principal": Counter(limpo(p.get("DS_ASSUNTO_PRINCIPAL")) or "não informado" for p in unicos.values()).most_common(30),
            "por_tribunal": Counter(tribunal(p["SG_UF_TRIBUNAL"], p["NR_INSTANCIA"]) for p in unicos.values()).most_common(),
            "por_instancia": Counter({"1": "zona eleitoral", "2": "TRE", "3": "TSE"}.get(str(p["NR_INSTANCIA"]), "?") for p in unicos.values()).most_common(),
            "por_mes_autuacao": sorted(mes.items()),
            "decisoes_por_tipo": Counter(limpo(d.get("DS_TIPO_DECISAO")) or "não informado" for d in dec).most_common(),
            "decisoes_por_mes": sorted(Counter((iso(d.get("DT_DECISAO")) or "?")[:7] for d in dec).items()),
            "recursos_por_classe": Counter(limpo(r.get("DS_CLASSE")) or "não informado" for r in rec).most_common(),
            "recursos_por_tribunal": Counter(tribunal(r["SG_UF_TRIBUNAL"], r["NR_INSTANCIA"]) for r in rec).most_common(15),
            "temas": temas, "tema_por_chapa": tema_chapa, "candidatos_presidencia": pres}


def main(argv=None) -> int:
    root = Path(".")
    interno = os.environ.get("ODI_INTERNO_DIR")
    D, brutos = {}, {}
    with tempfile.TemporaryDirectory() as t:
        for k, nome in ARQS.items():
            brutos[k], D[k] = ler(nome, Path(t))
            print(f"{nome}: {len(D[k])} linhas")
    gerado = D["processo"][0].get("DT_GERACAO") if D["processo"] else None
    out = {"schema_version": 1, "coletado_em_utc": now_utc(), "gerado_pelo_tse": iso(gerado), "fonte": FONTE,
           "arquivos": [BASE + v + ".zip" for v in ARQS.values()], **agregar(D, candidatos_presidencia(root)),
           "nota": "Processos do PJe da Justiça Eleitoral referentes ao pleito de 2026, como o TSE publica. Os temas são lidos nos assuntos "
                   "de cada processo (assunto principal e demais assuntos), por expressões: um processo pode estar em mais de um tema. "
                   "Partes que não são candidatos à Presidência não aparecem com nome; o link leva à consulta pública do processo."}
    pasta = root / "data/tse/processual"
    pasta.mkdir(parents=True, exist_ok=True)
    (pasta / "resumo.json").write_text(json.dumps(out, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    if interno:
        pv = Path(interno) / "tse/processual"
        pv.mkdir(parents=True, exist_ok=True)
        for k, txt in brutos.items():
            with gzip.open(pv / f"{ARQS[k]}.csv.gz", "wt", encoding="utf-8") as f:
                f.write(txt)
    T = out["totais"]
    print(f"processual (TSE {out['gerado_pelo_tse']}): {T['processos']} processos · {T['decisoes']} decisões · {T['recursos']} recursos · "
          f"temas {[(k, v['processos']) for k, v in out['temas'].items()]} · candidatos à Presidência como parte "
          f"{[(c['nome'], c['processos']) for c in out['candidatos_presidencia']]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
