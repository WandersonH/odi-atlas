"""Rede compartilhada pelos coletores: GET com User-Agent, download com SHA-256
e correção da cadeia de certificados incompleta (caso dos servidores do IBGE).

Alguns servidores não enviam o certificado intermediário. Navegadores buscam esse
certificado sozinhos pelo endereço "CA Issuers" (AIA) gravado no certificado do
servidor; o Python não. `ssl_context_for(host)` faz essa busca uma vez, adiciona o
intermediário ao contexto e mantém a verificação ligada. Nada aqui desliga a
verificação de certificado.
"""
from __future__ import annotations

import datetime as dt
import hashlib
import http.cookiejar
import json
import os
import ssl
import tempfile
import urllib.parse
import urllib.request
from pathlib import Path

UA = "odi-atlas-coletor/1.0 (+https://github.com/WandersonH/odi-atlas)"
CHUNK = 1 << 20
_CTX: dict[str, ssl.SSLContext] = {}


def now_utc() -> str:
    return dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _aia_context(host: str) -> ssl.SSLContext:
    pem = ssl.get_server_certificate((host, 443))  # sem verificação: só para ler o AIA
    with tempfile.NamedTemporaryFile("w", suffix=".pem", delete=False) as f:
        f.write(pem)
        path = f.name
    try:
        info = ssl._ssl._test_decode_cert(path)  # noqa: SLF001 (decodifica o certificado em dict)
    finally:
        os.unlink(path)
    urls = info.get("caIssuers") or ()
    if not urls:
        raise ssl.SSLError(f"{host}: certificado sem endereço CA Issuers (AIA)")
    ctx = ssl.create_default_context()
    for u in urls:
        with urllib.request.urlopen(urllib.request.Request(u, headers={"User-Agent": UA}), timeout=30) as r:
            der = r.read()
        ctx.load_verify_locations(cadata=ssl.DER_cert_to_PEM_cert(der) if not der.startswith(b"-----") else der.decode())
    return ctx


def ssl_context_for(host: str) -> ssl.SSLContext | None:
    return _CTX.get(host)


def opener(cookies: http.cookiejar.CookieJar | None = None, host: str | None = None):
    handlers = []
    if cookies is not None:
        handlers.append(urllib.request.HTTPCookieProcessor(cookies))
    if host and host in _CTX:
        handlers.append(urllib.request.HTTPSHandler(context=_CTX[host]))
    return urllib.request.build_opener(*handlers)


def open_url(url: str, timeout: int = 120, cookies=None, headers: dict | None = None):
    """Abre a URL; se a verificação falhar por cadeia incompleta, busca o intermediário (AIA) e tenta de novo."""
    host = urllib.parse.urlparse(url).hostname
    req = urllib.request.Request(url, headers={"User-Agent": UA, **(headers or {})})
    try:
        return opener(cookies, host).open(req, timeout=timeout)
    except urllib.error.URLError as e:
        if "CERTIFICATE_VERIFY_FAILED" not in str(e) or host in _CTX:
            raise
        _CTX[host] = _aia_context(host)
        return opener(cookies, host).open(req, timeout=timeout)


def get_json(url: str, **kw):
    with open_url(url, **kw) as r:
        return json.load(r)


def download(url: str, dest: Path, timeout: int = 600) -> dict:
    """Baixa em streaming e devolve a ficha de proveniência (SHA-256, bytes, cabeçalhos)."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    h, size, started = hashlib.sha256(), 0, now_utc()
    with open_url(url, timeout=timeout) as r, open(dest, "wb") as f:
        headers = {k: r.headers.get(k) for k in ("Last-Modified", "ETag", "Content-Length", "Content-Type")}
        while True:
            b = r.read(CHUNK)
            if not b:
                break
            h.update(b)
            f.write(b)
            size += len(b)
    if headers.get("Content-Length") and int(headers["Content-Length"]) != size:
        raise IOError(f"download incompleto: {size} de {headers['Content-Length']} bytes")
    return {"url": url, "file": dest.name, "bytes": size, "sha256": h.hexdigest(),
            "http": headers, "started_at_utc": started, "finished_at_utc": now_utc()}


def sha256_file(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(CHUNK), b""):
            h.update(b)
    return h.hexdigest()


import urllib.error  # noqa: E402  (usado em open_url)
