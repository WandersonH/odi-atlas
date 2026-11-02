# ODI Atlas

Protótipo de observatório acadêmico do **Observatório de Desinformação e Intolerância Digital (ODI) · PPGCOM/UNIP**, sobre as eleições de 2026.

> **Estado em 01/11/2026.** Esta seção foi reescrita depois da revisão do segundo par. A anterior, de 15/10, descrevia só a etapa P1. O registro completo, versão a versão, está no `CHANGELOG.md`.

## O que o Atlas é hoje

Um sistema de **coleta, processamento, preservação e visualização** sobre a eleição de 2026. Tem 129 scripts em `scripts/`, 79 workflows em `.github/workflows/` e 271 testes unitários em 79 arquivos de `tests/` (contagens de 01/11/2026). A interface é `ODI_Atlas_v15_MVP.html`.

| Frente | O que cobre | Onde |
|---|---|---|
| Resultados eleitorais | 1º turno 2022 e 2026 por município, conferidos com fonte oficial e independente (`docs/VALIDACAO_P1.md`); 2º turno 2026 por seção | `data/elections*.json`, `data/tse/` |
| Comunicação das campanhas (universo A) | Contas declaradas ao TSE das chapas 13 e 22: YouTube, TikTok, Kwai, Instagram, Facebook e X | `data/youtube/`, `data/tiktok/`, `data/kwai/`, `data/instagram/`, `data/facebook/`, `data/x/` |
| Circulação pública (universo B) | Comentários, respostas, Google Trends, imprensa, checagens, anúncios e 25 casos por termo ou hashtag | `data/*/comentarios/`, `data/trends/`, `data/casos/` |
| Análise | Livros de códigos (Bardin, pré-codificação), CHD de Reinert própria, redes (GEXF, GraphML e NodeXL), sentimento por modelo | `data/config/livro_codigos_*.json`, `data/corpus/` |
| Controle | Manifesto de cada coleta, saúde operacional e qualidade da coleta, estado da evidência por painel, matriz caso × análise | `data/saude_coleta.json`, `data/config/estado_evidencia.json`, `data/casos/matriz.json` |

## Como ler um resultado

Todo painel da página mostra o **estado da evidência**:

- **coletado:** há evidência bruta com proveniência;
- **processado:** os scripts calcularam indicadores, mas sem avaliação independente;
- **validado:** cumpriu um critério de avaliação registrado;
- **interpretável:** sustenta a afirmação específica que o painel faz, dentro do escopo indicado.

Em 01/11/2026, quase tudo está como **processado**. Ainda faltam:

- a codificação humana (kappa) dos livros de códigos;
- a conferência da CHD no IRaMuTeQ;
- a revisão humana das bolhas de apoio e das posições.

Mais regras de leitura:

- **Universo e amostra:** toda amostra aparece com o universo que a plataforma informa. Quando a plataforma não informa, o universo fica ⛔ desconhecido, nunca estimado (regra 9 do `CLAUDE.md`).
- **"Coleta em dia" não é "coleta completa":** a saúde operacional diz se chegou dado novo dentro do prazo. A linha de qualidade de cada série diz o que os arquivos permitem verificar: perfis esperados × lidos, buscas que bateram no limite, execuções parciais.
- **Cuidados de interpretação:**
  - uma comunidade de rede não é, sozinha, uma "bolha";
  - citar um candidato não é apoiá-lo;
  - Trends por estado e voto por município são medidas agregadas de unidades diferentes, sem inferência individual nem causal.

## Origem: a etapa P1
## Como a proveniência funciona

1. O workflow consulta a API CKAN do TSE (`resultados-2022`, `resultados-2026`) e só aceita o arquivo cujo nome é exatamente `votacao_candidato_munzona_<ANO>.zip`.
2. Cada original recebe SHA-256, tamanho, `Last-Modified` e `ETag` e vai para um **Release** (o arquivo é grande demais para o Git).
3. O recorte Presidente / 1º turno vai para `data/tse/presidente_1t_<ANO>_munzona.csv.gz`, com as mesmas colunas do TSE.
4. Linhas repetidas entre arquivos do mesmo ZIP são descartadas uma vez e **contadas**; repetição com valores diferentes **bloqueia** a execução.
5. O log de cada execução fica público na aba *Actions*, com um resumo em tabela.

**Dado ausente é bloqueio, não sucesso:** se um ano não tiver o arquivo no CKAN, o manifesto registra `bloqueado` e o workflow termina em erro.

## Próximas etapas

As prioridades estão na revisão do segundo par (01/11/2026) e no `CHANGELOG.md`:

1. Validação humana dos livros de códigos, com kappa.
2. Conferência da CHD no IRaMuTeQ.
3. Integração de atores, narrativas e tempo.
4. O caso 002 como piloto de busca e IA generativa.
5. Ampliação controlada do universo eleitoral.

## Rodar localmente

```bash
python -m unittest discover -s tests -v
python scripts/fetch_sources.py --years 2022 2026 --malha 2025
```

A etapa P1 usa só a biblioteca padrão do Python 3.10+. As análises usam numpy, networkx e os modelos citados em cada script.

## Licenças

- Código: MIT (`LICENSE`).
- Dados derivados produzidos aqui: CC BY 4.0.
- Dados originais: seguem os termos do TSE e do IBGE, que são as fontes e devem ser citadas.
