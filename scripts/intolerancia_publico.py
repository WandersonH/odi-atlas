"""Arquivos públicos para conferir a triagem de intolerância de um caso (pedido do responsável, 02/11/2026, 15h19:
"queria que intolerância já tivesse disponível pra pessoa baixar o arquivo e conferir como fizemos com todo resto").

Lê, do repositório privado, casos/<id>/intolerancia/escores.csv.gz (saída de scripts/intolerancia.py) e os itens do caso,
e grava no público:
- data/casos/<id>/intolerancia_escores.csv: uma linha por texto lido, com rede, tipo, dia e o escore de cada rótulo de
  cada modelo, mais a marcação pelo limiar. SEM texto, SEM id da publicação e SEM conta (regra do projeto: texto e autor de
  pessoa comum só no privado). Dá para refazer todas as contagens e testar outro limiar.
- data/casos/<id>/intolerancia_resumo.csv: a tabela da página (modelo × rede × rótulo: lidos, marcados, %).
E acrescenta em data/casos/<id>/intolerancia.json a chave "arquivos" com os dois caminhos.

Não roda modelo nenhum: só reorganiza o que já foi calculado. Uso: python scripts/intolerancia_publico.py --caso 014 [--caso 021 ...]
"""
from __future__ import annotations

import csv
import gzip
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(Path(__file__).resolve().parent))
from intolerancia import LIMIAR, ler_textos, positivo  # noqa: E402


def publicar(caso: str, priv: Path, pub_dir: Path) -> dict:
    esc_p = priv / "intolerancia" / "escores.csv.gz"
    js_p = pub_dir / "intolerancia.json"
    if not esc_p.exists() or not js_p.exists():
        return {"caso": caso, "erro": "⛔ sem escores no privado ou sem intolerancia.json: rode scripts/intolerancia.py antes"}
    res = json.loads(js_p.read_text(encoding="utf-8"))
    meta = {}
    for r in ler_textos(priv):
        meta.setdefault(r["id"], (r["tipo"], r["dia"]))
    linhas = list(csv.DictReader(gzip.open(esc_p, "rt", encoding="utf-8"), delimiter=";"))
    cols = [c for c in (linhas[0].keys() if linhas else []) if ":" in c]
    modelos = sorted({c.split(":", 1)[0] for c in cols})
    sinal = {m: [c for c in cols if c.startswith(m + ":") and positivo(c.split(":", 1)[1])] for m in modelos}
    linhas.sort(key=lambda r: (r.get("rede") or "", meta.get(r["id"], ("", ""))[1], r["id"]))
    cab = ["n", "rede", "tipo", "dia"] + cols + [f"{m}:marcado(limiar {str(LIMIAR).replace('.', ',')})" for m in modelos]
    with open(pub_dir / "intolerancia_escores.csv", "w", encoding="utf-8", newline="") as fh:
        w = csv.writer(fh, delimiter=";")
        w.writerow(cab)
        for i, r in enumerate(linhas, 1):
            tipo, dia = meta.get(r["id"], ("", ""))
            marc = ["s" if any(float(r[c] or 0) >= LIMIAR for c in sinal[m]) else "n" for m in modelos]
            w.writerow([i, r.get("rede", ""), tipo, dia] + [r[c] for c in cols] + marc)
    with open(pub_dir / "intolerancia_resumo.csv", "w", encoding="utf-8", newline="") as fh:
        w = csv.writer(fh, delimiter=";")
        w.writerow(["caso", "modelo", "id_do_modelo", "rede", "rotulo", "lidos", "marcados", "pct"])
        for nome, m in (res.get("modelos") or {}).items():
            if "total" not in m:
                continue
            w.writerow([caso, nome, m["modelo"], "todas", "algum rótulo", m["total"]["lidos"], m["total"]["sinalizados"], m["total"]["pct"]])
            for rede, t in m["por_rede"].items():
                w.writerow([caso, nome, m["modelo"], rede, "algum rótulo", t["lidos"], t["sinalizados_algum_rotulo"], t["pct_algum"]])
                for rot, v in t["por_rotulo"].items():
                    w.writerow([caso, nome, m["modelo"], rede, rot, t["lidos"], v["n"], v["pct"]])
    res["arquivos"] = {
        "escores": f"data/casos/{caso}/intolerancia_escores.csv",
        "resumo": f"data/casos/{caso}/intolerancia_resumo.csv",
        "linhas_escores": len(linhas),
        "nota": "Escores por texto sem texto, sem id e sem conta (só no repositório privado). Separador ';'. "
                "A coluna 'marcado' aplica o limiar a qualquer rótulo de sinal do modelo; refazer a contagem por rede reproduz a tabela.",
    }
    js_p.write_text(json.dumps(res, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    return {"caso": caso, "linhas": len(linhas), "sem_meta": sum(1 for r in linhas if r["id"] not in meta)}


def main(argv: list[str]) -> int:
    casos = [argv[i + 1] for i, a in enumerate(argv) if a == "--caso"]
    interno = os.environ.get("ODI_INTERNO_DIR")
    if not interno:
        print("⛔ ODI_INTERNO_DIR não definido")
        return 1
    rc = 0
    for c in casos:
        r = publicar(c, Path(interno) / "casos" / c, ROOT / "data/casos" / c)
        print(r)
        rc |= 1 if "erro" in r else 0
    return rc


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
