"""Auditoria da urna, 2º turno de 2026, com os dados abertos do próprio TSE (caso 022, "Relatório Pericial Independente").

Pedido do responsável (02/11/2026, 15h57: "pode aplicar"). Estrutura conferida pela sonda C19.298 (run 41506429826).

Lê, para cada UF, o arquivo mais recente do 2º turno de:
- Boletim de Urna (bweb_2t_<UF>_*.zip; dataset resultados-2026-boletim-de-urna): por seção, aptos, comparecimento,
  QT_ELEI_BIOM_SEM_HABILITACAO (eleitores liberados sem a biometria), abertura e encerramento da urna, votos para presidente.
- Correspondência efetivada (CEFT_2t_<UF>_*.zip; dataset resultados-2026-correspondencias-esperadas-e-efetivadas-2-turno):
  urna esperada × urna que de fato votou, origem do voto e TP_DIVERGENCIA.
Saída pública (só agregados; o BU é público e não tem dado pessoal): data/tse/auditoria_urna/2t/resumo.json e municipios.csv.
Grátis. Uso: python scripts/collect_tse_auditoria_urna.py [UF ...]
"""
from __future__ import annotations

import csv
import io
import json
import math
import re
import sys
import tempfile
import urllib.request
import zipfile
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from net import now_utc  # noqa: E402

csv.field_size_limit(10**9)
ROOT = Path(__file__).resolve().parents[1]
UA = {"User-Agent": "Mozilla/5.0 (ODI Atlas; pesquisa acadêmica)"}
CKAN = "https://dadosabertos.tse.jus.br/api/3/action/package_show?id="
PK_BU = "resultados-2026-boletim-de-urna"
PK_CE = "resultados-2026-correspondencias-esperadas-e-efetivadas-2-turno"
UFS = "AC AL AM AP BA CE DF ES GO MA MG MS MT PA PB PE PI PR RJ RN RO RR RS SC SE SP TO ZZ".split()
HORA = re.compile(r"(\d{1,2}):(\d{2})")


def get(u: str):
    return urllib.request.urlopen(urllib.request.Request(u, headers=UA), timeout=1800)


def recursos(pacote: str) -> list[dict]:
    return json.loads(get(CKAN + pacote).read())["result"]["resources"]


def mais_recente(res: list[dict], prefixo: str, uf: str) -> str | None:
    """URL do arquivo mais recente (pelo carimbo DDMMAAAAHHMM do nome) de um prefixo e UF."""
    rx = re.compile(rf"/{prefixo}_2t_{uf}_(\d{{2}})(\d{{2}})(\d{{4}})(\d{{4}})\.zip$", re.I)
    achados = []
    for r in res:
        m = rx.search(r.get("url") or "")
        if m:
            d, mth, a, hm = m.groups()
            achados.append((a + mth + d + hm, r["url"]))
    return max(achados)[1] if achados else None


def baixar(url: str, pasta: Path) -> zipfile.ZipFile:
    destino = pasta / url.rsplit("/", 1)[1]
    with get(url) as r, open(destino, "wb") as f:
        while b := r.read(1 << 20):
            f.write(b)
    return zipfile.ZipFile(destino)


def linhas(z: zipfile.ZipFile):
    for n in z.namelist():
        if n.lower().endswith(".csv"):
            with z.open(n) as f:
                yield from csv.DictReader(io.TextIOWrapper(f, encoding="latin-1", newline=""), delimiter=";")


def i(v) -> int:
    try:
        return int(v)
    except (TypeError, ValueError):
        return 0


def hora(v: str) -> float | None:
    m = HORA.search(v or "")
    return int(m.group(1)) + int(m.group(2)) / 60 if m else None


def ler_bu(z: zipfile.ZipFile) -> dict:
    """{(mun, zona, secao): dados da seção} só com o cargo Presidente."""
    sec: dict = {}
    for r in linhas(z):
        if (r.get("DS_CARGO_PERGUNTA") or "").strip().lower() != "presidente":
            continue
        k = (r["CD_MUNICIPIO"], r["NR_ZONA"], r["NR_SECAO"])
        s = sec.get(k)
        if s is None:
            s = sec[k] = {"uf": r["SG_UF"], "mun": r["CD_MUNICIPIO"], "nome": r["NM_MUNICIPIO"], "aptos": i(r["QT_APTOS"]),
                          "comp": i(r["QT_COMPARECIMENTO"]), "abst": i(r["QT_ABSTENCOES"]), "sem_bio": i(r.get("QT_ELEI_BIOM_SEM_HABILITACAO")),
                          "abre": hora(r.get("DT_ABERTURA")), "fecha": hora(r.get("DT_ENCERRAMENTO")), "votos": Counter(),
                          "agregadas": bool((r.get("DS_SECOES_AGREGADAS") or "").strip() not in ("", "#NULO#", "-1"))}
        s["votos"][r["NR_VOTAVEL"]] += i(r["QT_VOTOS"])
    return sec


def ler_ceft(z: zipfile.ZipFile) -> dict:
    c = Counter()
    for r in linhas(z):
        c["urnas"] += 1
        c["divergencia_" + ((r.get("TP_DIVERGENCIA") or "").strip() or "nenhuma")] += 1
        c["origem_" + ((r.get("DS_ORIGEM_VOTO") or "").strip() or "?")] += 1
        if (r.get("NR_URNA_EFETIVADA") or "") != (r.get("NR_URNA_ESPERADA") or ""):
            c["urna_trocada"] += 1
    return dict(c)


def pearson(xs: list[float], ys: list[float]) -> float | None:
    n = len(xs)
    if n < 3:
        return None
    mx, my = sum(xs) / n, sum(ys) / n
    sxy = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    sx = math.sqrt(sum((x - mx) ** 2 for x in xs))
    sy = math.sqrt(sum((y - my) ** 2 for y in ys))
    return round(sxy / (sx * sy), 3) if sx and sy else None


def agregar(secoes: list[dict]) -> dict:
    t = Counter()
    faixas = Counter()
    for s in secoes:
        t["secoes"] += 1
        t["aptos"] += s["aptos"]
        t["comparecimento"] += s["comp"]
        t["sem_biometria"] += s["sem_bio"]
        t["lula_13"] += s["votos"].get("13", 0)
        t["flavio_22"] += s["votos"].get("22", 0)
        t["brancos_95"] += s["votos"].get("95", 0)
        t["nulos_96"] += s["votos"].get("96", 0)
        f = s["fecha"]
        if f is None:
            faixas["sem horário"] += 1
        elif f < 17:
            faixas["antes das 17h"] += 1
        elif f < 17.5:
            faixas["17h00–17h29"] += 1
        elif f < 18:
            faixas["17h30–17h59"] += 1
        elif f < 19:
            faixas["18h00–18h59"] += 1
        else:
            faixas["19h ou depois"] += 1
    v = t["lula_13"] + t["flavio_22"]
    return {**t, "pct_sem_biometria_do_comparecimento": round(100 * t["sem_biometria"] / t["comparecimento"], 2) if t["comparecimento"] else None,
            "pct_lula_validos": round(100 * t["lula_13"] / v, 2) if v else None, "encerramento_das_secoes": dict(faixas)}


def main(argv: list[str]) -> int:
    ufs = [a.upper() for a in argv] or UFS
    agora = now_utc()
    rbu, rce = recursos(PK_BU), recursos(PK_CE)
    todas, ceft, fontes, faltam = [], {}, {"boletim_de_urna": {}, "correspondencia_efetivada": {}}, []
    with tempfile.TemporaryDirectory() as tmp:
        for uf in ufs:
            ubu, uce = mais_recente(rbu, "bweb", uf), mais_recente(rce, "CEFT", uf)
            if not ubu:
                faltam.append(f"{uf}: boletim de urna do 2º turno não listado no catálogo")
            else:
                z = baixar(ubu, Path(tmp))
                sec = ler_bu(z)
                todas += list(sec.values())
                fontes["boletim_de_urna"][uf] = ubu
                Path(z.filename).unlink()
                print(f"{uf}: {len(sec)} seções no BU")
            if not uce:
                faltam.append(f"{uf}: correspondência efetivada do 2º turno não listada")
            else:
                z = baixar(uce, Path(tmp))
                ceft[uf] = ler_ceft(z)
                fontes["correspondencia_efetivada"][uf] = uce
                Path(z.filename).unlink()
    por_uf = defaultdict(list)
    por_mun = defaultdict(list)
    for s in todas:
        por_uf[s["uf"]].append(s)
        por_mun[(s["uf"], s["mun"], s["nome"])].append(s)
    br = [s for s in todas if s["uf"] != "ZZ"]
    xs = [100 * s["sem_bio"] / s["comp"] for s in br if s["comp"]]
    ys = [100 * s["votos"].get("13", 0) / (s["votos"].get("13", 0) + s["votos"].get("22", 0)) if (s["votos"].get("13", 0) + s["votos"].get("22", 0)) else 0
          for s in br if s["comp"]]
    corr_uf = {}
    for uf, ss in por_uf.items():
        pares = [(100 * s["sem_bio"] / s["comp"], 100 * s["votos"].get("13", 0) / (s["votos"].get("13", 0) + s["votos"].get("22", 0)))
                 for s in ss if s["comp"] and (s["votos"].get("13", 0) + s["votos"].get("22", 0))]
        corr_uf[uf] = pearson([a for a, _ in pares], [b for _, b in pares])
    ce_tot = Counter()
    for c in ceft.values():
        ce_tot.update(c)
    out = {
        "schema_version": 1, "turno": 2, "gerado_em_utc": agora, "caso": "022",
        "pedido": "Responsável, 02/11/2026, 15h57: incorporar os dados de auditoria da urna do TSE (caso 022).",
        "fontes": {"boletim_de_urna": "https://dadosabertos.tse.jus.br/dataset/resultados-2026-boletim-de-urna",
                   "correspondencia": "https://dadosabertos.tse.jus.br/dataset/resultados-2026-correspondencias-esperadas-e-efetivadas-2-turno",
                   "arquivos": fontes},
        "universo": "todas as seções com boletim de urna publicado pelo TSE no 2º turno (cargo Presidente); é o universo, não amostra",
        "definicoes": {"sem_biometria": "QT_ELEI_BIOM_SEM_HABILITACAO: eleitores com biometria cadastrada liberados pelo mesário sem a digital (procedimento previsto quando a digital não é reconhecida)",
                       "encerramento": "horário de encerramento gravado no boletim (hora local da urna)",
                       "correlacao": "Pearson entre % sem biometria e % de Lula nos votos de Lula + Flávio, por seção; correlação não indica causa (a cobertura biométrica e o voto variam juntos por região, idade e escolaridade)"},
        "brasil_sem_exterior": agregar(br), "exterior_ZZ": agregar(por_uf.get("ZZ", [])),
        "correlacao_secao_sem_biometria_x_lula": {"brasil": pearson(xs, ys), "por_uf": corr_uf},
        "ufs": {uf: agregar(ss) for uf, ss in sorted(por_uf.items())},
        "correspondencia_efetivada": {"total": dict(ce_tot), "por_uf": ceft},
        "lacunas": faltam,
    }
    pasta = ROOT / "data/tse/auditoria_urna/2t"
    pasta.mkdir(parents=True, exist_ok=True)
    (pasta / "resumo.json").write_text(json.dumps(out, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    with open(pasta / "municipios.csv", "w", encoding="utf-8", newline="") as fh:
        w = csv.writer(fh, delimiter=";")
        w.writerow(["uf", "cd_municipio_tse", "municipio", "secoes", "aptos", "comparecimento", "sem_biometria", "pct_sem_biometria",
                    "lula_13", "flavio_22", "brancos", "nulos", "secoes_encerradas_17h30_ou_depois"])
        for (uf, mun, nome), ss in sorted(por_mun.items()):
            a = agregar(ss)
            tarde = sum(1 for s in ss if s["fecha"] is not None and s["fecha"] >= 17.5)
            w.writerow([uf, mun, nome, a["secoes"], a["aptos"], a["comparecimento"], a["sem_biometria"], a["pct_sem_biometria_do_comparecimento"],
                        a["lula_13"], a["flavio_22"], a["brancos_95"], a["nulos_96"], tarde])
    b = out["brasil_sem_exterior"]
    print(f"Brasil: {b['secoes']} seções · comparecimento {b['comparecimento']} · sem biometria {b['sem_biometria']} "
          f"({b['pct_sem_biometria_do_comparecimento']}%) · Lula {b['pct_lula_validos']}% · encerramento {b['encerramento_das_secoes']} · "
          f"correlação {out['correlacao_secao_sem_biometria_x_lula']['brasil']} · correspondência {dict(ce_tot)} · lacunas {len(faltam)}")
    return 0 if not faltam else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
