#!/usr/bin/env python3
"""Diagnóstico grátis (02/11/2026): lê o esquema de entrada de atores do TikTok na Apify (GET, sem rodar ator, sem custo)
e lista os campos de data, ordenação e hashtag. Objetivo: achar como pedir só vídeos recentes por hashtag.
Uso: APIFY_TOKEN=... python scripts/diag_atores_tiktok.py ator1 ator2 ..."""
import json
import os
import re
import sys
import urllib.request

TOKEN = os.environ.get("APIFY_TOKEN", "")
CHAVE = re.compile(r"date|time|sort|order|recent|newest|oldest|since|until|period|range|hashtag|keyword|search|max|limit|result", re.I)

for ator in sys.argv[1:]:
    try:
        req = urllib.request.Request(f"https://api.apify.com/v2/acts/{ator}/builds/default", headers={"Authorization": f"Bearer {TOKEN}"})
        d = json.load(urllib.request.urlopen(req, timeout=60))["data"]
        sch = d.get("inputSchema")
        sch = json.loads(sch) if isinstance(sch, str) else (sch or {})
        props = sch.get("properties") or {}
        print(f"{ator}: build {d.get('buildNumber')} · {len(props)} campos")
        for k, v in props.items():
            if CHAVE.search(k) or CHAVE.search(str(v.get("title", ""))):
                print(f"  {k} [{v.get('type')}] {str(v.get('title',''))[:60]} | enum={v.get('enum')} | padrão={v.get('default', v.get('prefill'))} | {re.sub(r'<[^>]+>','',str(v.get('description','')))[:220]}")
    except Exception as e:  # noqa: BLE001
        print(f"{ator}: ⛔ {type(e).__name__}: {str(e)[:150]}")
