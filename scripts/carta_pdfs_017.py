"""Caso 017: os três PDFs originais da carta (Poder360), com hash, metadados, credenciais de conteúdo (C2PA) e diferenças de texto.

Enviados pelo responsável em 02/11/2026, 19h33. O ambiente de trabalho não alcança static.poder360.com.br; roda no Actions.
Saídas: data/casos/017/midia/carta_v<N>.pdf (documento público de figura pública), carta_v<N>.txt (texto extraído) e
data/casos/017/pdfs.json (hash SHA-256, tamanho, páginas, Producer/Creator/datas, XMP, C2PA, diferenças entre versões).
Não interpreta: registra o que está no arquivo. Uso: python scripts/carta_pdfs_017.py
"""
from __future__ import annotations

import difflib
import hashlib
import json
import re
import subprocess
import sys
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from net import now_utc  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
MIDIA = ROOT / "data/casos/017/midia"
UA = {"User-Agent": "Mozilla/5.0 (ODI Atlas; pesquisa acadêmica)"}
VERSOES = [
    (1, "brasão \"Estados Unidos do Brazil\" + \"presidente eleito\"",
     "https://static.poder360.com.br/uploads/2026/10/discurso-de-flavio-bolsonaro-apos-fuga-do-brasil-com-brasao-brazil-28-outubro-2026.pdf"),
    (2, "brasão atual + \"presidente eleito\"",
     "https://static.poder360.com.br/uploads/2026/10/Discurso-de-Flavio-Bolsonaro-apos-fugir-para-os-Eua-28-out-2026.pdf"),
    (3, "\"líder do Brasil\"",
     "https://static.poder360.com.br/uploads/2026/10/Discuso-de-Flavio-como-22lider-do-Brasil22-28.out_.2026.pdf"),
]
CHAVES = [b"/Producer", b"/Creator", b"/CreationDate", b"/ModDate", b"/Author", b"/Title"]


def pdfinfo(p: Path) -> dict:
    try:
        out = subprocess.run(["pdfinfo", str(p)], capture_output=True, text=True, timeout=60).stdout
    except Exception:  # noqa: BLE001
        return {}
    return {k.strip(): v.strip() for k, v in (l.split(":", 1) for l in out.splitlines() if ":" in l)}


def texto(p: Path) -> str:
    try:
        return subprocess.run(["pdftotext", "-layout", str(p), "-"], capture_output=True, text=True, timeout=120).stdout
    except Exception:  # noqa: BLE001
        return ""


def metadados_brutos(b: bytes) -> dict:
    m = {}
    for k in CHAVES:
        vals = [v.decode("latin-1", "replace")[:200] for v in re.findall(re.escape(k) + rb"\s*\(([^)]*)\)", b)]
        if vals:
            m[k.decode()[1:]] = sorted(set(vals))
    i = b.find(b"<x:xmpmeta")
    xmp = b[i:b.find(b"</x:xmpmeta>", i) + 12].decode("latin-1", "replace") if i >= 0 else ""
    m["xmp_presente"] = bool(xmp)
    if xmp:
        for tag in ("xmp:CreatorTool", "pdf:Producer", "xmp:CreateDate", "xmp:ModifyDate", "dc:creator"):
            mm = re.search(rf"<{tag}>(.*?)</{tag}>", xmp, re.S) or re.search(rf'{tag}="([^"]*)"', xmp)
            if mm:
                m[tag] = re.sub(r"<[^>]+>", " ", mm.group(1)).strip()[:200]
        m["xmp_menciona"] = sorted({w for w in ("c2pa", "contentcredentials", "openai", "gpt", "chatgpt", "adobe", "word", "google", "canva", "pages")
                                    if w in xmp.lower()})
    low = b.lower()
    m["marcas_no_binario"] = sorted({w for w in ("c2pa", "jumbf", "openai", "gpt-6", "gpt-5", "chatgpt", "cai:", "contentauth") if w.encode() in low})
    return m


def c2pa(p: Path) -> dict:
    """Leitura das Content Credentials com a biblioteca c2pa (se instalada); senão, só a presença do manifesto."""
    try:
        import c2pa  # type: ignore
    except Exception as e:  # noqa: BLE001
        return {"biblioteca": f"⛔ c2pa não disponível ({type(e).__name__})"}
    try:
        r = c2pa.Reader(str(p))
        js = json.loads(r.json())
        act = js.get("active_manifest")
        man = (js.get("manifests") or {}).get(act) or {}
        return {"biblioteca": "c2pa-python", "manifesto_ativo": act, "claim_generator": man.get("claim_generator") or (man.get("claim_generator_info") or [{}])[0],
                "assinatura": (man.get("signature_info") or {}), "acoes": [a for ass in man.get("assertions", []) if "actions" in ass.get("label", "")
                                                                            for a in (ass.get("data") or {}).get("actions", [])][:10],
                "validacao": js.get("validation_status")}
    except Exception as e:  # noqa: BLE001
        return {"biblioteca": "c2pa-python", "erro": f"{type(e).__name__}: {str(e)[:200]}"}


def main() -> int:
    MIDIA.mkdir(parents=True, exist_ok=True)
    out = {"gerado_em_utc": now_utc(), "fonte_dos_arquivos": "Poder360 (links enviados pelo responsável em 02/11/2026, 19h33)", "versoes": []}
    textos = {}
    for n, marca, url in VERSOES:
        reg = {"n": n, "marca_segundo_a_imprensa": marca, "url": url}
        p = MIDIA / f"carta_v{n}.pdf"
        try:
            b = urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=120).read()
            p.write_bytes(b)
        except Exception as e:  # noqa: BLE001
            reg["erro"] = f"⛔ {type(e).__name__}: {str(e)[:150]}"
            out["versoes"].append(reg)
            continue
        reg.update(arquivo=str(p.relative_to(ROOT)), sha256=hashlib.sha256(b).hexdigest(), bytes=len(b))
        info = pdfinfo(p)
        reg["pdfinfo"] = {k: info[k] for k in ("Producer", "Creator", "CreationDate", "ModDate", "Pages", "Title", "Author", "PDF version", "Metadata Stream") if k in info}
        reg["metadados"] = metadados_brutos(b)
        reg["content_credentials"] = c2pa(p)
        t = texto(p)
        (MIDIA / f"carta_v{n}.txt").write_text(t, encoding="utf-8")
        textos[n] = t
        tl = t.lower()
        reg["texto"] = {"caracteres": len(t), "palavras": len(t.split()), "presidente_eleito": tl.count("presidente eleito"),
                        "lider_do_brasil": tl.count("líder do brasil") + tl.count("lider do brasil"), "brazil": tl.count("brazil"),
                        "fraude": tl.count("fraude"), "sha256_texto": hashlib.sha256(t.encode()).hexdigest()}
        out["versoes"].append(reg)
    out["diferencas"] = []
    ns = sorted(textos)
    for a, b_ in zip(ns, ns[1:]):
        la, lb = [l.strip() for l in textos[a].splitlines() if l.strip()], [l.strip() for l in textos[b_].splitlines() if l.strip()]
        d = [l for l in difflib.unified_diff(la, lb, lineterm="", n=0) if l[:1] in "+-" and l[:3] not in ("+++", "---")]
        out["diferencas"].append({"de": a, "para": b_, "linhas_removidas": sum(1 for l in d if l[0] == "-"), "linhas_acrescentadas": sum(1 for l in d if l[0] == "+"),
                                  "trechos": d[:40], "texto_identico": textos[a] == textos[b_]})
    out["nota"] = ("Content Credentials e metadados dizem qual ferramenta gerou ou exportou o arquivo, não quem escreveu o texto. "
                   "Os PDFs são a versão que o Poder360 hospeda; se o veículo regravou o arquivo, as credenciais originais podem ter sido perdidas.")
    (ROOT / "data/casos/017/pdfs.json").write_text(json.dumps(out, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    for v in out["versoes"]:
        print(v["n"], v.get("erro") or f"{v['bytes']} B · {v['pdfinfo']} · {v['metadados'].get('marcas_no_binario')} · xmp {v['metadados'].get('xmp_presente')} · cc {v['content_credentials'].get('claim_generator') or v['content_credentials'].get('biblioteca')} · {v['texto']}")
    for d in out["diferencas"]:
        print(f"v{d['de']}→v{d['para']}: -{d['linhas_removidas']} +{d['linhas_acrescentadas']} idêntico={d['texto_identico']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
