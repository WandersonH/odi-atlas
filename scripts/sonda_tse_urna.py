"""Sonda (só estrutura) para a alienação eleitoral e os dados processuais (pedido de 22/10/2026, 01h26).

- Busca no catálogo do TSE (CKAN) o conjunto de locais de votação de 2026 (coordenadas) e tenta o endereço de costume.
- Tamanho (HEAD) dos boletins de urna do 1º turno por UF.
- Boletim de urna do AC (o menor): colunas, nº de linhas, cargos, valores de NR_VOTAVEL 95/96 e campos de aptos/comparecimento/abstenção.
- Processual 2026: colunas e contagens de colunas com poucos valores; na tabela de partes, só colunas e nº de linhas.
A saída vai para o repositório privado (o log do Actions é público). Nenhuma linha de dado pessoal é impressa.
"""
import csv
import io
import json
import sys
import urllib.parse
import urllib.request
import zipfile
from collections import Counter

csv.field_size_limit(10**9)
UA = {"User-Agent": "Mozilla/5.0 (ODI Atlas; pesquisa acadêmica)"}
BU = "https://cdn.tse.jus.br/estatistica/sead/eleicoes/eleicoes2026/buweb/bweb_1t_{uf}_051020261403.zip"
UFS = "AC AL AM AP BA CE DF ES GO MA MG MS MT PA PB PE PI PR RJ RN RO RR RS SC SE SP TO ZZ".split()
PROC = ["processo_eleitoral_2026", "processos_eleitorais_assuntos_2026", "processos_eleitorais_decisoes_2026", "processos_eleitorais_partes_2026",
        "recursos_eleitorais_2026"]


def get(u, metodo="GET"):
    return urllib.request.urlopen(urllib.request.Request(u, headers=UA, method=metodo), timeout=600)


def resumo(nome, txt, sensivel=False):
    r = csv.reader(io.StringIO(txt), delimiter=";")
    cab = next(r)
    linhas = list(r)
    print(f"-- {nome}: {len(linhas)} linhas; colunas: {cab}")
    if sensivel:
        return cab, linhas
    for i, c in enumerate(cab):
        cnt = Counter(l[i] for l in linhas if len(l) > i)
        if len(cnt) <= 30:
            print(f"   {c}: {cnt.most_common(30)}")
        else:
            print(f"   {c}: {len(cnt)} distintos")
    return cab, linhas


print("== catálogo: locais de votação")
for q in ("local de votação 2026", "eleitorado 2026"):
    try:
        d = json.loads(get("https://dadosabertos.tse.jus.br/api/3/action/package_search?rows=10&q=" + urllib.parse.quote(q)).read())
        for p in d["result"]["results"]:
            print(" pacote:", p["name"], "|", p["title"])
            for rs in p.get("resources", []):
                if any(k in (rs.get("name", "") + rs.get("url", "")).lower() for k in ("local", "secao", "seção", "perfil_eleitor_secao")):
                    print("    recurso:", rs.get("name"), rs.get("url"))
    except Exception as e:  # noqa: BLE001
        print(" erro catálogo", q, type(e).__name__, e)
for u in ("https://cdn.tse.jus.br/estatistica/sead/odsele/eleitorado_locais_votacao/eleitorado_local_votacao_2026.zip",):
    try:
        z = zipfile.ZipFile(io.BytesIO(get(u).read()))
        print("local de votação:", u, z.namelist()[:6])
        n = next(x for x in z.namelist() if x.lower().endswith(".csv"))
        cab, linhas = resumo(n, z.read(n).decode("latin-1"), sensivel=True)
        for c in ("NR_LATITUDE", "NR_LONGITUDE", "SG_UF", "NM_MUNICIPIO", "NR_ZONA", "NR_SECAO", "NR_LOCAL_VOTACAO", "QT_ELEITOR_SECAO", "QT_ELEITOR"):
            if c in cab:
                i = cab.index(c)
                vals = [l[i] for l in linhas if len(l) > i]
                print(f"   {c}: {len(set(vals))} distintos; vazios/-1: {sum(1 for v in vals if v in ('', '-1', '#NULO#'))}")
    except Exception as e:  # noqa: BLE001
        print("local de votação: erro", u, type(e).__name__, e)

print("== boletins de urna, 1º turno (tamanho)")
tot = 0
for uf in UFS:
    try:
        n = int(get(BU.format(uf=uf), "HEAD").headers.get("Content-Length") or 0)
        tot += n
        print(f" {uf}: {n / 1e6:.1f} MB")
    except Exception as e:  # noqa: BLE001
        print(f" {uf}: erro {type(e).__name__} {e}")
print(f" total: {tot / 1e9:.2f} GB")

print("== boletim de urna AC")
z = zipfile.ZipFile(io.BytesIO(get(BU.format(uf="AC")).read()))
print(z.namelist())
n = next(x for x in z.namelist() if x.lower().endswith(".csv"))
cab, linhas = resumo(n, z.read(n).decode("latin-1"), sensivel=True)
ix = {c: i for i, c in enumerate(cab)}
for c in ("DS_CARGO_PERGUNTA", "NR_TURNO", "DS_TIPO_VOTAVEL", "CD_TIPO_URNA", "DS_TIPO_URNA", "DS_ORIGEM_VOTO"):
    if c in ix:
        print(f"   {c}: {Counter(l[ix[c]] for l in linhas).most_common(15)}")
for c in ("NR_VOTAVEL", "NM_VOTAVEL"):
    if c in ix:
        print(f"   {c} (95/96/97 e nomes 'branco/nulo'): {Counter(l[ix[c]] for l in linhas if l[ix['NR_VOTAVEL']] in ('95', '96', '97')).most_common(6)}")
for c in ("QT_APTOS", "QT_COMPARECIMENTO", "QT_ABSTENCOES", "QT_VOTOS", "NR_SECAO", "NR_ZONA", "CD_MUNICIPIO", "NR_LOCAL_VOTACAO", "NR_URNA_EFETIVADA"):
    print(f"   {c}: {'presente' if c in ix else 'ausente'}")
sec = {(l[ix["CD_MUNICIPIO"]], l[ix["NR_ZONA"]], l[ix["NR_SECAO"]]) for l in linhas} if all(k in ix for k in ("CD_MUNICIPIO", "NR_ZONA", "NR_SECAO")) else set()
print(f"   seções distintas no AC: {len(sec)}")

print("== processual 2026")
for p in PROC:
    try:
        z = zipfile.ZipFile(io.BytesIO(get(f"https://cdn.tse.jus.br/estatistica/sead/odsele/processual/{p}.zip").read()))
        n = next((x for x in z.namelist() if "BRASIL" in x.upper()), None) or next(x for x in z.namelist() if x.lower().endswith(".csv"))
        print(f" {p}: {len(z.namelist())} arquivos; lendo {n}")
        resumo(n, z.read(n).decode("latin-1"), sensivel="partes" in p)
    except Exception as e:  # noqa: BLE001
        print(f" {p}: erro {type(e).__name__} {e}")
sys.exit(0)
