"""Denúncias eleitorais (Pardal) e pesquisas eleitorais registradas — Portal de Dados Abertos do TSE, eleição 2026 (grátis, diário).

Fontes (estrutura conferida pela sonda de 20/10/2026, run 39535985536):
- https://dadosabertos.tse.jus.br/dataset/denuncias-eleitorais → denuncia_2026.zip (denuncia_2026_BRASIL.csv; uma linha por denúncia;
  colunas: UF, município, cargo, tipo de irregularidade, origem (app/web), situação, processo no PJe). Não há data da denúncia,
  só a data de geração do arquivo: a série no tempo é montada pelo Atlas a cada coleta (historico.csv).
- https://dadosabertos.tse.jus.br/dataset/pesquisas-eleitorais-2026 → pesquisa_eleitoral_2026.zip, pesquisa_contratante_2026.zip,
  pesquisa_pagante_2026.zip (registro da pesquisa: empresa, datas, entrevistados, valor, contratante, pagante, origem do recurso).
  O registro NÃO traz o resultado (intenção de voto); o resultado é divulgado pelos institutos e por agregadores.

Saída pública (só agregados e dados de empresas): data/tse/denuncias/resumo.json, data/tse/denuncias/historico.csv,
data/tse/pesquisas/resumo.json. Contratante ou pagante com CPF (pessoa física) aparece como "pessoa física (nome omitido)".
O nome do estatístico responsável não é publicado. Bruto (CSV do TSE) no repositório privado: ODI_INTERNO_DIR/tse/.
Uso: python scripts/collect_tse_denuncias_pesquisas.py
"""
from __future__ import annotations

import csv
import gzip
import io
import json
import os
import re
import statistics
import sys
import urllib.request
import zipfile
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from net import now_utc  # noqa: E402

BASE = "https://cdn.tse.jus.br/estatistica/sead/odsele/"
ARQ_DEN = "denuncia/denuncia_2026.zip"
ARQ_PESQ = {"pesquisa": "pesquisa_eleitoral/pesquisa_eleitoral_2026.zip", "contratante": "pesquisa_eleitoral/pesquisa_contratante_2026.zip",
            "pagante": "pesquisa_eleitoral/pesquisa_pagante_2026.zip"}
FONTE_DEN = "https://dadosabertos.tse.jus.br/dataset/denuncias-eleitorais"
FONTE_PESQ = "https://dadosabertos.tse.jus.br/dataset/pesquisas-eleitorais-2026"
PRIMEIRO_TURNO = "2026-10-04"
NULOS = {"", "#NULO", "#NULO#", "NÃO DIVULGÁVEL", "NAO DIVULGAVEL"}
# tipos do Pardal que dizem respeito a ambiente digital ou mensagens (o Pardal não tem uma categoria única de "internet")
DIGITAIS = re.compile(r"internet|mensage|telemarketing|desinforma|intelig[êe]ncia artificial|conte[úu]do sint", re.I)
csv.field_size_limit(10**9)

# Abrangência da pesquisa. O TSE registra toda pesquisa que inclui presidente com UE = BR, mesmo quando a amostra é de um só estado
# ou município (verificado em 21/10/2026: 1.404 de 1.404 com UE = BR). A abrangência real está no texto do plano amostral e da
# área de coleta, escritos pela empresa; a classificação abaixo é automática (por expressões) e fica marcada como tal na página.
UFN = {"ACRE": "AC", "ALAGOAS": "AL", "AMAPA": "AP", "AMAZONAS": "AM", "BAHIA": "BA", "CEARA": "CE", "DISTRITO FEDERAL": "DF", "ESPIRITO SANTO": "ES",
       "GOIAS": "GO", "MARANHAO": "MA", "MATO GROSSO DO SUL": "MS", "MATO GROSSO": "MT", "MINAS GERAIS": "MG", "PARAIBA": "PB", "PARANA": "PR",
       "PARA": "PA", "PERNAMBUCO": "PE", "PIAUI": "PI", "RIO DE JANEIRO": "RJ", "RIO GRANDE DO NORTE": "RN", "RIO GRANDE DO SUL": "RS",
       "RONDONIA": "RO", "RORAIMA": "RR", "SANTA CATARINA": "SC", "SAO PAULO": "SP", "SERGIPE": "SE", "TOCANTINS": "TO"}
_UFS = "|".join(sorted(UFN, key=len, reverse=True))
RX_NAC = re.compile(r"TERRITORIO (NACIONAL|BRASILEIRO)|AMBITO NACIONAL|ABRANGENCIA NACIONAL|AMOSTRA NACIONAL|PESQUISA NACIONAL|NIVEL NACIONAL|"
                    r"ELEITORADO (BRASILEIRO|NACIONAL|DE BRASIL|DO BRASIL)|ELEITORES BRASILEIROS|BRASILEIROS (A PARTIR|COM|DE 16)|TODO O (BRASIL|PAIS)|"
                    r"TODAS AS (27 )?(UNIDADES DA FEDERACAO|UFS?|REGIOES|CINCO REGIOES|GRANDES REGIOES)|27 (UNIDADES|UFS?|ESTADOS)|"
                    r"\b5 REGIOES|CINCO (GRANDES )?REGIOES|(UNIVERSO|ABRANGENCIA)[^.]{0,60}\bBRASIL\b|ELEITORES (DO|DE TODO O) BRASIL|COLETA E NACIONAL|ABRANGENCIA (DA COLETA )?(E )?NACIONAL")
RX_EST = re.compile(r"(ESTADO|ELEITORADO|ELEITORES|UF|UNIDADE DA FEDERACAO|ESTADUAL|POPULACAO)\b[^.;]{0,40}?\b(DO|DA|DE)\s+(" + _UFS + r")\b|"
                    r"ABRANGENCIA[^.]{0,40}?:\s*(" + _UFS + r")\s*(?:\.|$|A RELACAO)")
RX_EST_SIGLA = re.compile(r"\bESTADO D[OEA]\s+(" + "|".join(sorted(set(UFN.values()))) + r")\b")
RX_EST_SEM_UF = re.compile(r"DESTA UF|DESTE ESTADO|ABRANGENCIA ESTADUAL|PESQUISA ESTADUAL|PLANO AMOSTRAL ESTADUAL|AMOSTRA ESTADUAL")
RX_MUN = re.compile(r"MUNICIPIO D[EO]\s+[A-Z]|CIDADE D[EOA]\s+[A-Z]|RESIDENTES NO MUNICIPIO|ELEITORADO D[OE] MUNICIPIO|"
                    r"ABRANGENCIA[^.]{0,40}?:\s*[A-Z ]+\s*-\s*[A-Z]{2}\b|\bMUNICIPAL\b")


def _sem_acento(s: str | None) -> str:
    import unicodedata
    return "".join(c for c in unicodedata.normalize("NFD", (s or "").upper()) if unicodedata.category(c) != "Mn")


def abrangencia(plano: str | None, area: str | None, metodo: str | None = None) -> tuple[str, str | None]:
    """Uma única UF nomeada como universo (estado/eleitorado/eleitores de X) → estadual, mesmo que o texto cite o Brasil em outro
    ponto (textos-padrão citam "população brasileira" do IBGE); senão, expressão de universo nacional → nacional."""
    t = _sem_acento(f"{plano or ''} . {area or ''} . {metodo or ''}")
    ufs = {UFN[m.group(3) or m.group(4)] for m in RX_EST.finditer(t)} | {m.group(1) for m in RX_EST_SIGLA.finditer(t)}
    if len(ufs) == 1:
        return "estadual", next(iter(ufs))
    if RX_NAC.search(t):
        return "nacional", None
    if RX_EST_SEM_UF.search(t):
        return "estadual", None
    if RX_MUN.search(t):
        return "municipal", None
    return "não identificada", None


def baixar(rel: str) -> zipfile.ZipFile:
    req = urllib.request.Request(BASE + rel, headers={"User-Agent": "Mozilla/5.0 (ODI Atlas; pesquisa acadêmica)"})
    return zipfile.ZipFile(io.BytesIO(urllib.request.urlopen(req, timeout=300).read()))


def ler_brasil(z: zipfile.ZipFile) -> tuple[str, list[dict]]:
    nome = next(n for n in z.namelist() if n.upper().endswith("_BRASIL.CSV"))
    txt = z.read(nome).decode("latin-1")
    return txt, list(csv.DictReader(io.StringIO(txt), delimiter=";"))


def limpo(v: str | None) -> str:
    v = (v or "").strip()
    return "" if v.upper() in NULOS else v


def contar(rows: list[dict], campo: str, rotulo_vazio: str = "não informado") -> list[list]:
    return [[k, n] for k, n in Counter(limpo(r.get(campo)) or rotulo_vazio for r in rows).most_common()]


def turno(r: dict) -> str:
    return "2º turno" if "2" in re.sub(r"2026", "", r.get("DS_ELEICAO") or "") else "1º turno"


def data_iso(v: str | None) -> str | None:
    v = (v or "").strip()
    m = re.match(r"(\d{2})/(\d{2})/(\d{4})", v)
    if m:
        return f"{m.group(3)}-{m.group(2)}-{m.group(1)}"
    return v[:10] if re.match(r"\d{4}-\d{2}-\d{2}", v) else None


def resumo_denuncias(rows: list[dict]) -> dict:
    gerado = data_iso(rows[0].get("DT_GERACAO")) if rows else None
    pres = [r for r in rows if (r.get("DS_CARGO") or "").upper() in ("PRESIDENTE", "VICE-PRESIDENTE")]
    dig = [r for r in rows if DIGITAIS.search(r.get("TP_IRREGULARIDADE") or "")]
    peticionadas = sum((r.get("ST_PETICIONAMENTO") or "").upper().startswith("PETICIONADA") for r in rows)
    por_tipo_cargo = defaultdict(Counter)
    for r in rows:
        por_tipo_cargo[limpo(r.get("TP_IRREGULARIDADE")) or "não informado"][limpo(r.get("DS_CARGO")) or "não informado"] += 1
    return {"gerado_pelo_tse": gerado, "hora_geracao_tse": (rows[0].get("HH_GERACAO") if rows else None), "total": len(rows),
            "por_turno": [[k, n] for k, n in Counter(turno(r) for r in rows).most_common()],
            "por_tipo": contar(rows, "TP_IRREGULARIDADE"), "por_cargo": contar(rows, "DS_CARGO"), "por_uf": contar(rows, "SG_UF"),
            "por_situacao": contar(rows, "ST_PETICIONAMENTO"), "por_origem": contar(rows, "DS_ORIGEM_DENUNCIA"),
            "peticionadas_pje": peticionadas,
            "municipios_top": [[f"{m} ({uf})", n] for (m, uf), n in Counter((r.get("NM_MUNICIPIO"), r.get("SG_UF")) for r in rows).most_common(15)],
            "presidente": {"total": len(pres), "por_tipo": contar(pres, "TP_IRREGULARIDADE"), "por_uf": contar(pres, "SG_UF"),
                           "por_turno": [[k, n] for k, n in Counter(turno(r) for r in pres).most_common()],
                           "por_situacao": contar(pres, "ST_PETICIONAMENTO")},
            "digitais": {"tipos": sorted({r.get("TP_IRREGULARIDADE") for r in dig}), "total": len(dig), "por_cargo": contar(dig, "DS_CARGO"),
                         "por_uf": contar(dig, "SG_UF"), "por_turno": [[k, n] for k, n in Counter(turno(r) for r in dig).most_common()]},
            "tipo_por_cargo": {t: dict(c.most_common()) for t, c in por_tipo_cargo.items()}}


def historico(arq: Path, d: dict) -> list[dict]:
    cols = ["gerado_pelo_tse", "coletado_em_utc", "total", "turno_1", "turno_2", "presidente", "digitais", "propaganda_internet", "peticionadas_pje"]
    linhas = list(csv.DictReader(open(arq, encoding="utf-8"), delimiter=";")) if arq.exists() else []
    t = dict(d["por_turno"])
    nova = {"gerado_pelo_tse": d["gerado_pelo_tse"], "coletado_em_utc": d["coletado_em_utc"], "total": d["total"], "turno_1": t.get("1º turno", 0),
            "turno_2": t.get("2º turno", 0), "presidente": d["presidente"]["total"], "digitais": d["digitais"]["total"],
            "propaganda_internet": dict(d["por_tipo"]).get("Propaganda na Internet", 0), "peticionadas_pje": d["peticionadas_pje"]}
    linhas = [x for x in linhas if x["gerado_pelo_tse"] != nova["gerado_pelo_tse"]] + [nova]  # um registro por arquivo do TSE
    linhas.sort(key=lambda x: x["gerado_pelo_tse"] or "")
    with open(arq, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, cols, delimiter=";", lineterminator="\n")
        w.writeheader()
        w.writerows(linhas)
    return linhas


def valor(v: str | None) -> float | None:
    v = limpo(v)
    try:
        return float(v.replace(".", "").replace(",", ".")) if v else None
    except ValueError:
        return None


def pessoa(doc: str | None, nome: str | None) -> str:
    """Empresa (CNPJ, 14 dígitos) aparece com nome; pessoa física (CPF) não."""
    d = re.sub(r"\D", "", doc or "")
    if len(d) == 14 and limpo(nome):
        return limpo(nome)
    return "pessoa física (nome omitido)" if len(d) == 11 else (limpo(nome) or "não informado")


def resumo_pesquisas(pesq: list[dict], contr: list[dict], pag: list[dict]) -> dict:
    cpor, ppor = defaultdict(list), defaultdict(list)
    for r in contr:
        cpor[r["NR_PROTOCOLO_REGISTRO"]].append(r)
    for r in pag:
        ppor[r["NR_PROTOCOLO_REGISTRO"]].append(r)
    pres = [r for r in pesq if "presidente" in (r.get("DS_CARGO") or "").lower()]

    def item(r: dict) -> dict:
        cs, ps = cpor.get(r["NR_PROTOCOLO_REGISTRO"], []), ppor.get(r["NR_PROTOCOLO_REGISTRO"], [])
        ab, uf = abrangencia(r.get("DS_PLANO_AMOSTRAL"), r.get("DS_DADO_MUNICIPIO"), r.get("DS_METODOLOGIA_PESQUISA"))
        return {"protocolo": r["NR_PROTOCOLO_REGISTRO"], "ue_registro": r.get("SG_UE"), "abrangencia": ab, "uf_amostra": uf, "empresa": limpo(r.get("NM_EMPRESA_FANTASIA")) or limpo(r.get("NM_EMPRESA")),
                "razao_social": limpo(r.get("NM_EMPRESA")), "registro": data_iso(r.get("DT_REGISTRO")), "inicio": data_iso(r.get("DT_INICIO_PESQUISA")),
                "fim": data_iso(r.get("DT_FIM_PESQUISA")), "divulgacao": data_iso(r.get("DT_DIVULGACAO")),
                "entrevistados": int(r["QT_ENTREVISTADO"]) if (r.get("QT_ENTREVISTADO") or "").isdigit() else None, "valor": valor(r.get("VR_PESQUISA")),
                "propria": (r.get("ST_PESQUISA_PROPRIA") or "").upper() == "S", "cargos": r.get("DS_CARGO"),
                "contratantes": sorted({pessoa(c.get("NR_CPF_CNPJ_CONTRATANTE"), c.get("NM_CONTRATANTE")) for c in cs}),
                "pagantes": sorted({pessoa(p.get("NR_CPF_CNPJ_PAGANTE"), p.get("NM_PAGANTE")) for p in ps}),
                "origem_recurso": sorted({limpo(x.get("DS_ORIGEM_RECURSO")) for x in cs + ps} - {""}),
                "segundo_turno": bool(data_iso(r.get("DT_INICIO_PESQUISA")) and data_iso(r.get("DT_INICIO_PESQUISA")) > PRIMEIRO_TURNO)}

    todos = [item(r) for r in pres]
    todos.sort(key=lambda x: (x["divulgacao"] or "", x["empresa"] or ""), reverse=True)
    itens = [x for x in todos if x["abrangencia"] == "nacional"]
    seg = [x for x in itens if x["segundo_turno"]]
    ents = [x["entrevistados"] for x in itens if x["entrevistados"]]
    vals = [x["valor"] for x in itens if x["valor"]]
    mes = Counter((x["divulgacao"] or "?")[:7] for x in itens)
    emp = Counter(x["empresa"] for x in itens)
    contratantes = Counter(c for x in itens for c in x["contratantes"])
    origem = Counter(o for x in itens for o in x["origem_recurso"])
    ab = Counter(x["abrangencia"] for x in todos)
    ab2 = Counter(x["abrangencia"] for x in todos if x["segundo_turno"])
    return {"gerado_pelo_tse": data_iso(pesq[0].get("DT_GERACAO")) if pesq else None, "registradas_total": len(pesq),
            "com_presidente": len(pres), "ue_registro_presidente": Counter(r.get("SG_UE") for r in pres).most_common(),
            "abrangencia_presidente": ab.most_common(), "abrangencia_presidente_2t": ab2.most_common(),
            "estaduais_por_uf": Counter(x["uf_amostra"] or "UF não identificada" for x in todos if x["abrangencia"] == "estadual").most_common(),
            "por_cargo_registro": [[k, n] for k, n in Counter(limpo(r.get("DS_CARGO")) or "não informado" for r in pesq).most_common(12)],
            "nacionais": {"total": len(itens), "segundo_turno": len(seg), "empresas": len(emp), "por_mes_divulgacao": sorted(mes.items()),
                          "por_empresa": emp.most_common(25), "contratantes_top": contratantes.most_common(20), "origem_recurso": origem.most_common(),
                          "proprias": sum(x["propria"] for x in itens), "entrevistados_mediana": statistics.median(ents) if ents else None,
                          "entrevistados_max": max(ents) if ents else None, "valor_total": round(sum(vals), 2) if vals else None,
                          "valor_mediana": statistics.median(vals) if vals else None, "com_valor": len(vals)},
            "lista_presidente": todos}


def main(argv=None) -> int:
    root = Path(".")
    agora = now_utc()
    interno = os.environ.get("ODI_INTERNO_DIR")
    priv = Path(interno) / "tse" if interno else None
    if priv:
        priv.mkdir(parents=True, exist_ok=True)
    erros, rc = [], 0
    pd_ = root / "data/tse/denuncias"
    pd_.mkdir(parents=True, exist_ok=True)
    try:
        txt, rows = ler_brasil(baixar(ARQ_DEN))
        d = {"schema_version": 1, "coletado_em_utc": agora, "fonte": FONTE_DEN, "arquivo": BASE + ARQ_DEN, **resumo_denuncias(rows),
             "nota": "Denúncias registradas pelo eleitor no Pardal (app ou site do TSE), como o TSE publica. Denúncia não é irregularidade "
                     "comprovada: a situação mostra se virou petição no PJe ou foi baixada. O arquivo não traz a data de cada denúncia; "
                     "a série no tempo é a soma acumulada lida pelo Atlas a cada coleta."}
        d["historico"] = historico(pd_ / "historico.csv", d)
        (pd_ / "resumo.json").write_text(json.dumps(d, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
        if priv:
            with gzip.open(priv / "denuncia_2026_BRASIL.csv.gz", "wt", encoding="utf-8") as f:
                f.write(txt)
        print(f"denúncias: {d['total']} (TSE {d['gerado_pelo_tse']} {d['hora_geracao_tse']}) · presidente {d['presidente']['total']} · "
              f"digitais {d['digitais']['total']} · peticionadas {d['peticionadas_pje']}")
    except Exception as e:  # noqa: BLE001
        erros.append(f"denúncias: {type(e).__name__}: {str(e)[:200]}")
        rc = 1
    pp = root / "data/tse/pesquisas"
    pp.mkdir(parents=True, exist_ok=True)
    try:
        lidos = {k: ler_brasil(baixar(v)) for k, v in ARQ_PESQ.items()}
        p = {"schema_version": 1, "coletado_em_utc": agora, "fonte": FONTE_PESQ, "arquivos": [BASE + v for v in ARQ_PESQ.values()],
             **resumo_pesquisas(lidos["pesquisa"][1], lidos["contratante"][1], lidos["pagante"][1]),
             "referencia_agregador": {"nome": "PollingData · PDVoto (agregador de pesquisas)",
                                      "url": "https://flex.pollingdata.com.br/pdvoto/2026/presidente/br/t2_flavio-lula",
                                      "nota": "Referência externa para a intenção de voto agregada. O Atlas não reproduz as estimativas do "
                                              "agregador (produto comercial, todos os direitos reservados)."},
             "nota": "Registro obrigatório no TSE (Res. TSE nº 23.600/2019). O registro traz quem fez, quem pagou, quando, quantas entrevistas "
                     "e quanto custou; não traz o resultado. Pesquisas nacionais = registro com abrangência Brasil (UE = BR) que inclui "
                     "o cargo de presidente. Contratante ou pagante pessoa física aparece sem nome."}
        (pp / "resumo.json").write_text(json.dumps(p, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
        if priv:
            for k, (txt, _) in lidos.items():
                with gzip.open(priv / f"{k}_2026_BRASIL.csv.gz", "wt", encoding="utf-8") as f:
                    f.write(txt)
        n = p["nacionais"]
        print(f"pesquisas: {p['registradas_total']} registradas (TSE {p['gerado_pelo_tse']}) · com presidente {p['com_presidente']} · "
              f"abrangência {p['abrangencia_presidente']} · nacionais {n['total']} ({n['segundo_turno']} com campo após o 1º turno) · {n['empresas']} empresas")
    except Exception as e:  # noqa: BLE001
        erros.append(f"pesquisas: {type(e).__name__}: {str(e)[:200]}")
        rc = 1
    print(f"erros: {erros}")
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
