# Validação da P1 — Origem

Registro da primeira execução real e das conferências feitas sobre ela. Datas em UTC.

## Execução

- Run do GitHub Actions: `38774161017` (15/10/2026, 17:03–17:07 UTC), disparo manual.
- Originais no Release `fontes-*` correspondente; hashes em `data/manifest/p1-20261015T170351Z.json`.

| Original | Bytes | SHA-256 | Last-Modified (servidor) |
|---|---|---|---|
| `votacao_candidato_munzona_2022.zip` | 581.030.017 | `4c258fb6ef8c25f5f9a7e210d3d143ccbbb81ccb23a5d6201d4b9e31f1fc46c3` | 15/10/2026 07:10:30 |
| `votacao_candidato_munzona_2026.zip` | 457.846.585 | `393dae04ca66b81cc1b71a1b44e928ebf1c8b4e9417f63cf1f7decf31610a6ff` | 15/10/2026 16:10:15 |
| `BR_Municipios_2025.zip` (IBGE) | 237.062.431 | `840bbe6f73726ef9d1460ce49fdfe01a278935c41180d3c893e25ca21db083bd` | — |

**Atenção:** o TSE regravou os dois ZIPs em 15/10/2026 (`Last-Modified`). A versão analisada é a identificada pelo hash acima; execuções futuras podem trazer outro hash.

## Estrutura encontrada nos ZIPs

As linhas de Presidente / 1º turno estão **só** em dois arquivos de cada ZIP: `_BR.csv` e `_BRASIL.csv`. O segundo repete integralmente o primeiro (2022: 69.113 linhas repetidas; 2026: 75.504). A deduplicação descartou as cópias, **sem nenhum conflito de valores**. Somar os dois arquivos teria **dobrado** os votos.

## Conferência 1 — 2022 contra o resultado oficial

Total nominal do recorte (inclui exterior), somando `QT_VOTOS_NOMINAIS_VALIDOS`:

| Nº | Candidatura | Votos | % válidos |
|---|---|---|---|
| 13 | Lula | 57.259.504 | 48,43% |
| 22 | Jair Bolsonaro | 51.072.345 | 43,20% |
| 15 | Simone Tebet | 4.915.423 | 4,16% |
| 12 | Ciro Gomes | 3.599.287 | 3,04% |
| | **Total nominal** | **118.229.719** | |

Coincide com o resultado oficial divulgado pelo TSE para o 1º turno de 2022.

## Conferência 2 — 2026 contra fonte independente

Comparado com os totais municipais publicados pelo votocruzado.com.br (gerados a partir de `resultados.tse.jus.br`, excluindo exterior), para os números 22 e 13 e o total de votos válidos:

- **27 de 27 UFs idênticas.**
- Brasil sem exterior: 22 = 55.960.603; 13 = 53.722.151; válidos = 118.969.906 — **idênticos nas duas fontes**.
- Municípios: 5.526 casados pelo nome com votos **iguais**; **0 divergentes**; 45 não casados apenas por grafia (ex.: `OLHO D'ÁGUA DAS FLORES`). Esses 45 são tarefa da P3 (correspondência sem *fuzzy matching*).

Com exterior, o recorte de 2026 soma 119.300.788 votos nominais válidos (22 = 56.104.503; 13 = 53.879.538).

O votocruzado é usado **só como prova cruzada**: seus dados não são redistribuídos aqui (o repositório deles não tem licença).

## Pendências que esta validação não cobre

- Brancos, nulos, comparecimento e abstenção (não estão no arquivo de votação nominal).
- Correspondência TSE ↔ IBGE (P3). O TSE usa código de município próprio.
- A API de localidades do IBGE falhou por certificado (cadeia incompleta no servidor). A tabela de municípios passou a vir do `.dbf` da malha oficial.

## 2º turno de 2022 e 2026 (conferência de 01/11/2026)

Arquivo do Atlas: `data/elections_2t.json`, campo `diagnostics.sources.<ano>`, somando os municípios do Brasil e o exterior.

| Ano | Candidatura | Atlas | Referência | Resultado |
|---|---|---|---|---|
| 2026 | Lula (13) | 64.256.232 | 64.256.232 | ✅ igual |
| 2026 | Flávio Bolsonaro (22) | 59.826.041 | 59.826.041 | ✅ igual |
| 2026 | Válidos (13 + 22) | 124.082.273 | 124.082.273 | ✅ igual |
| 2022 | Lula (13) | 60.345.999 | 60.345.999 | ✅ igual |
| 2022 | Jair Bolsonaro (22) | 58.206.354 | 58.206.354 | ✅ igual |

- **Referência de 2026:** totais divulgados pelo TSE com 100% das seções apuradas, como reproduzidos pela Brasil 61 (https://brasil61.com/n/lula-e-reeleito-presidente-com-vantagem-no-nordeste-flavio-liderou-no-sul-e-centro-oeste-bras2617371). O texto da matéria traz em um trecho 51,76% para Lula; a tabela e os votos dão 51,79%, que é o que os votos acima produzem (64.256.232 / 124.082.273).
- **Referência de 2022:** resultado oficial do TSE do 2º turno de 2022, conhecido publicamente. O arquivo do Atlas vem dos dados abertos do TSE (`presidente_2t_2022_munzona.csv.gz`).
- **Soma por seção** (`data/tse/secoes/presidente_2t_resumo.json`, arquivo `votacao_secao_2026_BR.zip` do TSE, 499.205 seções): Lula 64.256.232, Flávio 59.826.041, brancos 1.430.496, nulos 2.723.305. Os votos são iguais ao arquivo por município e à referência. Brancos e nulos também são iguais à referência (Brasil 61: 1.430.496 e 2.723.305).
- **⛔ Não coberto:** comparecimento e abstenção do 2º turno.
