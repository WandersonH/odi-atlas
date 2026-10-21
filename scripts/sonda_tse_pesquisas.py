"""Sonda (só estrutura): cabeçalhos e contagens dos arquivos do TSE (Pardal e pesquisas 2026) e endereços de dados do PollingData.
Não imprime linhas: só nomes de colunas, nº de linhas, valores de colunas com até 25 valores distintos e nº de distintos das demais
(o log do Actions é público). Uso único para desenhar o coletor."""
import csv
import io
import re
import sys
import urllib.request
import zipfile
from collections import Counter

BASE = "https://cdn.tse.jus.br/estatistica/sead/odsele/"
ARQS = ["denuncia/denuncia_2026.zip", "pesquisa_eleitoral/pesquisa_eleitoral_2026.zip",
        "pesquisa_eleitoral/pesquisa_contratante_2026.zip", "pesquisa_eleitoral/pesquisa_pagante_2026.zip"]
csv.field_size_limit(10**9)


def get(u):
    return urllib.request.urlopen(urllib.request.Request(u, headers={"User-Agent": "Mozilla/5.0 (ODI Atlas)"}), timeout=180).read()


for a in ARQS:
    try:
        z = zipfile.ZipFile(io.BytesIO(get(BASE + a)))
    except Exception as e:  # noqa: BLE001
        print(f"{a}: ERRO {type(e).__name__} {e}")
        continue
    nomes = z.namelist()
    print(f"== {a}: {len(nomes)} arquivos: {nomes[:8]}")
    for n in [x for x in nomes if x.lower().endswith((".csv", ".txt"))][:1] + [x for x in nomes if "_BRASIL" in x.upper() or "_BR." in x.upper()][:1]:
        txt = z.read(n).decode("latin-1")
        r = list(csv.reader(io.StringIO(txt), delimiter=";"))
        cab, linhas = r[0], r[1:]
        print(f"-- {n}: {len(linhas)} linhas; colunas: {cab}")
        for i, c in enumerate(cab):
            cnt = Counter(l[i] for l in linhas if len(l) > i)
            if len(cnt) <= 25:
                print(f"   {c}: {cnt.most_common(25)}")
            else:
                ex = "" if re.search(r"NM_|NR_CPF|CNPJ|DS_|TX_|NOME|EMAIL|TEL|END", c, re.I) else f" ex. maiores: {[k for k, _ in cnt.most_common(3)]}"
                print(f"   {c}: {len(cnt)} distintos{ex}")

try:
    h = get("https://flex.pollingdata.com.br/pdvoto/2026/presidente/br/t2_flavio-lula").decode("utf-8", "replace")
    js = re.findall(r'src="([^"]+\.js)"', h)
    print("pollingdata scripts:", js[:10])
    for s in js[:6]:
        u = s if s.startswith("http") else "https://flex.pollingdata.com.br" + ("" if s.startswith("/") else "/") + s
        t = get(u).decode("utf-8", "replace")
        achados = sorted(set(re.findall(r'https?://[A-Za-z0-9./_-]*(?:api|json|data|firestore|supabase|amazonaws|storage)[A-Za-z0-9./_?=&-]*', t)))[:40]
        rel = sorted(set(re.findall(r'["\'](/(?:api|data)[A-Za-z0-9./_{}$-]*)["\']', t)))[:40]
        print(f"js {u} ({len(t)} bytes): urls {achados} rel {rel}")
except Exception as e:  # noqa: BLE001
    print(f"pollingdata ERRO {type(e).__name__} {e}")
sys.exit(0)
