# Registro de versões — ODI Atlas

Toda mudança no repositório entra aqui, da mais recente para a mais antiga. Cada entrada diz **o que mudou, como foi testado, o que ficou pendente** e onde está a evidência. "Testado" só vale para o que foi realmente executado.

Legenda de estado: ✅ concluído e verificado · ⚠️ concluído com ressalva · ⛔ bloqueado · 🔜 planejado (não implementado)

---

## [C1.0] 2026-10-15 — Novas coletas: Google Trends, TSE candidaturas/redes, IBGE Internet

**Mudou**
- `scripts/net.py` (novo, compartilhado): corrige cadeia de certificados incompleta buscando o intermediário pelo endereço AIA do certificado, **sem desligar a verificação**; descompacta respostas gzip que o IBGE envia sem ser pedido.
- `scripts/collect_trends.py` + `data/config/trends.json` + workflow `trends.yml` (diário, 08h40): série temporal e recorte por UF, cada coleta numa pasta nova `data/trends/AAAA-MM-DD/HHMMSS/`.
- `scripts/collect_gov.py` + workflow `coletas-gov.yml` (segundas, 06h20):
  - `tse-candidatos`: cadastro de candidaturas em **allowlist** (CPF, e-mail, título, nascimento e nome civil nunca são gravados) e redes sociais declaradas, com a plataforma classificada pelo domínio.
  - `sidra`: tabelas da PNAD Contínua sobre Internet, descobertas pelo catálogo oficial do IBGE.
- 18 testes no total (antes 9).

**Testado**
- ✅ Run `38781040915` — TSE 2026: 21.017 candidaturas (16 Presidente, 16 Vice) e 62.635 URLs de redes; 258 URLs das chapas presidenciais em `data/tse/redes_presidencia_2026.json`. O arquivo de redes também repete as linhas entre `_BR` e `_BRASIL` (63.837 cópias descartadas).
- ✅ Run `38781834841` — API de municípios do IBGE funcionando após a correção do certificado: **5.571 municípios**.
- ✅ Trends: consultas por palavra e por tópico coletadas (séries + 27 UFs).
- ⚠️ **Achado metodológico:** a palavra "Lula" também é o molusco. Nos últimos 3 meses, por **palavra**, a média foi Flávio 3,1 × Lula 9,1 (razão 2,9); por **tópico** (entidade), Flávio 6,3 × Lula 9,4 (razão 1,5). A configuração passou a usar tópicos, escolhidos pelo tipo, e mantém um grupo por palavra só para comparação.
- ⚠️ No Trends, Augusto Cury está cadastrado como "Médico e psiquiatra brasileiro", não como candidato: o tipo aceito é definido por candidato.

**Pendente**
- SIDRA: ver entrada seguinte quando o run terminar.
- 🔜 Trends: os valores são relativos (0–100) dentro de cada consulta; nunca comparar entre grupos ou períodos diferentes.

---

## [P1.3] 2026-10-15 — Workflow: commit resistente a push concorrente

**Mudou**
- O passo "Commitar recorte e manifesto" faz `git pull --rebase` antes do `git push`, com até 3 tentativas.

**Por quê:** o run das 17:27 UTC (disparado manualmente) baixou e extraiu tudo e publicou o Release, mas falhou no commit: durante a coleta houve outro push na `main` (index.html e CHANGELOG), e o push do runner foi recusado por estar desatualizado.

**Testado**
- ✅ Run `38778407292`: coleta e commit concluídos com sucesso.

---

## [P1.2] 2026-10-15 — Acesso pelo navegador (GitHub Pages)

**Mudou**
- `index.html` na raiz redireciona para `ODI_Atlas_v15_MVP.html`; `.nojekyll` para o Pages servir os arquivos como estão.

**Testado**
- ✅ Pages ativado manualmente (*Settings → Pages*, `main` / root). `https://wandersonh.github.io/odi-atlas/ODI_Atlas_v15_MVP.html` abre com a interface completa (conferido no navegador). O primeiro acesso deu 404 porque o deploy ainda estava em andamento.

**Pendente**
- O caderno 12 continua sem votos até a P2.

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
