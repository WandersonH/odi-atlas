"""Sonda (só estrutura) dos conjuntos do TSE 2026 ainda não incorporados (pedido do responsável, 02/11/2026, 15h57: "pode aplicar").

Lista os recursos (nome, URL, tamanho por HEAD) de: correspondências esperadas e efetivadas (1º e 2º turno), boletim de urna,
arquivos transmitidos para totalização, logs das urnas (GEDAI), comparecimento e abstenção (perfil) e eleitorado (perfil).
Para os arquivos de até LIMITE_MB, abre o CSV e imprime colunas, nº de linhas e valores de colunas com poucos valores distintos.
Não imprime linha de dado (o log do Actions é público). Mesários: fora (decisão de 02/11/2026; ver CHANGELOG C19.298).
"""
import csv
import io
import json
import sys
import urllib.request
import zipfile
from collections import Counter

csv.field_size_limit(10**9)
UA = {"User-Agent": "Mozilla/5.0 (ODI Atlas; pesquisa acadêmica)"}
CKAN = "https://dadosabertos.tse.jus.br/api/3/action/package_show?id="
PACOTES = ["resultados-2026-correspondencias-esperadas-e-efetivadas-2-turno", "resultados-2026-correspondencias-esperadas-e-efetivadas-1-turno",
           "resultados-2026-boletim-de-urna", "resultados-2026-arquivos-transmitidos-para-totalizacao",
           "resultados-2026-logs-do-sistema-de-preparacao-das-urnas-eletronicas-gedai-2-turno", "comparecimento-e-abstencao-2026", "eleitorado-2026"]
LIMITE_MB = float(sys.argv[1]) if len(sys.argv) > 1 else 120
ABRIR = ("correspondencia", "perfil_comparecimento_abstencao_2026", "perfil_eleitorado_2026", "bweb_2t_AC", "bweb_2t_ac", "transmitid", "_AC")


def get(u, metodo="GET"):
    return urllib.request.urlopen(urllib.request.Request(u, headers=UA, method=metodo), timeout=600)


def estrutura(nome, txt):
    r = csv.reader(io.StringIO(txt), delimiter=";")
    cab = next(r)
    linhas = list(r)
    print(f"   -- {nome}: {len(linhas)} linhas; {len(cab)} colunas: {cab}")
    for i, c in enumerate(cab):
        cnt = Counter(l[i] for l in linhas if len(l) > i)
        if len(cnt) <= 12 and not c.startswith(("NM_", "NR_TITULO", "NR_CPF")):
            print(f"      {c}: {cnt.most_common(12)}")
        else:
            print(f"      {c}: {len(cnt)} distintos")


for p in PACOTES:
    print(f"== {p}")
    try:
        d = json.loads(get(CKAN + p).read())["result"]
    except Exception as e:  # noqa: BLE001
        print("   erro catálogo", type(e).__name__, e)
        continue
    print(f"   {d.get('title')} · modificado {d.get('metadata_modified')} · {len(d.get('resources', []))} recursos")
    for rs in d.get("resources", []):
        u = rs.get("url") or ""
        try:
            mb = int(get(u, "HEAD").headers.get("Content-Length") or 0) / 1e6
        except Exception as e:  # noqa: BLE001
            mb = -1
            print(f"   ! HEAD {u}: {type(e).__name__}")
        print(f"   recurso: {rs.get('name')} | {u} | {mb:.1f} MB | modificado {rs.get('last_modified') or rs.get('metadata_modified')}")
        if 0 < mb <= LIMITE_MB and u.lower().endswith(".zip") and any(k.lower() in u.lower() for k in ABRIR):
            try:
                z = zipfile.ZipFile(io.BytesIO(get(u).read()))
                nomes = z.namelist()
                print(f"   zip: {len(nomes)} arquivos: {nomes[:8]}")
                n = next((x for x in nomes if x.lower().endswith(".csv") and ("brasil" in x.lower() or "_br" in x.lower())), None) or \
                    next((x for x in nomes if x.lower().endswith(".csv")), None)
                if n:
                    estrutura(n, z.read(n).decode("latin-1"))
            except Exception as e:  # noqa: BLE001
                print(f"   erro ao abrir: {type(e).__name__} {e}")
sys.exit(0)
