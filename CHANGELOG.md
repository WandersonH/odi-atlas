# Registro de versões — ODI Atlas

Toda mudança no repositório entra aqui, da mais recente para a mais antiga. Cada entrada diz **o que mudou, como foi testado, o que ficou pendente** e onde está a evidência. "Testado" só vale para o que foi realmente executado.

Legenda de estado: ✅ concluído e verificado · ⚠️ concluído com ressalva · ⛔ bloqueado · 🔜 planejado (não implementado)

---

## [C2.0] 2026-10-15 — Seguidores Instagram/Facebook via Apify, agendado (caderno 02)

**Mudou**
- `scripts/collect_meta_apify.py` + `data/config/seguidores_meta.json` + workflow `seguidores-meta.yml` (diário, 07h10): conta seguidores dos perfis **Instagram e Facebook** declarados ao TSE pelas chapas presidenciais (Presidente e Vice), com os atores oficiais `apify~instagram-profile-scraper` e `apify~facebook-pages-scraper`.
- Token só pelo segredo `APIFY_TOKEN` do GitHub; nunca gravado nem impresso.
- Orçamento: **US$ 0,50 por execução** (`maxTotalChargeUsd` em cada ator) e **US$ 5,00 por mês**; antes de rodar, soma o custo real registrado nos manifestos do mês e bloqueia se passar do teto.
- Saída `data/seguidores/latest.csv` no formato do modelo CSV do caderno 02, histórico `coleta_AAAA-MM-DD.csv`, manifesto com custo real por ator e bruto mínimo (chave, número, campo usado, URL — sem posts nem comentários).
- Caderno 02 carrega `latest.csv` automaticamente: cards “Não coletado” passam a “Coletado”, com fonte e data. Importação manual continua tendo prioridade.
- 27 testes (5 novos, incluindo bloqueio sem token e bloqueio por teto sem chamar a API).

**Testado**
- ✅ Run `38793764408`: Instagram 52 perfis pedidos → 49 com número (US$ 0,1173); Facebook 27 → 24 com número (US$ 0,2050). **Custo total US$ 0,32**, dentro do teto de US$ 0,50. 73 linhas em `data/seguidores/latest.csv`.
- ✅ Campos usados: `followersCount` (Instagram) e `followers` (Facebook) — nenhum caso caiu em “curtidas”.
- ✅ Navegador headless, caderno 02 · Lula: 11 cards passaram a “Coletado”; 15 seguem “Pendente” (outras plataformas ou perfis sem número).
- ⚠️ 8 perfis sem número (4 links de compartilhamento do Facebook `/share/…`, que não apontam para a página; 4 Instagram sem resposta). Ficam “Não coletado”, não zero.
- ⚠️ 3 perfis declarados por Flávio Bolsonaro (`denunciabr_reserva`, `denunciabr_reserva1`, `denuncia.br.2026`) retornaram 0 seguidores: registrado como veio da fonte.
- ⚠️ **Orçamento:** a US$ 0,32 por dia, o mês sairia ~US$ 9,70 — acima do teto de US$ 5,00; a coleta pararia sozinha por volta do 15º dia. Decisão pendente do usuário: semanal (~US$ 1,40/mês) ou teto mensal maior.

**Pendente**
- Perfil sem número na resposta fica “Não coletado” (não vira zero).

---

## [P4.0] 2026-10-15 — Mapa com a malha oficial do IBGE e escala de cores legível

**Mudou**
- `scripts/build_geo.sh`: converte `BR_Municipios_2025.zip` (IBGE, mesmo arquivo e hash da P1) em GeoJSON por UF com mapshaper — simplificação de 4% feita no Brasil inteiro de uma vez (vizinhos continuam encaixados), sem as 2 áreas operacionais das lagoas, só com `CD_MUN`, `NM_MUN`, `SIGLA_UF`. Saída em `data/geo/2025/` (27 arquivos, 17 MB; maior: MG com 2,5 MB) + `indice.json` com contagem e hash por UF.
- Caderno 12 lê a malha local em vez da geodata-br; a ficha municipal usa o código IBGE da malha.
- Escala de “% dos votos válidos” em faixas fixas de 10 pontos (< 20%, 20–30 … ≥ 70%), iguais para todas as UFs e anos, com a legenda mostrando as faixas.
- Workflow `p1-fontes.yml` regenera a malha depois da coleta.

**Testado**
- ✅ Conversão local a partir do original do Release (SHA-256 `840bbe6f…`, igual ao da P1): **27 UFs, 5.571 municípios**.
- ✅ Cruzamento malha × `elections.json`: 2026 — 5.571 de 5.571 formas com dado; 2022 — falta só Boa Esperança do Norte (MT), que não existia em 2022 (a evolução aparece como “Indisponível”, como deve).
- ✅ Navegador headless: SP desenhado pela malha IBGE; ficha de Areiópolis (43,41% → 39,31%; −4,10 pp; IBGE 3503604).

**Pendente**
- 🔜 Conferir no navegador ao menos três municípios contra a página oficial do TSE (gate 6 do dossiê), testar celular e falta de rede.
- 🔜 Comparação lado a lado 2022 | 2026 (desejada no dossiê).

---

## [P2.1] 2026-10-15 — Correção do zoom do mapa (caderno 12)

**Mudou**
- `ODI_Atlas_v15_MVP.html`: o mapa só ajusta o enquadramento quando o caderno está visível, e reenquadra ao abrir o caderno. Duas linhas no script do caderno 12; visual ODI intacto.

**Por quê:** erro latente do v15, que só apareceu com dados reais. O mapa era desenhado com o caderno ainda oculto (área de tamanho zero), o Leaflet ia para o zoom máximo e a tela mostrava só um município, em azul uniforme.

**Testado**
- ✅ Navegador headless (Chromium) servindo o HTML localmente: base 2022 e 2026 carregada; SP com 645 municípios, nº 13 = 9.505.413 votos (38,20%) em 2026; mapa do estado inteiro desenhado; clique abre a ficha (ex.: Itatiba, 30,03% → 27,85%, −2,19 pp; código IBGE 3523404).

**Pendente**
- ⚠️ Escala de cores divide 0–100% em 7 faixas: como quase todos os municípios ficam entre 20% e 60%, o contraste é baixo. Revisar na P4.

---

## [P2.0] 2026-10-15 — Mapa de votos: `data/elections.json` real (P2 + P3)

**Mudou**
- `scripts/build_elections.py`: totaliza por município a partir do recorte da P1 (soma das zonas), separa o exterior, faz a correspondência TSE→IBGE e grava `data/elections.json` no formato que o caderno 12 já lê.
- `data/config/tse_ibge_excecoes.csv`: 15 exceções revisadas à mão (grafia S/Z, preposição, nome abreviado, Boa Saúde = Januário Cicco). O resto casa por nome idêntico após normalização. **Sem aproximação automática:** município sem correspondência bloqueia.
- Portões: somas por UF iguais ao recorte bruto; código IBGE único por ano; UF do código igual à do TSE.
- Workflow `p1-fontes.yml` gera o `elections.json` logo após a coleta.
- 22 testes (4 novos).

**Testado**
- ✅ Execução local sobre os dados da P1: **2022 — 5.570 municípios; 2026 — 5.571**; 0 sem correspondência; 0 divergência por UF.
- ✅ 2022 com exterior: 13 = 57.259.504 e 22 = 51.072.345 (resultado oficial). 2026 sem exterior: 13 = 53.722.151 e 22 = 55.960.603 (iguais ao votocruzado).
- ✅ Geometria do caderno 12 (geodata-br): as 5.564 formas encontram dado (5.534 pelo nome, 30 pelo código IBGE).
- 🐞 Os portões pegaram um erro meu na primeira execução: excluir as lagoas por prefixo de código removia municípios reais do RS (ex.: Aceguá). Corrigido para os dois códigos exatos, com teste.

**Pendente**
- ⚠️ A geometria geodata-br é antiga e não tem cerca de 7 municípios recentes (5.564 formas × 5.571 municípios): ficam sem forma no mapa. Trocar pela malha oficial do IBGE é a P4.
- ⚠️ O "22" é Jair em 2022 e Flávio em 2026: a evolução 2022→2026 compara o número de urna, não a pessoa. O aviso está no `source.nota` do JSON.
- Brancos, nulos e abstenção não estão no arquivo de votação nominal.

**Evidência:** `data/elections.json` (`diagnostics`), `data/config/tse_ibge_excecoes.csv`, `tests/test_build_elections.py`.

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

- ✅ Run `38788448582` (coleta de governo, versão final): TSE ok; SIDRA com **12 de 25** tabelas de Internet da PNAD Contínua baixadas para Brasil + 27 UFs, últimos 6 períodos (ex.: tabela 7307 — domicílios com uso de internet, 1.344 linhas). As outras 13 deram erro no servidor do IBGE e serão tentadas de novo toda segunda.
- Correções no caminho: a API v3 do IBGE deu timeout/erro 500 em todas as tabelas → troca para a API clássica `apisidra`; a coleta ficou dividida em passos com manifesto salvo a cada tabela; commit centralizado em `scripts/commit_push.sh` com diagnóstico.
- ✅ Trends com todos os grupos ok: Flávio, Lula e Caiado como tópico "candidato/presidente"; Augusto Cury como tópico "Médico e psiquiatra"; Renan Santos só como palavra (sem entidade no Trends).

**Pendente**
- ⚠️ SIDRA: 13 tabelas com erro do servidor (6447, 6793, 7313, 7314, 7317, 7318, 7321, 7323, 7324, 7331, 7332, 7333, 7337).
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
