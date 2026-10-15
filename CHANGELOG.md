# Registro de versões — ODI Atlas

Toda mudança no repositório entra aqui, da mais recente para a mais antiga. Cada entrada diz **o que mudou, como foi testado, o que ficou pendente** e onde está a evidência. "Testado" só vale para o que foi realmente executado.

Legenda de estado: ✅ concluído e verificado · ⚠️ concluído com ressalva · ⛔ bloqueado · 🔜 planejado (não implementado)

---

## [P1.3] 2026-10-15 — Workflow: commit resistente a push concorrente

**Mudou**
- O passo "Commitar recorte e manifesto" faz `git pull --rebase` antes do `git push`, com até 3 tentativas.

**Por quê:** o run das 17:27 UTC (disparado manualmente) baixou e extraiu tudo e publicou o Release, mas falhou no commit: durante a coleta houve outro push na `main` (index.html e CHANGELOG), e o push do runner foi recusado por estar desatualizado.

**Testado**
- 🔜 Validar no próximo run.

---

## [P1.2] 2026-10-15 — Acesso pelo navegador (GitHub Pages)

**Mudou**
- `index.html` na raiz redireciona para `ODI_Atlas_v15_MVP.html`; `.nojekyll` para o Pages servir os arquivos como estão.

**Testado**
- ⛔ Ativação do Pages pela API foi recusada nesta sessão; precisa ser ligada manualmente em *Settings → Pages* (branch `main`, pasta `/`).

**Pendente**
- 🔜 Confirmar o endereço `https://wandersonh.github.io/odi-atlas/` depois de ativado. O caderno 12 continuará sem votos até a P2.

---

## [P1.1] 2026-10-15 — Municípios a partir da malha IBGE

**Mudou**
- A tabela oficial de municípios agora sai do `.dbf` da malha `BR_Municipios_2025.zip` → `data/ibge/municipios_malha_2025.csv` (5.573 linhas, 15 colunas, UTF-8).
- A falha da API de localidades do IBGE deixou de bloquear a execução e virou **aviso** (`warnings` no manifesto).
- Novo teste do leitor de DBF (9 testes no total).
- `docs/VALIDACAO_P1.md` criado.

**Por quê:** a API do IBGE respondeu com cadeia de certificados incompleta (`CERTIFICATE_VERIFY_FAILED`) no runner do GitHub. A malha é fonte oficial e a mesma da geometria do mapa.

**Testado**
- ✅ Run `38774937828`: concluído com sucesso; status `ok`; 1 aviso (API IBGE).
- ✅ Hashes dos três originais **idênticos** aos do run anterior → coleta reprodutível.

**Pendente**
- ⚠️ 5.573 linhas na malha contra 5.571 municípios no votocruzado: conferir na P3 quais registros a malha traz a mais (possivelmente áreas que não são municípios).

**Evidência:** `data/manifest/latest.json`, Release `fontes-20261015T171439Z`, aba Actions.

---

## [P1.0] 2026-10-15 — Origem: coletor TSE/IBGE com proveniência

**Mudou**
- Repositório criado com a interface `ODI_Atlas_v15_MVP.html` (sem alterações em relação ao v15 recebido) e `data/elections.json` ainda como `pending_source_import`.
- `scripts/fetch_sources.py`: descobre pelo CKAN do TSE o `votacao_candidato_munzona_<ANO>.zip` (nome exato), baixa com SHA-256/tamanho/cabeçalhos HTTP, extrai Presidente / 1º turno sem alterar colunas, deduplica entre arquivos e bloqueia em caso de dado ausente ou conflitante.
- `.github/workflows/p1-fontes.yml`: manual + toda segunda 06h15 (Brasília); originais vão para Release, recorte e manifesto são commitados.
- Testes com fixtures; licenças MIT (código) e CC BY 4.0 (dados derivados).

**Testado**
- ✅ Run `38774161017`: TSE 2022 e 2026 baixados e extraídos.
  - 2022: 581.030.017 bytes, `4c258fb6…`, 69.113 linhas Presidente/1T.
  - 2026: 457.846.585 bytes, `393dae04…`, 75.504 linhas Presidente/1T.
- ✅ 2022 confere com o resultado oficial (Lula 57.259.504; Bolsonaro 51.072.345).
- ✅ 2026 confere com fonte independente (votocruzado): 27/27 UFs e total nacional idênticos; 5.526 municípios iguais, 0 divergentes.
- ⛔ IBGE API de localidades: falha de certificado (resolvido na P1.1).

**Achado relevante:** os votos para Presidente estão em `_BR.csv` e repetidos integralmente em `_BRASIL.csv`. Somar os dois dobraria os votos; a deduplicação descartou as cópias sem conflito.

**Pendente**
- 🔜 P2: totalização por município e geração do `elections.json` real.
- 🔜 P3: correspondência TSE ↔ IBGE; 45 municípios não casaram por grafia (ex.: `OLHO D'ÁGUA`).
- 🔜 P4: ligar o caderno 12 ao JSON real e usar a malha IBGE no lugar da geometria provisória.

**Evidência:** `docs/VALIDACAO_P1.md`, `data/manifest/p1-20261015T170351Z.json`, Release `fontes-20261015T170659Z`.

---

## Antes deste repositório (referência, não verificado aqui)

- **v1–v9:** dashboards com Modash/TSE, fichas de perfis, Big Numbers, PNAD, Social Blade.
- **v10–v14:** identidade editorial ODI; v14 com expediente e LEIA-ME.
- **v15:** caderno 12 (Geografia do Voto) com mapa Leaflet, sem dados eleitorais carregados.

Fonte: dossiê de continuidade de 15/10/2026.
