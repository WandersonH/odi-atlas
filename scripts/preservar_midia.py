#!/usr/bin/env python3
"""Preserva cópias (vídeo e imagem) das publicações de Instagram e Facebook coletadas em um caso, antes que saiam do ar.

Pedido do responsável (30/10/2026, 00h08): "conseguimos pegar os 12 posts [da ação do MPT contra a Meta] e ver se temos eles
antes que saiam do ar" (a 77ª Vara do Trabalho de São Paulo mandou a Meta tirar do ar, em 24 h, as publicações indicadas pelo MPT).
A lista das publicações da ação não é pública; o Atlas guarda a mídia de TODAS as publicações do caso no período, para que as da
ação, quando forem conhecidas, possam ser conferidas.

Lê os brutos do privado (ODI_INTERNO_DIR/casos/<caso>/bruto_{instagram,facebook}_*.jsonl.gz), pega os endereços de mídia que a
coleta devolveu (os do Instagram e do Facebook são assinados e expiram em alguns dias: endereço vencido = ⛔ registrado),
baixa cada arquivo uma vez (SHA-256) e grava tudo no privado: ODI_INTERNO_DIR/casos/<caso>/preservacao/ (manifesto.json) e os
arquivos num pacote .tar por execução, que o workflow publica como anexo de uma release do repositório privado.
Grátis (só download). Público: data/casos/<caso>/preservacao.json (só contagens).
Uso: python scripts/preservar_midia.py --caso 014 [--min-curtidas 0] [--max 600]
"""
from __future__ import annotations

import gzip
import hashlib
import json
import os
import sys
import tarfile
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from collect_casos import norm  # noqa: E402
from net import now_utc  # noqa: E402

UA = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124 Safari/537.36"}


def midias(rede: str, x: dict) -> list[tuple[str, str]]:
    """[(tipo, url)] na ordem: vídeo primeiro, depois imagens."""
    out = []
    if rede == "instagram":
        if x.get("videoUrl"):
            out.append(("video", x["videoUrl"]))
        vv = x.get("video_versions") or []
        if vv and isinstance(vv, list) and isinstance(vv[0], dict) and vv[0].get("url"):
            out.append(("video", vv[0]["url"]))
        if x.get("displayUrl"):
            out.append(("imagem", x["displayUrl"]))
        iv = ((x.get("image_versions") or {}).get("items") if isinstance(x.get("image_versions"), dict) else x.get("image_versions")) or []
        if iv and isinstance(iv, list) and isinstance(iv[0], dict) and iv[0].get("url"):
            out.append(("imagem", iv[0]["url"]))
        for c in x.get("childPosts") or []:
            if isinstance(c, dict):
                if c.get("videoUrl"):
                    out.append(("video", c["videoUrl"]))
                elif c.get("displayUrl"):
                    out.append(("imagem", c["displayUrl"]))
    else:
        v = x.get("video")
        if isinstance(v, str) and v.startswith("http"):
            out.append(("video", v))
        for vf in x.get("video_files") or []:
            u = vf.get("video_hd_file") or vf.get("video_sd_file") if isinstance(vf, dict) else None
            if u:
                out.append(("video", u))
        im = x.get("image")
        if isinstance(im, dict) and im.get("uri"):
            out.append(("imagem", im["uri"]))
        elif isinstance(im, str) and im.startswith("http"):
            out.append(("imagem", im))
        if x.get("video_thumbnail"):
            out.append(("imagem", x["video_thumbnail"]))
    vistos, uniq = set(), []
    for t, u in out:
        if u not in vistos:
            vistos.add(u)
            uniq.append((t, u))
    return uniq


def baixar(url: str, dest: Path) -> dict:
    try:
        with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=90) as r, open(dest, "wb") as f:
            h, n = hashlib.sha256(), 0
            while True:
                b = r.read(1 << 20)
                if not b:
                    break
                h.update(b)
                f.write(b)
                n += len(b)
        return {"status": "ok", "bytes": n, "sha256": h.hexdigest()}
    except Exception as e:  # noqa: BLE001
        dest.unlink(missing_ok=True)
        code = getattr(e, "code", "")
        return {"status": f"⛔ {type(e).__name__} {code}".strip() + (" (endereço assinado vencido)" if code in (403, 410) else "")}


def main(argv=None) -> int:
    argv = sys.argv[1:] if argv is None else list(argv)
    caso = argv[argv.index("--caso") + 1] if "--caso" in argv else "014"
    minc = int(argv[argv.index("--min-curtidas") + 1]) if "--min-curtidas" in argv else 0
    maxn = int(argv[argv.index("--max") + 1]) if "--max" in argv else 600
    interno = os.environ.get("ODI_INTERNO_DIR")
    if not interno:
        print("⛔ ODI_INTERNO_DIR ausente")
        return 1
    cfg = next(c for c in json.loads(Path("data/config/casos.json").read_text(encoding="utf-8"))["casos"] if c["id"] == caso)
    priv = Path(interno) / "casos" / caso
    pres = priv / "preservacao"
    pres.mkdir(parents=True, exist_ok=True)
    man_f = pres / "manifesto.json"
    man = json.loads(man_f.read_text(encoding="utf-8")) if man_f.exists() else {"caso": caso, "itens": {}}
    # do bruto mais novo para o mais antigo: endereços mais novos têm mais chance de ainda valer
    posts = {}
    for f in sorted(list(priv.glob("bruto_instagram_*.jsonl.gz")) + list(priv.glob("bruto_facebook_*.jsonl.gz")), key=lambda p: p.name.split("_")[-1], reverse=True):
        rede = f.name.split("_")[1]
        for linha in gzip.open(f, "rt", encoding="utf-8"):
            x = json.loads(linha)
            try:
                r = norm(rede, x, x.get("_termo") or "", "")
            except ValueError:
                continue
            if not r or (r.get("publicado_em") or "")[:10] < cfg["desde"]:
                continue
            k = f"{rede}:{r['item_id']}"
            if k in posts:
                continue
            curt = int(r["curtidas"]) if str(r.get("curtidas") or "").isdigit() else 0
            if curt < minc:
                continue
            posts[k] = {"rede": rede, "url": r["url"], "conta": r["conta"], "publicado_em": r["publicado_em"], "curtidas": curt,
                        "visualizacoes": r.get("visualizacoes"), "texto": (r.get("texto") or "")[:500], "midias": midias(rede, x), "bruto": f.name}
    ordem = sorted(posts.items(), key=lambda kv: -kv[1]["curtidas"])
    agora = now_utc()
    lote = pres / f"lote_{agora.replace(':', '').replace('-', '')}"
    lote.mkdir(parents=True, exist_ok=True)
    feitos = 0
    for k, p in ordem:
        reg = man["itens"].get(k)
        if reg and any(m.get("status") == "ok" for m in reg.get("arquivos", [])):
            continue  # já preservado
        if feitos >= maxn:
            break
        feitos += 1
        arquivos = []
        for i, (tipo, u) in enumerate(p["midias"]):
            ext = ".mp4" if tipo == "video" else ".jpg"
            nome = f"{k.replace(':', '_')}_{i + 1}{ext}"
            res = baixar(u, lote / nome)
            arquivos.append({"tipo": tipo, "arquivo": nome if res["status"] == "ok" else None, "lote": lote.name, **res})
        man["itens"][k] = {k2: v for k2, v in p.items() if k2 != "midias"} | {"tentado_em_utc": agora, "arquivos": arquivos,
                                                                            "sem_midia_no_bruto": not p["midias"]}
    pacote = None
    if any(lote.iterdir()):
        pacote = pres / f"{lote.name}.tar"
        with tarfile.open(pacote, "w") as t:
            t.add(lote, arcname=lote.name)
    for f in lote.iterdir():
        f.unlink()
    lote.rmdir()
    ok = sum(1 for v in man["itens"].values() if any(m.get("status") == "ok" for m in v["arquivos"]))
    man.update(atualizado_em_utc=agora, posts_no_periodo=len(posts), preservados=ok,
               vencidos=sum(1 for v in man["itens"].values() if v["arquivos"] and not any(m.get("status") == "ok" for m in v["arquivos"])),
               sem_midia=sum(1 for v in man["itens"].values() if v.get("sem_midia_no_bruto")))
    man_f.write_text(json.dumps(man, ensure_ascii=False, indent=1), encoding="utf-8")
    pub = {"caso": caso, "atualizado_em_utc": agora, "pedido": "Responsável em 30/10/2026, 00h08: \"ver se temos eles [os posts da ação do MPT] antes que saiam do ar\"",
           "posts_instagram_facebook_no_periodo": len(posts), "com_copia_guardada": ok, "endereco_vencido_ou_erro": man["vencidos"], "sem_midia_no_bruto": man["sem_midia"],
           "onde": "repositório privado (arquivos de pessoas comuns não são publicados)",
           "nota": "A lista das publicações da ação do MPT contra a Meta não é pública; o Atlas guarda a mídia de todas as publicações do caso para conferência posterior."}
    Path("data/casos", caso).mkdir(parents=True, exist_ok=True)
    (Path("data/casos") / caso / "preservacao.json").write_text(json.dumps(pub, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"caso {caso} preservação: {len(posts)} posts IG/FB no período · tentados nesta execução {feitos} · com cópia {ok} · vencidos/erro {man['vencidos']} · "
          f"sem mídia no bruto {man['sem_midia']} · pacote {pacote.name if pacote else '—'} ({pacote.stat().st_size if pacote else 0} bytes)")
    if pacote:
        Path(os.environ.get("GITHUB_OUTPUT", "/dev/null")).open("a").write(f"pacote={pacote}\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
