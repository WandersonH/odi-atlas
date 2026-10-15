# Registro de versões — ODI Atlas

Toda mudança no repositório entra aqui, da mais recente para a mais antiga. Cada entrada diz **o que mudou, como foi testado, o que ficou pendente** e onde está a evidência. "Testado" só vale para o que foi realmente executado.

Legenda de estado: ✅ concluído e verificado · ⚠️ concluído com ressalva · ⛔ bloqueado · 🔜 planejado (não implementado)

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
- ⛔→✅ 1ª execução no Actions (run `38801248459`) falhou nos testes: os layouts do networkx precisam de `numpy`, que não vem junto. Corrigido fixando `numpy==2.3.4` no workflow. Reproduzido localmente em Python 3.12 + networkx 3.6.1 + numpy 2.3.4: 45 testes OK e **rede idêntica** à gerada em Python 3.13 + numpy 2.5.3 (mesmas posições, comunidades e arestas).
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
