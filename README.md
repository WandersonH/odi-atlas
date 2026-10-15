# ODI Atlas

Protótipo de observatório acadêmico do **Observatório de Desinformação e Intolerância Digital (ODI) · PPGCOM/UNIP**, sobre as eleições de 2026.

> **Estado real (15/10/2026):** a interface v15 está aqui, mas o mapa do caderno 12 **ainda não tem dados eleitorais**. `data/elections.json` está como `pending_source_import`. Este repositório começa pela etapa **P1 — Origem**: trazer os originais oficiais com proveniência verificável. Nada além disso está declarado como pronto.

## O que existe

| Item | Estado |
|---|---|
| `ODI_Atlas_v15_MVP.html` | Interface editorial com 12 cadernos. Caderno 12 (Geografia do Voto) aguarda dados. |
| `scripts/fetch_sources.py` | P1: baixa os originais do TSE (CKAN) e do IBGE, registra SHA-256, tamanho e cabeçalhos HTTP, e extrai Presidente / 1º turno sem alterar colunas. |
| `tests/` | Testes com arquivos sintéticos (filtro de cargo/turno, deduplicação entre arquivos BR e UF, conflitos, encoding Latin-1, execução completa sem rede). **Não substituem** a execução real. |
| `.github/workflows/p1-fontes.yml` | Executa a P1 no GitHub Actions: manual ou toda segunda-feira. |
| `data/manifest/` | Manifestos de cada execução (gerados pelo workflow). |
| Releases `fontes-*` | ZIPs originais exatamente como baixados, imutáveis. |

## Como a proveniência funciona

1. O workflow consulta a API CKAN do TSE (`resultados-2022`, `resultados-2026`) e só aceita o arquivo cujo nome é exatamente `votacao_candidato_munzona_<ANO>.zip`.
2. Cada original recebe SHA-256, tamanho, `Last-Modified` e `ETag` e vai para um **Release** (o arquivo é grande demais para o Git).
3. O recorte Presidente / 1º turno vai para `data/tse/presidente_1t_<ANO>_munzona.csv.gz`, com as mesmas colunas do TSE.
4. Linhas repetidas entre arquivos do mesmo ZIP são descartadas uma vez e **contadas**; repetição com valores diferentes **bloqueia** a execução.
5. O log de cada execução fica público na aba *Actions*, com um resumo em tabela.

**Dado ausente é bloqueio, não sucesso:** se um ano não tiver o arquivo no CKAN, o manifesto registra `bloqueado` e o workflow termina em erro.

## Próximas etapas (não implementadas aqui)

- **P2 · Ingestão:** totalizar por município a partir do recorte; conferir com as tabelas oficiais do TSE e, como prova cruzada independente, com os totais municipais publicados pelo votocruzado.com.br.
- **P3 · Correspondência TSE ↔ IBGE:** sem *fuzzy matching*; exceções documentadas.
- **P4 · Front-end:** ligar o caderno 12 ao JSON real e trocar a geometria provisória pela malha oficial do IBGE.

## Rodar localmente

```bash
python -m unittest discover -s tests -v
python scripts/fetch_sources.py --years 2022 2026 --malha 2025
```

Só biblioteca padrão do Python 3.10+.

## Licenças

- Código: MIT (`LICENSE`).
- Dados derivados produzidos aqui: CC BY 4.0.
- Dados originais: seguem os termos do TSE e do IBGE, que são as fontes e devem ser citadas.
