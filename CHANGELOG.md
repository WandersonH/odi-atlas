# Registro de versões — ODI Atlas

Toda mudança no repositório entra aqui, da mais recente para a mais antiga. Cada entrada diz **o que mudou, como foi testado, o que ficou pendente** e onde está a evidência. "Testado" só vale para o que foi realmente executado.

Legenda de estado: ✅ concluído e verificado · ⚠️ concluído com ressalva · ⛔ bloqueado · 🔜 planejado (não implementado)

## C12.2 — Google Busca de hora em hora (2026-10-16) 🔜

- `google-busca.yml`: agenda passa de 07h40 e 19h40 para de hora em hora (minuto 17). Pedido do usuário.
- `data/trends/google_busca_historico.csv` recebe uma linha por resultado a cada hora (até 16 por execução).
- Teste: só a validação do YAML; a primeira execução agendada ainda não aconteceu (o GitHub pode atrasar ou pular execuções agendadas em horários de pico).

## C12.1 — Google Busca passa a usar o Google Notícias (RSS) (2026-10-16) ✅

**O que mudou**
- O usuário informou que a chave é a mesma do YouTube e criou o mecanismo; o cx (ID público, aparece no código de incorporação) entrou em `data/config/google_busca.json`.
- O teste da chave sem cx (workflow `google-busca.yml`) respondeu `400 INVALID_ARGUMENT`; com o cx, todas as consultas responderam `HTTP 403 This project does not have the access to Custom Search JSON API` (API fechada a novos clientes).
- `scripts/collect_google_busca.py`: quando a API recusa o projeto, usa o RSS público de busca do Google Notícias (`news.google.com/rss/search`, pt-BR/BR, sem chave): 5 primeiros na ordem do Google Notícias e 3 mais recentes da busca `when:3d`. `parse_rss` com teste em `tests/test_google_busca.py`.
- Página: bloco mostra a fonte, o veículo e o domínio; título "Google Busca · Google Notícias".

**Testes executados**
- `python -m unittest discover -s tests` sem falhas.
- Run do `google-busca.yml` das 03h47 (16/10): status ok, 5 + 3 resultados para cada candidato em `data/trends/google_busca.json` (ex.: Lula 1º O Globo "Lula na TV Globo..."; Flávio 1º Folha "Datafolha: Flávio Bolsonaro tem 51%...").
- Chromium local a 390 px: bloco renderizado, sem erro, sem rolagem horizontal.

**Ressalvas**
- Só notícias indexadas pelo Google Notícias, não a busca geral da web. A lista de sites do mecanismo não é usada nesse caminho.

## C12.0 — Anúncios pagos (Meta e Google), sentimento dos comentários do YouTube, chave do Google Busca (2026-10-16) ⚠️

**O que mudou**
- Diagnóstico `scripts/diag_bibliotecas_anuncios.py` + `teste-bibliotecas-anuncios.yml` (não grava dados). Run 38853829904:
  - Biblioteca da Meta sem login abre e mostra contagem ("50.000 resultados" para Lula e para Flávio Bolsonaro, anúncios políticos BR), mas sem gasto estruturado;
  - Central de Transparência do Google: a página de campanhas políticas BR carrega (`SearchCreatives`), a busca por anunciante via URL não devolveu resultados.
- Meta: `scripts/collect_meta_anuncios.py` (API oficial `ads_archive` v26.0, anúncios POLITICAL_AND_ISSUE_ADS no BR desde 20/07 que citam cada candidato), `data/config/meta_anuncios.json`, `.github/workflows/meta-anuncios.yml` (diário 09h25), `tests/test_meta_anuncios.py`. Bruto só no privado; público: agregados por candidato, fase e página anunciante.
- Página: nova subpágina "Anúncios pagos (Meta e Google)" no caderno 02 (`#adsLib`), com bloco explicando a proibição de impulsionamento eleitoral pelo Google (2024, mantida em 2026).
- Sentimento: `scripts/build_sentimento_comentarios.py` (modelo `pysentimiento/bertweet-pt-sentiment`, cache privado `youtube/comentarios/sentimento.csv.gz`, grava a cada 2.000 e para em 75 min), `data/config/sentimento_comentarios.json`, `.github/workflows/sentimento-youtube.yml` (diário 08h40), `tests/test_sentimento.py`. Público: `data/youtube/comentarios/sentimento.json` (percentuais por candidato, fase e vídeo com ≥ 30 comentários).
- Página: listas e detalhe de vídeo do YouTube mostram curtidas e comentários e a barra de tom; caderno 04 ganha "Tom geral dos comentários".
- Google Busca: aceita a chave do YouTube (`YOUTUBE_API_KEY`) quando `GOOGLE_CSE_KEY` não existe (o usuário informou que é a mesma chave); diagnóstico de presença dos segredos no workflow (sem valores). Status diz qual item falta.

**Por quê** — pedido do usuário: capturar bibliotecas de anúncios Google e Meta, marcar impulsionamento e trazer dados e sentimento dos vídeos do YouTube.

**Testes executados**
- `python -m unittest discover -s tests` sem falhas.
- Chromium local com dados de teste numa cópia descartável (não publicada): blocos renderizam, sem erro de JS, sem rolagem a 390 px.
- Google Busca run 38854074811 e seguinte: nenhum segredo GOOGLE_CSE_* encontrado.

**Pendente / bloqueios**
- ⛔ Meta: falta o segredo `META_AD_LIBRARY_TOKEN` (`data/meta/anuncios.json` registra o status).
- ⛔ Sentimento: primeiro run (38854095565) em andamento; números ainda não publicados. Sem validação humana.
- ⛔ Google Busca: falta `GOOGLE_CSE_CX`; a Custom Search JSON API está fechada a clientes novos e pode responder 403.
- 🔜 Monitoramento automático da Central de Transparência do Google.
- Os commits bb870e5 e anteriores desta rodada saíram sem entrada no CHANGELOG; esta entrada os cobre.

## P4.5 — Índice de busca por fase: pré-campanha, 1º turno, 2º turno (2026-10-16) ✅

**O que mudou**
- `data/config/trends.json`: novo bloco `fases` — pré-campanha 20/07–15/08 (convenções), campanha do 1º turno 16/08–04/10 (dia da votação), 2º turno 05/10–25/10.
- `scripts/build_trends_caderno.py`: `por_fase()` calcula, por termo e fase, dias observados, média, mediana, máximo (com data) e média sem picos; sai em `vegetativo[termo].fases` do `data/trends/caderno.json`. Manifestos antigos sem `fases` usam a config atual.
- Panorama: a linha do índice mostra "média · mediana" do período todo e uma linha por fase.
- Caderno de buscas: tabela "Por fase do calendário eleitoral" no card do método (média · mediana · máximo e média sem picos).

**Por quê** — pedido do usuário: dividir os números de busca em pré-campanha, campanha do 1º turno e 2º turno.

**Testes executados**
- `tests/test_trends_caderno.py::TestFases` (novo); `python -m unittest discover -s tests -v` sem falhas.
- `python3 scripts/build_trends_caderno.py` sobre a coleta `data/trends/2026-10-15/221726` (consulta `segundo_turno_topicos`, período eleitoral), resultado em `data/trends/caderno.json`:
  - Lula — pré 2,07 · 2 (27 dias); 1º turno 9,68 · 5 (50 dias, máx. 100 em 04/10); 2º turno 28,8 · 26,5 (10 dias, máx. 56 em 05/10).
  - Flávio — pré 1,44 · 1; 1º turno 5,64 · 3 (máx. 83 em 04/10); 2º turno 22,4 · 20 (máx. 47 em 05/10).
- Chromium (Playwright) local: linhas no Panorama e tabela no caderno renderizadas, sem erro de JS, sem rolagem horizontal a 390 px.

**Pendente / ressalvas**
- O 2º turno está em curso: só conta os dias já coletados (até 14/10 nesta coleta; o dia parcial fica de fora).
- O índice é 0–100 relativo dentro da consulta; a comparação entre fases vale porque todas estão na mesma série.

---

## [P4.4] 2026-10-16 — Panorama: índice de busca com média e mediana

**Por quê:** o usuário perguntou se o dado de busca era mediana ou número bruto e pediu os dois.

**Mudou:** na etapa 1 do Panorama, "Interesse médio" virou duas linhas, com valores lidos de `data/trends/caderno.json` (vegetativo, período eleitoral):
- "Índice de busca · média do período": Lula 9,52 × Flávio 6,26;
- "Índice de busca · mediana do período (dia típico)": Lula 5 × Flávio 2.

O Trends não fornece número bruto de buscas, só o índice relativo de 0 a 100.

**Testado:** ✅ Chromium, as duas linhas renderizadas sem erro; suíte de testes OK.

---

## [C11.0] 2026-10-16 — Buscas: o que o Google mostra (5 primeiros e 3 mais recentes por candidato)

**Por quê:** pedido do usuário: "usar a API search via chave Google para trazer os 5 primeiros resultados na página do Trends e os últimos 3 novos publicados".

**Mudou**
- `scripts/collect_google_busca.py` + `data/config/google_busca.json`: Google Custom Search JSON API, 4 consultas por execução (cota grátis: 100/dia).
  - Para Lula e para "Flávio Bolsonaro": 5 primeiros (relevância) e 3 mais recentes (`sort=date`, últimas 72 h).
  - Brasil e português; data de publicação lida das metatags quando a página informa.
  - Saída em `data/trends/google_busca.json` e histórico em `google_busca_historico.csv`.
- `.github/workflows/google-busca.yml`, às 07h40 e 19h40 BRT.
- Caderno 05: bloco "O que o Google mostra para cada candidato".

**Testado**
- ✅ `tests/test_google_busca.py` (2); suíte OK.
- ✅ Chromium 1300/390 px: bloco renderizado com o aviso de bloqueio, sem erro e sem rolagem horizontal.
- ⛔ Sem consulta real: faltam os segredos `GOOGLE_CSE_KEY` e `GOOGLE_CSE_CX` (o usuário cria; não são pedidos no chat).

**Atenção (fonte: [Brave, alternativas à API do Google](https://brave.com/learn/google-api-shutdown/))**
- O Google fechou a Custom Search JSON API a novos clientes e vai desligá-la em 01/01/2027.
- Mecanismos criados desde 20/01/2026 só buscam numa lista de até 50 sites. A "web inteira" só vale para mecanismos antigos.
- Serve para o período eleitoral (2º turno em 25/10/2026).

---

## [C10.1] 2026-10-16 — TikTok: mais 4 hashtags pedidas pelo usuário

**Mudou:** `data/config/tiktok_hashtags.json` ganhou #boralula e #exercitodolula (Lula) e #tropadoflavio e #bloquinho22 (Flávio), agora 14 hashtags. Pedido do usuário: "tropa do Flávio, bloquinho 22, boralula, exército do Lula".

**Testado (run `38851470318`)**
- ✅ As 4 novas hashtags trouxeram vídeos: #boralula 60 vídeos / 58 contas; #exercitodolula 59/50; #tropadoflavio 60/51; #bloquinho22 60/53.
- ✅ Acervo acumulado: 810 vídeos e 691 contas, 340 delas com 10 mil+ seguidores; 432 vídeos no público.
- ✅ Rede: 200 contas, o teto `MAX_CANAIS` atingido; ficam as que mais citam.
  - Lula: 138 contas (108 só dele), 1 pediu voto.
  - Flávio: 92 contas (62 só dele), 8 pediram voto (11 vídeos).
  - 30 falaram dos dois.

---

## [C10.0] 2026-10-16 — TikTok: contas que publicam sobre os candidatos (hashtags, grátis)

**Por quê:** o usuário notou que o TikTok do atlas mostrava só os perfis grandes das campanhas e pediu para "ver o que conseguimos free".

**Mudou**
- `scripts/collect_tiktok_hashtags.py` + `data/config/tiktok_hashtags.json`:
  - abre num Chromium headless, sem login, as páginas públicas de 10 hashtags (Lula: #lula13 #lula2026 #lulapresidente #fazol #lula; Flávio: #flaviobolsonaro #flavio22 #vote22 #flaviopresidente #bolsonaro);
  - guarda os vídeos que a página carrega, de qualquer conta;
  - lista completa no repositório privado; no público, só contas com 10 mil+ seguidores (mesmo corte do YouTube).
- `scripts/build_rede_tiktok_apoio.py`: rede bipartida conta × candidato com as mesmas regras dos influenciadores do YouTube (nível 1 = falou; nível 2 = pediu voto, pela legenda e pelas hashtags do vídeo). Perfis de campanha excluídos.
  - `build_rede_influenciadores.py` foi refatorado (`gerar()`) para servir às duas plataformas. A rede do YouTube refeita ficou idêntica, salvo o carimbo de data.
- `.github/workflows/tiktok-hashtags.yml`, diário às 09h15 BRT.
- Página: bloco "contas do TikTok que publicam com hashtags dos candidatos" na aba TikTok do caderno 02, com rede, tabela, GEXF e CSVs.

**Testado (run real `38850779477`)**
- ✅ Cada hashtag rendeu 57–60 vídeos e 49–57 contas. Só 2 páginas da rolagem carregam sem login, então a coleta acumula dia a dia.
- ✅ No 1º dia: 512 vídeos lidos, 442 após remover os repetidos entre hashtags, 385 contas (220 com 10 mil+).
- ✅ Rede pública: 174 contas e 213 vídeos.
  - Lula: 119 contas falaram dele (90 só dele), 1 pediu voto.
  - Flávio: 84 contas (55 só dele), 8 pediram voto (11 vídeos).
  - 29 contas falaram dos dois.
  - Entre as maiores: Metrópoles, g1, CNN, Jovem Pan News, UOL, Erika Hilton, PT, Instituto Lula.
- ✅ Testes: `tests/test_tiktok_hashtags.py` (2) e suíte OK.
- ✅ Chromium 1300/390 px: 176 círculos na rede do TikTok e a rede do YouTube intacta (202), sem erro e sem rolagem horizontal.

**Limites**
- A página de hashtag mostra vídeos "populares", não em ordem de data: não é amostra do universo.
- Hashtag não é apoio: o lado vem do texto.
- Comentários do TikTok continuam bloqueados sem login (D1.2).

---

## [D1.2] 2026-10-16 — Diagnóstico: comentários do TikTok (bloqueados) e vídeos de apoiadores por hashtag (funciona)

**Por quê:** o usuário pediu a página de comentários do TikTok e perguntou por que não aparecem os vídeos de apoio de contas menores.

**Testado (GitHub Actions, IP do GitHub, sem login)**
- ⛔ **Comentários do TikTok:**
  - o endpoint público `api/comment/list` devolveu resposta vazia nos 6 vídeos testados (5 de Lula e aliados, 1 de Flávio). O TikTok exige parâmetros assinados ou login;
  - num Chromium headless (Playwright), as duas páginas de vídeo foram para a tela de login ("Entrar | TikTok"), sem nenhum pedido de comentários;
  - o yt-dlp 2026.08.19 não tem extração de comentários do TikTok.
  - O coletor `collect_comentarios_tiktok.py` foi removido. O teste fica em `teste-comentarios-tiktok.yml` + `scripts/diag_tiktok_navegador.py`.
- ✅ **Páginas de hashtag no navegador headless:**
  - `#lula13`: 58 vídeos de 26 + 30 contas distintas em duas páginas da rolagem;
  - `#flaviobolsonaro`: 59 vídeos de 29 + 27 contas.
  - É o caminho gratuito para os vídeos de apoio de contas menores (o yt-dlp falhava nessas páginas: "No working app info", D1.1).
- ⛔ Busca do TikTok: tela de login.

**Pendente:** coletor de vídeos por hashtag e página de apoiadores (aguarda decisão do usuário).

---

## [P4.3] 2026-10-15 — Página reorganizada em 7 cadernos; Panorama vira resumo "da busca ao voto"

**Por quê:** pedido do usuário. Avaliar junções de páginas que se complementam, com visão focal; o Panorama deve ser "um resumo de todos os dados sobre os candidatos, de buscas a voto". A junção Comentários + Trends foi descartada pelo usuário ("não fazer"); Eleitorado + PNAD + Escala foi aprovada.

**Mudou**
- **Menu com 7 cadernos.** As páginas que se juntam ganham abas internas fixas no topo. O código de cada caderno não mudou, e os links antigos (`data-goto`) continuam funcionando.

  | Nº | Caderno | Abas |
  |---|---|---|
  | 01 | Panorama · da busca ao voto | — |
  | 02 | O que as campanhas dizem | YouTube, TikTok |
  | 03 | Quem acompanha | Seguidores agora, Ficha do perfil, Evolução no tempo, Série histórica do YouTube (Social Blade) |
  | 04 | Comentários · YouTube | — |
  | 05 | Buscas · Google Trends | — |
  | 06 | Eleitorado e território | Voto e eleitorado, Acesso à internet (PNAD), Contas × eleitorado |
  | 07 | Método, fontes e universo | LEIA-ME/fontes/método, Perfis declarados ao TSE |

- **Panorama: tabela Lula × Flávio em 5 etapas.** Cada linha é lida na hora do arquivo de origem e mostra fonte e data:
  1. Buscas (Trends, período eleitoral);
  2. Presença digital (Instagram e Facebook por Apify, YouTube pela API, TikTok pelo Modash, WhatsApp);
  3. O que publicam (YouTube API, TikTok, tema mais frequente);
  4. Reação (comentários, incivilidade, intolerância, interação no TikTok);
  5. Voto no 1º turno de 2026 (TSE).

  O sublinhado marca o maior valor só onde "maior" tem leitura direta.
- Faixas dos cadernos, índice do LEIA-ME, menções no texto e nos scripts/workflows renumerados (11 → 02, 12 → 05, 13 → 02, 14 → 04; geografia → 06).
- Correção: a aba de perfis declarados ao TSE transbordava a 390 px (antes desta mudança); filtros e tabela agora cabem, com rolagem própria na tabela.

**Testado**
- ✅ Chromium 1300 px e 390 px: os 7 cadernos e as abas internas (TikTok, Social Blade, Contas × eleitorado, Perfis declarados) abrem a seção certa e acendem o item certo do menu. Sem erro de console e sem rolagem horizontal.
- ✅ Valores do Panorama conferidos com as fontes, por exemplo:
  - Trends: média 9,52 × 6,26; Lula à frente nos 27 estados, com o menor valor dele em Roraima, 57 × 43;
  - YouTube: 1,82 mi × 1,52 mi;
  - votos: 53.722.151 (45,16%) × 55.960.603 (47,04%); municípios em 1º lugar: 2.665 × 2.906 de 5.571.
- ✅ Suíte de testes OK; YAML dos workflows válido.

---

## [C9.4] 2026-10-15 — Comentários: repositório privado ligado; redes para o Gephi e corpus para o IRaMuTeQ

**Por quê:** o usuário ajustou o token (Contents: read and write) e pediu "nos comentários, Gephi e IRaMuTeQ".

**Testado com dados reais**
- ✅ Run `38834967148` (comentarios-youtube) em **modo interno**:
  - 1.012 vídeos, 2.024 chamadas, 128.104 registros; 6 vídeos deram HTTP 400;
  - o repositório privado recebeu os comentários (11,9 MB, gz), o corpus IRaMuTeQ completo (15,3 MB), os trechos da CHD e a amostra de codificação.
  - A amostra tem 399 comentários, não 400: 200 de Lula e 199 de Flávio, por arredondamento da estratificação semanal. Ela fica assim, porque a amostra não é refeita.
- ✅ `scripts/build_rede_comentarios.py`, rodado localmente sobre o mesmo arquivo bruto (cópia do repositório privado):
  - **Rede de palavras:** 150 nós, 1.083 arestas, 5 comunidades, modularidade 0,226, a partir de 90.021 comentários (52.115 de Lula e 37.906 de Flávio). Mais típicas da audiência de Flávio: alfredo, gaspar, jair, vencer, ladrão, liberdade, stf. Da de Lula: gratidão, viva, democracia, bets, soberania, reeleito, tetra, estadista.
  - **Rede de respostas (pseudonimizada):** 12.515 autores, 14.092 ligações, maior componente com 9.708 autores, centralização de Freeman do grau de entrada 0,005 no todo. A maior comunidade (884 autores) tem 1,6% dos comentários em vídeos de Lula; as seguintes têm 87–99,6% em vídeos de Lula. As duas audiências quase não se respondem.
  - A posição dos nós usa o cosseno de Salton, porque o ForceAtlas2 empurrava os polos para as bordas. A cor é normalizada pelo tamanho de cada audiência.
- ✅ Saídas privadas enviadas ao `odi-atlas-interno` (commit próprio): `rede_respostas_identificada.gexf`, `codigos_autores.csv`, `corpus_iramuteq_amostra.txt` (2,0 MB).
- ✅ No público, nenhum ID de canal (`UC…`) nos arquivos da rede de respostas (grep).
- ✅ Testes: 2 novos (Freeman 1,0 numa estrela e 0 num ciclo; autorresposta ignorada); suíte OK. Chromium 1300/390 px sem erro e sem rolagem horizontal.

**Mudou**
- Script novo `scripts/build_rede_comentarios.py`, com passo no workflow `comentarios-youtube.yml`.
- Caderno 14 ganhou três blocos:
  - rede de palavras (desenho, comunidades, GEXF, CSVs e JSON);
  - rede de conversação (números, desenho dos 400 autores com mais ligações, tabela por comunidade com grau de entrada, centralização e % em vídeos de Lula, GEXF e CSVs);
  - IRaMuTeQ (onde ficam os corpora no repositório privado e como abrir).

**Limite:** a API devolve até 5 respostas por conversa; conversas longas aparecem incompletas na rede de respostas.

---

## [P4.2] 2026-10-15 — Página: LEIA-ME + Fontes & metodologia numa só; Geografia do voto no topo de Eleitorado

**Por quê:** pedidos do usuário: "fontes e metodologia e leia-me têm que virar uma única página"; "juntar geografia do voto ao topo da página eleitorado e participação".

**Mudou**
- **Caderno 10 · LEIA-ME · Fontes & metodologia**: a antiga página de Fontes & metodologia (fontes digitais, dados eleitorais, limitações, o que falta, referências externas) virou as seções 06 e 07 do LEIA-ME.
- O inventário de fontes foi atualizado: entram YouTube Data API, comentários, TikTok, Trends, WhatsApp e votação TSE × IBGE, com link para cada arquivo. O índice ficou com os 14 cadernos, e a frase "base até 11/10" saiu.
- **Caderno 08 · Eleitorado, voto & participação**: o mapa municipal (antigo caderno 12) abre a página; abaixo vem "Parte 2 / Eleitorado e participação". O código do mapa não mudou (carrega no início, independente da seção).
- **Renumeração (15 → 14 cadernos):** 13 → 11 (YouTube), 14 → 12 (Trends), 15 → 13 (TikTok), 16 → 14 (Comentários). As referências "caderno N" no HTML, nos scripts, nos workflows, no livro de códigos e em `data/tiktok/conteudo.json` foram atualizadas. Entradas antigas deste CHANGELOG mantêm a numeração da época.
- Links `data-goto` para `method` e `geoVote` agora apontam para as páginas que os absorveram.
- CSS: URLs longas das referências quebram a linha (a 390 px elas transbordavam).

**Testado**
- ✅ Chromium 1300 px e 390 px: 14 itens no menu, mapa com 5.572 caminhos, referências renderizadas, sem erro de console e sem rolagem horizontal.
- ✅ Suíte de testes OK.

---

## [C9.3] 2026-10-15 — Diagnóstico do acesso ao repositório privado

**Por quê:** o run `38834073420`, o primeiro depois de o usuário criar o segredo `ODI_INTERNO_TOKEN`, parou no `git clone` do `odi-atlas-interno` (exit 128). O log não é legível daqui.

**Mudou:** quando o clone falha, o passo publica uma anotação com o erro do git (token mascarado), o código HTTP da API do repositório com esse token, o tamanho do token e o prefixo `github_pat_`. Assim dá para distinguir token vazio, sem acesso ao repositório ou sem permissão.

**Testado:** YAML validado; o run seguinte registra o resultado.

---

## [C9.2] 2026-10-15 — Texto de aviso do caderno 16

**Mudou:** o aviso dizia "repositório privado ainda não ligado", o que dava a entender que o repositório não estava conectado. Ele está conectado à sessão do Claude (README enviado no commit `8932e7f`). O que falta é a permissão da coleta automática do GitHub Actions, que roda no servidor do GitHub e precisa do segredo `ODI_INTERNO_TOKEN`. O texto agora diz isso.

**Testado:** suíte de testes OK; só texto alterado.

---

## [C9.1] 2026-10-15 — Caderno 16 (comentários do YouTube) e WhatsApp na página; primeiros runs reais

**Mudou**
- Página: novo **caderno 16 · Audiência · comentários YouTube**, só com agregados:
  - números por candidato;
  - nuvens de palavras;
  - intolerância/incivilidade e populismo em barras pareadas (vermelho/verde);
  - aderência ao tema do vídeo;
  - série diária (sem o dia da coleta);
  - classes da CHD;
  - método e downloads.
- Caderno 02 ganhou o cartão "Canais de WhatsApp · seguidores", lido de `data/whatsapp/seguidores.csv`.
- `whatsapp_canais.json`: o segundo canal é o "Canal do Lula", nome lido da página; lado = Lula. A primeira linha da planilha recebeu o mesmo rótulo de lado (configuração, não medida).

**Testado (dados reais)**
- ✅ Run `38827011582` (comentarios-youtube): 1.012 vídeos, 2.024 chamadas (= unidades de cota) e 151.484 registros lidos; 128.125 após remover os repetidos entre "relevância" e "recentes". Um vídeo deu HTTP 400.
  - Lula: 63.386 comentários e 11.253 respostas em 641 vídeos, 31.272 autores; incivilidade 1,55%, intolerância 0,75%, copiar e colar 1,42%.
  - Flávio: 48.485 comentários e 5.000 respostas em 371 vídeos, 22.734 autores; incivilidade 1,53%, intolerância 0,52%, copiar e colar 3,8%.
  - CHD: 6 classes por candidato, com 99,6% e 99,8% da amostra classificada.
  - Rodou em **modo efêmero**: o segredo `ODI_INTERNO_TOKEN` não existe, então o texto bruto foi descartado no fim do run e a amostra humana não foi gravada.
- ✅ Run `38827172627` (whatsapp): EXÉRCITO DO LULA "4,6 mi seguidores" → 4.600.000; Canal do Lula "1,7 mi seguidores" → 1.700.000.
- ✅ Chromium 1300 px e 390 px: cadernos 16 e 02 sem erro de console e sem rolagem horizontal.

**Pendente**
- ⛔ `ODI_INTERNO_TOKEN` (segredo do repositório público, criado pelo usuário: token fino só para `odi-atlas-interno`, Contents read/write). Sem ele não há texto guardado, amostra para codificação nem corpus IRaMuTeQ.
- ⚠️ Percentuais de intolerância vêm de pré-codificação por palavras; validar com a amostra humana (kappa) antes de citar.
- 🔜 Links dos demais canais de WhatsApp.

---

## [D2.0] 2026-10-15 — WhatsApp: seguidores diários dos canais (planilha)

**Por quê:** pedido do usuário: "extraia os números dessas páginas diariamente e grave no nosso banco em uma planilha". Links enviados: Exército do Lula (`0029VbCbRfD7tkj88k3soZ0Y`, repetido 3 vezes na mensagem) e `0029VaDH1GU7DAWpJTrCXH39` (nome a confirmar pela própria página).

**Mudou**
- `scripts/collect_whatsapp.py`: lê a página pública `whatsapp.com/channel/<id>`, com nome e número de seguidores. Converte "45,6 mil", "1,2 mi" e "2.1M" e grava também o texto original.
- `data/config/whatsapp_canais.json`: lista de canais.
- Saída: `data/whatsapp/seguidores.csv` (histórico, uma linha por dia e canal; abre no Excel/Sheets), `seguidores_latest.csv` e `manifesto_latest.json`.
- `.github/workflows/whatsapp.yml`, diário às 08h05 BRT.

**Testado**
- ✅ `tests/test_whatsapp.py` (4 testes, HTML fictício).
- ⛔ Este ambiente não alcança whatsapp.com (proxy 403). A leitura real depende do run no GitHub Actions. Se a página não trouxer o número, o manifesto grava o começo do texto visível para diagnóstico.

---

## [C9.0] 2026-10-15 — Comentários do YouTube: coleta, livro de códigos de intolerância e análise agregada (pipeline)

**Por quê:** pedido do usuário: "análise de discurso dos comentários do YouTube por candidato". Ele escolheu guardar o texto no repositório privado `odi-atlas-interno`, criado hoje.

**Mudou**
- `data/config/livro_codigos_intolerancia.json` (v1.0): 10 categorias, separando incivilidade de intolerância (Rossini 2022):
  - incivilidade;
  - rótulo pejorativo político (simétrico: gado/bolsominion e petralha/mortadela);
  - desumanização;
  - ódio de gênero, LGBT, raça/origem e religião;
  - ameaça/violência;
  - ataque à integridade eleitoral;
  - acusação de corrupção.

  Cada categoria tem definição, fonte, exemplo, regra de exclusão e trechos excluídos.
- `scripts/collect_comentarios_youtube.py`: `commentThreads.list`, até 100 conversas por relevância e 100 mais recentes por vídeo das campanhas desde 16/08, com as respostas que vêm junto. Teto de 4.000 unidades de cota. O texto bruto vai só para o repositório privado (ou para uma pasta temporária, apagada no fim do run). No público fica só o manifesto.
- `scripts/build_comentarios.py`: só agregados em `data/youtube/comentarios/analise.json`, por candidato:
  - volume e concentração de autores;
  - "copiar e colar" (mesmo texto de 3+ autores);
  - nuvem de palavras (termo em 10+ comentários);
  - temas;
  - aderência ao tema do vídeo;
  - populismo e intolerância em %;
  - curtidas de comentários incivis × civis;
  - série diária;
  - CHD de Reinert (formas, sem trechos).
- No privado: amostra de 200 comentários por candidato para codificação humana (sorteada uma vez), pré-codificação separada, corpus IRaMuTeQ e trechos característicos das classes.
- `.github/workflows/comentarios-youtube.yml` (diário, 07h50 BRT). Grava no privado se existir o segredo `ODI_INTERNO_TOKEN`; senão roda em modo efêmero.
- Repositório privado inicializado com README de regras (LGPD).

**Testado**
- ✅ `tests/test_comentarios.py` (7 testes, dados fictícios):
  - formato da API;
  - mescla por `comment_id`;
  - exclusões do livro ("preço do gado", "fraude do INSS", "matar a saudade");
  - ponta a ponta confirmando que frase, nome e canal do autor não aparecem no JSON público;
  - modo privado gera amostra (200 por candidato) e corpus.
- ⚠️ Primeira versão do workflow com erro de YAML (":" num comando sem bloco); o GitHub não registrou o gatilho manual. Corrigido e validado com `yaml.safe_load`.
- 🔜 Run real: em seguida.

---

## [C8.2] 2026-10-15 — YouTube na página: API oficial como fonte; Modash como adendo

**Por quê:** decisão do usuário: "todo indicador de YouTube vamos deixar pela API oficial; dado do Modash é um adendo a essa tela".

**Mudou** (`ODI_Atlas_v15_MVP.html`)
- A página lê `data/youtube/fichas.json` antes de desenhar. Nos perfis de YouTube (Lula, Flávio, PT, PL), inscritos, engajamento, médias de visualizações, curtidas e comentários e a divisão curtos × longos vêm da API, nos cadernos:
  - 01 (visão geral);
  - 06 (fichas);
  - 07 (escala: inscritos pela API × % no Brasil do Modash).
- Se o arquivo faltar, esses campos ficam "—" com ⛔. O Modash não volta a preencher.
- Do Modash, o YouTube mantém só a composição estimada da audiência (gênero, idade, país), rotulada "Adendo Modash", porque a API pública não fornece esse dado.
- Caderno 06: novo cartão "Adendo Modash × API oficial", com os dois valores lado a lado.
- Caderno 03: série da API (`fichas_historico.csv`) com 10 indicadores; nos perfis de YouTube, os indicadores Modash aparecem como "adendo Modash", e o padrão é "Inscritos · API oficial".
- O caderno 02 já usava a API para o YouTube (sem mudança).

**Testado**
- ✅ Run `38822941698` (seguidores-youtube, dispatch): 4 canais, 61 unidades de cota, sem erro. Janela 13/09–13/10:

  | Canal | Inscritos | Vídeos | Visualizações médias | Engajamento |
  |---|---|---|---|---|
  | Lula | 1.820.000 | 215 | 183.776 | 8,14% |
  | Flávio | 1.520.000 | 208 | 137.247 | 8,27% |
  | PT | 670.000 | 239 | 52.790 | 7,58% |
  | PL | 207.000 | 52 | 35.297 | 4,43% |

- ✅ Chromium (cadernos 01, 02, 03, 06 e 07, YouTube): valores da API exibidos com fonte e data, sem erro de console. Exemplo: PT na API, 52,8 mil visualizações médias; no Modash de 10/10, 9,5 mil.
- ✅ Testes: suíte completa OK.

**Pendente**
- ⚠️ Caderno 04 (Social Blade · YouTube) continua com a série do Social Blade (12/09–11/10). A API não dá histórico retroativo; a série própria começa em 15/10.

---

## [C8.1] 2026-10-15 — YouTube: fichas pela API oficial (coletor)

**Por quê:** decisão do usuário: "todo indicador de YouTube vamos deixar pela API oficial; dado do Modash é um adendo".

**Mudou**
- `scripts/build_youtube_fichas.py` + `data/config/youtube_fichas.json`: para @LulaOficial, @flaviobolsonaro, @ptbrasil e @PartidoLiberal22, lê pela YouTube Data API:
  - inscritos, total de vídeos e de visualizações do canal;
  - médias e medianas de visualizações, curtidas e comentários dos vídeos dos últimos 30 dias, sem as últimas 48 h;
  - engajamento = (curtidas + comentários) ÷ visualizações;
  - divisão curtos (≤ 180 s, aproximação de Shorts) × longos.
- Saída em `data/youtube/fichas.json` e `fichas_historico.csv`. Novo passo no workflow `seguidores-youtube.yml`.

**Testado**
- ✅ `tests/test_youtube_fichas.py` (4 testes, dados fictícios); suíte completa OK.
- ✅ Lógica aplicada, sem chamar a API, aos vídeos já coletados em `data/youtube/videos_latest.csv.gz` (15/10), janela 13/09–13/10:
  - Lula: 215 vídeos, média de 183.419 visualizações, engajamento 8,14%;
  - Flávio: 208 vídeos, média de 137.181, engajamento 8,27%.
  - O Modash de 15/10 mostrava médias de 29,8 mil (Lula) e 30,7 mil (Flávio).
- ⛔ Chamada real da API (inclui PT e PL, que não estão no TSE): depende do run do workflow.

**Pendente:** página passar a ler `fichas.json` (C8.2).

---

## [C8.0] 2026-10-15 — Modash: relatórios de 15/10 e leitor reprodutível dos PDFs

**Por quê:** o usuário enviou 6 relatórios Modash de 15/10 (Instagram, TikTok e YouTube de Lula e Flávio) e os 13 PDFs originais de 10 e 11/10. Antes, os valores Modash estavam digitados no HTML, sem script que os refizesse.

**Mudou**
- `scripts/extrair_modash.py`: lê os PDFs com `pdftotext -layout` e grava `data/modash/`:
  - `perfis/<data>_<perfil>.json`, com tudo o que o PDF imprime (hashtags e menções, composição da audiência, interesses, marcas, idade × sexo);
  - `historico.csv`, no formato do caderno 03;
  - `provas.json`, com SHA-256 e o que mudou em relação à captura anterior;
  - `conferencia.json`, com os seguidores Modash × coleta própria do mesmo dia.
- Com `--html`, o script atualiza `DATA.profiles`, `BN_BASE`, `INITIAL_HISTORY` e `PROOFS` na página.
- Os PDFs ficam em `entrada/modash/`, fora do repositório (`.gitignore`). O upload guarda um prefixo porque o Modash dá o mesmo nome (`report-flaviobolsonaro-Oct-15-2026.pdf`) aos relatórios de Instagram e YouTube.
- Página:
  - a data de captura de cada ficha agora vem do próprio perfil (antes, "10/10/2026" estava fixo no código);
  - caderno 06 ganhou dois cartões: "Hashtags e menções mais usadas pelo perfil" e "Composição estimada dos seguidores" (Instagram);
  - caderno 03 ganhou o bloco "Controle de qualidade das capturas";
  - LEIA-ME e Fontes atualizados (19 relatórios).

**Testado**
- ✅ Regressão contra a primeira implementação: os 13 PDFs de 10 e 11/10 reproduzem os 301 registros de `INITIAL_HISTORY` sem nenhuma diferença. Os campos de `DATA.profiles` também batem. Os SHA-256 dos 4 PDFs listados em `PROOFS` conferem.
- ✅ `python -m unittest discover -s tests`: 81 OK. Inclui `tests/test_modash.py`, com texto fictício.
- ✅ Chromium: cadernos 03 e 06 renderizados sem erro de console. Tabela de qualidade com 8 comparações e 11 linhas de conferência.

**Achados (15/10 × captura anterior, de `data/modash/provas.json`)**
- TikTok @lulaoficial: 19 de 19 indicadores iguais aos de 10/10. O relatório não foi atualizado pela Modash.
- Instagram de Lula e de Flávio: mudaram só seguidores e engajamento. Os 30 demais indicadores, médias e percentuais de audiência, ficaram iguais. A Modash atualizou o cabeçalho, não a análise da audiência.
  - Lula: 15,1 mi → 16,5 mi; engajamento 0,27 → 0,35%.
  - Flávio: 11,7 mi → 13,8 mi; engajamento 0,86 → 0,72%.
- YouTube: Flávio caiu de 1,5 mi para 1,1 mi, e o canal aparece como "TV Celular Flavio Bolsonaro". Lula foi de 1,8 mi para 1,7 mi.
- Conferência com a coleta própria do mesmo dia (`data/seguidores/`):
  - Instagram Lula −5,2% (16,5 mi × 17.399.404);
  - Instagram Flávio −2,6% (13,8 mi × 14.166.897);
  - YouTube Lula −6,6% (1,7 mi × 1.820.000);
  - **YouTube Flávio −27,2%** (1,1 mi × 1.510.000 pela API oficial). O número Modash do YouTube de Flávio não deve ser usado.
- TikTok @flaviobolsonaro: as hashtags do Modash convergem com o nosso acervo de 81 vídeos desde 16/08:

  | Hashtag | Modash | Acervo próprio |
  |---|---|---|
  | #fy | 91,1% | 88,9% |
  | #bolsonaro | 87,3% | 87,7% |
  | #flaviobolsonaro | 84,8% | 86,4% |
  | #vote22 | 29,1% | 32,1% |
  | #forapt | 16,5% | 17,3% |

  As menções também convergem com a rede de menções (@bolsonaromessiasjair, Nikolas, Sargento Fahur). Já no @lulaoficial, que quase não usa hashtag (0,7% dos 300 vídeos), os 20% do Modash vêm de uma base pequena.

**Pendente**
- ⛔ TikTok sem coleta própria de seguidores: não há com o que conferir os números Modash.
- ⚠️ PT e PL continuam só com 10/10.
- ⚠️ O Modash não informa a janela nem quantos posts entram nas médias.

---

## [C7.5] 2026-10-15 — Correção: rede de menções sem scipy (testes do GitHub falhavam)

**Problema:** o run `38817560315` (TikTok) parou nos testes. A disposição da rede de menções usava `kamada_kawai_layout`, que exige o scipy; o GitHub Actions instala só networkx e numpy. Localmente passava porque este ambiente tem scipy. O mesmo teste roda no workflow do YouTube, que também quebraria na próxima coleta.

**Correção:** `spring_layout` com semente fixa (só numpy), um bloco por campanha como antes.

**Testado**
- ✅ Reproduzido o erro em Python 3.12 com networkx 3.6.1 e numpy 2.3.4, sem scipy ("No module named 'scipy'"). Depois da correção: 76 OK nesse ambiente e 76 OK aqui.
- ✅ Rede de menções regenerada: 25 contas e 23 ligações, idêntica em conteúdo. Chromium: 25 nós, sem rolagem horizontal.

---

## [C7.4] 2026-10-15 — Trends: método do período (normal × pico; pico → mediana; média por período), por candidato

**Por quê:** método do professor Maurício nas aulas (transcrição 1ed89c28 e 3641f036): "calculo o desvio padrão e sei aquilo que está acima do que é considerado normal… tiro o valor que saiu e substituo pela mediana… não trabalhei com o dia, trabalhei com a média do período, 7 dias, 15 dias… comparei média com média". Pedido do usuário.

**Mudou**
- `build_trends_caderno.py` → função `vegetativo()`, aplicada às séries diárias (período eleitoral e 3 meses). Fica de fora a de 7 dias por hora, porque pico de hora não é agenda diária. Por termo, calcula:
  - média, desvio-padrão, mediana e faixa normal (média ± 1σ);
  - **picos** = dias acima de média + k·σ, com o escore z;
  - **série sem picos** (cada pico substituído pela mediana);
  - **médias por blocos de 7 e 15 dias**, com e sem picos.
- Parâmetros em `trends.json` → `metodo_vegetativo`: k = 2 por padrão. A fala da aula não fixa k ("fora do desvio padrão"), por isso a contagem de picos com k = 1 também é registrada.
- Caderno 14:
  - alternância "Série original / Sem picos (pico → mediana)", com linha do limite de pico por candidato e picos circulados;
  - bloco "O que é nível normal e o que é pico de agenda", com estatísticas, lista de picos e barras das médias de 7 ou 15 dias. A parte clara da barra mostra a contribuição dos picos.

**Testado**
- ✅ Testes: 76 OK (novos: pico substituído pela mediana sem alterar o resto; blocos de 7 e 15 dias; mais picos com k = 1 do que com k = 2; série curta não calcula).
- ✅ Dados reais, 2º turno por tópicos, período eleitoral (coleta de 2026-10-15 22:17 UTC):
  - **Lula:** média 9.52, σ 13.57, mediana 5, limite 36.66; picos 2026-10-04 = 100, 2026-10-05 = 56 (com 1σ seriam 12).
  - **Flávio:** média 6.26, σ 11.06, mediana 2, limite 28.39; picos 2026-10-04 = 83, 2026-10-05 = 47 (com 1σ seriam 9).
  - Os dois picos coincidem com o 1º turno e o dia seguinte.
  - Médias de 15 dias sem picos: Lula 1.93 → 2.6 → 5.8 → 5.0 → 12.13 → 22.5; Flávio 1.27 → 1.8 → 2.6 → 2.67 → 6.47 → 16.42.
- ✅ Chromium headless (1400×900 e 390×844): 4 picos circulados, 24 barras; o bloco some na série de 7 dias por hora; sem rolagem horizontal.

---

## [C7.3] 2026-10-15 — Mapa estadual de verdade no Trends; rede de menções do TikTok; perfis do TikTok com a última leitura bem-sucedida

**Mudou**
- **Trends por UF:** o mapa em grade virou **mapa do Brasil por estado** (pedido: "isso deveria ser um mapa, não?").
  - Malha `data/geo/2025/brasil_ufs.json` (27 UFs, 157 KB), obtida dissolvendo por UF a malha nacional de municípios (mapshaper). O `build_geo.sh` também a gera.
  - Rótulos com UF e divisão Lula·Flávio; dica com os valores ao passar o cursor. A tabela continua ao lado.
- **Rede de menções do TikTok** (o usuário escolheu só a rede grátis): `scripts/build_rede_mencoes_tiktok.py`.
  - **Rede:** dirigida, perfil da campanha → conta marcada com @ na legenda; peso = nº de vídeos.
  - **Saídas:** JSON, GEXF, CSV de nós e arestas, e CSV de vídeos com link.
  - **Disposição:** um bloco por campanha (Lula à esquerda, Flávio à direita). Perfis sem marcação saem do desenho e ficam listados.
  - **Página:** bloco "Quem as campanhas marcam no TikTok" no caderno 15; o clique mostra os vídeos de cada marcação. Roda no `tiktok.yml`.
- **Etiquetas dos perfis do TikTok:** antes mostravam só o resultado da última tentativa, o que fazia parecer que "não leu nada" depois de um bloqueio. Agora mostram **quantos vídeos e quando foi a última leitura bem-sucedida**, e marcam se a última tentativa foi bloqueada. O status geral explica que os números são da última leitura boa.

**Testado**
- ✅ Testes: 74 OK (novo: extração de @, peso, corte por data, automenção, posição por campanha, perfil sem marcação).
- ✅ Rede de menções (acervo de 2026-10-15 21:57 UTC):
  - 25 contas e 23 ligações no desenho;
  - Lula: 99 marcações para 17 contas, a partir de 2 perfis (@alckmingeraldo → @lulaoficial 19, @presidente 16, @fernandohaddadoficial 13, @marciofrancasp 13, @marinasilvaoficial 12, @simonetebet 12);
  - Flávio: 9 marcações para 6 contas (@flaviobolsonaro → @bolsonaromessiasjair 4, @nikolas, @sargentofahur.oficial…);
  - sem marcação no período: @brasilcomlula_ e @pode_espalhar.
- ✅ Chromium headless (1400×900 e 390×844):
  - Trends: 27 estados no mapa, 48 itens de relacionados;
  - TikTok: 25 nós e 23 setas; etiqueta "@alckmingeraldo · Lula · 80 vídeos · lido em 15/10, 18:57 · ⛔ última tentativa bloqueada";
  - sem rolagem horizontal.

---

## [D1.1] 2026-10-15 — Diagnóstico: rede de quem fala dos candidatos no TikTok (páginas de hashtag)

**Por quê:** pedido do usuário, uma rede do TikTok como a de influenciadores do YouTube (contas que falaram de Lula/Flávio ou pediram voto).

**Testado**
- ⛔ Run `38816712756`: páginas de hashtag via yt-dlp (#lula, #flaviobolsonaro, #lula13, #flavio22) → "No working app info is available" nas quatro. A listagem por hashtag ou busca depende da API interna do app do TikTok, que o yt-dlp não acessa. **Não há caminho grátis** para a rede de entrada (quem fala deles).
- ✅ Mesmo run: perfis das campanhas legíveis (10 vídeos de @lulaoficial e 10 de @flaviobolsonaro).
- ✅ Rede de saída (quem as campanhas marcam com @ nas legendas), a partir do acervo existente (vídeos desde 16/08):
  - Lula: 629 vídeos, 17 contas marcadas (fernandohaddadoficial 13, marciofrancasp 13, simonetebet 12, marinasilvaoficial 12, ricardostuckert 4…);
  - Flávio: 81 vídeos, 6 contas (bolsonaromessiasjair 4, nikolas, sargentofahur.oficial…).

**Pendente:** a rede de entrada depende de serviço pago (Apify, com teto de custo e autorização do usuário) ou da API de pesquisa oficial do TikTok (elegibilidade a verificar).

---

## [C7.2] 2026-10-15 — Trends: consultas e assuntos relacionados (método exploratório das aulas); TikTok bloqueado numa rodada, dados preservados

**Por quê:** nas aulas de IA e produção de texto, o Trends é usado como etapa exploratória. As consultas relacionadas mostram como o público formula a busca e que termos associa ao tema (exemplo da aula: "Paraisópolis" associado a "Morumbi"). Esses termos orientam as strings de busca da coleta.

**Mudou**
- `collect_trends.py`: widgets `RELATED_QUERIES` e `RELATED_TOPICS` (endpoint `relatedsearches`), listas "principais" e "em alta".
  - **Escopo:** só o grupo 2º turno por tópicos (Lula × Flávio), nos períodos eleitoral e de 7 dias, ou seja, 8 chamadas a mais por coleta. Configurável em `trends.json` → `relacionados`.
  - **Saída:** `…__relacionados.csv` em formato longo (termo, tipo, lista, posição, texto, tipo de assunto, valor, rótulo).
- `build_trends_caderno.py` leva os relacionados para `caderno.json`.
- Caderno 14: bloco "O que o público busca junto com cada candidato", com consultas ou assuntos, "em alta" e "principais", por candidato.

**Testado**
- ✅ Testes: 73 OK (novo: CSV longo dos relacionados).
- ✅ Run `38816064106` (Trends, 2026-10-15): 90 linhas de relacionados em 7 dias e 100 no período eleitoral. Em alta em 7 dias:
  - **Lula:** "veja vorcaro lula", "audio vorcaro lula", "vorcaro instituto lula", "manifestação lula paulista" (aumento repentino);
  - **Flávio:** "flavio usuario master", "flavio bolsonaro mussolini" (aumento repentino), "tropa do flavio" (+2.400%), "pesquisa lula e flávio segundo turno" (+1.250%).
- ⛔ TikTok, run de 2026-10-15 22:06 UTC: **0 de 10 perfis** ("Unable to extract secondary user ID"). **O acervo de 710 vídeos foi preservado**, como projetado, e a página marca cada perfil como ⛔ não lido nesta coleta. Às 21:57 UTC haviam sido 7 de 10. Instabilidade do TikTok contra servidores, já registrada em D1.0.

---

## [C7.1] 2026-10-15 — TikTok com o mesmo pacote analítico do YouTube (Bardin, CHD/IRaMuTeQ, rede de coocorrência)

**Por quê:** pedido do usuário ("cadê as redes e o IRaMuTeQ do TikTok, eu falei mesmo formato").

**Mudou**
- `scripts/plataformas.py`: entrada única das análises. Converte o acervo do TikTok para o formato de linha do YouTube (só vídeos desde 16/08) e define os caminhos de saída por plataforma.
  - `corpus_populismo.py`, `chd_reinert.py`, `concordancia.py` e `build_rede.py` aceitam `--plataforma tiktok`. Sem o parâmetro, continuam no YouTube.
  - **Mesmas regras, sem cópia de código.** O corpus IRaMuTeQ ganhou a variável `*plat_`.
- **Saídas do TikTok:**
  - `data/tiktok/populismo.json`;
  - `data/corpus/tiktok_candidatos_iramuteq.txt` e `tiktok_candidatos_segmentos.csv`;
  - `data/corpus/chd_reinert_tiktok.json`;
  - `data/codificacao/amostra_populismo_tiktok_v1.csv` (+ pré-codificação separada) e `concordancia_tiktok_v1.json`;
  - `data/tiktok/rede.json`, `.gexf`, `rede_nos.csv`, `rede_arestas.csv` e `rede_videos_termos.csv`.
- Caderno 15: blocos "Estratégias discursivas e classes de discurso" e "Que assuntos andam juntos" (rede, tabelas de nós e arestas, downloads para o Gephi), iguais aos do caderno 13.
- As redes de coocorrência dos cadernos 13 e 15 passam para o padrão Lula vermelho × Flávio verde (antes azul × terracota).
- `tiktok.yml` roda essas análises depois de cada coleta, com networkx e numpy nas versões fixas.

**Testado**
- ✅ Testes: 72 OK (novos: argumentos e caminhos por plataforma; TikTok convertido para o formato do YouTube, descartando vídeos anteriores a 16/08).
- ✅ **Regressão:** com as mesmas entradas, `rede.json`, `chd_reinert.json` e `populismo.json` do YouTube saíram **idênticos** antes e depois da refatoração (comparação de JSON, sem os campos de data).
- ✅ TikTok, sobre o acervo de 2026-10-15 21:57 UTC (710 vídeos desde 16/08):
  - **Pré-codificação:** Lula 250 vídeos com alguma categoria, Flávio 30.
  - **CHD:** 1087/1099 segmentos (98.9%), 945 formas. Classes: 1 (7.9%, Lula 38.4%): bolsonaro, rede, federacao, pdt, psol; 2 (7.9%, Lula 93.0%): fernandohaddadoficial, marciofrancasp, paulo, simonetebet, marinasilvaoficial; 3 (7.9%, Lula 91.9%): flavio, bolsonaro, master, banco, vorcaro; 4 (17.3%, Lula 97.3%): futuro, educacao, soberano, mundo, pais; 5 (32.8%, Lula 91.0%): lula, brasil, frente, votar, lugar; 6 (26.2%, Lula 96.8%): escala, 6x1, familias, bets, familia.
  - **Rede:** 150 nós, 1023 arestas, 6 comunidades, modularidade 0.24.
- ✅ Chromium headless (1400×900 e 390×844): caderno 15 com 7 barras, 6 classes, 150 nós, 1.023 linhas e tabela de 150 nós. Caderno 13 sem regressão (148 nós, 6 classes, 202 nós na rede de influenciadores).

**Limite:** no TikTok, Lula tem 629 vídeos e Flávio 81 (só @flaviobolsonaro tem vídeos), então a rede e a CHD são dominadas por Lula. Compare a estrutura, não o tamanho.

---

## [C7.0] 2026-10-15 — Caderno 15 (TikTok, grátis com yt-dlp); Trends no período eleitoral completo; mapa do Brasil inteiro

**Mudou**
- **TikTok.**
  - `scripts/collect_tiktok.py` + workflow `tiktok.yml`, que roda 2× por dia (07h35 e 19h35) para dar uma segunda chance quando o TikTok bloqueia.
  - **Perfis:** os perfis de TikTok declarados ao TSE pelas chapas 13 e 22, titulares e vices (10 perfis).
  - **Coleta:** yt-dlp sem login, só metadados públicos; o texto dos comentários não é coletado. Leitura página a página, guardando o que já chegou. Até 3 tentativas por perfil, com espera.
  - **Preservação:** perfil bloqueado mantém os dados da última coleta boa e fica ⛔ no manifesto. Perfil sem vídeos públicos não conta como bloqueio.
  - **Data de publicação:** vem do próprio ID do vídeo.
- `scripts/build_tiktok.py`: as **mesmas regras do caderno 13** (temas, texto repetido, nuvem, cita adversário, pede voto), mais as hashtags e a **taxa de interação** ((curtidas + comentários + compartilhamentos) ÷ visualizações).
- **Caderno 15 · Conteúdo · TikTok por tema:**
  - situação de cada perfil;
  - quadros Lula (vermelho) × Flávio (verde), com filtros por tema;
  - linha do tempo de bolhas proporcionais às visualizações. As miniaturas do TikTok expiram em horas e não servem para isso;
  - nuvens e hashtags;
  - listas e **player oficial do TikTok** ao clicar.
- **Trends:**
  - período `eleitoral` = das convenções (20/07/2026, Lei 9.504, art. 8º) ao 2º turno (25/10), com fim "hoje" até a eleição;
  - passa a ser o padrão do caderno 14, com marcos no gráfico (convenções, início da campanha, 1º turno, 2º turno).
- **Mapa do Brasil inteiro** no caderno 12 (pedido: "por que só fez de SP?").
  - **Antes:** os 27 estados já existiam, mas só um por vez, e o mapa abria em SP.
  - **Agora:** "Brasil · todos os municípios" é o padrão, com a malha nacional `data/geo/2025/brasil_municipios.json` (5.571 municípios, 4,5 MB, mapshaper ~0,9%, também gerada pelo `build_geo.sh`).
  - Quadros, ranking e exportação funcionam no nível nacional.
- `.github/workflows/teste-tiktok-kwai.yml` continua como diagnóstico manual.

**Testado**
- ✅ Testes: 70 OK (novos: perfis do TSE por chapa, data pelo ID, mescla que preserva os bloqueados, processamento, janela do período eleitoral).
- ⛔→✅ TikTok, 3 runs no Actions:
  - `38811032377` e `38812495873`, **com** `yt-dlp[curl-cffi]`: 0 de 10 perfis ("Failed to parse JSON").
  - Run seguinte, **sem** curl-cffi: **7 de 10 perfis**, 710 vídeos no acervo (yt-dlp 2026.08.19).
  - Sem vídeos públicos: @canaltvcelular e @alfredogaspar. ⛔ @alfredogasparoficial ("Unable to extract secondary user ID").
- ✅ Caderno 15 com dados reais (desde 16/08):
  - **Lula:** 629 vídeos em 4 perfis, 7,914,508 visualizações, interação mediana 0.1183, cita o adversário 80, pede voto 57.
  - **Flávio:** 81 vídeos (só @flaviobolsonaro), 9,369,000 visualizações, interação mediana 0.0608, cita o adversário 17, pede voto 9.
  - Chromium 1400×900 e 390×844: 710 bolhas, sem rolagem horizontal.
- ✅ Trends com o período eleitoral (run de 2026-10-15 21:58 UTC): 9 consultas, sendo 3 eleitorais com 88 dias cada. Pico no dia do 1º turno.
- ✅ Mapa nacional: 5.571 municípios; Lula 53.722.151 votos (45,16% dos válidos), 1º lugar em 2.665 municípios. O total é **igual** ao validado na P2/P4 (sem exterior). Lado a lado: 11.142 formas.

**Pendente**
- TikTok é instável por natureza (bloqueios intermitentes do TikTok aos servidores). O manifesto registra cada coleta.
- @alfredogasparoficial não é lido pelo yt-dlp.
- Kwai continua sem caminho grátis (diagnóstico D1.0).

---

## [D1.0] 2026-10-15 — Diagnóstico: coleta gratuita de TikTok (yt-dlp) e Kwai (página pública e navegador automático)

**Por quê:** o usuário quer evitar a assinatura da Apify; testar se as ferramentas gratuitas dos repositórios de referência funcionam a partir do GitHub Actions.

**Mudou:** `.github/workflows/teste-tiktok-kwai.yml`, só manual (workflow_dispatch), sem gravar dados. Testa os perfis declarados ao TSE (`@lulaoficial` e `@flaviobolsonaro`) e publica o resultado como anotações do run.

**Testado (runs reais)**
- `38809517125` e `38809599505`: **TikTok via yt-dlp funcionou para os dois perfis.** Leu 10 vídeos de cada, com visualizações, curtidas, comentários e legenda. Exemplos: Flávio 7696508814228638997, 64.000 visualizações e 859 comentários; Lula 7696860113348431122, 22.600 visualizações.
- `38809722618`, com `yt-dlp[curl-cffi]`: Flávio ✅; **Lula ⛔** ("Failed to parse JSON", resposta vazia do TikTok). **Instável:** o TikTok bloqueia de forma intermitente os IPs do GitHub. O detalhe completo de um vídeo falhou sem curl-cffi ("no impersonate target").
- Kwai: a página pública responde HTTP 200, mas **sem nenhum dado de vídeo no HTML** (0 ocorrências de photoId, viewCount e caption) nos dois perfis.
  - Navegador automático (Playwright/Chromium): nenhuma resposta JSON com vídeos para @lulaoficial; **tempo esgotado (60 s)** para @flaviobolsonaro.
  - **Não há coleta gratuita do Kwai a partir do GitHub.**

**Pendente**
- Coletor de TikTok com yt-dlp: novas tentativas, último dado válido preservado, ⛔ quando falhar.
- Kwai continua dependendo de serviço pago (Apify ou ScrapeCreators) com teto de custo por execução, mediante autorização.

---

## [C6.0] 2026-10-15 — Livro de códigos de estratégias populistas (Bardin), CHD de Reinert e corpus para o IRaMuTeQ

**Por quê:** alinhar o caderno 13 ao método das leituras da disciplina, ou seja, à análise de conteúdo categorial (Bardin) e à análise de conteúdo automatizada (Cervi, 2018: IRaMuTeQ/Reinert) usadas por Montuori Fernandes (2021, 2022, 2026), e à concordância entre codificadores do IPIE (TP2025.2). Pedido do usuário.

**Mudou**
- `data/config/livro_codigos_populismo.json` (v1.1): 7 categorias com definição, fonte teórica, indicadores, exemplo e regra de exclusão.
  - **Categorias:** equivalência com o povo, contraposição ao inimigo, personalismo, antipolítica, ataque à imprensa, instituições em conflito (com direção ataque/defesa/UC) e anticiência.
  - **Simetria:** os indicadores são simétricos, e o populismo de esquerda e o de direita caem nas mesmas categorias.
  - **Códigos:** 0, 1 ou UC (incerto).
  - **Exclusões (v1.1):** acrescentadas depois de ler os primeiros resultados da pré-codificação. Antes delas:
    - "Sistema Único de Saúde" contava como *inimigo*;
    - "Lula fala com a imprensa" contava como *ataque à imprensa*;
    - Lula **defendendo** vacinas contava como *anticiência*. Por isso "vacina" e "especialistas" saíram dos indicadores.
- `scripts/corpus_populismo.py`:
  - **pré-codificação** por vídeo, com o trecho que disparou → `data/youtube/populismo.json`, marcada como sugestão, não resultado;
  - **corpus no formato do IRaMuTeQ** (`**** *cand_ *mes_ *sem_ *formato_ *canal_ *pop_…`) → `data/corpus/youtube_candidatos_iramuteq.txt`;
  - segmentos de ~40 palavras → `youtube_candidatos_segmentos.csv`;
  - **amostra estratificada de 200 vídeos** (candidato × mês, semente 42) para dois codificadores → `data/codificacao/amostra_populismo_v1.csv`. A pré-codificação fica num arquivo separado e a amostra é gerada uma única vez, nunca sobrescrita.
- `scripts/chd_reinert.py`: CHD de Reinert em Python/numpy, com classificação simples.
  - **Procedimento:** 1º fator da análise de correspondência; corte de maior χ²; realocação dos segmentos; formas e variáveis características por χ² ≥ 3,84; segmentos característicos.
  - **Diferenças declaradas em relação ao IRaMuTeQ:** sem lematização; classificação simples, não dupla.
  - **Classe mínima de 8% dos segmentos, com teste de sensibilidade gravado no JSON.** Com 3% e 5%, várias classes se formavam por nomes próprios de convidados (Dani Marques, Jeffrey Chiquini) e não tinham leitura temática.
  - Os nomes das classes ficam para o pesquisador (`nome: null`).
- `scripts/concordancia.py`: kappa de Cohen por categoria e precisão/cobertura da pré-codificação contra o consenso humano. Sem as duas planilhas de codificadores, grava "aguardando codificação humana" (bloqueio, não sucesso).
- Caderno 13, bloco "Estratégias discursivas e classes de discurso":
  - barras Lula × Flávio por categoria, com ⛔ de validação pendente;
  - dendrograma das classes;
  - cards das classes com formas, χ², divisão Lula × Flávio e segmentos característicos;
  - downloads do corpus IRaMuTeQ, segmentos, livro de códigos, amostra e CHD.
- O workflow do YouTube roda os três scripts todos os dias, depois da coleta.
- `tests/test_populismo_chd.py`: 10 testes. Cobrem:
  - simetria esquerda/direita e exclusões;
  - trecho registrado;
  - limpeza do corpus para o IRaMuTeQ;
  - segmentos e variáveis;
  - amostra estável e proporcional;
  - a CHD separando dois vocabulários sintéticos;
  - o sinal do χ²;
  - o kappa contra um valor conhecido (po = 0,7 e pe = 0,5 → κ = 0,4);
  - precisão e cobertura.
  - Total: 64.

**Testado**
- ✅ `python -m unittest discover -s tests`: 64 OK.
- ✅ Corpus real (coleta do YouTube de 2026-10-15, vídeos desde 16/08): Lula 784 vídeos, 159 com alguma categoria; Flávio Bolsonaro 402 vídeos, 58 com alguma categoria. 1.416 segmentos.
- ✅ CHD: 1330 de 1416 segmentos classificados (93.9%), 792 formas ativas. Classes: classe 1 (29.2%, Lula 34.7%): flavio, bolsonaro, lula, vencer, flaviobolsonaro, vote22; classe 2 (8.0%, Lula 76.4%): entrevista, tapete, imprensa, participa, professora, pastor; classe 3 (18.0%, Lula 82.8%): 6x1, escala, mundo, mostrar, recado, segundo; classe 4 (8.0%, Lula 89.6%): presidente, sus, medidas, novas, bolso, sanciona; classe 5 (8.0%, Lula 77.4%): seguranca, lei, acima, proteger, crime, territorio; classe 6 (28.9%, Lula 82.6%): futuro, brasil, pais, educacao, oportunidades, brasileiro.
- ✅ Chromium headless (1400×900 e 390×844): 7 barras, 6 classes e o dendrograma; sem rolagem horizontal (corrigida a quebra das formas nos cards).
- ⚠️ **Nada da pré-codificação está validado:** a precisão real de cada categoria só sai depois da codificação humana. O kappa está ⛔ pendente.
- ⚠️ CHD não conferida no IRaMuTeQ: o CRAN e o `rainette` estão bloqueados pela rede deste ambiente. Conferência pendente com o corpus exportado.

**Pendente**
- Duas pessoas codificarem a amostra (`codificador_A_v1.csv` e `codificador_B_v1.csv`) → kappa e precisão.
- Rodar o mesmo corpus no IRaMuTeQ e comparar as classes.
- O pesquisador nomear as classes.

---

## [P4.1] 2026-10-15 — Geografia do Voto sem dependência externa, com nomes, cores e 2022 | 2026 lado a lado; favicon

**Mudou**
- Caderno 12 (pedido do usuário: “arrumar a página geografia do voto”).
  - **Sem Leaflet e sem mapa-base da CARTO.** O mapa é desenhado em SVG direto da malha do IBGE que já está no repositório (`data/geo/2025/mun_UF.json`). Projeção equiretangular corrigida pela latitude média da UF.
    - Antes, se o CDN (unpkg) ou o servidor de mapa-base falhasse, o mapa ficava em branco; foi o que aconteceu no teste deste ambiente.
    - Agora funciona offline (era um critério do dossiê).
    - Zoom pela roda ou pelos botões, arrastar para mover, dica ao passar o cursor, clique para a ficha.
  - **Candidaturas pelo nome**, ordenadas por votos no ano, a partir de `elections.json/candidates` (TSE): “Lula (13)”, “Flavio Bolsonaro (22)”… Antes eram só “Número 13/22”.
  - **Cores:** Lula (13) em escala vermelha e nº 22 em escala verde (padrão adotado nos cadernos 13 e 14). Demais números continuam em azul.
  - Novo indicador **“Quem venceu · 13 × 22”**: margem em pontos percentuais, divergente vermelho/verde. É o padrão ao abrir.
  - Novo recorte **“Lado a lado · 2022 | 2026”**: dois mapas com o mesmo zoom. Era uma pendência do dossiê.
  - Variação 2022 → 2026 com escala divergente (cor do candidato = ganho; cinza = perda).
  - **Ficha municipal** com os 3 primeiros colocados de cada ano (% e votos), a variação e o código IBGE.
  - **Ranking da UF**: 5 maiores e 5 menores valores do indicador. Clicar abre a ficha.
  - Quadro novo: “municípios em 1º lugar”.
- **Favicon** (imagem enviada pelo usuário) em `assets/`: `favicon.ico`, PNG 32 px e 180 px (apple-touch). Ligado no Atlas e no `index.html`.

**Testado**
- ✅ Chromium headless (1400×900 e 390×844), com o CDN bloqueado:
  - SP: 645 municípios desenhados; lado a lado: 1.290 formas; RS: 497. Sem erro de JavaScript e sem rolagem horizontal.
- ✅ Ficha de São José do Rio Preto conferida com `elections.json`:
  - 2026: Flavio Bolsonaro 62,46% (156.807), Lula 28,39% (71.275), em 251.050 válidos;
  - 2022: Jair Bolsonaro 60,91%, Lula 29,34%;
  - variação de Lula: −0,95 pp.
- ✅ SP 2026: Lula com 9.505.413 votos (38,20% dos válidos), 1º lugar em 40 de 645 municípios. Mesmos números do quadro anterior, agora com o nome.
- ✅ Testes Python: 54 OK (o mapa é só front-end; nenhum script de dados mudou).

**Pendente**
- O nome vem como o TSE grava (“Flavio”, sem acento).
- Visão do Brasil inteiro por município (5.571 formas, ~17 MB) não foi ativada, por peso no celular. Segue por UF.
- Conferência de 3 municípios contra as páginas oficiais do TSE (critério do dossiê) continua pendente: só conferi contra a nossa base.

---

## [C5.0] 2026-10-15 — Rede de influenciadores do YouTube (Lula vermelho × Flávio verde) e caderno 14 · Google Trends

**Mudou — influenciadores (caderno 13)**
- `scripts/collect_influenciadores.py` + `data/config/influenciadores_youtube.json`. Coleta diária dentro do workflow `seguidores-youtube.yml`, com a mesma chave `YOUTUBE_API_KEY`:
  - **Busca** no YouTube (search.list) por “Lula” e “Flávio Bolsonaro” em três janelas: mais vistos desde 16/08, mais vistos em 7 dias e mais recentes em 3 dias. Depois, videos.list e channels.list.
  - **Teto de 2.500 unidades de cota por execução** (de 10.000/dia).
  - **Acumula** em `data/youtube/influenciadores/videos.csv.gz` e `canais.csv`.
- **Exclusões:**
  - canais de campanha declarados ao TSE;
  - categorias Guias e estilo (o molusco “lula”), Música, Esportes e Jogos;
  - termos de culinária;
  - vídeo sem o nome no título ou na descrição;
  - canal com menos de 10.000 inscritos públicos (assim, pessoa comum não entra).
- **Níveis por vídeo, iguais para os dois** (definição do usuário, como no Flaviômetro):
  - **1 · falou de**: nome, @, hashtag ou número como voto (“Flávio 22”, “#lula13”);
  - **2 · pediu voto**: “vote 22”, “dia 25 é Flávio”, “vote 13”, “dia 25 é Lula”, “voto no Lula”…
  - O trecho que disparou cada classificação vai para a planilha, para conferência humana.
  - As regras são reaplicadas a todo o acervo a cada execução: mudar a regra não exige coletar de novo.
- `scripts/build_rede_influenciadores.py`: rede bipartida, com os candidatos e até 200 canais (os que mais falam deles), posição por ForceAtlas2 LinLog.
  - Cores: **Lula #c8102e (vermelho), Flávio #1f8a3b (verde)**, canais na mistura.
  - Arestas: tracejada = falou; cheia = algum vídeo pediu voto.
  - Saídas: `rede.json`, `rede.gexf`, `rede_nos.csv`, `rede_arestas.csv` e `videos_validos.csv` (link, nível e trecho de cada vídeo).
- Página: bloco “Quem fala de Lula e de Flávio”, com quadros-resumo, rede (zoom, arrastar, painel com os vídeos mais vistos do canal e seus níveis), tabela ordenável de canais e downloads.

**Mudou — Google Trends (caderno 14, novo)**
- A coleta já rodava desde a versão C1.0, mas **não aparecia em nenhum caderno** (pendência registrada). Agora aparece.
- `scripts/build_trends_caderno.py` consolida a coleta mais recente com status ok em `data/trends/caderno.json`. Roda no `trends.yml` depois de cada coleta.
- Caderno 14 “Buscas · Google Trends”, com Lula vermelho e Flávio verde:
  - consultas: 2º turno (tópicos), 1º turno (5 mais votados) e 2º turno (palavras soltas); períodos de 7 dias (por hora) e 3 meses (por dia);
  - quadros com média, pico e nº de UFs em que lidera;
  - série temporal, com o trecho incompleto tracejado;
  - mapa em grade das 27 UFs (divisão Lula·Flávio) e tabela por UF;
  - links para os CSVs originais e o tópico exato consultado.

**Testado**
- ✅ `python -m unittest discover -s tests` — 54 testes OK. Os novos cobrem:
  - os níveis com 12 frases reais e de controle (“Flávio Dino” não conta; “Olê olá Lula 13” = falou; “Eu voto no Flávio Bolsonaro” = pediu voto);
  - o molusco;
  - o teto de cota;
  - o bloqueio sem chave;
  - a rede bipartida com corte por inscritos;
  - o consolidador do Trends (usa a coleta ok mais recente; vazio vira null, não zero).
- ✅ Run `38802451628` (Actions, 2026-10-15 ~20:30 UTC): coleta de influenciadores ok.
  - **Cota usada: 2.023**.
  - 870 vídeos retornados, 821 válidos.
  - Exclusões: 31 de canais de campanha, 8 Esportes, 5 Música, 2 Jogos, 1 Guias e estilo e 2 sem menção.
  - 239 canais.
- ✅ Rede (gerada localmente com as regras finais, sobre esse acervo): **200 canais, 779 vídeos, 312 arestas**.
  - Lula: 161 canais e 551 vídeos; só falaram dele 49 canais; **1 vídeo pediu voto** (TV Fórum).
  - Flávio: 151 canais e 543 vídeos; só falaram dele 39 canais; **3 pediram voto** (Deltan Dallagnol “vote Flávio Bolsonaro 22”; Sem Freio Clips com Rui Costa Pimenta “eu voto no Flávio”; Itatiaia).
  - 112 canais falaram dos dois, quase todos veículos de notícia (UOL, CNN Brasil, Itatiaia, SBT News…).
- ⚠️ Conferência manual dos 6 casos “pediu voto” da 1ª versão da regra encontrou erro: “Flávio 22” numa notícia da CNN contava como pedido de voto. Corrigido para nível 1 (número como voto = “falou”, como na definição do usuário).
- ⚠️ Limite que permanece: a Itatiaia **noticia** que Flávio pediu voto e a regra por palavras conta como pedido. O trecho está na planilha.
- ✅ Trends (coleta de 2026-10-15 18:29 UTC), 2º turno por tópicos, 7 dias:
  - média Lula 62 × Flávio 44;
  - Lula lidera nas 27 UFs, com divisão entre 55·45 (ES) e 61·39 (AM);
  - por palavra solta (que inclui o molusco), Lula 62 × Flávio 15. Mostra por que o padrão é o tópico.
- ✅ Chromium headless (1400×900 e 390×844):
  - caderno 13: rede de influenciadores com 202 pontos, 312 linhas e 200 linhas na tabela;
  - caderno 14: 27 UFs, séries de 2 e 5 termos e tabela;
  - sem rolagem horizontal.

**Pendente**
- O nível “pediu voto” por palavras confunde notícia com pedido. Para separar, só com leitura humana de amostra ou IA validada.
- “Falar” não mede posição (a favor/contra).
- O acervo de influenciadores cresce a cada dia. A busca do YouTube devolve no máximo ~500 resultados por consulta, então a cobertura é amostral, não censo.
- Trends: ainda não há histórico de várias coletas no caderno (mostra só a mais recente; as anteriores ficam nas pastas datadas).

---

## [C4.2] 2026-10-15 — Caderno 13: análise de redes (coocorrência) com tabela, planilhas e GEXF para o Gephi

**Mudou**
- `scripts/build_rede.py` (networkx 3.6.1 + numpy 2.3.4, versões fixas no workflow). Usa o mesmo texto útil do `build_conteudo`: sem links, sem rodapés repetidos, sem o nome do canal, sem o nome do próprio candidato, sem o pacote fixo de tags.
  - **Nós:** palavras e #tags presentes em 8+ vídeos (até 150).
  - **Arestas:** dois termos no mesmo vídeo. O peso é o nº de vídeos em comum, com mínimo 3. Cada nó guarda até 8 arestas, as mais fortes.
  - **Medidas:** comunidades por **Louvain**, posição por **ForceAtlas2 LinLog** (partindo de um layout de mola com semente) e intermediação (*betweenness*). Semente fixa 42, então a mesma entrada gera a mesma rede. Se o layout gerar uma posição inválida (NaN), a rede não é publicada.
- Saídas em `data/youtube/`:
  - `rede.json`: desenhada na página;
  - `rede.gexf`: abre direto no Gephi, já com posição, cor e tamanho;
  - `rede_nos.csv` e `rede_arestas.csv`: no formato do *Importar planilha* do Gephi (Id/Label; Source/Target/Weight/Type);
  - `rede_videos_termos.csv`: matriz de origem, com os termos da rede que cada vídeo contém e o link do vídeo. Permite refazer à mão o peso de qualquer aresta.
- Caderno 13, novo bloco **“Que assuntos andam juntos em cada campanha”** (no fim da página):
  - **Rede:** cor por candidato (azul ↔ terracota) ou por comunidade; tamanho do ponto = nº de vídeos. Arrastar move, a roda do mouse aproxima. Passar o mouse ou clicar destaca os vizinhos; um painel mostra os termos que aparecem junto e a comunidade. Ao lado, as 8 maiores pontes por intermediação.
  - **Tabela de nós** e **tabela de arestas**, ordenáveis e com filtro por termo.
  - Botões para baixar as quatro planilhas e o GEXF, com instruções de importação no Gephi.
- `build_conteudo.py`: mais palavras funcionais na lista de exclusão (neste, desse, nisso…). Os topos da nuvem não mudaram.
- `seguidores-youtube.yml`: instala `networkx==3.6.1` e `numpy==2.3.4` e roda `build_rede.py` depois da classificação, todo dia.
- `tests/test_build_rede.py`: 3 testes:
  - peso, lado e corte por mínimo;
  - rede idêntica em duas execuções e comunidades separadas;
  - execução completa em que o peso de **toda** aresta do CSV é refeito a partir da matriz vídeo × termos.
  - Total: 45.

**Testado**
- ✅ `python -m unittest discover -s tests` — 45 OK.
- ✅ `python scripts/build_rede.py` na coleta de 2026-10-15T20:06:19Z (run `38799228938`), com 784 vídeos de Lula e 401 de Flávio. Resultado: **148 nós, 797 arestas, 5 comunidades, modularidade 0,272**.
  - C1 (57 nós, lado médio 0,73): brasil, presidente, país, futuro, vote.
  - C2 (29 nós, 0,88): vida, família, mulheres, 6x1, escala.
  - C3 (26 nós, 0,87): povo, brasileiro, flavio, bolsonaro, história, sus.
  - C4 (20 nós, **0,25 — o grupo de Flávio**): vencer, governo, lula, verdade, #vote22, #direita.
  - C5 (16 nós, 0,86): segurança, bets, crime, famílias.
  - Maior ponte: “brasil” (intermediação 0,53).
- ✅ Conferência manual: o peso de 3 arestas refeito pela matriz vídeo × termos bateu com o CSV (#direita–#eleicoes 6; brasil–mundo 13; brasileiro–ninguém 6).
- ✅ `rede.gexf` relido com `networkx.read_gexf`: 148 nós, 797 arestas. **Não abri no Gephi** (não há Gephi neste ambiente).
- ⛔→✅ 1ª execução no Actions (run `38801248459`) falhou nos testes: os layouts do networkx precisam de `numpy`, que não vem junto. Corrigido fixando `numpy==2.3.4` no workflow. A 2ª execução (run `38801414101`) passou em todos os passos, coletou de novo (2026-10-15T20:22:46Z) e regenerou a rede sozinha: 148 nós, 797 arestas, 5 comunidades, modularidade 0,272 (iguais à rede gerada localmente). Reproduzido localmente em Python 3.12 + networkx 3.6.1 + numpy 2.3.4: 45 testes OK e **rede idêntica** à gerada em Python 3.13 + numpy 2.5.3 (mesmas posições, comunidades e arestas).
- ✅ Chromium headless (1400×900 e 390×844):
  - 148 pontos e 797 linhas; tabela de nós com 148 linhas e tabela de arestas com 797;
  - o filtro “seg” deixa 1 nó; o clique destaca os vizinhos;
  - sem rolagem horizontal no celular.
- ⚠️ O networkx emite um aviso numérico interno no LinLog (divisão por distância zero). Conferi que as 148 posições são finitas, e a checagem de NaN bloqueia a publicação se isso mudar.

**Limites**
- Coocorrência no mesmo vídeo não é relação semântica: termos frequentes viram centro por volume.
- Lula tem quase o dobro de vídeos e descrições mais longas, então domina a rede. Compare a estrutura, não o tamanho. A página avisa isso.

---

## [C4.1] 2026-10-15 — Caderno 13: mapa de tags (Lula × Flávio) e coleta das tags dos vídeos

**Mudou**
- `scripts/collect_youtube.py`: grava a coluna nova `tags` (as tags que o próprio canal colocou em cada vídeo, `snippet.tags`). Vem na mesma chamada `videos.list`, **sem cota extra**.
- `scripts/build_conteudo.py`:
  - `mapa_tags`: para cada tag, em quantos vídeos de cada candidato ela aparece. Fontes: tags do canal + #hashtags do título e da descrição útil. Normalizadas sem acento e sem espaço. Mínimo 2 vídeos, top 90.
  - **Pacote fixo**: o mesmo conjunto exato de tags repetido em 10+ vídeos do mesmo canal é tratado como etiqueta aplicada em lote. Fica fora do mapa e é publicado à parte (`pacotes_de_tags`), como já se fazia com os rodapés das descrições.
- Caderno 13: bloco **“Mapa de tags”** em três zonas: só Lula | usadas pelos dois (barra dividida na proporção) | só Flávio. Os blocos têm tamanho proporcional ao nº de vídeos. Clicar numa tag filtra a linha do tempo, as listas e os quadros. Abaixo ficam os pacotes fixos de cada canal, com a lista de tags.
- Testes: +3 (tag do canal e hashtag unificadas, pacote fixo sai do mapa e abaixo do limiar não é pacote, contagem por candidato). Total: 42.

**Testado**
- ✅ `python -m unittest discover -s tests` — 42 OK.
- ✅ Run `38799228938` (workflow `seguidores-youtube.yml`, disparado em 2026-10-15 20:06 UTC) concluído com sucesso, já com a coluna `tags`. Resultado:
  - Lula: 784 vídeos; 84 com tags.
  - Flávio: 401 vídeos; 162 com tags.
- ✅ Achado nos dados reais:
  - Canal “Lula”: o mesmo pacote de 19 tags em **78** vídeos (inclui “Eleições 2022”, “Lula inocente”, “Lula em Salvador”, “FM 103.9”).
  - Canal “TV Celular Flavio Bolsonaro”: pacote de 28 tags em **124** vídeos (inclui “Ustra”, “Olavo de Carvalho”, “Bolsomito”, “Karl Marx”, “Presidente 2022”).
  - Fora dos pacotes, Lula não tem nenhuma tag própria em 2+ vídeos. Flávio tem 39: #vote22 (24 vídeos), #direita (22), #tvcelular (14), #forapt (12), #eleicoes (10), #bolsonaro (9) e outras.
  - Em comum: #flaviobolsonaro (Lula 1, Flávio 46), #eleicoes2026 (1·6), #seguranca (1·5), #lula (1·2).
- ✅ Chromium headless (1400×900 e 390×844): 43 blocos, clique em #flaviobolsonaro filtra para 13 itens nas listas e 41 miniaturas; sem rolagem horizontal no celular.
- Os números de temas mudaram pouco com a coleta nova (Lula 784 vídeos, economia 102; Flávio inalterado).

**Limites**
- A tag é o que o canal declara ao YouTube, não o conteúdo de fato do vídeo. Pacotes antigos (2022) aparecem em vídeos de 2026.

---

## [C4.0] 2026-10-15 — Caderno 13: conteúdo do YouTube por tema, linha do tempo e nuvem de palavras (Lula × Flávio)

**Mudou**
- Novo **caderno 13 · Conteúdo · YouTube por tema** em `ODI_Atlas_v15_MVP.html`, no padrão editorial ODI (fita do caderno, manchete serifada, cards):
  - filtros por tema (com contagem), “só pedidos de voto” e “só citam o adversário”;
  - quadro por candidato: vídeos no filtro, visualizações somadas, nº que cita o adversário, nº que pede voto e barras por tema;
  - **nuvem de palavras por candidato** (assuntos mais abordados);
  - **linha do tempo horizontal por semana de campanha** (referência visual enviada pelo usuário): miniaturas de Lula acima do eixo, de Flávio abaixo, até 24 por semana ordenadas por visualizações, com “+N” para o restante;
  - listas lado a lado dos 12 vídeos mais recentes no filtro e painel de detalhe com link para o YouTube.
  - O caderno lê `data/youtube/conteudo.json` só quando é aberto. Sem a base, mostra ⛔ com o motivo (não mostra números de exemplo).
- `scripts/build_conteudo.py` (roda no workflow `seguidores-youtube.yml` logo após a coleta diária):
  - classificação por **dicionário aberto** (`data/config/temas_youtube.json`), não por IA, sobre título + descrição;
  - antes de classificar: remove links e trechos de descrição repetidos em 10+ vídeos do mesmo canal (rodapés e textos institucionais; emojis agora também separam trechos);
  - **nuvem**: em quantos vídeos cada palavra, hashtag ou par de palavras aparece; mínimo 3 vídeos, top 60; exclui palavras funcionais, meses, termos de formato (“propaganda eleitoral”, “acesse”, “inscreva-se”), o nome do próprio candidato e o nome/hashtag do próprio canal. Par de palavras absorve a palavra solta quando cobre 80%+ dela (ex.: “escala 6x1”).
- **Correção de bug:** termos com `*` (prefixo, ex.: `trabalhador*`, `petista*`) **nunca funcionaram** porque `norm()` removia o `*` antes da checagem. O teste novo pegou; corrigido. Efeito nos números reais: Lula `sem_tema` 552 → 529, economia 81 → 101; Flávio `sem_tema` 317 → 301, economia 9 → 17. Conferi na base real todas as palavras que cada prefixo captura: nenhum falso positivo encontrado (ex.: `ato*` → ato/atos; `medic*` → medicamentos/médicos).
- `tests/test_build_conteudo.py`: 9 testes (prefixo e palavra inteira, pedido de voto só com o próprio número, link não vira tema, rodapé repetido removido, emoji separa trecho, nuvem conta 1x por vídeo e exclui o próprio nome, par absorve palavra, hashtag sem par, execução completa com CSV sintético).

**Testado**
- ✅ `python -m unittest discover -s tests` — 39 testes OK.
- ✅ `python scripts/build_conteudo.py` sobre `data/youtube/videos_latest.csv.gz` da coleta de 2026-10-15T19:54:20Z (run `38797622447`; sha256 do CSV descompactado `b828137b…952f`):
  - Lula: 783 vídeos; sem tema 529; economia 101; educação 44; segurança 41; religião e valores 38; saúde 34; cita o adversário 66; pede voto 21.
  - Flávio Bolsonaro: 401 vídeos; sem tema 301; agenda de campanha 29; segurança 20; economia 17; eleição e instituições 12; religião e valores 10; cita o adversário 67; pede voto 20.
  - Topo da nuvem: Lula — brasil (202 vídeos), povo (107), presidente (94), país (56), brasileiro (54), futuro (52), flavio (51); Flávio — brasil (135), vencer (55), lula (52), governo (35), vote (28), #vote22 (24), #direita (22).
- ✅ Chromium headless (1400×900 e 390×844): caderno carrega, 120 palavras nas duas nuvens, 9 semanas, 24 itens nas listas, filtro “Segurança” reduz a linha do tempo, painel de detalhe abre, sem rolagem horizontal da página no celular.
- ⚠️ No ambiente de teste as miniaturas (`i.ytimg.com`) não carregam por bloqueio de rede; no navegador do usuário/GitHub Pages elas vêm do próprio YouTube. Não conferido visualmente com imagens.

**Limites (também escritos na página)**
- Dicionário erra ironia e contexto; ~2/3 dos vídeos de Lula e ~3/4 dos de Flávio ficam “sem tema identificado” (muitos são Shorts com título curto).
- “Cita o adversário” e “pede voto” são marcas por regra; não medem apoio, alcance ou intenção de voto.
- Nuvem mede frequência de termos, não sentimento nem posição.

**Pendente**
- 🔜 Classificação por IA (Claude) validada contra este dicionário, se aprovada (custo e amostra de conferência humana antes).
- 🔜 Transcrição/legendas não são usadas (a API oficial não entrega legenda de terceiros sem OAuth do dono do canal).

---

## [C3.0] 2026-10-15 — YouTube pela API oficial; correção de URLs sem esquema

**Mudou**
- `scripts/collect_youtube.py` + workflow `seguidores-youtube.yml` (diário, 07h20): inscritos dos **15 canais** declarados pelas chapas presidenciais, pela YouTube Data API v3 (`channels.list`, 1 unidade de cota por canal). Chave só pelo segredo `YOUTUBE_API_KEY`. Saída `data/seguidores/youtube_latest.csv`. Canal com contagem oculta fica sem número.
- **Vídeos:** todos os vídeos de cada canal publicados desde o início da campanha (16/08/2026), com visualizações, curtidas e número de comentários, em `data/youtube/videos_<data>.csv.gz` (uma foto por dia). Cota estimada: poucas unidades por canal. O **texto dos comentários não é coletado** (dados de pessoas comuns; LGPD).
- Caderno 02 carrega as duas coletas automáticas (Apify e YouTube), cada card indicando a origem.
- **Correção:** o TSE grava algumas URLs sem `https://` (ex.: `INSTAGRAM.COM/BRASILCOMLULA`). O número era coletado mas o card não o reconhecia. Agora coletores gravam a URL completa (`net.with_scheme`) e o caderno 02 aceita URL sem esquema. O `latest.csv` de hoje foi corrigido só na coluna `url` (3 linhas; números inalterados).
- 30 testes (inclui paginação da lista de vídeos parando ao passar da data).

**Testado**
- ✅ Navegador headless, caderno 02 · Lula: “Coletado” passou de 11 para 12 (Instagram BRASILCOMLULA, 1.028.524).
- ✅ Run `38796649549` (após o usuário cadastrar `YOUTUBE_API_KEY`): **12 de 15 canais** com inscritos; **2.125 vídeos** publicados desde 16/08/2026 com estatísticas; **cota usada: 115** de 10.000.
- ⚠️ 3 canais não encontrados: os 2 declarados por ID em MAIÚSCULAS (Augusto Cury, Alfredo Gaspar — como previsto) e `@tv.celular` (handle inexistente). Registrados no manifesto, não adivinhados.
- ⚠️ O YouTube arredonda publicamente os inscritos (ex.: Lula 1.820.000; Flávio 1.510.000).

**Pendente**
- ⚠️ 2 canais declarados por ID (Augusto Cury, Alfredo Gaspar) estão em MAIÚSCULAS no TSE e o ID do YouTube diferencia maiúsculas: podem não ser encontrados. Ficarão registrados no manifesto, não adivinhados.

---

## [C2.1] 2026-10-15 — Teto mensal da coleta Apify para US$ 10

**Mudou**
- `data/config/seguidores_meta.json`: `teto_mensal_usd` de 5,00 para **10,00**, mantendo a coleta **diária** (07h10) e o teto de US$ 0,50 por execução. Decisão do usuário (“pode ajustar”) após a primeira execução custar US$ 0,32.

**Por quê:** a US$ 0,32/dia o mês sai ~US$ 9,70; com teto de US$ 5 a coleta pararia por volta do 15º dia, no meio da reta final da eleição (2º turno em 25/10).

**Testado**
- ✅ Testes (27) passando; o bloqueio por teto continua coberto por `test_teto_mensal_bloqueia_antes_de_gastar`.

**Pendente**
- Se o custo por execução subir (mais perfis ou mudança de preço da Apify), o teto mensal volta a bloquear sozinho; o custo real de cada dia fica em `data/seguidores/manifesto-*.json`.

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
