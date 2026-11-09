#!/usr/bin/env python3
"""Anonimiza, na árvore pública, tudo o que identifica uma pessoa protegida (caso 020: criança).

09/11/2026 (C19.371, pedido do responsável: "manteria anonimizado nome dele mais exibiria as redes").
Casos com `anonimizar_publico_regex` em data/config/casos.json têm os arquivos de texto de data/casos/<id>/ e
data/redes/gephi/<id>_* reescritos:
  - GEXF: nó cujo id ou rótulo casa com a expressão vira id `crianca_<n>` e rótulo "[referência à criança]"
    (o mesmo padrão do visualizador, build_redes_viewer.py); ligações seguem o novo id; atributos de texto
    recebem "[…]". Nós distintos continuam distintos (nada é fundido).
  - JSON, CSV e demais textos: cada ocorrência vira "[…]".
Os originais NÃO são descartados (regra 8): com --copia DIR, cada arquivo é copiado para DIR antes de mudar
(uso: DIR dentro do repositório privado). Nos workflows, scripts/commit_push.sh roda este script antes do
commit; o que entra no público já vem anonimizado e os originais seguem só no privado (coletor).

Uso: python scripts/anonimizar_publico.py [--copia DIR] [--verificar]
  --verificar: não muda nada; sai com código 1 se algum arquivo público ainda tiver ocorrência.
"""
from __future__ import annotations

import argparse
import glob
import json
import os
import re
import shutil
import sys
import xml.etree.ElementTree as ET

ROT = "[referência à criança]"
TROCA = "[…]"
TEXTO = (".json", ".csv", ".tsv", ".gexf", ".txt", ".md", ".html", ".xml")


def casos_protegidos(cfg: str = "data/config/casos.json") -> dict[str, re.Pattern]:
    d = json.load(open(cfg, encoding="utf-8"))
    d = d if isinstance(d, list) else d.get("casos", list(d.values()))
    return {str(c["id"]): re.compile(c["anonimizar_publico_regex"], re.I) for c in d if c.get("anonimizar_publico_regex")}


def arquivos(cid: str) -> list[str]:
    fs = glob.glob(f"data/casos/{cid}/**/*", recursive=True) + glob.glob(f"data/redes/gephi/{cid}_*")
    return sorted(f for f in fs if os.path.isfile(f) and f.lower().endswith(TEXTO))


def gexf(caminho: str, rx: re.Pattern) -> str | None:
    texto = open(caminho, encoding="utf-8", newline="").read()
    if not rx.search(texto):
        return None
    m = re.search(r'xmlns="([^"]+)"', texto)
    ns = m.group(1) if m else ""
    ET.register_namespace("", ns)
    for p, u in re.findall(r'xmlns:(\w+)="([^"]+)"', texto):
        ET.register_namespace(p, u)
    raiz = ET.fromstring(texto)
    q = (lambda t: f"{{{ns}}}{t}") if ns else (lambda t: t)
    novo, i = {}, 0
    for n in raiz.iter(q("node")):
        if rx.search(n.get("id", "")) or rx.search(n.get("label", "")):
            i += 1
            novo[n.get("id")] = f"crianca_{i}"
            n.set("id", novo[n.get("id")])
            n.set("label", ROT)
    for e in raiz.iter(q("edge")):
        for k in ("source", "target"):
            if e.get(k) in novo:
                e.set(k, novo[e.get(k)])
    for el in raiz.iter():
        for k, v in list(el.attrib.items()):
            if rx.search(v):
                el.set(k, rx.sub(TROCA, v))
        if el.text and rx.search(el.text):
            el.text = rx.sub(TROCA, el.text)
    saida = '<?xml version="1.0" encoding="UTF-8"?>\n' + ET.tostring(raiz, encoding="unicode")
    return saida


def texto_simples(caminho: str, rx: re.Pattern) -> str | None:
    t = open(caminho, encoding="utf-8", errors="strict", newline="").read()
    if caminho.endswith(".json"):
        # \uXXXX escondem acentos da expressão: normaliza para UTF-8 quando o JSON é válido
        try:
            obj = json.loads(t)
            if not rx.search(json.dumps(obj, ensure_ascii=False)):
                return None

            def anda(o):
                if isinstance(o, str):
                    return rx.sub(TROCA, o)
                if isinstance(o, list):
                    return [anda(x) for x in o]
                if isinstance(o, dict):
                    return {anda(k): anda(v) for k, v in o.items()}
                return o
            mi = re.match(r"\s*[\[{]\r?\n( +)", t)
            ind = len(mi.group(1)) if mi else None
            sep = (",", ":") if (ind is None and '":' in t[:400] and '": ' not in t[:400]) else None
            asc = "\\u00" in t
            return json.dumps(anda(obj), ensure_ascii=asc, indent=ind, separators=sep) + ("\n" if t.endswith("\n") else "")
        except ValueError:
            pass
    return rx.sub(TROCA, t) if rx.search(t) else None


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--copia")
    ap.add_argument("--verificar", action="store_true")
    a = ap.parse_args()
    falhas, mudados = [], 0
    for cid, rx in casos_protegidos().items():
        for f in arquivos(cid):
            try:
                if a.verificar:
                    if rx.search(open(f, encoding="utf-8", errors="ignore").read()):
                        falhas.append(f)
                    continue
                novo = gexf(f, rx) if f.endswith(".gexf") else texto_simples(f, rx)
                if novo is None:
                    continue
                if a.copia:
                    dst = os.path.join(a.copia, f)
                    os.makedirs(os.path.dirname(dst), exist_ok=True)
                    if not os.path.exists(dst):
                        shutil.copy2(f, dst)
                open(f, "w", encoding="utf-8", newline="").write(novo)
                mudados += 1
                if rx.search(novo):
                    falhas.append(f)
            except Exception as e:  # noqa: BLE001 — falha fechada: o commit não segue
                falhas.append(f"{f} ({e})")
    if a.verificar:
        print(f"anonimizar_publico: {len(falhas)} arquivo(s) com ocorrência")
    else:
        print(f"anonimizar_publico: {mudados} arquivo(s) anonimizado(s)")
    for f in falhas:
        print("  ⛔", f)
    return 1 if falhas else 0


if __name__ == "__main__":
    sys.exit(main())
