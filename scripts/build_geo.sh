#!/usr/bin/env bash
# P4 — converte a malha municipal oficial do IBGE (shapefile) em GeoJSON leve por UF,
# para o caderno 12. Usa mapshaper (simplificação que preserva a topologia entre vizinhos).
# Entrada: raw/BR_Municipios_<ANO>.zip (baixado pela P1). Saída: data/geo/<ANO>/mun_<UF>.json
set -euo pipefail
ANO="${1:-2025}"
ZIP="raw/BR_Municipios_${ANO}.zip"
OUT="data/geo/${ANO}"
[ -f "$ZIP" ] || { echo "::error::malha ausente: $ZIP"; exit 1; }
rm -rf tmp_malha && mkdir -p tmp_malha "$OUT" && unzip -q "$ZIP" -d tmp_malha
SHP=$(find tmp_malha -name '*.shp' | head -1)
# 1) simplifica o Brasil inteiro de uma vez (vizinhos continuam encaixados),
# 2) remove as duas áreas operacionais das lagoas (não são municípios),
# 3) mantém só código, nome e UF, 4) separa por UF.
npx -y mapshaper@0.6.102 -i "$SHP" encoding=utf8 \
  -filter '["4300001","4300002"].indexOf(CD_MUN) === -1' \
  -simplify 4% keep-shapes weighting=0.7 \
  -filter-fields CD_MUN,NM_MUN,SIGLA_UF \
  -proj wgs84 \
  -split SIGLA_UF \
  -o "$OUT/" format=geojson precision=0.0001 extension=.json
for f in "$OUT"/*.json; do b=$(basename "$f" .json); [[ "$b" == mun_* || "$b" == brasil_municipios || "$b" == indice ]] || mv "$f" "$OUT/mun_${b}.json"; done
# 5) visão nacional (caderno 12, opção "Brasil"): mesma malha, simplificação maior (~0,9%) para caber num arquivo só
npx -y mapshaper@0.6.102 -i "$SHP" encoding=utf8 \
  -filter '["4300001","4300002"].indexOf(CD_MUN) === -1' \
  -simplify 0.9% keep-shapes weighting=0.7 \
  -filter-fields CD_MUN,NM_MUN,SIGLA_UF \
  -proj wgs84 \
  -o "$OUT/brasil_municipios.json" format=geojson precision=0.001
python3 - "$OUT" "$ANO" <<'PY'
import json, sys, pathlib, hashlib
out, ano = pathlib.Path(sys.argv[1]), sys.argv[2]
idx = {"fonte": f"IBGE · malha municipal {ano} (BR_Municipios_{ano}.zip), simplificada a 4% com mapshaper",
       "ufs": {}}
total = 0
for f in sorted(out.glob("mun_*.json")):
    g = json.loads(f.read_text(encoding="utf-8"))
    n = len(g["features"]); total += n
    idx["ufs"][f.stem[4:]] = {"municipios": n, "bytes": f.stat().st_size,
                             "sha256": hashlib.sha256(f.read_bytes()).hexdigest()}
idx["total_municipios"] = total
(out / "indice.json").write_text(json.dumps(idx, ensure_ascii=False, indent=1), encoding="utf-8")
print("UFs", len(idx["ufs"]), "municípios", total)
if len(idx["ufs"]) != 27: raise SystemExit("::error::esperadas 27 UFs")
PY
rm -rf tmp_malha
