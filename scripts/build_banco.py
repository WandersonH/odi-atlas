#!/usr/bin/env python3
"""Banco DuckDB do Atlas: tudo o que foi coletado, num arquivo consultável por SQL.

Pedido do responsável (combinado no início do projeto, tarefa "Banco DuckDB com tudo que já temos"; cobrado em
04/11/2026, 23h45 e 05/11/2026, 00h20: "monta esse banco"). Nada é apagado nem alterado nos repositórios: o banco é
refeito do zero a partir dos arquivos a cada execução.

Dois arquivos:
- público  (`--publico`): só `data/` do repositório público (agregados e o que já é público por regra);
- completo (`--completo`): o público + o repositório privado (ODI_INTERNO_DIR), com texto e autor de pessoas comuns.
  Só para a equipe e pesquisadores aprovados; nunca vai para o repositório público.

Como os arquivos viram tabelas:
- Cada "família" de arquivos (mesmo caminho, mudando só o caso, a data ou o id da coleta) vira uma tabela:
  `casos/021/itens.csv.gz` e `casos/033/itens.csv.gz` → tabela `priv_casos_itens_csv`, com a coluna `_caso`.
- CSV e CSV.GZ → colunas do próprio arquivo (tipos inferidos; se a inferência falhar, tudo como texto).
- JSONL e JSONL.GZ (respostas brutas da Apify e coletores) → uma linha por registro, coluna `registro` (JSON).
- JSON → tabela única `<origem>_json_documentos`, um documento por arquivo, coluna `conteudo` (JSON).
- TXT, VTT, SRT, MD → tabela `<origem>_textos` (transcrições, corpus IRaMuTeQ), coluna `texto`.
- Imagens, vídeos, PDFs e GEXF (redes do Gephi, cujos nós e arestas já estão nas tabelas `*rede_nos*`/`*rede_arestas*`)
  ficam fora: só o caminho e o tamanho, na tabela `_arquivos_fora`.
Toda linha leva `_arquivo` (caminho de origem), `_caso` (quando o arquivo é de um caso) e `_data_no_nome` (data que
aparece no nome do arquivo ou da pasta, quando há; não é a data de publicação dos itens).
Tabela `_catalogo`: uma linha por tabela, com origem, família de caminhos, nº de arquivos, nº de linhas, bytes lidos,
se os tipos foram inferidos ou ficou tudo como texto, e erros. `_sobre`: quando e de quais commits o banco foi feito.

Universo × amostra (regra 9): o banco guarda o que o Atlas leu; o universo informado pelas plataformas está nos
manifestos (`*_manifesto*.json`, em `_json_documentos`) e nas páginas. O banco não estima universo.

Uso (com `--zip`, grava também o .zip para distribuição):
     python scripts/build_banco.py --publico data/banco/atlas_publico.duckdb
     ODI_INTERNO_DIR=... python scripts/build_banco.py --completo atlas_completo.duckdb
"""
from __future__ import annotations

import datetime as dt
import json
import os
import re
import subprocess
import sys
import time
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TABULARES = (".csv", ".csv.gz")
LINHAS_JSON = (".jsonl", ".jsonl.gz", ".ndjson")
DOCS_JSON = (".json", ".json.gz", ".geojson")
TEXTOS = (".txt", ".vtt", ".srt", ".md")  # 05/11/2026: GEXF (370 MB no público) fica fora; nós e arestas já estão nas tabelas *rede_nos* e *rede_arestas*
RX_DATA = re.compile(r"(\d{4}-\d{2}-\d{2})(?:T(\d{2})[:\-]?(\d{2})[:\-]?(\d{2})?Z?)?|(\d{4})(\d{2})(\d{2})T(\d{2})(\d{2})(\d{2})Z|(?<!\d)(20\d{2})(\d{2})(\d{2})(?!\d)")


def familia(rel: str) -> str:
    """Caminho sem o que muda entre coletas da mesma série (caso, data, id de run, id de vídeo)."""
    p = re.sub(r"(^|/)casos/\d{3}[a-z]?/", r"\1casos/<id>/", rel)
    p = re.sub(r"\d{4}-\d{2}-\d{2}T[\d:\-]+Z?|\d{8}T\d{6}Z|\d{4}-\d{2}-\d{2}|(?<!\d)20\d{6}(?!\d)", "<data>", p)
    p = re.sub(r"\brun_?\d+|\b\d{6,}\b", "<n>", p)
    p = re.sub(r"apify/[A-Za-z0-9]{17}", "apify/<run>", p)
    p = re.sub(r"_[A-Za-z0-9]{17}(\.jsonl)", r"_<run>\1", p)
    p = re.sub(r"(transcricoes|miniaturas|midia)/[^/]+$", r"\1/<item>", p)
    return p


def nome_tabela(origem: str, fam: str) -> str:
    base = re.sub(r"\.(csv|jsonl|ndjson)(\.gz)?$", lambda m: "_" + m.group(1), fam)
    base = re.sub(r"<[^>]+>", "", base)
    base = re.sub(r"[^0-9a-zA-Z]+", "_", base).strip("_").lower()
    base = re.sub(r"_+", "_", base.replace("/", "__"))
    return f"{origem}_{base}"[:120]


def caso_de(rel: str) -> str | None:
    m = re.search(r"(?:^|/)casos/(\d{3}[a-z]?)/", rel)
    return m.group(1) if m else None


def data_no_nome(rel: str) -> str | None:
    m = RX_DATA.search(rel)
    if not m:
        return None
    if m.group(1):
        return m.group(1) + (f"T{m.group(2)}:{m.group(3)}:{m.group(4) or '00'}Z" if m.group(2) else "")
    if m.group(5):
        return f"{m.group(5)}-{m.group(6)}-{m.group(7)}T{m.group(8)}:{m.group(9)}:{m.group(10)}Z"
    return f"{m.group(11)}-{m.group(12)}-{m.group(13)}"


def listar(raiz: Path, sub: str | None = None) -> list[Path]:
    base = raiz / sub if sub else raiz
    out = []
    for d, ds, fs in os.walk(base):
        ds[:] = [x for x in ds if x not in (".git", "node_modules", "__pycache__")]
        out += [Path(d) / f for f in fs]
    return sorted(out)


def sql_str(s: str) -> str:
    return "'" + s.replace("'", "''") + "'"


def carregar(con, origem: str, raiz: Path, arquivos: list[Path], catalogo: list[dict], log) -> None:
    grupos: dict[tuple[str, str], list[Path]] = defaultdict(list)
    textos, docs, fora = [], [], []
    for a in arquivos:
        rel = a.relative_to(raiz).as_posix()
        nome = a.name.lower()
        if nome.endswith(TABULARES):
            grupos[("csv", familia(rel))].append(a)
        elif nome.endswith(LINHAS_JSON):
            grupos[("jsonl", familia(rel))].append(a)
        elif nome.endswith(DOCS_JSON):
            docs.append(a)
        elif nome.endswith(TEXTOS):
            textos.append(a)
        else:
            fora.append(a)
    usados: set[str] = set()
    for (tipo, fam), fs in sorted(grupos.items()):
        tab = nome_tabela(origem, fam)
        if tab in usados:  # famílias diferentes com o mesmo nome curto (ex.: videos.csv e videos_<data>.csv): sufixo
            k = 2
            while f"{tab}_{k}" in usados:
                k += 1
            tab = f"{tab}_{k}"
        usados.add(tab)
        t0 = time.time()
        reg = {"tabela": tab, "origem": origem, "familia": fam, "tipo": tipo, "arquivos": len(fs),
               "bytes": sum(f.stat().st_size for f in fs), "tipos": None, "linhas": 0, "erros": []}
        partes = []
        for f in fs:
            rel = f.relative_to(raiz).as_posix()
            extra = (f"{sql_str(rel)} AS _arquivo, {sql_str(caso_de(rel)) if caso_de(rel) else 'NULL'}::VARCHAR AS _caso, "
                     f"{sql_str(data_no_nome(rel)) if data_no_nome(rel) else 'NULL'}::VARCHAR AS _data_no_nome")
            partes.append((f, extra))
        criado = False
        for f, extra in partes:
            if f.stat().st_size == 0:
                continue
            if tipo == "csv":
                fonte = None
                for modo in ("auto", "texto"):
                    try:
                        opts = "union_by_name=true, sample_size=20000, ignore_errors=false" if modo == "auto" else "all_varchar=true, ignore_errors=true, null_padding=true, parallel=false"
                        fonte = f"SELECT {extra}, * FROM read_csv({sql_str(str(f))}, {opts})"
                        con.execute(f"CREATE TEMP TABLE _t AS {fonte}")
                        reg["tipos"] = reg["tipos"] if reg["tipos"] == "texto" else ("inferidos" if modo == "auto" else "texto")
                        break
                    except Exception as e:  # noqa: BLE001
                        con.execute("DROP TABLE IF EXISTS _t")
                        if modo == "texto":
                            reg["erros"].append(f"{f.name}: {str(e)[:160]}")
                            fonte = None
                if fonte is None:
                    continue
            else:
                try:
                    con.execute(f"CREATE TEMP TABLE _t AS SELECT {extra}, json AS registro FROM read_ndjson_objects({sql_str(str(f))}, ignore_errors=true)")
                except Exception as e:  # noqa: BLE001
                    con.execute("DROP TABLE IF EXISTS _t")
                    reg["erros"].append(f"{f.name}: {str(e)[:160]}")
                    continue
            try:
                if not criado:
                    con.execute(f'CREATE TABLE "{tab}" AS SELECT * FROM _t')
                    criado = True
                else:
                    con.execute(f'INSERT INTO "{tab}" BY NAME SELECT * FROM _t')
            except Exception:  # noqa: BLE001  colunas novas ou tipos diferentes entre coletas: amplia a tabela
                cols_novas = con.execute("SELECT column_name, column_type FROM (DESCRIBE _t)").fetchall()
                exist = {c for c, in con.execute(f"SELECT column_name FROM (DESCRIBE \"{tab}\")").fetchall()}
                for c, _ in cols_novas:
                    if c not in exist:
                        con.execute(f'ALTER TABLE "{tab}" ADD COLUMN "{c}" VARCHAR')
                for c, ty in con.execute(f'SELECT column_name, column_type FROM (DESCRIBE "{tab}")').fetchall():
                    if ty != "VARCHAR" and c in {x for x, _ in cols_novas}:
                        con.execute(f'ALTER TABLE "{tab}" ALTER COLUMN "{c}" TYPE VARCHAR')
                cols = ", ".join(f'CAST("{c}" AS VARCHAR) AS "{c}"' for c, _ in cols_novas)
                try:
                    con.execute(f'INSERT INTO "{tab}" BY NAME SELECT {cols} FROM _t')
                    reg["tipos"] = "misto (colunas divergentes viram texto)"
                except Exception as e:  # noqa: BLE001
                    reg["erros"].append(f"{f.name}: {str(e)[:160]}")
            con.execute("DROP TABLE IF EXISTS _t")
        if criado:
            reg["linhas"] = con.execute(f'SELECT count(*) FROM "{tab}"').fetchone()[0]
        reg["segundos"] = round(time.time() - t0, 1)
        catalogo.append(reg)
        if reg["erros"] or reg["arquivos"] > 20 or reg["linhas"] > 50000:
            log(f"{tab}: {reg['arquivos']} arquivos, {reg['linhas']} linhas, tipos {reg['tipos']}{' · erros ' + str(len(reg['erros'])) if reg['erros'] else ''}")
    # documentos JSON e textos
    for tab, lista, kind in ((f"{origem}_json_documentos", docs, "json"), (f"{origem}_textos", textos, "texto")):
        con.execute(f'CREATE TABLE IF NOT EXISTS "{tab}" (_arquivo VARCHAR, _familia VARCHAR, _caso VARCHAR, _data_no_nome VARCHAR, bytes BIGINT, '
                    f'{"conteudo JSON" if kind == "json" else "texto VARCHAR"})')
        erros, n = [], 0
        for f in lista:
            rel = f.relative_to(raiz).as_posix()
            try:
                if kind == "json":
                    import gzip
                    bruto = (gzip.open(f, "rt", encoding="utf-8") if f.name.endswith(".gz") else open(f, encoding="utf-8")).read()
                    json.loads(bruto)  # garante JSON válido
                    val = bruto
                else:
                    val = f.read_text(encoding="utf-8", errors="replace")
                con.execute(f'INSERT INTO "{tab}" VALUES (?, ?, ?, ?, ?, ?)', [rel, familia(rel), caso_de(rel), data_no_nome(rel), f.stat().st_size, val])
                n += 1
            except Exception as e:  # noqa: BLE001
                erros.append(f"{rel}: {str(e)[:120]}")
        catalogo.append({"tabela": tab, "origem": origem, "familia": "(todos os arquivos " + kind + ")", "tipo": kind, "arquivos": len(lista),
                         "bytes": sum(f.stat().st_size for f in lista), "tipos": "documento inteiro", "linhas": n, "erros": erros[:50]})
        log(f"{tab}: {n} de {len(lista)} arquivos{' · erros ' + str(len(erros)) if erros else ''}")
    con.execute("CREATE TABLE IF NOT EXISTS _arquivos_fora (origem VARCHAR, _arquivo VARCHAR, bytes BIGINT)")
    for f in fora:
        con.execute("INSERT INTO _arquivos_fora VALUES (?, ?, ?)", [origem, f.relative_to(raiz).as_posix(), f.stat().st_size])


def commit_de(raiz: Path) -> str | None:
    try:
        return subprocess.run(["git", "-C", str(raiz), "rev-parse", "HEAD"], capture_output=True, text=True, check=True).stdout.strip()
    except Exception:  # noqa: BLE001
        return None


def montar(destino: Path, completo: bool) -> dict:
    import duckdb
    destino.parent.mkdir(parents=True, exist_ok=True)
    tmp = destino.with_suffix(".tmp.duckdb")
    for p in (tmp, Path(str(tmp) + ".wal")):
        if p.exists():
            p.unlink()
    con = duckdb.connect(str(tmp))
    con.execute("SET preserve_insertion_order=false")
    catalogo: list[dict] = []
    log = lambda s: print(s, flush=True)  # noqa: E731
    t0 = time.time()
    carregar(con, "pub", ROOT / "data", [f for f in listar(ROOT / "data") if "banco" not in f.relative_to(ROOT / "data").parts[:1]], catalogo, log)
    fontes = {"publico": {"repositorio": "WandersonH/odi-atlas", "pasta": "data/", "commit": commit_de(ROOT)}}
    if completo:
        interno = Path(os.environ.get("ODI_INTERNO_DIR", ""))
        if not interno.is_dir():
            raise SystemExit("⛔ ODI_INTERNO_DIR não definido ou inexistente (banco completo precisa do repositório privado)")
        carregar(con, "priv", interno, listar(interno), catalogo, log)
        fontes["privado"] = {"repositorio": "WandersonH/odi-atlas-interno", "pasta": "/", "commit": commit_de(interno)}
    con.execute("CREATE TABLE _catalogo (tabela VARCHAR, origem VARCHAR, familia VARCHAR, tipo VARCHAR, arquivos INTEGER, bytes BIGINT, "
                "tipos VARCHAR, linhas BIGINT, segundos DOUBLE, erros VARCHAR[])")
    for r in catalogo:
        con.execute("INSERT INTO _catalogo VALUES (?,?,?,?,?,?,?,?,?,?)", [r["tabela"], r["origem"], r["familia"], r["tipo"], r["arquivos"], r["bytes"],
                                                                              r["tipos"], r["linhas"], r.get("segundos"), r["erros"]])
    sobre = {"gerado_em_utc": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"), "tipo": "completo" if completo else "publico",
             "fontes": fontes, "tabelas": len(catalogo), "linhas": sum(r["linhas"] for r in catalogo),
             "arquivos_lidos": sum(r["arquivos"] for r in catalogo), "tabelas_com_erro": sum(1 for r in catalogo if r["erros"]),
             "aviso": ("Banco COMPLETO: contém texto e autor de pessoas comuns. Uso restrito à equipe e a pesquisadores aprovados, para pesquisa; "
                       "não redistribuir; anonimizar em qualquer publicação." if completo else
                       "Banco público: só o que já está no repositório público (agregados; pessoas comuns como código)."),
             "universo": "O banco guarda o que o Atlas leu (amostra). O universo informado por cada plataforma está nos manifestos e nas páginas; ⛔ quando não informado."}
    con.execute("CREATE TABLE _sobre AS SELECT * FROM (SELECT ? AS chave, ? AS valor) WHERE false", ["", ""])
    for k, v in sobre.items():
        con.execute("INSERT INTO _sobre VALUES (?, ?)", [k, json.dumps(v, ensure_ascii=False) if not isinstance(v, str) else v])
    con.execute("CHECKPOINT")
    con.close()
    os.replace(tmp, destino)
    sobre["bytes"] = destino.stat().st_size
    sobre["segundos"] = round(time.time() - t0, 1)
    return {"sobre": sobre, "catalogo": catalogo}


def main(argv: list[str]) -> int:
    alvo = None
    if "--publico" in argv:
        alvo, completo = Path(argv[argv.index("--publico") + 1]), False
    elif "--completo" in argv:
        alvo, completo = Path(argv[argv.index("--completo") + 1]), True
    if not alvo:
        print(__doc__)
        return 1
    r = montar(alvo, completo)
    s = r["sobre"]
    if "--zip" in argv:  # distribuição: .zip abre em qualquer sistema (o .duckdb completo passa de 2 GB; zipado fica em ~0,7 GB)
        import zipfile
        with zipfile.ZipFile(alvo.with_suffix(".zip"), "w", zipfile.ZIP_DEFLATED, compresslevel=6) as z:
            z.write(alvo, alvo.name)
        s["zip_bytes"] = alvo.with_suffix(".zip").stat().st_size
    resumo = alvo.with_suffix(".catalogo.json")
    resumo.write_text(json.dumps({"sobre": s, "catalogo": [{k: v for k, v in c.items()} for c in r["catalogo"]]}, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(f"banco {s['tipo']}: {alvo} · {s['bytes'] / 1e6:.1f} MB · {s['tabelas']} tabelas · {s['linhas']} linhas · "
          f"{s['arquivos_lidos']} arquivos · {s['tabelas_com_erro']} tabelas com erro · {s['segundos']} s"
          + (f" · zip {s['zip_bytes'] / 1e6:.1f} MB" if s.get("zip_bytes") else ""))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
