#!/usr/bin/env python3
"""Pesquisas eleitorais registradas no TSE (PesqEle) e denúncias do Pardal — dados abertos do TSE, 2026.

Fontes (pedido do responsável em 20/10/2026):
- https://dadosabertos.tse.jus.br/dataset/pesquisas-eleitorais-2026 (registro, contratantes, pagantes; CSV em ZIP)
- https://dadosabertos.tse.jus.br/dataset/denuncias-eleitorais (denúncias registradas no Pardal; CSV em ZIP)

O registro do PesqEle traz quem fez, quem pagou, amostra, período e valor — não traz os percentuais da pesquisa.
Notas fiscais, questionários e detalhamento por bairro são PDFs e não são baixados aqui.

Etapa P1 (origem): os CSVs brutos vão para o repositório privado (ODI_INTERNO_DIR/tse/); no público só o manifesto com
colunas, número de linhas e data de geração. Nenhuma linha de dado vai para o log (o log do Actions é público).
Uso: python scripts/collect_tse_pesquisas.py
"""
from __future__ import annotations

import csv
import gzip
import io
import json
import os
import sys
import urllib.request
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from net import now_utc  # noqa: E402

BASE = "https://cdn.tse.jus.br/estatistica/sead/odsele"
FONTES = {
    "pesquisa": f"{BASE}/pesquisa_eleitoral/pesquisa_eleitoral_2026.zip",
    "pesquisa_contratante": f"{BASE}/pesquisa_eleitoral/pesquisa_contratante_2026.zip",
    "pesquisa_pagante": f"{BASE}/pesquisa_eleitoral/pesquisa_pagante_2026.zip",
    "denuncia": f"{BASE}/denuncia/denuncia_2026.zip",
}
csv.field_size_limit(10**8)


def baixar(url: str) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (ODI Atlas, pesquisa acadêmica)"})
    with urllib.request.urlopen(req, timeout=300) as r:
        return r.read()


def ler_zip(dados: bytes) -> list[tuple[str, bytes]]:
    z = zipfile.ZipFile(io.BytesIO(dados))
    return [(n, z.read(n)) for n in z.namelist() if n.lower().endswith((".csv", ".txt"))]


def perfil_csv(nome: str, conteudo: bytes) -> dict:
    """Só estrutura: colunas, linhas e a data de geração (colunas DT_GERACAO/HH_GERACAO, padrão do TSE)."""
    txt = conteudo.decode("latin-1")
    r = csv.DictReader(io.StringIO(txt), delimiter=";")
    n, geracao = 0, set()
    for row in r:
        n += 1
        if row.get("DT_GERACAO"):
            geracao.add(f"{row['DT_GERACAO']} {row.get('HH_GERACAO') or ''}".strip())
    return {"arquivo": nome, "linhas": n, "colunas": r.fieldnames or [], "geracao": sorted(geracao)[-3:]}


def main(argv=None) -> int:
    interno = os.environ.get("ODI_INTERNO_DIR")
    pasta_priv = Path(interno) / "tse" if interno else None
    man = {"coletado_em_utc": now_utc(), "fontes": FONTES, "arquivos": {}, "erros": []}
    for chave, url in FONTES.items():
        try:
            dados = baixar(url)
        except Exception as e:  # noqa: BLE001
            man["erros"].append(f"{chave}: {type(e).__name__} {getattr(e, 'code', '')} {str(e)[:150]}")
            continue
        arqs = ler_zip(dados)
        man["arquivos"][chave] = {"bytes_zip": len(dados), "csvs": [perfil_csv(n, c) for n, c in arqs]}
        if pasta_priv:
            pasta_priv.mkdir(parents=True, exist_ok=True)
            for n, c in arqs:
                with gzip.open(pasta_priv / (Path(n).name + ".gz"), "wb") as f:
                    f.write(c)
        for p in man["arquivos"][chave]["csvs"]:
            print(f"{chave} · {p['arquivo']}: {p['linhas']} linhas · geração {p['geracao']} · colunas {p['colunas']}")
    if not pasta_priv:
        man["erros"].append("ODI_INTERNO_DIR ausente: bruto não gravado")
    pub = Path("data/tse")
    pub.mkdir(parents=True, exist_ok=True)
    (pub / "pesquisas_denuncias_manifesto.json").write_text(json.dumps(man, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"erros: {man['erros']}")
    return 0 if man["arquivos"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
