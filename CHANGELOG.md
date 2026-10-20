# Registro de versões — ODI Atlas

Toda mudança no repositório entra aqui, da mais recente para a mais antiga. Cada entrada diz **o que mudou, como foi testado, o que ficou pendente** e onde está a evidência. "Testado" só vale para o que foi realmente executado.

Legenda de estado: ✅ concluído e verificado · ⚠️ concluído com ressalva · ⛔ bloqueado · 🔜 planejado (não implementado)

## C19.78 — Padrão de análise para todos os casos; páginas separadas; "Em alta agora" permanente; checagens do período todo (2026-10-20) 🔜

- Pedidos do usuário (20/10, 13h20–13h26):
  - "Em alta" na página de Trends.
  - Checagens do período todo.
  - Nos casos, sempre redes (circulação e comentários) e IRaMuTeQ.
  - O caso 002 não tinha uma tela de linha de tendência e de estados: "se já temos um padrão de análise, os casos devem desenvolver dados".
  - A página do caso Ana Clara estava misturada com a do "ladrão" no título.
  - O fact-check é padrão para todos os casos.
- `redes_caso.py` (padrão dos casos):
  - Rede de circulação: canais do YouTube, veículos e contas do TikTok ligados ao termo ou hashtag que os trouxe; perfis com menos de 10 mil aparecem como código P0001.
  - Redes dos comentários: palavras que aparecem juntas e quem responde a quem, com autores sempre como código A0001.
  - CHD de Reinert nos comentários e corpus IRaMuTeQ no privado.
  - GEXF de cada rede. O desenho distribui cada componente em área própria; o layout anterior jogava componentes pequenos para os cantos.
  - Teste local (privado de 20/10): 005 com circulação de 238 nós, palavras de 1.039, respostas de 907 autores e 6 classes; 002 com 77, 10, 24 e 5 classes.
- Casos 001 e 003 entram no mesmo padrão (Trends, YouTube, imprensa, checagens, redes, classes): `collect_caso_busca.py` com configuração de cada um. O workflow diário roda 001, 002, 003 e 005.
- Página: cada caso numa aba própria do caderno 08 (#brasilinteiro, Consulta depreciativa no Google, Ninguém morre nos devendo, Caso Ana Clara). Cada aba tem título e contexto próprios e os blocos big numbers, debate (quando houver), Trends (linha em 5 anos, 12 meses e 7 dias; controles; relacionadas; tabela por estado com barras para cada termo), YouTube, comentários, redes, classes, imprensa e checagens. Filtro do 002 sem "pesquis" (trazia vídeo de assalto).
- "Em alta agora" permanente: depois da janela do debate, `collect_trends_agora.py` grava `data/trends/agora/em_alta.json` e acumula `em_alta_historico.csv`, com matérias do topo do Google Notícias para os termos de Política; o consolidado do debate fica congelado. O workflow passou de 15 em 15 min para de hora em hora. Novo painel no topo da página do Google Trends.
- Checagens: janela padrão de 60 para 400 dias (período todo da campanha e pré-campanha).
- Testes: `TestEmAlta` e `TestRedesCaso` (privacidade de nomes e códigos); suíte OK. Execuções reais: próxima entrada.
- Execuções: "Em alta agora" (run 39457956837) leu 35 termos em 4 h e 230 em 24 h, 15 de Política. A primeira tentativa das checagens com 400 dias (run 39457959969) falhou nos testes: `TestRedesCaso` precisava de numpy, que esse workflow não instala. Corrigido: o teste é pulado sem numpy/networkx (suíte conferida das duas formas).

## C19.77 — Casos 002 ("onde mora/nasceu o ladrão") e 005 (caso Ana Clara): coleta grátis de buscas, YouTube, imprensa e checagens (2026-10-20) ⚠️

- Pedidos do usuário (20/10, 12h45–12h47): ativar o caso 002 com o escopo sugerido e criar o caso Ana Clara ("buscas e vídeos do YouTube sobre o assunto e o alcance total"; o caso foi citado por Lula no debate).
- `collect_caso_busca.py` + `build_caso_busca.py` + `casos-busca.yml` (diário 11h53 e manual, grátis), configuração por caso:
  - Google Trends: variantes e controles separados, em 5 anos, 12 meses e 7 dias; UF e consultas relacionadas em 12 meses.
  - YouTube: busca pela API, filtro no título e descrição, e comentários dos 30 mais vistos (só no privado).
  - Google Notícias, checagens (Fact Check Tools) e cópia no Internet Archive das páginas de referência (artigo de Victor Gabry de 2022, para o 002; Agência Pública, para o 005).
  - Público (`data/casos/<id>/busca.json`): agregados; vídeos com nome só de canais com 10 mil inscritos ou mais.
- Caso 005: localiza na transcrição do debate (privada) as falas que citam o caso, com minuto e orador da codificação de turnos. Teste local: 4 falas, aos 31,7 min (Lula), 33,2 (Flávio Bolsonaro), 34,0 (Lula) e 35,1 (Lula).
- Caso 002: bateria manual de consultas ao Google com modelo de registro em `data/casos/002/bateria_modelo.csv`. Não há API do Google para isso: a Custom Search API recusou o projeto, e o Google bloqueia robôs.
- `casos.json`: 002 ativo, com título neutro e hashtags do TikTok; 005 novo, com contexto e fonte da Agência Pública. TikTok e Google dos dois pelo pipeline de casos (grátis).
- Testes: `TestCasoBusca`; `test_casos` ajustado; suíte OK.
- Primeira execução (run 39452047078, casos de busca; runs 39452052039 e 39452056962, TikTok e Google pelo pipeline de casos):
  - 005: 159 vídeos no YouTube, 7.300.612 visualizações somadas, 5.065 comentários lidos, 89 notícias, 0 checagens, 4 falas no debate. Página da Pública arquivada no Internet Archive em 20/10. TikTok: 101 vídeos (#casoanaclara e #pesquiseocasoanaclara).
  - 002: 20 vídeos (13 de 2022), 92.209 visualizações, 122 comentários, 0 notícias, 0 checagens. TikTok: 58 vídeos em #ondenasceuoladrao; 0 em #ondemoraoladrao e em #quantosanostemoladrao. ⛔ Arquivo do artigo de 2022: sem cópia, e o pedido de cópia falhou (URLError).
  - ⛔ Trends recusou algumas janelas (HTTP 429): no 005, variantes em 5 anos e controles em 12 meses; no 002, controles em 5 anos. Nova tentativa na coleta diária.
- Correções depois da conferência dos resultados:
  - O filtro do 005 aceitava qualquer "Ana Clara"; entre os mais vistos havia dois vídeos de outros casos com o mesmo nome. Agora exige um elemento deste caso (Niterói, Flávio, PM, fuzil, júri, debate, Lula…).
  - O filtro do 002 aceitava vídeo de assalto ("ladrão" + "anos"); agora exige a estrutura da consulta ("onde mora/nasceu", "quantos anos", "idade do ladrão") ou "Google".
  - Comentários de vídeos que saíram pelo filtro mais estrito continuam guardados no privado, mas deixam de entrar na conta.
  - ⚠️ As hashtags do TikTok (#casoanaclara) também pegam vídeos de outros casos com o mesmo nome; o marco zero de 2021 no TikTok precisa de conferência humana.
- Segunda execução, com os filtros novos (run 39453711364):
  - 005: 100 vídeos, 5.010.510 visualizações, 3.836 comentários lidos, 79 notícias, 4 falas no debate.
  - 002: 17 vídeos, 79.736 visualizações, 109 comentários. O artigo de 2022 já tem 1 cópia no Internet Archive.
  - O Trends voltou a recusar janelas (429). Para que uma janela recusada não apague a leitura anterior, a coleta agora reaproveita a última leitura boa da mesma janela, marcada com a data em que foi lida.
- Página: nova aba "Casos de busca (Ana Clara, "o ladrão")" no caderno 08, com big numbers, falas no debate, Trends (5 anos, 12 meses, 7 dias, controles, relacionadas, estados), YouTube por ano e mais vistos, comentários pré-codificados, imprensa e checagens, arquivo e a bateria manual do 002.

## C19.76 — Regra: nunca apagar ou limpar dados (2026-10-20) ✅

- O usuário avisou (20/10, 12h37) que em nenhum momento estou autorizado a limpar o banco de dados. Regra 8 do `CLAUDE.md`: não apagar nem limpar dados (`data/`, repositório privado, histórico do git) e não reescrever histórico sem autorização explícita; dado sensível no lugar errado é movido para o privado, nunca descartado.
- Conferência: a única remoção desta sessão foi `data/ia/rotulo_coleta.json`, que saiu do público em C19.75. O conteúdo foi preservado integralmente no privado (`ia/rotulo_coleta.json`, commit 4506e71: 174 vídeos do TikTok e 2.090 do YouTube). A proposta de reescrever o histórico público (C19.75) está cancelada.

## C19.75 — Página "Rótulo de IA nas campanhas" (caderno 08) e resultado dos testes (2026-10-19) ⚠️

- Teste do Instagram (conta 1, autorizado até US$ 1), três rodadas:
  - Runs 39357421750 e seguinte (apify/instagram-scraper e apify/instagram-reel-scraper, perfis @lulaoficial e @flaviobolsonaro): "no_items: Empty or private data for provided input". Custo registrado: US$ 0,0056 por rodada.
  - Rodada com 12 endereços de posts recentes dos dois perfis (apify/instagram-scraper, run JsmQCh9NFEiVgBln0): 12 posts, 64 campos, nenhum de IA. A API não informou custo para essa rodada.
  - ⛔ Conclusão: pelos meios testados, o rótulo "Informações de IA" do Instagram não chega.
- TikTok (run 39357423522, páginas de hashtag sem login): os campos `AIGCDescription`, `ShowAIGC`, `aigcLabelType` e `moderationAigcLabelType` aparecem no JSON. `ShowAIGC` veio verdadeiro em 173 de 174 vídeos e não indica rótulo; a regra passou a contar como rotulado quando `aigcLabelType` ou `moderationAigcLabelType` > 0. Resultado: 13 de 174 vídeos (7,5%) em #lula, #flaviobolsonaro e #eleicoes2026. Perfis oficiais das chapas: 0 vídeos sem login (⛔).
- YouTube: `containsSyntheticMedia` ausente nos 2.090 vídeos lidos (⛔).
- Checagens: 58 de 333 citam IA (40), deepfake (1) ou montagem/manipulação/edição (26); 37 citam Lula e 23 citam Flávio Bolsonaro. "IA" passou a ser buscado só em maiúsculas, porque "ia" é também o verbo ir.
- Privacidade: a primeira versão gravou a coleta bruta (contas pequenas das hashtags, com legenda) em `data/ia/rotulo_coleta.json`, no repositório público. O arquivo foi removido e a coleta bruta vai para o privado (`ia/rotulo_coleta.json`). ⚠️ Continua no histórico do git público (commit desta noite). No público, só aparecem com nome e link contas com 10 mil seguidores ou mais; nesta leitura, os 13 rotulados são de contas menores ou sem número de seguidores e entram só na contagem.
- Página: nova aba "Rótulo de IA nas campanhas" no caderno 08 (Casos), com big numbers, tabela do que dá para medir em cada plataforma, TikTok, checagens e método. Verificada no Chromium local (1300 e 390 px), sem erro de JavaScript.
- Premissa interna do projeto registrada no repositório privado (`PREMISSA_INTERNA.md`), a pedido do usuário; não vai para o público.

## C19.74 — Caso "Rótulo de IA nas campanhas": coleta grátis no YouTube e no TikTok (2026-10-19) 🔜

- Pedido do usuário (19/10, 23h00): começar a página do caso sobre o rótulo de IA ("quanto conteúdo sai declarado como IA").
- `collect_rotulo_ia.py` + `rotulo-ia.yml` (diário 10h47 e manual, grátis):
  - YouTube: campo `status.containsSyntheticMedia` (declaração do canal) dos vídeos dos canais das candidaturas e dos vídeos sobre o debate.
  - TikTok: página pública dos perfis declarados ao TSE pelas chapas presidenciais; guarda qualquer campo do JSON cujo nome indique rótulo de IA.
  - Instagram: ⛔ registrado como lacuna. Os ~16,6 mil posts já coletados no Atlas (privado) têm 15 campos e nenhum de IA (verificação de 19/10).
- `build_rotulo_ia.py` → `data/ia/rotulo.json`: por candidato e plataforma, listas do que foi rotulado e checagens da base Google Fact Check que citam IA, deepfake, montagem ou manipulação. Pela regra de 19/10: 49 de 333.
- Primeira execução (run 39356820487):
  - YouTube: 2.090 vídeos lidos e o campo `containsSyntheticMedia` veio ausente em todos. A API não entrega essa declaração para vídeos de terceiros, então ⛔ não serve para medir.
  - TikTok: os perfis voltaram com 0 vídeos (a página de perfil não entrega a lista sem login). A coleta passa a ler também as páginas de hashtag (#lula, #flaviobolsonaro, #eleicoes2026), que funcionam sem login.
  - Checagens: 58 de 333 citam IA, deepfake, montagem ou manipulação.
- Teste do Instagram, autorizado pelo usuário (19/10, 23h05: "pode testar uma coleta teste de até 1 dólar"; conta 1 confirmada em seguida): `teste_instagram_rotulo.py` + `teste-instagram-rotulo.yml`. Usa dois atores que devolvem o JSON completo (apify/instagram-scraper e apify/instagram-reel-scraper), nos posts e reels mais recentes de @lulaoficial e @flaviobolsonaro, com teto de US$ 0,35 cada e US$ 1 no total. Grava só nomes de campos e o que vier marcado como IA.

## C19.73 — Execuções "canceladas" e "com falha" no GitHub Actions explicadas; workflow inválido corrigido (2026-10-19) ✅

- Pergunta do usuário (19/10, 22h32): por que há tantos scripts abortados. Levantamento das execuções desde 17/10 que não terminaram em sucesso (API do GitHub):
  - 57 "pages build and deployment" cancelados. É a publicação do site: cada coleta que grava dados dispara uma publicação, e quando outra coleta grava logo depois, o GitHub cancela a publicação antiga e fica com a mais nova. Nenhum dado se perde; o site sai com a versão mais recente.
  - 3 falhas de `apify-contas.yml` em push: erro meu em C19.72. Ao comentar o agendamento, a chave `schedule:` ficou vazia, o que torna o arquivo inválido. Corrigido: a chave foi removida e o workflow continua só manual.
  - 4 falhas de "Google Trends — candidaturas" e 1 de "Checagens": o teste que criava a pasta `/nao` (corrigido em C19.63, 19/10 ~03h).
  - 1 falha de "Seguidores YouTube" (conflito do git, corrigido em C19.71) e 1 de "Seguidores Meta" em 18/10 (teste sem numpy, corrigido em C19.61).
  - 3 falhas do teste de preços da loja Apify, 3 do X (assuntos do momento), 2 do Instagram, 1 do Meta Anúncios, 1 de Casos, 1 do 1º turno e 1 de `posicao-teste.yml`: execuções de 17 e 18/10, antes das correções ou com as contas Apify bloqueadas.

## C19.72 — Caso 003 "Ninguém morre nos devendo" (Flamengo e as bets) ativado, coleta grátis do TikTok (2026-10-19) ⚠️

- Pedido do usuário (19/10, 19h11): coletar o caso Flamengo / "ninguém morre nos devendo" (depois da proibição das bets) na página de casos, começando pelo TikTok, com a conta Apify `APIFY_TOKEN_FL` (US$ 5) só para este caso e sem as consultas às contas que precederam o bloqueio. Em seguida (19h12): "você já bloqueou a conta" / "colete na versão free".
  - Nenhuma chamada foi feita com `APIFY_TOKEN_FL` nesta sessão: o caso usa só a coleta grátis (página pública do TikTok, sem login). O caminho com conta exclusiva (`"segredo"` no caso, sem consulta de saldo) ficou no código para uso futuro e não está ativo.
  - Consulta de preços na loja Apify (run teste-apify-loja de 19/10) usou o token da conta 1, como nas consultas anteriores; só leitura.
- O caso 003 já existia como dossiê aguardando data e termos; agora está ativo, com a descrição do contexto, as fontes Aos Fatos (29/09) e Poder360 (08/10) e o marco "desde" em 25/09/2026 (MP que proibiu as bets).
  - TikTok: hashtag #ninguemmorrenosdevendo e buscas "ninguém morre nos devendo" e "flamengo ninguém morre nos devendo".
  - Google Trends e Notícias.
- `collect_tiktok_hashtags.py`: além da página da hashtag, abre a busca do site (`/search/video?q=`) e lê as respostas `/api/search/`. Sem login, o TikTok pode limitar a busca; o manifesto registra quantas respostas vieram.
- `apify-contas.yml`: agendamento diário desligado. Ele consultava todas as contas todo dia, o tipo de chamada que o usuário pediu para evitar.
- Testes: suíte OK; `test_casos` ajustado (casos 002 e 004 continuam aguardando).
- Execução real (run 39333583748, carga, TikTok e Google, grátis):
  - Hashtag #ninguemmorrenosdevendo: 59 vídeos de 44 contas, 27 deles publicados desde 25/09. Primeiro vídeo localizado no período: 27/09, 21h (Brasília), conta com 455,9 mil seguidores.
  - Busca por frase: 0 vídeos nas duas buscas (2 respostas cada). Sem login, a busca do TikTok não entrega resultados; ⛔ a busca por frase fica pendente.
  - Google: 169 pontos do Trends e 43 notícias.

## C19.71 — Coletas diárias de seguidores: duas coletas no mesmo arquivo não se derrubam mais (2026-10-19) ✅

- Pedido do usuário (19/10, 19h04): a coleta de "Quem acompanha" deve ser diária. Situação de 19/10:
  - Seguidores Meta (run 39290012064), WhatsApp (39294037889), WhatsApp canais (39296768953), TikTok (39291556905) e Kwai (39309924473) gravaram os dados do dia.
  - ⛔ Seguidores YouTube (run 39290277156) coletou, mas não gravou: o envio ao GitHub parou em conflito do git com a coleta Meta, que tinha gravado `data/seguidores/latest.csv` e `variacao.json` um minuto antes. Os números do YouTube de 19/10 se perderam nessa execução.
  - ⛔ Seguidores faltantes (39294371417): rodou, mas todos os perfis voltaram sem número, porque usa as contas Apify 3 a 7, recusadas pela Apify.
  - Os agendamentos de 07h10 a 08h41 só começaram entre 13h57 e 14h45 (atraso do agendador do GitHub).
- Correção: `scripts/resolver_conflitos.py`, chamado por `commit_push.sh` quando o rebase para em conflito. Tabelas de seguidores: junta as duas versões, uma linha por candidato/rede/endereço, ficando com a captura mais recente; nenhuma coleta apaga a outra. Arquivos derivados: fica a versão desta coleta (recalculada na próxima). Teste de integração `tests/test_commit_push.py`, com dois clones gravando o mesmo `latest.csv`: as duas atualizações sobrevivem. Suíte OK.
- Seguidores YouTube disparado de novo em 19/10 (resultado na próxima entrada).

## C19.70 — Checagens das falas do debate (Lupa e Estadão Verifica) (2026-10-19) ⚠️

- O usuário observou (19/10, 03h36) que as checagens do painel 09 eram anteriores ao debate. É isso mesmo: a Google Fact Check Tools API ainda não indexou checagens do debate (a mais recente é de 16/10). Busca na web (19/10 ~03h45) encontrou as checagens do debate publicadas pelas agências:
  - Agência Lupa, "Ao vivo: checagem do debate…" (atualizada 19/10 01h27): 40 falas. Lula 17 (verdadeiro 9, falso 2, exagerado 2, falta contexto 2, insustentável 1, subestimado 1); Flávio Bolsonaro 23 (verdadeiro 2, falso 8, exagerado 4, falta contexto 5, insustentável 3, subestimado 1).
  - Estadão Verifica, "Checamos o debate…" (republicado no Terra, 19/10 01h01): 28 falas. Lula 13 (verdadeiro/é verdade 8, enganoso 2, exagerado 2, impreciso 1); Flávio Bolsonaro 15 (verdadeiro 1, enganoso 5, falta contexto 5, é falso 2, exagerado 1, subestimado 1).
  - Ranking dos Políticos (76 falas) ficou de fora: não há indicação de que seja agência de checagem reconhecida.
- `data/checagens/debate_band.json`: lista transcrita à mão (assistida por IA, a partir da leitura das páginas das agências) com orador, rótulo da agência, tema (resumo do Atlas) e link. Rótulos agrupados só para a cor; os totais não se somam entre agências. ⚠️ Conferir na fonte antes de citar.
- Página: painel 09 abre com "Falas do debate checadas pelas agências" (barras por agência e candidato, lista expansível, link para cada checagem); as checagens do Google Fact Check passam a ter o título "Antes do debate · checagens da campanha". Big numbers: "Falas do debate checadas: 68 (Lupa 40 · Estadão Verifica 28)" e "Checagens na campanha: 344". Verificado no Chromium local (1300 e 390 px), sem erro de JavaScript. Suíte OK.
- Chat ao vivo: a loja da Apify tem atores de replay de chat (US$ 0,0002 a 0,001 por mensagem, consulta de 19/10, run de teste-apify-loja). Não foi rodado: a conta 1 exige autorização e teto, e o número de mensagens da live principal é desconhecido.

## C19.69 — Checagens: gráfico por candidato e big number corrigido (2026-10-19) ✅

- O usuário apontou (19/10, 03h28) que o big number mostrava 0 checagens, embora a lista do painel 09 tenha 344. O 0 era só "desde o dia do debate". Agora o big number mostra o total (344, 60 dias) e o "desde o debate" fica no texto de apoio.
- Pedido do mesmo horário: barras por candidato com verdadeiro, falso e outras classificações, acima da tabela. `collect_checagens.py` agrupa os rótulos das agências em Falso, Enganoso ou fora de contexto, Verdadeiro e Outros, e separa duas contagens:
  - Checagens que **citam** o candidato: Lula 246 (falso 172, enganoso/fora de contexto 72, verdadeiro 2); Flávio Bolsonaro 101 (falso 79, enganoso 22). Quase todas checam boatos **sobre** o candidato. A página avisa que "falso" ali não quer dizer que o candidato mentiu.
  - Afirmações **ditas pelo próprio candidato**, segundo o campo "quem disse" da agência: Lula 4 (2 enganosas/fora de contexto, 2 verdadeiras); Flávio Bolsonaro 1 (enganosa/fora de contexto). A página avisa que números tão pequenos não permitem comparar os dois.
  - Recalculado sobre a coleta do run 39206833280, sem nova chamada à API.
- Privacidade: em 3 checagens, "quem disse" trazia nome de pessoa comum; o público passa a mostrar "pessoa ou perfil (nome omitido pelo Atlas)". Também foi corrigida a exibição de afirmações vazias ("/"), que agora mostram o título da checagem.
- Testes: `TestRotulos`; suíte OK. Verificado no Chromium local (1300 e 390 px), sem erro de JavaScript.

## C19.68 — Debate: big numbers e painel do YouTube na página (2026-10-19) ✅

- Run 39209236316 (19/10 06h2x UTC), sem erro: 418 vídeos achados, 404 sobre o debate, de 216 canais. Somados: 76.283.920 visualizações, 1.752.743 curtidas, 108.501 comentários (contadores públicos) e 223,5 h de vídeo. A transmissão da Band Jornalismo (Gqc1rQtzWUk) sozinha tem 31.125.686 visualizações.
  - Por formato: 80 transmissões ao vivo (60,9 mi visualizações), 221 vídeos curtos (7,6 mi), 88 cortes (7,4 mi), 15 íntegras ou vídeos longos (364 mil).
  - Por origem: emissoras do debate 52,5 mi; outros canais (comentaristas, cortes, perfis) 13,4 mi; outros veículos 7,7 mi; canais das campanhas 2,8 mi (4 vídeos, todos do canal TV Celular Flávio Bolsonaro).
  - Comentários lidos: 8.932 em 40 vídeos, de 6.341 autores. 24,2% citam Lula e 25,5% citam Flávio Bolsonaro; incivilidade 3,2% e intolerância 0,8% (pré-codificação por dicionário).
  - Nas lives, 0% dos 4.984 comentários lidos foi escrito durante a transmissão: o primeiro comentário de cada live é do minuto em que ela terminou. Isso confirma o que o usuário apontou: durante a live a conversa acontece no chat, que a API não oferece depois (⛔ não coletado).
- `build_debate_youtube.py`: classificação por conteúdo pelo título (o debate e trechos, análise/reação/cobertura, pré-debate), comentários por hora e indicador "durante a transmissão".
- Página (aba do debate): cartão "Big numbers" logo abaixo do vídeo (YouTube, duração, tempo de fala, checagens) e painel "10 · YouTube" (barras por formato, origem e conteúdo; 20 vídeos mais vistos; comentários com o aviso de que chat não é comentário; comentários por hora; tabela por origem; termos). Nenhum texto ou autor de comentário é publicado. Verificado no Chromium local, em 1300 e 390 px (largura 390), sem erro de JavaScript. Suíte OK.

## C19.67 — Debate no YouTube: todos os vídeos, big numbers e comentários (2026-10-19) ✅ (resultados em C19.68)

- Pedido do usuário (19/10, 03h16): big numbers do debate somando as réplicas (todas as cópias, lives, íntegras e cortes) e análise do que foi publicado no YouTube e dos comentários, na mesma página, lembrando que o chat da live é diferente dos comentários.
- `collect_debate_youtube.py` + `debate-youtube.yml` (a cada 6 h, grátis): busca na YouTube Data API (6 consultas, até 150 vídeos cada, publicados desde 18/10 12h UTC, e a busca "debate" nos 4 canais das campanhas), filtra pelo título/descrição, lê os números públicos de cada vídeo e os comentários dos 40 mais vistos (até 100 por relevância + 100 recentes). Comentários só no privado. O chat ao vivo não é lido: a API só o oferece enquanto a live está no ar (registrado como ⛔).
- `build_debate_youtube.py` → `data/debate/youtube.json`: totais (vídeos, canais, visualizações, curtidas, comentários, horas), por formato (live, íntegra, corte, curto) e por origem (emissoras do debate, outros veículos, campanhas, outros canais), vídeos mais vistos e agregados dos comentários (menções, incivilidade e intolerância pelo livro de códigos, termos).
- Testes: `tests/test_debate_youtube.py`; suíte OK. Execução real: próxima entrada.

## C19.66 — Debate: quem fala, por codificação manual dos turnos (2026-10-19) ⚠️

- 205 turnos marcados sobre a íntegra (legenda automática), lendo a transcrição inteira: Lula, Flávio Bolsonaro, mediação, intervalo comercial e 4 trechos indefinidos (falas sobrepostas). Codificação assistida por IA (Claude), ainda **não validada por pessoa da equipe**. As âncoras de cada turno (começo da fala) ficam no privado (`debate/turnos_codificacao.tsv`); `resolver_turnos.py` gera `data/config/debate_turnos.json`, só com tempos e oradores.
- Resultado (`build_debate_transcricao.py`, rodado localmente): Lula 35,8 min (5.879 palavras), Flávio Bolsonaro 43,1 min (8.397), mediação 20,4 min, não atribuído 0,2 min, intervalos 10,1 min (fora da conta). CHD: 6 classes, 394 de 400 trechos classificados.
- Conferência com as regras do debate: no 1º confronto (banco de 15 min por candidato), a mediação anunciou que Flávio esgotou o tempo e que Lula tinha 1min08 restantes. Na codificação, Lula tem 13,8 min nesse confronto (15 − 1,1 = 13,9) e Flávio 16,8 min. O excedente de Flávio vem das falas por cima do adversário: a legenda não separa vozes simultâneas e o cronômetro só corre para quem está com a palavra. Tempo de fala é aproximado.
- `build_debate_transcricao.py`: rótulo "intervalo", que fica fora das análises; a marca ">>" da legenda sai do texto analisado; o método da atribuição vai para a página. A página troca o aviso quando a atribuição é manual.
- Testes: `TestTurnos` (âncora encontrada / não encontrada); suíte OK. Verificado no Chromium local, sem erro de JavaScript.

## C19.65 — Debate: transcrição completa a partir do .srt da íntegra enviado pelo usuário (2026-10-19) ⚠️

- Bloco 3 pela Apify: mais uma tentativa (run 39207352137; Apify 4UDA8RrgDVAlYpv5S, US$ 0,00005), de novo ⛔ "HTTP Error 429: Too Many Requests". Até aqui eram 2 dos 3 blocos (~70 de ~100 min).
- O usuário enviou (19/10, 03h00) a legenda automática do YouTube da íntegra, em .srt ("ÍNTEGRA (1) debate entre Lula e Flávio Bolsonaro nas eleições 2026", baixada em DownloadYoutubeSubtitles.com). Lida: 2.928 trechos, 18.859 palavras, 114,3 min, da abertura ("começa agora o primeiro debate…") ao encerramento. O id do vídeo não veio no arquivo.
- `importar_srt.py`: grava a transcrição privada no formato de sempre e guarda o .srt no privado (`debate/integra_legenda_youtube_auto.srt`). `collect_debate_video.py` não troca mais uma transcrição maior por uma menor (a menos que se passe `--forcar`), para que uma nova leitura por blocos não apague a íntegra.
- `build_debate_transcricao.py` rodado localmente sobre a íntegra: 470 trechos de análise, CHD com 6 classes, redes regeradas. ⛔ Quem fala continua sem atribuição confiável: só 18 deixas da mediação para 208 trocas de voz; Não atribuído 89,0 min. Próximo passo: codificação manual dos turnos.
- Testes: `TestSrt` em `tests/test_debate_transcricao.py`; suíte OK.

## C19.64 — Checagens publicadas funcionando; painel 09 na página do debate (2026-10-19) ✅

- O usuário liberou a Fact Check Tools API na chave do Google Cloud (19/10, 02h52). Run 39206833280: 344 checagens únicas em português (60 dias), sem erro. Por consulta: "Lula" 257, "Flávio Bolsonaro" 114, "urna eletrônica" 13, "eleições 2026" 12, "debate presidencial" 1, "debate Band" 0 (há sobreposição entre consultas). Agências: UOL Notícias 86, Aos Fatos 84, Estadão 62, AFP Checamos 55, BOL-UOL 34, Projeto Comprova 16, Observador 7. Rótulos: falso 245, enganoso 58, distorcido 14. Nenhuma checagem com data de 18/10 em diante; a mais recente é de 16/10. 181 sem data de checagem na API.
- Página (aba do debate): painel "09 · Checagens publicadas", com filtro Todas / Citam Lula / Citam Flávio Bolsonaro, resumo por agência e rótulo, e tabela das 60 mais recentes com link para cada checagem. Aviso: rótulo e texto são das agências, o Atlas não dá veredito, e "citam" não quer dizer autoria.
- Correção de layout: a tabela de temas da transcrição estourava a largura no celular (484 px em tela de 390); agora rola dentro do cartão. Verificado no Chromium local, em 1300 e 390 px (largura da página 390), sem erro de JavaScript. Suíte OK.

## C19.63 — Checagens publicadas: Google Fact Check Tools API (2026-10-19) ⛔ (resolvido em C19.64)

- Pedido do usuário (19/10, 02h35): protocolo de fact-check para o discurso. Primeiro passo do protocolo: cruzar com o que as agências já checaram, sem veredito do Atlas. O usuário confirmou às 02h45 que a Fact Check Tools API está ativa no Google Cloud.
- `collect_checagens.py` + `checagens.yml` (a cada 6 h, grátis): `claims:search` em português para "Lula", "Flávio Bolsonaro", "debate Band", "debate presidencial", "eleições 2026", "urna eletrônica" (janela de 60 dias); junta por link, marca o candidato citado e se a checagem é de 18/10 em diante. Chave: segredo `FACTCHECK_API_KEY` ou, na falta, `YOUTUBE_API_KEY`. Saída: `data/checagens/checagens.json`.
- Testes: `tests/test_checagens.py`; suíte OK. Primeira execução real: ver a próxima entrada.
- Execução real (run 39206410820, 19/10 ~05h55 UTC): ⛔ HTTP 403 em todas as consultas — "Requests to this API factchecktools.googleapis.com … are blocked" (PERMISSION_DENIED). Sem `FACTCHECK_API_KEY`, o script usou a chave do YouTube, que está restrita à YouTube Data API. Falta: incluir a Fact Check Tools API nas restrições dessa chave ou criar outra chave e salvá-la como segredo `FACTCHECK_API_KEY`. 0 checagens gravadas.
- Correção encontrada na primeira execução (run 39206306669, falhou no passo de testes): `test_trends_agora.test_fora_da_janela` criava a pasta antes de checar a janela; no GitHub (usuário sem root) isso dá "Permission denied: '/nao'". Localmente passava porque o ambiente roda como root. Como todos os workflows de coleta rodam a suíte antes de coletar, as coletas diárias de 19/10 (07h10 em diante) falhariam. `collect_trends_agora.py` agora só cria a pasta depois de checar a janela.

## C19.62 — Debate: legendas dos blocos 1 e 2 lidas; atribuição automática de quem fala retirada por ser errada (2026-10-19) ⚠️

- Run 39204798894 (19/10 05h2x UTC, `--blocos … --apify`): Apify, conta 1, run eoKn1Ix5Qn02Kwg6l, status SUCCEEDED, 3 itens. Bloco 1 (S17iktRbpa0, "Acompanhe o 1° bloco do Debate da Band", Rádio BandNews FM, 46 min): 1.256 trechos de legenda automática. Bloco 2 (HMn0LIrfcws, 23,5 min): 619. ⛔ Bloco 3 (Omay_TlhdZM, 30 min): item sem segmentos (o ator devolveu erro; o motivo não foi gravado). Total lido: 12.281 palavras.
- Erro encontrado na saída desse run: a atribuição por deixas da mediação deu Lula 91,2 min e Flávio 37,2 min, mais que a duração dos blocos. Duas causas: (1) os trechos da legenda automática se sobrepõem e a soma contava a sobreposição — agora cada trecho vai até o início do seguinte; (2) só há 12 deixas para ~166 trocas de voz (">>" na legenda), então o orador "herdava" a fala do outro por minutos (ex.: uma fala de Flávio dirigida a Lula saiu como de Lula). Agora troca de voz sem deixa vira "Não atribuído". Com a regra nova (rodada local sobre a mesma transcrição): Lula 3,3 min, Flávio 0,2, Mediação 0,5, Não atribuído 65,4 — ou seja, a atribuição automática não serve; o próximo passo é a codificação manual dos turnos em `data/config/debate_turnos.json`.
- Bloco 3, mais duas tentativas só dele (runs 39205286932 e 39205516384; Apify 0ZpTf4gPAePYA9d8h e aoVUsUBuCLDhOwIqN, US$ 0,00005 cada): ⛔ o YouTube respondeu "HTTP Error 429: Too Many Requests" ao ator. Fica para nova tentativa mais tarde, dentro do mesmo teto de US$ 0,05.
- Enquanto isso, a rede "Os dois" e a CHD usam todas as falas fora da mediação identificada (candidatos + não atribuídas); temas por candidato só contam trechos atribuídos.
- `collect_debate_video.py`: reaproveita do privado os blocos já lidos e só pede à Apify o que falta; grava `ini_video` e a fonte por trecho; registra o erro do item e o custo do run.
- Página: barra de tempo de fala com "Não atribuído" e aviso explicando por quê. Verificado no Chromium local (sem erro de JavaScript). Suíte OK.

## C19.61 — Debate: player por bloco; legendas pela Apify (conta 1, teto US$ 0,05); testes não derrubam mais a coleta Meta (2026-10-19) ⚠️

- Página: o player saiu da transmissão ao vivo (Gqc1rQtzWUk) e passou para os três vídeos por bloco indicados pelo usuário (S17iktRbpa0, HMn0LIrfcws, Omay_TlhdZM), com botões Bloco 1/2/3 que trocam o vídeo, o título e o link "Abrir no YouTube". Pedido do usuário (19/10, 02h2x): "video tambem tem que ser atualizado na pagina vc deixou com ao vivo". Estilo dos botões (`.pt-chips`) estendido às seções `#debate` e `#casos`, onde estava sem estilo. Verificado no Chromium local: clique no Bloco 3 troca src, título e link; sem erro de JavaScript (o vídeo em si não carrega no ambiente de teste, que não acessa o YouTube).
- `collect_debate_video.py --apify` (input `apify` no `debate-video.yml`): lê as legendas dos 3 blocos com o ator seemuapps~youtube-transcript-scraper na conta 1 (`APIFY_TOKEN`), teto US$ 0,05 — autorização do usuário só para isso (19/10). Resultado do run registrado na próxima entrada.
- Correção: o workflow diário "Seguidores Meta" falhou em 18/10 (run 39133868120) no passo de testes, antes da coleta, porque `tests/test_normalizacao.py` importava `chd_reinert` (numpy), que o workflow não instala. Agora os testes que dependem de numpy/networkx (`test_normalizacao`, `test_debate_transcricao`, `test_rede_debate`) são pulados quando a biblioteca falta. Testado: suíte completa OK; suíte com numpy e networkx bloqueados: 166 testes, OK (14 pulados).
- Pendente: ⛔ não houve coleta Meta (Instagram/Facebook) em 18/10; a de 19/10 roda às 07h10 (conta 1, `APIFY_TOKEN`). "Seguidores faltantes" usa as contas 3 a 7, hoje recusadas pela Apify (401).

## C19.60 — Debate: vídeos por bloco; legendas existem, mas o YouTube recusa a leitura pelo GitHub (2026-10-19) ⛔

- O usuário indicou os vídeos do debate por bloco (18/10, 23h31): S17iktRbpa0, HMn0LIrfcws, Omay_TlhdZM. `collect_debate_video.py --blocos` lê um por um e junta a transcrição em sequência (bloco e tempo guardados).
- Run de 19/10 05h20 UTC: a YouTube Data API (captions.list, só a chave do Google Cloud) confirma legenda automática em português nos três blocos. Mas a leitura do texto falhou em todos os caminhos: yt-dlp com 5 clientes do YouTube (padrão, tv_embedded/web_embedded, mweb, android_vr, ios) pede login ("confirme que não é um robô") e o endpoint público de legendas (timedtext) volta vazio. Baixar pela API (captions.download) exige autorização do dono do canal.
- Caminhos restantes, aguardando o usuário: ator de legendas da Apify na conta 1 (a única ativa; ~US$ 0,0001 a 0,01 por vídeo, loja de 18/10) ou leitura pelo Chrome do usuário (exige liberar youtube.com na extensão).

## C19.59 — Debate: vídeo e transcrição (2026-10-18) 🔜

- Pedido do usuário (18/10, 23h07): vídeo do debate no início da página, análise de redes da transcrição, análise no estilo IRaMuTeQ e contagem por tema.
- `collect_debate_video.py` + `debate-video.yml` (grátis): procura o vídeo pela YouTube Data API (canal da Band ou do Estadão, mais de 1 h, publicado desde 18/10 17h) e baixa a legenda do YouTube (manual ou automática) por yt-dlp; opção de transcrever o áudio com faster-whisper. Transcrição integral só no privado; público: `data/debate/video.json`.
- Execuções (runs de 18/10 23h1x e 39188742204): vídeo encontrado pela API — "Flávio Bolsonaro x Lula: debate presidencial do 2º turno na Band - 18/10/2026", Band Jornalismo, id Gqc1rQtzWUk, 6h12min (live iniciada 15h59; o debate começa por volta de 4h00 do vídeo). ⛔ Legendas e áudio recusados pelo YouTube nos servidores do GitHub ("Sign in to confirm you're not a bot"; yt-dlp pede cookies). A YouTube Data API não serve: baixar legenda (captions.download) exige autorização do dono do canal. O Chrome do usuário não tem permissão para youtube.com.
- `build_debate_transcricao.py` (pronto, aguardando a transcrição): orador por deixas da mediação (corrigível em `data/config/debate_turnos.json`), segmentos de ~40 palavras, contagem por tema (dicionário do Atlas), rede de coocorrência por orador (GEXF), CHD de Reinert com a variável orador, corpus IRaMuTeQ (privado), trechos públicos ≤ 25 palavras. Testes: `tests/test_debate_transcricao.py`.
- Página: vídeo no topo da aba do debate (player do YouTube sem cookies, abrindo em ~4h00) e bloco "Análise da transcrição" (tempo de fala, temas, classes CHD, rede de palavras), hoje com ⛔ explicando por que a transcrição não entrou. Suíte OK.

## C19.58 — Debate: redes de canais e de palavras-chave (2026-10-18) ✅

- Pedido do usuário (18/10, 23h05): "pode gerar as redes de canais e palavras-chave". `build_rede_debate.py` (no workflow `trends-agora`, depois de cada leitura):
  - rede de canais: termo em alta de Política — veículo com matéria entre as 5 primeiras do Google Notícias para o termo (peso = nº de matérias);
  - rede de palavras-chave: termo em alta de Política — termos que o Trends agrupa nele; Lula, Flávio Bolsonaro e "debate" — consultas relacionadas (24 h).
  - Variações de acento viram um nó só ("flávio miliciano" = "flavio miliciano"). Saídas: `data/trends/agora/rede_{canais,palavras}.{gexf,json}` e CSVs de nós e ligações.
- Leitura de 19/10 01h53 UTC: canais 163 nós e 255 ligações; palavras 288 nós e 280 ligações. Veículos mais presentes no topo: Poder360 (23), Valor Econômico (18), O Globo (14), Estadão (14), Metrópoles (12), UOL (10), Folha (10), G1 (9).
- Página: painel 08 · Redes (canais / palavras-chave), desenho com os ~90 nós mais ligados, rótulos sem sobreposição, GEXF e CSVs para baixar. Verificado no Chromium local (1300 e 390 px, sem erro de JavaScript).
- Testes: `tests/test_rede_debate.py`; suíte OK.

## C19.57 — Debate: termos mais buscados por estado e matérias no topo de cada busca (2026-10-18) ✅

- Pedidos do usuário (18/10, 22h37 e 22h50): "falta só os termos mais buscados por estado" e "ver quais matérias estão no início de cada busca".
- Por estado: na primeira leitura de cada hora, consultas relacionadas (principais e em alta, até 10) a Lula, Flávio Bolsonaro e "debate" em cada UF, últimas 24 h (`relacionados_por_uf`). Página: painel 07 ganha "Termos mais buscados sobre… no estado" ao lado da lista em alta do estado.
- Matérias: para cada termo de Política em alta (até 60), as 5 primeiras matérias do Google Notícias nas últimas 24 h, na ordem do Google Notícias, renovadas a cada hora (`data/trends/agora/materias.json`). Aparecem no ranking (5) e na lista de cada estado (2). Limite: é o Google Notícias, não a busca geral da web (a API de busca do Google recusou o projeto), e não é personalizado.
- Workflow com tempo máximo de 25 min. Leitura de 19/10 01h53 UTC: termos relacionados nas 27 UFs; matérias para 59 termos de Política. Testes: `test_trends_agora` com matérias simuladas; suíte OK.

## C19.56 — Debate: perguntas, termos mais buscados e buscas por estado (2026-10-18) 🔜

- Referência do usuário (18/10, 22h30): a sala digital Band e Google acompanha "principais perguntas", "termos mais buscados sobre…", curvas e buscas por estado. `collect_trends_agora.py` passa a guardar, para Lula, Flávio Bolsonaro e "debate" nas últimas 24 h: consultas relacionadas (principais e em alta), as que começam como pergunta, e o interesse por UF (divisão entre os três termos na mesma consulta).
- Página do debate: painéis 04 · Principais perguntas, 05 · Termos mais buscados sobre… (por termo, principais × em alta) e 06 · Buscas por estado (divisão por UF; Lula primeiro com o aviso de ordem). No visual do Atlas, não no da Band.
- Leitura de 19/10 01h31 UTC: 6 perguntas (ex.: "onde vai ser o debate presidencial hoje", em alta +2.100%; "quem tá na frente flávio bolsonaro ou lula"), 25 consultas relacionadas por termo e lista, 27 UFs.
- Pergunta do usuário (22h31): "recorte por estado… é possível pegar esse dado?". Além do interesse por UF, o coletor lê a lista "Em alta agora" de cada estado (geo BR-UF, 24 h, até 40 termos) na primeira leitura de cada hora; página: painel 07 · Em alta em cada estado (seletor de UF, filtro Política).
- Testes: `TestRelacionados`; suíte OK.

## C19.55 — Debate do 2º turno: Google Trends "em alta agora" (2026-10-18) 🔜

- Pedido do usuário (18/10, 22h24): página sobre o debate, "cópia do Trends mais precisa", tendências das últimas horas e categoria Política; "debate iniciou às 8 mas antes já temos notícias, por isso a janela de 24 h e repercussão de +24 h". Debate Band/Estadão, 18/10, 20h (Brasília), conforme o DGABC.
- `collect_trends_agora.py` + `trends-agora.yml` (a cada 15 min, grátis): lista "Em alta agora" do Brasil (4 h e 24 h; termo, volume aproximado, aumento, início, se segue ativo, categorias, termos agrupados), RSS de tendências (volume e notícias por termo), curvas de Lula, Flávio Bolsonaro e "debate" (24 h a cada 8 min; 7 dias por hora). Retratos em `data/trends/agora/retratos/`, consolidado em `data/trends/agora/debate.json`. Fora da janela (até 19/10 20h) o coletor não faz nada.
- 1ª execução (19/10 01h26 UTC): 137 termos nas últimas 4 h, 403 nas 24 h, 57 na categoria Política; posições conferidas pela amostra bruta (termo, início, volume, aumento, termos agrupados, categorias). Nomes das categorias corrigidos pelos termos de cada id (ex.: 17 = jogos de futebol, 20 = previsão do tempo, 9 = Unicamp/OAB, 10 = locais de votação); a 1ª versão chamava o id 10 de "Empregos e educação".
- Página: aba **Debate do 2º turno (em alta agora)** no caderno de Buscas — termos por horário de início × volume (Política em vermelho; noite do debate ou janela inteira), curvas de Lula, Flávio e "debate" (24 h e 7 dias), ranking com termos agrupados, notícias do RSS, "visto pelo Atlas", filtros Política/todas e antes/depois do debate/ainda em alta. Verificado no Chromium local (1300 e 390 px, sem erro de JavaScript).
- Testes: `tests/test_trends_agora.py`; suíte OK.

## C19.54 — ⛔ Apify bloqueou as contas 2 a 12 (2026-10-18)

- Informação do usuário (18/10, 18h11): "o Apify bloqueou as contas todas". Confirma o diagnóstico de C19.53: chaves com formato correto (46 caracteres, prefixo `apify_api_`, sem aspas nem espaços), recusadas com HTTP 401 desde ~17h30.
- Efeito: toda coleta paga fica parada, exceto pela conta 1 (que segue fora por pedido do usuário). Rotinas diárias afetadas — terminam com ⛔ no manifesto, sem apagar dados anteriores: `seguidores-faltantes` (11h17 UTC), `kwai` (13h10 UTC, conta 2), etapa Apify do `tiktok` (o TikTok por yt-dlp continua). Coletas grátis seguem: YouTube (API oficial), TikTok por yt-dlp, Google Trends e Notícias, X trends, Internet Archive, WhatsApp (canais públicos).
- Caso 1: a coleta do cross (+ US$ 3,50 autorizados) não foi feita; nada foi gasto nas tentativas. O caso continua com o que já foi coletado (10.976 publicações, quase todas do X).

## C19.53 — Diagnóstico do formato das chaves Apify (2026-10-18) 🔜

- 17h39: as contas 2 a 12 seguem com HTTP 401 (a 12 passou a existir e também é recusada); só a conta 1 responde (`data/apify/contas.json`). Como todas falham igual, o mais provável é o valor gravado, não as contas.
- `diag-chaves-apify.yml`: mostra só características de cada segredo (tamanho, prefixo `apify_api_`, aspas, espaço ou quebra no meio, "=", "Bearer", caracteres válidos), nunca o valor. Sem custo.

## C19.52 — ⛔ Chaves Apify das contas 2 a 10 recusadas (2026-10-18)

- Teste da coleta do cross (runs 39163386868 e seguinte): todas as chamadas à Apify voltaram HTTP 401 "user-or-token-not-found". Conferido no `apify-contas` às ~17h40: as contas 2 a 10 respondem 401 (às ~17h25 as contas 2 a 8 respondiam normalmente e 9 e 10 apareciam como segredo ausente; logo, os segredos foram trocados ou as chaves revogadas nesse intervalo). Só a conta 1 responde, e ela não é usada por pedido do usuário.
- Nada foi gasto nesses testes. A coleta do cross (+ US$ 3,50 autorizados) fica parada até as chaves serem regravadas nos segredos do GitHub (Settings → Secrets → Actions). Coletas diárias que usam essas contas também vão falhar até lá.
- `collect_casos.py` passa a registrar a mensagem de erro da Apify (sem o token) no manifesto; o workflow de casos recebe também a conta 8.

## C19.51 — Caso 1: coleta para o cross entre redes (2026-10-18) 🔜

- Pergunta do usuário (18/10, 17h22): "você só coletou Twitter, eu quero entender o cross". Diagnóstico: TikTok 82, Instagram 19, Facebook 13, Kwai 0 contra X 10.862; nos posts do X, só 69 trazem link para outra rede (Instagram 36, WhatsApp 14, x.com 8, YouTube 2, TikTok 1; contagem nos brutos do privado, `entities.urls`).
- Autorização (18/10, 17h2x): "+ US$ 3,50" (teto do caso 3 + 3,50 = 6,50). Tetos por rede: X 2,40; TikTok 1,10; Instagram 1,25; Facebook 0,65; Kwai 0,40 (= 5,80).
- Atores trocados onde a carga veio rasa: TikTok pelo novi/multiple-tiktok-hashtag-scraper (US$ 0,001 por vídeo + 0,001 por hashtag; a leitura grátis pela página parava em 2 páginas); Instagram pelo apify/instagram-hashtag-scraper (feed da hashtag; o apidojo por palavra-chave devolveu 10); Facebook sem `recent_posts` (com ele vieram 5); Kwai por busca de palavra completada com o feed da hashtag (o feed sozinho veio vazio). Itens por hashtag pelo teto: TikTok ~521, Instagram ~228, Facebook ~119, Kwai ~95.
- Contas: saldo consultado (run do `apify-contas`, 18/10): só as contas 8 e 7 têm saldo útil (5 e 6 quase no fim; 2, 3 e 4 esgotadas no mês; 9 a 15 sem chave). Instagram na 8; TikTok, Facebook, Kwai e X na 7 (`segredos_por_rede`).
- Testes: `test_casos` (novos atores e normalização do TikTok); suíte OK. Pendente: teste e carga no Actions; análise do cross.

## C19.50 — Caso 1: são duas hashtags (#brasilinteiro e #verdeeamarelo) (2026-10-18) 🔜

- Correção do usuário (18/10, 16h54): "@verdeeamarelo — eu tinha te dito que eram duas #". Saem a busca "@verdeeamarelo OR from:verdeeamarelo" no X e a leitura do perfil @verdeeamarelo no Instagram; título do caso: "#brasilinteiro e #verdeeamarelo". `build_casos.py` passa a usar só os termos atuais do caso: publicação trazida apenas por termo removido sai dos agregados (havia 1, que também tinha #brasilinteiro e fica). O bruto continua no privado.
- O que a busca do @ custou (manifesto de 18/10 13h33): X 1 post, US$ 0,00015; Instagram 0 itens, sem cobrança.
- #verdeeamarelo passa a ser hashtag principal: a carga parou no limite (1.685) com o mais antigo em 17/10 12h48 UTC; novo complemento do X de 16/10 até esse horário. Tetos do caso redistribuídos dentro dos US$ 3 (gasto até aqui US$ 1,35): X 2,20; Instagram 0,20; Facebook 0,50; Kwai 0,10; máximo por termo 6.000.
- Complemento de #verdeeamarelo (run 39161034090): 5.405 posts de 16/10 até 17/10 12h48 UTC, abaixo do pedido (5.982), ou seja, a janela fechou. Caso: 10.079 publicações de 5.257 contas (X 9.965). Na hora das 09h de 17/10: 7.349 publicações (pico e decolagem). #verdeeamarelo: 1ª publicação lida 16/10 11h (X).
- Lacuna das 10h de 17/10 em #brasilinteiro (3 posts, contra 388 de #verdeeamarelo): novo complemento só dessa janela, com o teto do X a 2,40 (Instagram 0,20; Facebook 0,30; Kwai 0,10 — soma US$ 3,00; gasto do caso até aqui US$ 2,16).
- Complemento da lacuna (run 39161280098): 1.148 posts de #brasilinteiro entre 12h59 e 14h01 UTC de 17/10, abaixo do pedido (2.114); a hora das 10h passou de 3 para 1.090. Lacuna retirada da página; fica a nota de que a busca do X não garante devolver tudo. Caso: 10.976 publicações de 5.582 contas (X 10.862). Gasto do caso: US$ 2,33 de 3.
- Testes: `test_casos` atualizado (duas hashtags; 6.000 itens por termo com o novo teto); suíte OK.

## C19.49 — Caso 1: X completado por janelas de horário, lacunas e decolagem (2026-10-18) ⚠️

- Complementos do X para #brasilinteiro (runs 39133523009, 39133657951, 39133785803): antes de 17/10 06h (Brasília) 36 posts (abaixo do limite); 12h05–12h18 UTC 2.000 (no limite); 09h00–12h05 UTC 1.098 (abaixo do limite de 1.325). Total do caso: 7.776 publicações de 4.212 contas (X 7.662, TikTok 82, Instagram 19, Facebook 13, Kwai 0).
- Observado nos dados (privado, contagem por minuto): o volume no X sobe de 1–3 posts por minuto para 361 no minuto 12h00 UTC (09h00 de Brasília) de 17/10 e fica acima de 100 por minuto na meia hora seguinte. É padrão de publicação concentrada num horário; os dados não dizem quem combinou nem se houve automação.
- Lacunas registradas em `casos.json` e mostradas na página: X #brasilinteiro 17/10 10h (só 3 posts lidos contra centenas nas horas vizinhas: a busca pulou o trecho; o teto do X para o caso acabou) e X #verdeeamarelo antes de 17/10 09h48 (carga no limite, sem complemento).
- Marco zero geral (TikTok, 16/10 09h) é um post de futebol que usa a hashtag ("O Brasil inteiro é SC Internacional"): a página passa a dizer que o marco zero pode ser uso sem relação e mostra a **decolagem** (1ª hora com ≥ 5% do pico, mínimo 10): 17/10 09h, 5.072 publicações.
- Agregados regerados localmente com o privado (`build_casos.py`) e verificados no Chromium local (1300 e 390 px, sem erro de JavaScript). Testes: suíte OK.

## C19.48 — Cargas do 1º turno e do caso 1: limites marcados, Kwai refeito, começo do caso no X (2026-10-18) ⚠️

- Carga das demais chapas (run 39131229326): acervos TikTok 1.494, Instagram 3.942, Facebook 464, X 3.017 publicações. Sem leitura: Facebook EDPCB21 ("no_items") e AUGUSTOCURY.AUTOR ("not_available"); Instagram com 0 no período: cleusa_santos191, cachorreirosdesaopaulo, gateirosdabahia, gateirosdesaopaulo; X @Clarianabr 0; TikTok @oncaviral e @eduardogiraooficial sem vídeo desde 20/07. No limite (piso, não total): Instagram 294 em 10 perfis, X 574 em 3, TikTok 300 (limite do coletor) em 3 — o TikTok passa a marcar `no_limite` como as outras redes. Kwai falhou por falta de conta com saldo ≥ 0,60 → com conta reaproveitada aceita saldo menor; refeito só o Kwai.
- Caso 1, complemento do X (run 39132855716): +1.855 posts (total 4.642 publicações, X 4.528), mas o mais antigo continuou 17/10 12h18 UTC — no pico o X teve ≈ 2 mil posts por hora, e a busca "mais recentes" não alcança o começo. Tetos do caso redistribuídos dentro dos US$ 3 (X 1,30; Instagram 0,40; Kwai 0,30; Facebook 0,80) e novo complemento só antes de 17/10 06h (Brasília).
- `build_casos.py`: rede com termo no limite em qualquer coleta fica marcada (`no_limite`); a página mostra "≥" nos números e avisa na linha do tempo que o começo naquela rede pode estar fora.
- Testes: o commit anterior saiu com `test_casos` desatualizado (esperava 1.688 itens por termo; com o novo teto do X o máximo de 2.000 cabe) — corrigido no commit seguinte; suíte OK.

## C19.47 — Caso 1: resultado da carga e complemento do começo no X (2026-10-18) ⚠️

- Carga do caso 1 (run 39132035304): 2.787 publicações de 1.335 contas — X 2.673, TikTok 82, Instagram 19, Facebook 13, Kwai 0 (o feed da hashtag não trouxe nada desde 16/10). Pico: 17/10 11h (Brasília), 501 publicações na hora; meia-vida 3 h (`data/casos/001/caso.json`).
- Limites observados: no X as duas hashtags pararam no máximo pedido (1.685 cada) e a busca devolve as mais recentes primeiro — o mais antigo lido foi 17/10 12h48 UTC, então o começo do caso no X ficou de fora. O Instagram devolveu 10 por hashtag e nada de @verdeeamarelo; o Facebook, 5 por busca; o TikTok, 59 vídeos por hashtag (2 páginas).
- `--complemento` / modo `complemento` no workflow: roda só as buscas de `complementos_x` (caso 1: "#brasilinteiro since:2026-10-16 until:2026-10-17_12:48:00_UTC"), dentro do que resta do teto do X do caso.
- Testes: `TestComplemento`; suíte OK.

## C19.46 — Página: Casos e análises, todas as chapas do 1º turno e seguidores retroativos (2026-10-18) ⚠️

- Novo caderno **08 · Casos e análises** (menu lateral; índice passa a 8 cadernos): fichas dos 4 casos, dossiê do caso selecionado (marco zero geral e por termo, linha do tempo, números por rede, Google Trends e Notícias, circulação hora a hora com filtro por rede, primeiros e maiores, galeria, quadro de ligações com GEXF/CSV, palavras, tom ⛔, método e limites). Casos 2–4 aparecem como "aguardando confirmação de datas e termos", sem números. Nenhum custo de coleta na página.
- Panorama ganha a aba **Todas as chapas do 1º turno** (`data/primeiro_turno/resumo.json`): tabela chapa × rede (publicações, visualizações, interações ou seguidores; pré-campanha, 1º turno ou ambos), votos do 1º turno, soma por chapa, "≥" quando algum perfil bateu no limite, Lula primeiro com o aviso de que a ordem não indica preferência.
- Quem acompanha ganha a aba **Seguidores retroativos (todas as chapas)**: Social Blade e Internet Archive em séries separadas (não emendadas), tabela de cobertura por perfil, aviso de série parada (@eduardogiraooficial no TikTok) e de perfis só com o dia da coleta.
- Ajustes depois do teste do caso 1 (run 39131491525, 40 publicações: TikTok 25, X 10, Facebook 5): Instagram devolveu 0 itens pela página da hashtag → passa a usar a busca por palavra-chave do ator; Kwai ficou sem conta porque cada rede exigia conta diferente → agora reaproveita conta já usada quando nenhuma outra tem saldo (também no coletor do 1º turno); Google Notícias trazia títulos sem relação (busca casa com o corpo do texto) → só entram títulos com um dos termos do caso; a nuvem de palavras exclui as próprias hashtags do caso.
- Corrigido antes de publicar: o id `rtStatus` da nova aba colidia com o do caderno Reuters (renomeado para `sr*`).
- Verificado no Chromium local (1300 px e 390 px): as três abas renderizam com os dados do repositório, sem erro de JavaScript (só o 404 esperado de `wayback_historico.csv`, ainda não gerado), sem rolagem horizontal em 390 px. Testes: suíte OK. Pendente: cargas do caso 1 e do 1º turno, Internet Archive, conferência no site publicado.

## C19.45 — Casos e análises: coleta por hashtag e termo; seguidores pelo Internet Archive (2026-10-18) 🔜

- Pedido do usuário (18/10, 04h33): "Implemente a página de casos"; teto do caso 1 escolhido: US$ 3 ("caso 1 completo; os casos 2 a 4 entram como dossiê com o que já temos, até você confirmar as datas").
- `collect_casos.py` + `casos.yml`, configuração em `data/config/casos.json` (4 casos; só o 001 com `coletar: true`). Caso 001: #brasilinteiro, #verdeeamarelo, @verdeeamarelo, desde 16/10. TikTok pela página pública da hashtag (Playwright, grátis); X pelo xquik (hashtags e "@verdeeamarelo OR from:verdeeamarelo"); Instagram pelo apidojo/instagram-hashtag-scraper (página da hashtag) e esdrasdw (perfil @verdeeamarelo); Facebook pelo scrapeforge/facebook-search-posts; Kwai pelo feed da hashtag; Google Trends (por hora, 7 dias) e Google Notícias (RSS). Preços da loja Apify lidos no run 39130885845 (18/10); tetos por rede X 0,80 · Instagram 0,75 · Facebook 0,80 · Kwai 0,50 (= 2,85); itens por termo saem do teto (X 1.688, Instagram 800, Facebook 146, Kwai 118).
  - Aviso registrado no caso: #verdeeamarelo é hashtag antiga e genérica; cada publicação guarda o termo que a trouxe e a página separa os dois.
- `build_casos.py` → `data/casos/indice.json` e `data/casos/<id>/caso.json` (números por rede e termo, série por hora em horário de Brasília, pico e meia-vida, marco zero geral/por rede/por termo, primeiros e maiores, galeria, palavras, Google, desenho da rede, método) + `rede.gexf` e CSVs para o Gephi. Privacidade: publicações de qualquer pessoa; arquivo completo só no privado; conta com menos de 10 mil seguidores e sem selo aparece como código, sem texto nem link; perfis declarados ao TSE identificados. Tom da audiência ⛔ (o caso não coleta comentários). O custo da coleta não vai para a página.
- `collect_wayback_seguidores.py` + `wayback-seguidores.yml` (grátis): número de seguidores nas capturas do Internet Archive (até 1 por mês desde 01/2026), com o link de cada captura; perfis de todas as chapas do 1º turno.
- Social Blade na carga de 18/10 (run 39130851181): 602 pontos; 31 dias para 9 perfis de TikTok e 10 de YouTube; 13 perfis de TikTok com 1 ponto só (o Social Blade não tem histórico deles); erro em 5 perfis (alfredogasparoficial, 3 canais do YouTube de apoio e o de Gilberto Kassab). @eduardogiraooficial (TikTok) veio com série de 10/10 a 16/12/2024: o Social Blade parou de atualizar esse perfil — não é dado de 2026.
- Coleta das demais chapas (run 39130849798, teste): 10 posts por rede lidos em TikTok, Instagram, Facebook, X e Kwai. Carga disparada em seguida.
- Testes: `tests/test_casos.py` (pedidos e normalização; coleta simulada → agregados: marco zero anonimizado, perfil do TSE identificado, sem custo no JSON público, estado dos casos 2–4) e Wayback em `tests/test_primeiro_turno.py`; suíte completa OK. Pendente: execuções no Actions e a página.

## C19.44 — Todas as chapas do 1º turno e vices; seguidores retroativos para todos (2026-10-18) 🔜

- Pedido do usuário (18/10, 04h33): "colete todos dados de rede dos candidatos do 1º turno e vices" e "você consegue coletar seguidor retroativo?". Tetos escolhidos pelo usuário: US$ 6 para as publicações; "use até $5" para os seguidores retroativos. Contas dos outros pesquisadores (a conta 1 não é usada; a 8 fica com o Instagram).
- `collect_primeiro_turno.py` + `primeiro-turno.yml`: chapas que foram às urnas, menos 13 e 22 (já cobertas), titular e vice (vice soma na chapa), perfis declarados ao TSE. Endereços "site_ou_outro" só entram quando dizem a rede ("Tik Tok - @clarianabr", "X - @Clarianabr", kwai-video.com/u/@wilsongrassi); "@clarianabarao" solto não é atribuído. Chapa 28 fora (não foi às urnas). Perfis: Instagram 29, TikTok 14, Facebook 13, X 11, Kwai 4 (contagem de `alvos()` sobre o arquivo do TSE).
  - TikTok por yt-dlp (grátis). Instagram, Facebook, X e Kwai pela Apify com teto por rede em `data/config/primeiro_turno.json` (Facebook 3,40; X 1,00; Instagram 0,90; Kwai 0,60 = 5,90). Posts por perfil saem do teto, iguais para todos da rede: Facebook 49, X 575, Instagram 294 (duas leituras: posts e reels), Kwai 71 (`por_perfil`). Perfil que bateu no limite fica marcado (`no_limite`).
  - YouTube já cobria todas as chapas (API oficial; `videos_latest.csv.gz` tem Renan Santos, Zema, Caiado, Marçal, Hertz Dias, Girão).
- `build_primeiro_turno.py` → `data/primeiro_turno/resumo.json`: por chapa e rede, seguidores (último número de cada endereço), posts, visualizações e interações por fase, votos do 1º turno; cobertura da coleta das demais chapas (pedido por perfil, perfis com erro).
- Social Blade (`collect_socialblade.py`): de 13 e 22 para todas as chapas do 1º turno (TikTok e YouTube; Instagram segue bloqueado pelo Social Blade), canal corrigido do Augusto Cury, pula perfil com série lida há menos de 2 dias. Teto total 3 + 5 = US$ 8. Resposta ao "retroativo": o ator devolve ~30 dias (31 pontos por perfil na carga de 18/10); repetir a coleta a cada 2–4 semanas emenda a série.
- Testes: `tests/test_primeiro_turno.py` (alvos, endereços explícitos, cálculo por perfil, coleta com ator simulado, resumo, alvos do Social Blade); suíte completa OK. Pendente: execuções no Actions (IDs na próxima entrada).

## C19.43 — Teste de posicionamento v2: com contexto e só sobre o dono do conteúdo (2026-10-18) ⚠️

- Escolha do usuário (18/10): "versão 2 com modelo aberto". `teste_posicao.py --v2`: premissa "Comentário publicado num vídeo do canal de <dono> / em resposta a uma postagem de <dono>: <texto>", hipóteses "quem escreveu apoia / critica <dono>" (só o dono do conteúdo); links e @menções removidos; texto que sobra com menos de 8 letras → "sem conteúdo". Mesma amostra (semente 42).
- Privado: `posicao/teste_amostra_v2.csv` (previsões) e `posicao/codificacao_posicao_v2.csv` — 200 itens (50 por rede × dono), embaralhados e SEM a previsão do modelo, para duas pessoas codificarem (favor / contra / neutro / sem conteúdo). Público: `data/pontes/posicao_teste_v2.json`, só distribuição, "TESTE v2 · NÃO VALIDADO".
- Testes: suíte OK (`TestV2`). Execução: run 39107597882 (24 min, CPU do Actions).
- Resultado: pior que a v1. 600 itens: contra 434 (72%), favor 114, sem conteúdo 52. Leitura de 30 previsões sorteadas (privado, semente 11): 12 apoios explícitos rotulados "contra" com probabilidade ≥ 0,98 (ex.: "Presidente lula tem meu voto", "FLÁVIO BOLSONARO NO PRIMEIRO TURNO", "LULA VAI SER REELEITO"); a hipótese "critica" é aceita para quase tudo. Conclusão: o modelo sem treino não serve para a etiqueta de posição, nem com contexto. A planilha de codificação humana (200 itens, privado) continua válida para testar outra abordagem.

## C19.42 — Página do Instagram em branco no site (2026-10-18) ✅

- Relato do usuário (18/10, 04h15): "página Instagram tá em branco". Conferido no Chrome do usuário, no site publicado: os dados carregavam (4.629 posts de Lula e 695 de Flávio), mas a seção estava fora de `<main>` (filha de `<body>`, depois do rodapé), porque foi inserida após o último script do Facebook, que fica fora da área principal. O conteúdo ia para baixo do layout e a área visível ficava vazia. O teste local anterior usava captura da página inteira e não pegou isso.
- Correção: a seção do Instagram vai para dentro de `<main>`, logo depois da do Facebook; conferido que nenhum painel fica fora de `<main>`. Título da aba do navegador: V14 → V15 (auditoria, item 8).
- Verificado no Chromium local pelo caminho do usuário (menu → "O que as campanhas dizem" → aba Instagram), em tela de 1200×700: título, introdução e acervo visíveis no topo; sem erro de JavaScript.
- Testes: suíte OK.

## C19.41 — Pontes entre públicos: Gephi e IRaMuTeQ (2026-10-18) ✅

- Pedido do usuário (18/10, 03h23): "nessa página ponte entre públicos não esqueça IRaMuTeQ e Gephi". `build_pontes.py` passa a gerar, por rede: `data/pontes/<rede>_contas_ponte.gexf` (bipartida conta-ponte × conteúdo, peso = comentários, tom predominante na ligação) e `data/pontes/<rede>_respostas_entre_publicos.gexf` (dirigida, quem responde → respondido, nº de negativas). Autores só por código P0001… (ordem de atividade); a tabela código ↔ conta fica no privado (`pontes/<rede>_codigos.csv`). Corpus IRaMuTeQ privado (`pontes/<rede>_corpus_iramuteq.txt`) com os comentários das contas-ponte e as respostas entre públicos e as variáveis `*rede_ *conteudo_ *publico_ *ponte_ *resposta_entre_publicos_ *tom_ *fase_`.
- Números da execução local (repositório privado, 18/10): YouTube — rede de contas-ponte 1.530 nós / 3.501 ligações, respostas entre públicos 193 / 118, corpus 4.730 comentários; X (com a carga por post: 29.260 respostas, 12.693 autores) — 585 contas-ponte (4,61% dos autores), 58 respostas entre públicos de 2.561 com mensagem respondida na amostra, rede 1.172 / 3.978, corpus 4.926; Facebook (11.882 comentários após a ampliação) — 30 contas-ponte (0,28%), sem respostas.
- Página: cartão "Redes para o Gephi e corpus para o IRaMuTeQ" na aba Pontes, por rede, com downloads e instruções; a nota do X corrigida (agora há respostas entre públicos). Verificado no Chromium local, sem erro de JavaScript.
- Testes: suíte OK.

## C19.40 — Teste de posicionamento sem treino (2026-10-18) 🔜

- Pergunta do usuário (18/10, 03h57): "conseguimos testar?" (camada de posição proposta na revisão de literatura). Os textos do UstanceBR não são distribuídos (só ids do X, verificado no artigo), então o teste usa um modelo aberto de inferência textual multilíngue (`MoritzLaurer/mDeBERTa-v3-base-xnli-multilingual-nli-2mil7`) rodando no próprio Actions: nenhum comentário sai para serviço externo, sem custo.
- `scripts/teste_posicao.py` + `posicao-teste.yml`: amostra com semente fixa (400 comentários do YouTube e 200 respostas do X, metade em conteúdo de cada candidato, 20+ caracteres); para Lula e para Flávio, hipóteses "o autor apoia / é contra"; rótulo pela mais provável acima de 0,6, senão "neutro/incerto". Privado: `posicao/teste_amostra.csv` com colunas vazias para dois codificadores. Público: `data/pontes/posicao_teste.json`, só distribuição, marcada "TESTE · NÃO VALIDADO".
- Correção: a última etapa do workflow tinha dois-pontos numa linha `run:` simples (YAML inválido; o GitHub recusava o disparo com "não tem workflow_dispatch"). Passou a bloco `run: |`.
- Execução (18/10, 06h59–07h22 UTC; 600 textos em 1.306 s de CPU, sem custo). Distribuição em `data/pontes/posicao_teste.json` (marcada TESTE · NÃO VALIDADO).
- Leitura da amostra (privado): o modelo rotula posição sobre o alvo mesmo quando o texto não o menciona (Lula: 378 de 517 rótulos, 73%; Flávio: 307 de 512, 60%) e não sabe em que conteúdo o comentário está. Em 12 exemplos lidos, ao menos 5 erros evidentes (ex.: "@LulaOficial" + link → "apoia Lula" 0,996; crítica a Lula num vídeo de Lula → "contra Flávio" 0,949). Conclusão: como está, não serve para etiquetar comentários. Próximo passo proposto ao usuário: versão 2 com o contexto ("comentário num vídeo de X") e alvo = dono do conteúdo, mais validação humana.
- Testes: suíte OK (`test_posicao`).

## C19.39 — Nuvens, hashtags e mapa de tags acompanham o filtro de fase (2026-10-18) ⚠️

- Pedido do usuário (18/10, 03h31, print do mapa de tags com "acervo completo · não acompanha o filtro"): "integre ao filtro". `build_conteudo.py` (YouTube) grava `nuvem_por_fase` e `mapa_tags_por_fase`; `build_tiktok.py` (TikTok, Kwai, Facebook, X, Instagram) grava `nuvem_por_fase` e `hashtags_por_fase`. Nas 6 páginas, nuvens, hashtags e o mapa de tags são redesenhados ao trocar a fase, e o selo do cartão vira "acompanha o filtro de fase". Conteúdos regenerados localmente.
- Verificado no Chromium local (todo o período → 2º turno): YouTube, mapa de tags de Flávio "#vote22 29 vídeos" → "#flaviobolsonaro 6, #vote22 5"; TikTok, hashtags de Flávio "#ultimasnoticias 30, #vote22 28" → "#vote22 6, #bolsafamilia 3"; nuvens mudam; sem erro de JavaScript.
- ⚠️ Ainda não acompanham o filtro: estratégias discursivas (Bardin) e CHD (trabalho iniciado e guardado fora do repositório; o primeiro teste quebrou o gerador do corpus e não foi enviado), rede de influenciadores do YouTube e rede de contas do TikTok com hashtags dos candidatos.
- Testes: suíte OK.

## C19.38 — YouTube: canal correto do Augusto Cury (2026-10-18) 🔜

- O usuário indicou (18/10, 03h44) o canal correto: https://www.youtube.com/@AugustoCury. O endereço declarado ao TSE (`/CHANNEL/UC3F2E1LOB9X8AWYULLURYJG`, todo em maiúsculas) não é encontrado pela API. Novo `data/config/youtube_correcoes.json` (endereço do TSE → endereço usado, com quem indicou e quando); `collect_youtube.load_targets` usa o corrigido na consulta e mantém a URL do TSE para casar com o card (`corrigido_para` registrado).
- Testes: `test_youtube_correcoes`. Pendente: próxima coleta diária do YouTube.
- Fora deste commit (em andamento, não publicado): análise de conteúdo (Bardin e CHD) por fase — o primeiro teste local quebrou o gerador do corpus e sobrescreveu as CHDs locais com classes vazias; nada disso foi enviado.

## C19.37 — Redes do Gephi acompanham o filtro de fase (2026-10-18) ✅

- Pedido do usuário (18/10, 03h26): "a gente consegue fazer o Gephi também se alterar". `build_rede.py` e `build_rede_mencoes_tiktok.py` passam a gerar, além da rede do período todo, uma rede por fase (`rede_pre`, `rede_turno1`, `rede_turno2` e `rede_mencoes_<fase>`, em JSON, GEXF e CSV). Fase com menos de 10 conteúdos (coocorrência) ou 5 (menções) não gera rede, e arquivos antigos dessa fase são apagados.
- Página: ao trocar a fase em qualquer página de conteúdo, as redes de coocorrência e de menções recarregam a rede da fase, os desenhos antigos são limpos, os links de GEXF e CSV passam a apontar para a fase e o selo do cartão vira "acompanha o filtro de fase". Sem rede para a fase: "poucos conteúdos nesta fase para formar a rede". A rede de influenciadores do YouTube não é por fase e mantém o link original.
- Correção encontrada no teste: o botão "Baixar .gexf" do painel lateral das redes de TikTok, Kwai, Facebook, Instagram e X baixava a rede do YouTube (texto copiado na geração das páginas); agora baixa a rede da própria plataforma e da fase.
- Redes geradas localmente (exemplos): YouTube pré 41 nós, 1º turno 147, 2º turno 22; Facebook 1º turno 25, 2º turno 130, pré sem rede (sem posts coletados); menções do X pré 64 contas, 1º turno 124, 2º turno 104.
- Verificado no Chromium local (Facebook, YouTube, Instagram; período todo → 2º turno → pré): desenho e links mudam, sem erro de JavaScript.
- Testes: suíte OK.

## C19.36 — Página do Instagram verificada com a carga (2026-10-18) ✅

- Aberta no Chromium local com os 3.599 posts: cobertura (Lula 262 / 1.541 / 1.101; Flávio 159 / 393 / 143 por fase, com aviso de variação em Lula), lista de perfis, temas, linha do tempo, nuvens, posts, CHD e redes, sem erro de JavaScript.
- Correções: o "espalhamento" vertical das bolhas lia os últimos dígitos do id do post (no Instagram o código tem letras → coordenada NaN); agora usa um hash do código. A bolha usa curtidas quando o post não tem visualização (fotos e carrosséis), como o título já dizia. A lista de perfis lia `lidos` (campo do Facebook); passa a ler também `lidos_no_periodo` ("823 posts desde 20/07").
- Testes: suíte OK.

## C19.35 — Instagram: gravar a coleta antes das etapas lentas; miniaturas em paralelo (2026-10-18) 🔜

- A 1ª carga do Instagram (run 39100842854) terminou a coleta em 9 min, mas a etapa de miniaturas passou de 30 min (≈1.100 capas baixadas uma a uma, espera de até 30 s cada), com risco de o job (limite de 60 min) acabar antes de gravar os posts. `instagram-posts.yml`: grava `data/` logo após a coleta, miniaturas com limite de 15 min, job com limite de 120 min. `build_miniaturas_kwai.py`: 8 downloads em paralelo (vale para Kwai, Facebook, X e Instagram).
- Carga (run 39100842854, conta 8): 3.599 posts de 17 perfis desde 20/07 (US$ 0,34). @lulaoficial 823, @flaviobolsonaro 316; brasilcomlula, lulaversoficial e pode_espalhar bateram o limite de 400 (mais antigo: 26/09, 12/09 e 20/09); denunciabr_reserva, denunciabr_reserva1 e flaviocomaverdade sem posts no período. Visualizações vazias em 1.272 (fotos e carrosséis), legenda vazia em 14. Limite dos perfis de apoio sobe para 1.500 e a carga é refeita.
- Testes: suíte OK.

## C19.34 — Auditoria (itens 10 e 12): Trends, contas × eleitorado e Reuters (2026-10-18) ✅

- **10 · Trends**: o botão "2º turno · tópicos" escolhia os candidatos, não o período. As consultas passam a se chamar "Lula × Flávio · tópicos", "5 mais votados no 1º turno · tópicos" e "Lula × Flávio · palavras soltas", com rótulos separados para "quem entra na comparação" e "período (independe da consulta)". A série sem picos passa a se chamar "Série tratada · picos trocados pela mediana (não é observação direta)"; a original continua sendo a padrão.
- **12 · Contas × eleitorado**: o destaque deixa de ser o percentual (ex.: 9,83%) e passa a ser as duas magnitudes lado a lado ("≈ N contas no Brasil" e "158.745.463 eleitores aptos"); a razão fica como referência de escala.
- **12 · Reuters 2022 × 2026**: o aviso "pergunta diferente em 2022 e 2026 · não é tendência direta" sobe para o título dos dois gráficos de alcance semanal.
- Testes: suíte OK; Trends, Contas × eleitorado e Reuters abertos no Chromium local sem erro de JavaScript.

## C19.33 — Auditoria (item 9): cobertura da coleta por fase e Kwai que não fechava (2026-10-18) ⚠️

- **Kwai: Panorama com 50 vídeos de @Lulaoficial e lista de perfis com zero**: a lista lia `videos_no_acervo`, que `build_tiktok` não gravava. Agora grava `videos_no_acervo` e `videos_desde_20_07` por perfil (conteúdo regenerado: Lulaoficial 50 no acervo / 50 desde 20/07; podeespalhar 315 / 107; FlavioBolsonaro 955 / 100). As contagens "desde 16/08" do Kwai e do TikTok passam a "desde 20/07" (início adotado pelo Atlas); a introdução dos comentários do Kwai diz "desde 20/07". O "16/08" do Google (início oficial da campanha) foi mantido.
- **Comparações dominadas pela cobertura**: cada página de conteúdo (YouTube, TikTok, Kwai, Facebook, Instagram, X) ganha a tabela "Cobertura da coleta" (conteúdos por candidato e fase, e média por dia) com aviso quando a média de um candidato varia mais de 4× entre fases. Situação atual (Chromium local): Facebook — Lula 0 / 19 / 282 e Flávio 0 / 118 / 52 (pré / 1º / 2º turno; a coleta de posts começou em 16/08 e o ator lê os mais recentes primeiro); Kwai — Lula 21 / 74 / 62. ⚠️ Lacuna real do Facebook (pré-campanha e 1º turno de Lula); "comparação com cobertura equivalente" ainda não implementada.
- Testes: suíte OK; sem erro de JavaScript.

## C19.32 — Auditoria (item 8): versão, última coleta por fonte e revisão separadas (2026-10-18) ✅

- **8 · Documentação atrás das coletas** (cabeçalho "Capturas: 10–11 OUT 2026", rodapé "v14"): o cabeçalho passa a mostrar a data da coleta mais recente lida dos manifestos ("Última coleta: 18/10/2026, 02:30" no teste local); o rodapé diz v15 (MVP); o LEIA-ME ganha o quadro "Versão, coletas e revisão", com versão do produto, data da última revisão metodológica e uma tabela de 21 fontes com a data e a situação da última coleta de cada uma, lidas dos próprios manifestos ao abrir a página (sem custo). Arquivos que só têm o dia (assuntos do dia do X) aparecem como "(só o dia)" e não entram na data do cabeçalho.
- Testes: suíte OK; LEIA-ME aberto no Chromium local sem erro de JavaScript.

## C19.31 — Auditoria (item 1): o filtro de fase governa a página (2026-10-18) ✅

- **1 · Filtro de turno só mudava parte da página**: nas 6 páginas de conteúdo (YouTube, TikTok, Kwai, Facebook, Instagram, X), as contagens por tema (chips e barras), "citam o adversário", "pedem voto" e a interação mediana passam a ser calculadas sobre os conteúdos da fase escolhida (antes vinham do acervo inteiro). Componentes que dependem de análises pré-calculadas sobre o acervo (nuvens, mapa de tags, CHD, redes de coocorrência e de menções, influenciadores) ganham o selo "acervo completo · não acompanha o filtro de fase".
- Verificado no Chromium local (todo o período × 2º turno, Lula): YouTube 1.030 → 131 vídeos, cita adversário 79 → 22, pede voto 22 → 5, chip "Todos" 1.552 → 243; TikTok 826 → 112, interação mediana 11,7% → 16,7%; Facebook 301 → 282 posts; X 2.149 → 451. Sem erro de JavaScript.
- Testes: suíte OK.

## C19.30 — Auditoria (item 4): análises de discurso sem rodapé legal e sem acervo antigo (2026-10-18) ✅

- **4 · Classes da CHD com CNPJ, coligação, federação e partidos (Facebook e X) e com 2022/2024 e hashtags de formato (Kwai)**: `build_conteudo.texto_util` passa a descartar trechos do rodapé legal da propaganda (CNPJ, coligação, federação, "propaganda eleitoral"); hashtags de formato (#fyp, #viral, #parati, #explore...) entram na lista de palavras vazias; as análises de discurso do Kwai (corpus, CHD, redes) passam a usar só a campanha de 2026 (desde 20/07), como as outras redes — a página de conteúdo continua mostrando o acervo histórico. O texto original fica no acervo para auditoria.
- Regeneradas localmente as análises de conteúdo de YouTube, TikTok, Kwai, Facebook e X (`build_tiktok`/`build_conteudo`, `corpus_populismo`, `chd_reinert`, `concordancia`, `build_rede`). Conferido: nenhuma classe de YouTube, TikTok, Kwai, Facebook ou X contém "cnpj" ou "coligação"; classes novas, por exemplo, Facebook: escala 6×1 / descanso, programas sociais, futuro/esperança, voto 22; Kwai: escala 6×1, voto 22, independência/retrocesso. Pendente: Instagram (gerado antes da correção; refazer após a carga).
- Testes: suíte OK (`TestRodape`).

## C19.29 — Auditoria (itens 5 e 11): χ² com direção e palavras partidas (2026-10-18) ✅

- **5 · "χ² -79,7"**: a CHD grava o χ² 2×2 com sinal (+ acima do esperado, − abaixo). A página passa a mostrar o valor absoluto e a direção por extenso ("χ² 79,7 abaixo do esperado") e avisa que é implementação própria do método de Reinert, ainda não comparada com o IRaMuTeQ.
- **11 · "fla", "vio", "fami lia", "heart" nos comentários do Kwai**: parte dos comentários vem com acento decomposto (Unicode NFD) e o separador de palavras cortava no acento; o Kwai entrega emojis como texto ("[heart]", "[heart_eyes]"). `build_conteudo.termos` normaliza para NFC antes de separar e `norm` remove os emojis em colchetes (vale para nuvens, redes e CHD de todas as redes). Análises de comentários do Kwai regeneradas: `analise.json` e `rede_termos.json` sem esses fragmentos (conferido). Facebook e YouTube saem corrigidos no próximo run de cada um.
- Testes: suíte OK (`test_normalizacao`).

## C19.28 — Auditoria (itens 2, 3, 6 e 7) e página do Instagram (2026-10-18) ⚠️

- O usuário anexou uma auditoria (18/10, 02h21) com 12 correções. Feitas nesta entrada:
  - **2 · Sentimento do Kwai não fechava** ("513 de 678", 489 + 28 = 517 e "todos foram classificados"): o acervo repetia ids de comentário (agora contados uma vez); o total de classificados passa a contar só comentários do acervo; a página mostra "N de M comentários classificados (K sem texto classificável)" e o status quando não está completo. O texto de método deixa de repetir o universo do YouTube: cada rede tem o seu (`data/config/sentimento_comentarios.json`, chave `universo`). Os números só mudam no próximo run do sentimento (o arquivo atual do Kwai é de antes da carga de comentários terminar: 678 coletados contra 1.137 no acervo).
  - **3 · Anúncios por fase não somavam o total** (850 por busca; fases somam 664 em Lula e 743 em Flávio): a tabela ganhou a linha "sem data ou início fora das fases" (186 e 107) e o total da busca. A partir da próxima coleta, `collect_meta_anuncios.agregar` grava `fora_das_fases` com o gasto dessa linha; até lá a página mostra só a contagem e diz que o gasto não está separado.
  - **6 · Rede de respostas zerada onde não há respostas**: no Kwai e no Facebook a seção passa a dizer "não disponível: esta coleta não inclui respostas" (antes, zeros e "null" com texto da API do YouTube).
  - **7 · Textos copiados entre redes**: faixas do Kwai e do X diziam "TIKTOK"; a de comentários do Facebook dizia "KWAI"; "comentários dos vídeos" no Facebook vira "dos posts"; nas páginas do Facebook, X e Instagram "vídeo(s)" vira "post(s)" nos rótulos.
- Página do Instagram ("Instagram" em O que as campanhas dizem), gerada da página do Facebook com textos próprios: perfis (não páginas), visualizações só em reels, sem compartilhamentos. Verificação com os 10 posts do teste: com o Flávio ainda sem posts, o gráfico de bolhas gera coordenadas NaN; refazer a verificação com a carga completa.
- Testes: suíte OK; páginas de anúncios e Facebook abertas no Chromium local sem erro de JavaScript.

## C19.27 — Instagram: coletor de posts das campanhas (2026-10-18) 🔜

- Pedido do usuário (18/10, 02h21–02h24): página "o que as campanhas dizem" do Instagram, teto de US$ 5, numa das contas novas (conta 8, só para o Instagram).
- Preços consultados na loja Apify (API pública `/v2/store` pelo workflow `teste-apify-loja` e páginas dos atores, 18/10, plano gratuito): esdrasdw/instagram-content-scraper US$ 0,05/1.000 itens; sones/instagram-posts-scraper-lowcost US$ 0,30/1.000 + US$ 0,005 por execução; apidojo/instagram-scraper US$ 0,50/1.000; apify/instagram-post-scraper US$ 1,70/1.000; apify/instagram-scraper US$ 2,70/1.000. Ordem de teste no `data/config/instagram_posts.json`.
- `scripts/collect_instagram_posts.py` + `instagram-posts.yml`: perfis de Instagram das chapas 13 e 22 (presidente e vice; vice na chapa do titular), sem os 2 que não existem mais, desde 20/07; até 1.500 posts nos perfis principais e 400 nos demais; descarta itens de demonstração e fora do período. Mesmo formato de acervo das outras redes; `build_tiktok`, análises (`--plataforma instagram`), menções e miniaturas aceitam `--instagram`.
- 1º teste real (esdrasdw, conta 8, 10 posts de @lulaoficial): 10 de 10 com data, curtidas, comentários e imagem; sem legenda completa (só `title`, a 1ª linha) e sem visualizações (o ator só informa plays no modo reels). Correção: pedir `caption` em `selectedFields` e fazer uma 2ª leitura no modo reels só para as visualizações, juntando pelo shortCode.
- Testes: suíte OK (`test_instagram_posts`, dados simulados). Pendente: novo teste, carga e a página.

## C19.26 — Pontes entre públicos e temas que circulam (2026-10-18) ⚠️

- Pedido do usuário (18/10, 02h00 e 02h07): na área de comentários, encontrar contas que interagem com os dois campos, respostas entre comunidades e circulação dos mesmos temas em espaços distintos, sem presumir orientação política individual por uma interação.
- `scripts/build_pontes.py` (YouTube, X, Facebook) → `data/pontes/<rede>.json`, só agregados. "Público frequente" = autor com 2+ comentários e 2/3 deles num candidato (comportamento, não orientação). Mede contas-ponte (por semana e fase), tom (modelo de sentimento do Atlas) das contas-ponte, do público do adversário e do próprio público, respostas entre públicos (onde há árvore de respostas) com temas, e conteúdos que atraem o público do adversário (30+ comentaristas com público definido).
- `scripts/build_temas_circulam.py` → `data/pontes/temas.json`: % semanal dos conteúdos de cada candidato por tema (YouTube, TikTok, Kwai, Facebook, X e todas juntas) e dos comentários do YouTube; picos (média + 1 desvio-padrão, mínimo 5 pontos), quem chegou primeiro (pico do outro lado em até 2 semanas; sequência, não causa) e correlação semanal.
- Primeira execução com os dados atuais (repositório privado, 18/10): YouTube 158.365 comentários de 65.359 autores; 719 contas-ponte (1,1%); público frequente: 13.563 de Lula e 9.037 de Flávio; 127 de 19.498 respostas (0,65%) ligam públicos diferentes, tom 42,5% negativo (todas as respostas: 28,2%). Comentários das contas-ponte nos vídeos de Lula: 39,0% negativos (próprio público: 14,7%). Em 45,8% dos vídeos de Lula e 49,7% dos de Flávio com 30+ comentaristas de público definido aparece ao menos um do público do adversário. Facebook: 4 contas-ponte em 4.405 autores (amostra sem respostas). X: só o teste de 39 respostas até a carga terminar. Temas: picos em comum em segurança (2), religião e valores (3), eleição e instituições (2) e agenda de campanha (1).
- Página: nova aba "Pontes entre públicos" em Comentários, com aviso de método no topo, escolha de rede, quatro blocos e downloads. Aberta no Chromium local (1300 px e 390 px, sem rolagem lateral, sem erro de JavaScript).
- Diário: `sentimento-youtube.yml` classifica também as respostas do X (`--plataforma x`, lendo `x/respostas`) e recalcula as pontes e os temas depois do sentimento.
- ⚠️ Os comentários do YouTube começam em 16/08 (a pré-campanha tem 1 autor); o X e o Facebook dependem das cargas em andamento.
- Testes: suíte OK (`test_pontes`).

## C19.25 — Facebook: amostra maior de comentários (2026-10-18) 🔜

- Pedido do usuário (18/10, 02h10): ampliar os comentários do Facebook com mais US$ 3 (teto da fonte: US$ 1,50 → US$ 4,50). Cota por candidato 2.800 → 8.800; até 200 comentários por post (antes 50).
- `collect_comentarios_facebook.py`: um post deixa de ser "feito" só por ter alguma coleta; volta à fila se tiver menos de 80% da meta atual. Comentários repetidos (mesmo id) são descartados ao juntar com o acervo. Custo conhecido: a nova leitura de um post já coletado paga de novo os comentários que já tínhamos.
- 1ª carga (run de 18/10 05h14 UTC): 1.518 comentários novos (acervo 5.994: Lula 3.344, Flávio 2.650; 431 posts). Parou porque a conta 3 bateu o limite do mês (HTTP 403 "Monthly usage hard limit exceeded") e o coletor não trocava de conta. Correção: em 403 ele passa para a próxima conta com saldo; o teto da fonte vale para a soma das contas.
- Testes: suíte OK. Pendente: continuar a carga.

## C19.24 — X: respostas aos candidatos para a análise de pontes (2026-10-18) 🔜

- Pedido do usuário (18/10, 02h07): coletar as respostas aos posts dos candidatos no X. Coletar tudo custaria ~US$ 147 (os posts de Lula e Flávio desde 20/07 em `data/x/videos.csv.gz` informam 981.931 respostas; US$ 0,00015 cada, `data/config/x_posts.json`); o usuário escolheu teto de US$ 5.
- `scripts/collect_x_respostas.py` + `data/config/x_respostas.json` + `x-respostas.yml`: busca `to:<perfil> since:<dia> until:<dia+1> filter:replies` para @LulaOficial e @FlavioBolsonaro, um dia por vez desde 20/07, mesmo número por candidato e por dia (o teto define quantas por dia). Troca de conta quando o saldo acaba (contas 3 a 15). Texto e autor só no repositório privado (`x/respostas/respostas.csv.gz`, mesmas colunas dos comentários do YouTube); manifesto público só com contagens.
- 1º teste real (run do x-respostas, 18/10 05h11 UTC): parou antes de chamar a Apify, porque o teto de teste (US$ 0,02) era menor que a estimativa do lote com margem (US$ 0,0266); custo zero. Teto de teste passa a US$ 0,05.
- 2º teste real (18/10 05h12 UTC, conta 3): 39 respostas de 10/10 (19 a @LulaOficial, 20 a @FlavioBolsonaro), 26 autores, todas com autor e post respondido. Campo `ordem` passa a marcar `direta` (resposta ao candidato) ou `na_conversa` (resposta a outra pessoa dentro da conversa do post).
- Carga por dia (run de 18/10 05h13 UTC, conta 3): 178 buscas, 8.041 respostas (3.978 a @LulaOficial, 4.063 a @FlavioBolsonaro), 4.415 autores, US$ 1,21. A busca devolveu bem menos que o pedido nas datas antigas (mediana de 19 respostas por dia; só 7 dias cheios por candidato): julho 306/431, outubro 1.692/1.636.
- 2ª estratégia (`--por-post`, modos `teste-por-post` e `carga-por-post`): respostas de cada post (`conversation_id:<id>`), os 15 posts com mais respostas de cada semana por candidato, mesmo teto por post, com o saldo restante da fonte (US$ 3,79).
- Carga por post (run de 18/10 05h21 UTC): 390 buscas (15 posts por semana por candidato, até 61 respostas cada), 22.626 respostas novas. Acervo final: 29.260 respostas (14.375 a @LulaOficial, 14.885 a @FlavioBolsonaro), 12.693 autores, todas com autor e post respondido; 1 busca com erro de rede (IncompleteRead). Gasto total da fonte: US$ 4,63 de US$ 5.
- Testes: suíte OK (`test_x_respostas`, dados simulados).

## C19.23 — WhatsApp: seguidores dos canais públicos (2026-10-18) 🔜

- Decisão do usuário (18/10, 02h): não usar o ator extremescrapes/whatsapp-messages-scraper (exige conectar um WhatsApp pessoal por QR code e lê conversas privadas e grupos, com telefone de pessoas comuns; não traz histórico). Primeira camada de WhatsApp: só os canais públicos declarados ao TSE.
- `scripts/collect_whatsapp_canais.py`: lê a página pública de cada canal (whatsapp.com/channel/…, sem login, sem Apify) e extrai nome e "N seguidores" das metatags. Link de grupo (chat.whatsapp.com) não é canal e fica registrado como não coletado. Saída `data/seguidores/whatsapp_latest.csv` (lida pela página e pelo resumo da IA) e manifesto. Workflow `whatsapp-canais.yml` diário (11h41 UTC).
- 1ª execução: 3 de 7 endereços com número — EXÉRCITO DO LULA 5,2 mi, Canal do Lula 1,7 mi, TROPA DO FLÁVIO 🇧🇷 1,9 mi (a página só mostra o número arredondado, ex.: "5,2 mi"). Sem número: 3 canais com ID declarado ao TSE todo em maiúsculas (o ID de canal do WhatsApp diferencia maiúsculas; o card explica) e 1 link de grupo de Alfredo Gaspar.
- A página usava a base de redes do TSE de 10/10; 13 endereços acrescentados pelo TSE depois disso (base de 15/10) não tinham card, entre eles os dois canais do Lula e a Tropa do Flávio. Incluídos em `DATA.declarations`, com a nota "acrescentado pelo TSE depois de 10/10/2026".
- A camada de WhatsApp que já existia (`collect_whatsapp.py`, `data/whatsapp/`, usada no Panorama) acompanhava só os 2 canais do Lula; a Tropa do Flávio entra em `data/config/whatsapp_canais.json`.
- Testes: suíte OK; página aberta no Chromium local com todos os candidatos, sem erro de JavaScript.

## C19.22 — Contas Apify 8 a 15 como reserva (2026-10-18) 🔜

- O usuário cadastrou mais uma conta Apify (18/10) e disse que pode cadastrar até mais 8. Todos os coletores que usam as contas dos outros pesquisadores (Kwai, comentários do Kwai e do Facebook, posts do Facebook e do X, seguidores do TikTok, Social Blade e perfis sem número) e a verificação diária de saldo passam a aceitar `APIFY_TOKEN_8` a `APIFY_TOKEN_15`, nessa ordem, depois das contas 3 a 7. Segredo ausente é pulado. A conta 1 continua só nas rotinas diárias.
- Testes: suíte OK. Pendente: verificação de saldo para confirmar o nome do segredo da conta nova.

## C19.21 — Card "Perfil não encontrado" e Facebook nos perfis sem número (2026-10-18) 🔜

- 2ª execução do coletor de faltantes: os atores responderam "Profile does not exist" para Instagram comitepopularoficial e alfredogasparoficial e "This profile/hashtag does not exist." para TikTok alfredogasparoficial (`data/seguidores/complemento_manifesto_latest.json`). Esses endereços foram declarados ao TSE mas não existem hoje na rede. O card deixa de dizer "Não coletado" e passa a dizer "Perfil não encontrado", com a mensagem da rede e a data da consulta.
- Facebook entra no coletor de faltantes (apify/facebook-pages-scraper): o card facebook.com/lulaverso estava sem número (item vazio na coleta diária de 17/10, `bruto/2026-10-17/facebook.json`).
- Execução com Facebook (3ª): facebook.com/lulaverso → o Facebook respondeu que o conteúdo foi apagado ou restrito; o card mostra "Perfil indisponível" com essa mensagem. X @pl22al: o ator devolveu item de **demonstração** do plano gratuito; o "1 seguidor" da 1ª execução foi descartado do CSV e itens de demonstração passam a ser ignorados.
- Varredura da página (Chromium local, todos os candidatos): os cards "Não coletado" não eram só da chapa 13/22. TikTok, X e o coletor de faltantes só olhavam as chapas 13 e 22, e gravavam os perfis dos vices com o id do titular (por isso Alckmin e Alfredo Gaspar ficavam "Pendente" no card deles). O coletor de faltantes passa a usar `redes_sociais_candidatos_2026.csv.gz` (presidente e vice, id de cada pessoa): 42 cards sem número, 2 preenchidos com número já coletado sob outro id e 40 perfis a consultar (uma consulta por perfil, mesmo se declarado por mais de uma pessoa).
- Execução com todos os candidatos (run 39095193884): 2 cards preenchidos com número já coletado; 20 de 40 perfis consultados com número — todos os TikToks que existem (ex.: pablomarcal1, renansantosmbl, romeuzemaoficial, ronaldocaiado, augustocuryoficial, eduardogiraooficial, alckmingeraldo). Sem número: Instagram cleusa_santos191, gateirosdesaopaulo, alfredogasparoficial e comitepopularoficial ("Profile does not exist"); Facebook augustocury.autor e lulaverso (apagado ou restrito); TikTok alfredogasparoficial (não existe); 13 perfis do X (o ator de perfis do X só devolveu item de demonstração, descartado).
- X passa a usar xquik/x-tweet-scraper (o mesmo dos posts, funciona no plano gratuito): post mais recente do perfil, em qualquer data, e o número de seguidores do autor.
- Execução com xquik (run 39095371366): 33 de 40 perfis consultados com número; todos os 13 do X resolvidos (ex.: romeuzema 604.079, edugiraooficial 548.564, ronaldocaiado 515.828, pablomarcal 433.450; LulaEvangelicos 287; pl22al 1, agora confirmado por um segundo ator). Os 7 sem número são perfis que a rede diz não existir ou estar restritos.
- YouTube: os 3 cards sem número são canais que a API do YouTube não encontrou (`youtube_manifesto_latest.json`, `encontrado: false`): 2 IDs de canal declarados ao TSE todo em maiúsculas (o ID do YouTube diferencia maiúsculas, não dá para recuperar) e @tv.celular. O card passa a dizer isso.
- Varredura final da página (Chromium local, todos os candidatos, sem erro de JavaScript): Lula e Flávio sem nenhum card "Não coletado" em rede com contagem pública. Ainda pendentes: Kwai de Augusto Cury, Ronaldo Caiado e Wilson Grassi (o coletor de Kwai só cobre 13 e 22) e 2 links de compartilhamento do Facebook (facebook.com/share/…, sem página identificável).
- Testes: suíte OK (140).

## C19.20 — Chat com a IA (Gemini) e perfis sem número de seguidores (2026-10-18) 🔜

- Chat: ícone no canto inferior esquerdo da página abre uma conversa com a IA (Gemini). A página chama a função `odi-chat` do Supabase (projeto gratuito `odi-atlas`, criado com autorização do usuário em 18/10); a chave do Gemini fica só nos segredos do Supabase (`GEMINI_API_KEY` ou `GEMINI`), nunca na página nem no repositório. A IA lê apenas `data/ia/resumo.json` (agregados públicos com fonte e data, gerado por `scripts/build_resumo_ia.py`, 42 KB), não o DuckDB nem textos de comentários. Código da função em `supabase/functions/odi-chat/index.ts` (versão implantada: 1).
- Seguidores: os cards "Não coletado" eram perfis em que o ator principal não devolveu número — TikTok (apidojo devolveu `noResults` para 7 perfis: evangelicoscomlula, comitedeluta, brasilcomlula_, canaltvcelular, alckmingeraldo, alfredogaspar, alfredogasparoficial; manifesto `tiktok_manifesto_latest.json`), X (LulaEvangelicos e pl22al sem post desde 20/07, e o número vinha dos posts; `data/x/manifesto_latest.json`) e Instagram (comitepopularoficial e alfredogasparoficial com item vazio; `bruto/2026-10-17/instagram.json`). Novo `scripts/collect_seguidores_faltantes.py`: consulta direta ao perfil com atores alternativos (TikTok: clockworks; X: apidojo/twitter-user-scraper; Instagram: apify/instagram-profile-scraper e apify/instagram-scraper), contas 3 a 7, saída `data/seguidores/complemento_latest.csv` (lida pela página e pelo resumo da IA). Workflow `seguidores-faltantes.yml` diário (11h17 UTC), que também regenera o resumo da IA.
- Execução real (run 39094718752): 8 de 11 perfis com número — TikTok brasilcomlula_ 3.026, comitedeluta 1.186, evangelicoscomlula 359, canaltvcelular 58, alckmingeraldo 234.800, alfredogaspar 46; X LulaEvangelicos 287, pl22al 1 (⚠️ valor do ator, conta sem posts desde 20/07; conferir no perfil). ⛔ sem número: TikTok e Instagram alfredogasparoficial e Instagram comitepopularoficial (os atores devolveram item de erro; o coletor passa a gravar a mensagem do ator no manifesto).
- Testes: suíte OK (`test_seguidores_faltantes`). Pendente: o chat só responde depois que a chave do Gemini for cadastrada no Supabase.

## C19.19 — Ordem fixa: Lula primeiro, com aviso (2026-10-18) 🔜

- Decisão do usuário (pergunta de 18/10): Lula primeiro em todas as páginas por ser o candidato à reeleição, com aviso. `data/config/trends.json`: termos com Lula primeiro nas 3 consultas que o incluem (a ordem não muda os índices do Trends, a escala é comum à consulta); `ordem_nota` registra a regra. Página: selo fixo no cabeçalho "ORDEM: LULA (ATUAL PRESIDENTE, À REELEIÇÃO) · FLÁVIO — NÃO INDICA PREFERÊNCIA".
- Testes: suíte OK. Pendente: nova coleta do Trends com a ordem nova.

## C19.18 — Social Blade: 30 dias retroativos de TikTok e YouTube (2026-10-18) ⚠️

- Carga (16 perfis, US$ 0,33): **222 pontos diários de 16/09 a 18/10** — TikTok flaviobolsonaro, lulaoficial, pode_espalhar e alckmingeraldo (31 dias cada); YouTube flaviobolsonaro, lulaoficial e brasilcomlula (31 dias cada); comitedeluta, canaltvcelular, brasilcomlula_, evangelicoscomlula e alfredogaspar com 1 ponto; alfredogasparoficial e 3 canais de YouTube sem dados. Arquivo `data/seguidores/socialblade_historico.csv`.
- Teste de histórico pelo id com `historyLimit` 365 (US$ 0,02): devolveu os mesmos 30 dias. O Social Blade só entrega ~30 dias por essa via; a pré-campanha (20/07 a 15/08) não tem série retroativa. Instagram: série bloqueada pelo próprio Social Blade (README do ator).
- Testes: suíte OK.

## C19.17 — Sentimento por semana de campanha (menu recolhível) (2026-10-18) 🔜

- Pedido do usuário (print do "Tom geral dos comentários"): nos quadros por fase, um menu oculto com a métrica por semana de campanha. `build_sentimento_comentarios.py` passa a gravar, em cada fase, `semanas` (segunda a domingo, rótulo da segunda-feira) com a mesma distribuição; a tabela de sentimento do YouTube, Kwai e Facebook ganha, sob cada fase, "Ver por semana de campanha (N)" (recolhido por padrão). "Fora da coleta (comentários desde 16/08)" virou "sem comentários coletados nesta fase" (a coleta agora começa em 20/07).
- Testes: suíte OK. Pendente: rodar o sentimento para gerar as semanas.

## C19.16 — Página sem custo de coleta; comentários do Kwai continuam pelas outras contas (2026-10-18) 🔜

- Pedido do usuário: "nunca exibir o custo da coleta". Removidos da página todos os textos de custo/gasto das coletas (Kwai, Facebook, X, anúncios da Meta e comentários do Kwai e do Facebook). Os manifestos com custo continuam no repositório como evidência (regra do CLAUDE.md), sem aparecer na página. "Gasto" dos anúncios (dado declarado pela Meta) continua.
- Comentários do Kwai: o coletor pula contas que já esgotaram as 25 execuções gratuitas do ator (conta 3; e as próximas, registradas no manifesto), começa pelo candidato com menos comentários (Flávio: 28) e passa a valer desde 20/07.
- Social Blade (teste TikTok @lulaoficial, US$ 0,02): 31 dias de série (18/09 a 18/10: seguidores, seguindo, vídeos, curtidas). Carga de 16 perfis (TikTok e YouTube) disparada.
- Testes: suíte OK.

## C19.15 — Seguidores retroativos via Social Blade pela Apify (2026-10-18) 🔜

- Pedido do usuário: série diária retroativa de seguidores coletada pela Apify, sem contratar a API do Social Blade. Loja (run de `teste-apify-loja`, 18/10): rl1987/social-blade-lookup (US$ 0,01 por evento: perfil, histórico, crescimento; Instagram, TikTok, YouTube e Twitch — sem X e Facebook), radeance/socialblade-api (US$ 0,01 por resultado), solidcode/socialblade-scraper (US$ 0,03 por item).
- `collect_socialblade.py` + `socialblade.yml`: 35 perfis declarados ao TSE pelas chapas 13 e 22 (Instagram 19, TikTok 10, YouTube 6), modo "profile" com histórico; série em `data/seguidores/socialblade_historico.csv` (plataforma, perfil, data, seguidores, seguindo, posts, visualizações). Teto US$ 3; contas 3 a 7.
- Teste 1 (18/10 03h31 UTC, conta 3): HTTP 400 "max-total-charge-usd-below-minimum" — este ator exige teto mínimo de US$ 0,10 por execução (o mesmo motivo provável do 400 no 1º teste dos comentários do Facebook). Teto por execução ajustado.
- Teste 2 (Instagram @lulaoficial, US$ 0,02): o perfil veio sem série. O README do ator informa que, no Instagram, histórico e crescimento são bloqueados pelo próprio Social Blade; ficam só TikTok e YouTube (16 perfis).
- Testes: suíte OK.

## C19.14 — X: assuntos do momento no Brasil, de hora em hora (2026-10-18) 🔜

- Pedido do usuário: coleta das top trends do dia no X. Diagnóstico (`diag-fontes-web.yml`): trends24.in e socialblade.com respondem 403 (Cloudflare) a robôs; getdaytrends.com/brazil/ responde 200. `collect_x_trends.py` + `x-trends.yml` (de hora em hora, grátis): lista do momento com volume de posts quando o X informa, em `data/x/trends/AAAA-MM-DD.csv` e resumo do dia em `latest.json` (top 30, melhor posição, horas na lista, assuntos que citam os candidatos).
- Seguidores retroativos: o Social Blade bloqueia acesso automatizado (Cloudflare, "Just a moment...") e contornar a verificação não é permitido; as plataformas não publicam série histórica de seguidores. A série diária cresce a partir das coletas próprias.
- 1ª execução: 0 assuntos — na página real há um gráfico (svg) entre o nome e o fim da linha e o padrão só aceitava 400 caracteres. Corrigido e conferido na página guardada: 15 assuntos (1º "#LulaTemOMaiorExercitoDoMundo"); o getdaytrends não mostra volume nessa tabela.
- Testes: `tests/test_x_trends.py`; suíte OK.

## C19.13 — Comentários do Facebook carregados; seguidores do TikTok; saldo das contas (2026-10-18) ⚠️

- Comentários do Facebook, carga (run 39085893432, conta 3): **4.965 comentários** — Lula 2.315, Flávio 2.650 — em 5 execuções; US$ 1,25 pela tabela (teto US$ 1,50). Texto só no repositório privado; agregados em `data/facebook/comentarios/`.
- Seguidores do TikTok (run `tiktok` 39086010561, US$ 0,0165): lulaoficial 6.162.331, flaviobolsonaro 2.519.862, pode_espalhar 174.335. Os outros 7 perfis voltaram sem número (sem erro): a investigar.
- Saldo real das contas (run `apify-contas`, 18/10 00h43 UTC): 1 US$ 11,08 (Starter, não usada); 2 −0,27; 3 US$ 2,37; 4 US$ 2,80; 5, 6 e 7 US$ 5,00 cada.

## C19.12 — Seguidores de todos os TikToks declarados (contas 3 a 7) (2026-10-17) 🔜

- Cards "Não coletado" do TikTok (print do usuário): nenhuma rotina lia seguidores dos perfis secundários. `collect_seguidores_tiktok.py` (apidojo/tiktok-profile-scraper, US$ 0,0003 por item; 1 item por perfil, ≈ US$ 0,003 por coleta) roda no `tiktok.yml` (2× ao dia) e grava `data/seguidores/tiktok_latest.csv` com a URL declarada ao TSE; `bnLoadAuto` lê o arquivo; variação diária incluída.
- Testes: `tests/test_seguidores_tiktok.py`; suíte OK.

## C19.11 — Página "O que as campanhas dizem no X" (2026-10-17) ✅

- Página X no caderno 02, gerada da do Facebook (perfis, fases, temas, linha do tempo, listas, Bardin + CHD, redes de coocorrência e de menções, downloads), lendo `data/x/`. Chromium 1300 e 390 px: 2.149 posts de Lula e 926 de Flávio desde 20/07, rede de coocorrência com 1.065 arestas, rede de menções com 240 contas, sem erro de JavaScript e sem rolagem horizontal.
- Comentários do Facebook: teste após o ajuste (manifesto de 18/10 01h16 UTC) com 20 comentários de 2 posts, US$ 0,005; carga disparada.
- Testes: suíte OK.

## C19.10 — X carregado; página Comentários sem nome das redes, com Facebook (2026-10-17) ⚠️

- X, carga (run 39085553991, xquik, conta 3): **3.061 posts** (sem reposts) desde 20/07 — LulaOficial 1.482, FlavioBolsonaro 485, alfredogaspar_ 440, geraldoalckmin 226, comitespop 147, lulaverso 119, pode_espalhar 109, obrasilcomlula 53; pl22al e LulaEvangelicos sem posts na busca. US$ 0,46 pela tabela. Seguidores de 8 perfis gravados em `data/seguidores/x_latest.csv` (LulaOficial 10.765.666; FlavioBolsonaro 3.794.692; geraldoalckmin 1.373.545; lulaverso 139.882; alfredogaspar_ 82.689; comitespop 12.113; pode_espalhar 7.803; obrasilcomlula 183).
- Comentários do Facebook, teste (run 39085646280, conta 3): HTTP 400 da Apify na entrada. Entrada reduzida a `startUrls` + `resultsLimit`; o erro passa a registrar a resposta da Apify (sem o token).
- Página: o menu passa a "Comentários" (sem o nome das redes), com as subabas YouTube, Kwai e Facebook; a do Facebook é gerada da do Kwai e lê `data/facebook/comentarios/`.
- Testes: suíte OK.

## C19.9 — Comentários do Facebook: coletor (contas 3 a 7, teto US$ 1,50) (2026-10-17) 🔜

- Pedido do usuário (22h05): criar a página de comentários do Facebook. Loja Apify (run de `teste-apify-loja`, 17/10): dami_studio/facebook-comments-scraper, US$ 0,25 por 1.000 comentários no plano gratuito (o oficial da Apify cobra US$ 2,50 por 1.000).
- `collect_comentarios_facebook.py` + `facebook-comentarios.yml`: posts desde 20/07 com comentários; cota igual por candidato (2.800), de 5 a 50 por post, por relevância, sem respostas; até 100 posts por execução. Texto e autor só no repositório privado; análises com `--plataforma facebook` (mesmas regras do YouTube e do Kwai); sentimento incluído em `sentimento-youtube.yml`.
- Testes: `tests/test_comentarios_facebook.py`; suíte OK.

## C19.8 — X: troca de coletor (2026-10-17) 🔜

- Teste (run 39085223674) e carga (run 39085278763) com apidojo/tweet-scraper (conta 3/4): no plano gratuito o ator devolve no máximo 10 itens por execução; 4 perfis vieram com 10 posts cada (LulaOficial 10.765.351 seguidores, FlavioBolsonaro 3.794.680, comitespop 12.111, pode_espalhar 7.803) e 6 perfis com nenhum post próprio. Gasto: US$ 0,044.
- Teste com xquik (run 39085419257, US$ 0,003): 20 itens da linha do tempo de @LulaOficial em ~1 hora, quase todos reposts e respostas. O coletor passa a usar a busca do próprio X (`from:perfil since:2026-07-20 -filter:retweets`): posts e respostas do perfil, sem reposts.
- O coletor passa para **xquik/x-tweet-scraper** (README: US$ 0,00015 por linha, funciona no plano gratuito), com leitura de campos tolerante a nomes diferentes; mesmo teto de US$ 2.
- Teste da busca (run 39085493277): 20 posts próprios de @LulaOficial (10.765.658 seguidores). Carga: até 2.500 posts dos perfis principais e 800 dos demais (≈ US$ 1,71 pela tabela).
- Testes: suíte OK.

## C19.7 — X: coletor de posts e seguidores dos perfis declarados (contas 3 a 7, teto US$ 2) (2026-10-17) 🔜

- Pedidos do usuário (17/10, 22h02): página "o que as campanhas dizem no X"; cards de seguidores "não coletados"; não usar a conta principal (1), só as dos outros pesquisadores.
- Loja Apify (run de `teste-apify-loja`, 17/10): apidojo/tweet-scraper (US$ 0,0004 por item; 9.488 usuários em 30 dias) e apidojo/tiktok-profile-scraper (US$ 0,0003 por item).
- `collect_x_posts.py` + `x-posts.yml`: 10 perfis de X declarados ao TSE pelas chapas 13 e 22, desde 20/07, até 1.000 posts dos principais e 300 dos demais (≈ US$ 1,76 pela tabela; teto US$ 2). Só posts do próprio perfil (reposts de outros ficam fora). Seguidores de cada perfil (do próprio post) em `data/seguidores/x_latest.csv`, com a URL declarada ao TSE, lidos pelos cards de "Quem acompanha"; variação diária incluída (`build_variacao_seguidores.py` aceita `x_` e `tiktok_`).
- `build_tiktok.py --x`, `plataformas.py` (x), `build_rede_mencoes_tiktok.py --x` e `build_miniaturas_kwai.py --x`: mesmas regras das outras redes.
- Testes: `tests/test_x_posts.py`; suíte OK.

## C19.6 — Contas Apify com troca automática; Facebook da pré-campanha (2026-10-17) 🔜

- O usuário confirmou que as contas Apify 2 a 7 são de pessoas diferentes do grupo. `escolher_conta()` (em `collect_meta_apify.py`) usa a primeira conta da lista com saldo real suficiente (`/users/me/limits`); listas em `segredos` de `kwai.json` (2→7), `kwai_comentarios.json` (3→7) e `facebook_posts.json` (2, 4→7). A conta 1 (Starter) fica para as rotinas diárias de seguidores e anúncios. O manifesto registra qual conta pagou.
- Facebook: modo `pre-campanha` (`--pre`): posts de 20/07 a 15/08 (`onlyPostsOlderThan` 16/08), até 60 das páginas principais e 20 das demais, sem repetir os já coletados; ≈ US$ 1,61 pela tabela, dentro do teto de US$ 5 (gasto até aqui US$ 2,52).
- Run `pre-campanha` 39084573495 (conta 4 escolhida automaticamente; US$ 0,01): 0 posts em todas as páginas — o filtro `onlyPostsOlderThan` devolve "no_items". Ajuste: o modo relê só as páginas principais desde 20/07, sem limite superior, até 200 posts cada (os posts já coletados são cobrados de novo; ≈ US$ 1,65 pela tabela, dentro do teto).
- Run `pre-campanha` 39084766464 (conta 4): lula 150 e flaviobolsonaro 150 posts lidos (até 200 pedidos), 81 novos (pré-campanha); acervo do Facebook 471 posts (Lula 301, Flávio 170); 80 capas novas; US$ 1,997. Gasto do Facebook: US$ 4,52 de 5.
- Testes: suíte OK.

## C19.5 — Todas as páginas desde a pré-campanha (20/07), com filtro por fase (2026-10-17) 🔜

- Pedido do usuário: "todas as páginas têm que ter os históricos de pré-campanha e pós, assim como captamos em tudo". Início das coletas e análises passa de 16/08 para **20/07/2026** (início da pré-campanha, `fases` de `data/config/trends.json`): `collect_youtube.py`, `collect_tiktok.py`, `build_tiktok.py` (TikTok e Facebook), `plataformas.py` (Bardin, CHD, redes), `corpus_populismo.py` (semana 1 = 20/07), `build_rede_mencoes_tiktok.py`, `build_comentarios.py` e configs de comentários do YouTube, hashtags do TikTok, influenciadores, Kwai, comentários do Kwai e Facebook. Fica em 16/08 só o que é marco da campanha (Google: anúncio exibido na campanha; contagem "desde 16/08"; janela de 30 dias das fichas).
- `build_tiktok.py`: novo `por_fase` (vídeos, visualizações e interação mediana na pré-campanha, 1º turno e 2º turno).
- Página: botões de fase (Desde 20/07 · Pré-campanha · 1º turno · 2º turno; no Kwai também "Acervo completo") no YouTube, TikTok, Kwai e Facebook; rótulos "desde 16/08" do Panorama e das páginas trocados por "desde 20/07". Chromium: botões filtram números e listas nas quatro páginas, sem erro de JavaScript. A pré-campanha aparece zerada no YouTube, TikTok e Facebook até as novas coletas.
- Testes ajustados ao novo início; suíte OK.
- Runs (17/10): `seguidores-youtube` 39084251540, `tiktok` 39084252795, `tiktok-hashtags` 39084254076, todos ok. Vídeos antes de 16/08 agora no acervo: YouTube Lula 220 e Flávio 82; TikTok Lula 168 e Flávio 44. Comentários do YouTube disparados.

## C19.4 — Diagnóstico de perfil do TikTok (2026-10-17) ✅

- Pergunta do usuário: por que @evangelicoscomlula (declarado ao TSE por LULA) não aparece. O manifesto da última coleta mostra o perfil lido com status ok e 8 vídeos lidos, 0 desde 16/08: o coletor para depois de 8 vídeos seguidos anteriores a 16/08 e só guarda os da campanha. `diag-tiktok-perfil.yml` lista os 40 primeiros vídeos de um perfil com a data (yt-dlp, sem custo) para conferir.
- Resultado (run do `diag-tiktok-perfil`, 17/10): o vídeo mais recente de @evangelicoscomlula é de 29/10/2022 (os 10 primeiros da lista vão de 25 a 29/10/2022, de 69 a 951 visualizações). O perfil existe, mas não publica desde a eleição de 2022; não há vídeo no período da campanha de 2026.

## C19.3 — Apify: saldo real das contas e trava antes de cada execução (2026-10-17) ⚠️

- Verificação das contas (run 39083808726, `data/apify/contas.json`): conta 1 STARTER, US$ 7,92 de 19 no ciclo até 23/10; conta 2 FREE, **US$ 5,27 de 5 (estourada)**; conta 3 FREE, US$ 0,82 de 5; contas 4 a 7 FREE, US$ 0 de 5.
- Achado: os manifestos do Kwai registraram US$ 0 (a Apify devolveu `chargedEventCounts` vazio), mas a conta 2 foi cobrada: o custo por execução não é confiável nesse ator. Os coletores do Kwai, do Facebook e dos comentários do Kwai passam a ler o saldo real da conta (`/users/me/limits`) antes de rodar e param com ⛔ se o saldo for menor que o teto da execução.
- Consequência: a coleta diária do Kwai (conta 2) fica parada até o novo ciclo da conta (01/11) ou até mudar de conta.
- Facebook (run `so-analises`): 340 capas (12 falhas, 38 posts sem URL de capa); rede de menções gerada. Página verificada no Chromium (1300 e 390 px): 22 capas na lista, 928 arestas na rede de coocorrência, rede de menções com 20 contas, sem erro de JavaScript e sem rolagem horizontal.
- Testes: suíte OK.

## C19.2 — Apify: verificação diária das contas 1 a 7 (2026-10-17) 🔜

- Pedido do usuário: verificar as contas Apify de 1 a 7. `verificar_contas_apify.py` + `apify-contas.yml` (diário, 09h05, e manual): só leitura (`/users/me` e `/users/me/limits`), sem custo; grava em `data/apify/contas.json` plano, uso do mês, limite e saldo de cada conta, sem nome de usuário, e-mail ou id.
- Correção: o 1º commit do workflow tinha erro de YAML (dois-pontos numa linha `run` sem bloco) e foi para o repositório sem esta entrada; corrigido no commit seguinte.
- Pendente: o run; a troca automática de conta quando uma falha não foi implementada (ver resposta ao usuário sobre os termos de uso da Apify).

## C19.1 — Facebook: carga das 12 páginas e página no caderno 02 (2026-10-17) ⚠️

- Teste (run 39083282446, US$ 0,036): 7 posts de facebook.com/lula (desde 16/08).
- Carga (run 39083340754, US$ 2,482 pela tabela): **390 posts** desde 16/08 — lula 112, flaviobolsonaro 112, obrasilcomlula 30, Pode-Espalhar 30, evangelicoscomlula 30, geraldoalckmin 30, geracaolula 30, alfredogasparoficial 12, denuncia.br.2026 3, canaltvcelular 1; lulaverso "not_available". Lula 262 posts (6 páginas, 63.341.066 visualizações de vídeos), Flávio 128 (4 páginas, 93.542.329). CHD: 629 segmentos, 6 classes. Gasto acumulado: US$ 2,52 de US$ 5.
- Página "Facebook" no caderno 02, gerada da do Kwai (perfis/páginas, temas, linha do tempo, listas com capa, Bardin + CHD, redes de coocorrência e de menções, downloads). Capas e rede de menções do Facebook: `build_miniaturas_kwai.py --facebook` e `build_rede_mencoes_tiktok.py --facebook`; modo `so-analises` no workflow refaz tudo sem nova coleta (sem custo).
- Testes: suíte OK.

## C19.0 — Facebook: o que as campanhas publicam (Apify, conta 2, teto US$ 5) (2026-10-17) 🔜

- Pedido do usuário: "com a conta apify 2 consegue fazer o que as campanhas dizem no face"; escolheu todas as páginas declaradas ao TSE, teto de US$ 5 (pergunta de 17/10, 21h3x).
- Loja Apify (run de `teste-apify-loja`, 17/10): apify/facebook-posts-scraper — no plano gratuito US$ 0,005 por post, até cerca de 1.000 posts (700 com filtro de data), segundo o README.
- `data/config/facebook_posts.json`: 12 páginas declaradas pelas chapas 13 e 22 (obrasilcomlula, repetida no TSE, entra uma vez); até 150 posts das páginas principais (facebook.com/lula, facebook.com/flaviobolsonaro) e 40 das demais, desde 16/08 (≈ 700 posts, ≈ US$ 3,51 pela tabela).
- `collect_facebook_posts.py` + `facebook-posts.yml` (teste: 10 posts de facebook.com/lula; carga: uma execução por página, 3 em paralelo). Acervo em `data/facebook/videos.csv.gz` com as colunas do TikTok/Kwai; bruto no repositório privado. `build_tiktok.py --facebook` e `plataformas.py` (facebook) aplicam as mesmas regras de tema, Bardin, CHD e rede.
- Testes: `tests/test_facebook_posts.py`; suíte OK.
- Pendente: runs de teste e carga; página "Facebook" no caderno 02.

## C18.12 — Comentários do Kwai: teto de US$ 5 e teste com o natanielsantos por vídeo único (2026-10-17) ⛔ (sem coletor gratuito para o restante)

- Pedido do usuário (21h24): "colete tudo que conseguir com até 5 dólares" — teto total dos comentários do Kwai passa a US$ 5.
- O zen-studio está bloqueado pelo limite de 25 execuções gratuitas da conta; não uso outras contas para contornar. Modos novos: `teste-nataniel` (1 vídeo × 20 comentários pelo natanielsantos/kwai-scraper, que no teste 1 não trouxe comentários com vários vídeos) e `carga-nataniel` (todos os pendentes numa execução por candidato).
- Resultado do `teste-nataniel` (run 39082754047, US$ 0,0021): 1 vídeo, **0 comentários** (eventos `comment`: 0). O natanielsantos/kwai-scraper não entrega comentários nesta conta. Sem plano pago na Apify, não há como coletar mais comentários do Kwai; o acervo fica em 678 (Lula 650, Flávio 28). Gasto acumulado registrado: US$ 0,81.
- Testes: suíte OK.

## C18.11 — Comentários do Kwai: limite gratuito do ator; página no ar com aviso de desequilíbrio (2026-10-17) ⚠️

- Carga por vídeo (run 39082082015): 67 vídeos de Lula × até 25 → **625 comentários**; os 70 de Flávio voltaram vazios. Re-execução (run 39082275709, com status de cada execução): 112 execuções SUCCEEDED, todas com a mesma resposta do ator — "You have used all 25 free runs for this Actor" (`limitReached`, `freeRunsLimit` 25). O zen-studio/kwai-comments-scraper só permite 25 execuções gratuitas por conta e, nessa conta, lê só o 1º vídeo de cada execução. O coletor passa a reconhecer essa resposta e a registrar o motivo no manifesto.
- Acervo de comentários do Kwai (privado): **678** — Lula 650 (26 vídeos, 570 autores), Flávio 28 (2 vídeos, 25 autores). Agregados em `data/kwai/comentarios/analise.json`; rede de termos com 2 nós (amostra pequena); CHD sem classes (poucos comentários longos).
- Gasto registrado: US$ 0,81 pela tabela de preços (estimativa conservadora); a Apify informou 0 eventos `comment-result` cobrados. Não usei outras contas para contornar o limite gratuito do ator.
- Página "Comentários · Kwai": no ar, com aviso de amostra desequilibrada ("não compare os dois lados") quando um candidato tem menos de 25% dos comentários do outro. Chromium 1300 e 390 px sem erro de JavaScript (só o 404 do sentimento, ainda não calculado) e sem rolagem horizontal.
- Pendente: comentários de Flávio (exige plano pago na conta da Apify ou outro coletor); sentimento do Kwai (workflow `sentimento-youtube.yml` disparado).

## C18.10 — Comentários do Kwai: uma execução por vídeo (2026-10-17) 🔜

- Run `--videos-lula` (39081858562, US$ 0,1001): o ator devolveu 50 vídeos de @Lulaoficial (o máximo que entregou, de 02/10 a 17/10), juntados ao acervo; capas (+50), temas e análises refeitos. Lula passa a 365 vídeos no Kwai (2 perfis, 24.053.656 visualizações).
- Carga 1 (39081962796, US$ 0,0476): pedidos 68 vídeos (Lula, até 25 cada) e 71 (Flávio, até 23 cada), mas cada execução leu só o 1º vídeo da lista: 25 + 23 comentários. Agora o coletor faz uma execução por vídeo (US$ 0,00005 de início cada), 4 em paralelo, com teto pequeno por execução e o mesmo teto total.
- Testes: suíte OK.

## C18.9 — Kwai: vídeos de @Lulaoficial e cota de comentários por candidato (2026-10-17) 🔜

- Teste 3 (run 39081710065): zen-studio/kwai-comments-scraper devolveu 5 comentários (campos `commentId`, `content`, `author`, `photoId`, `timestamp`, `likeCount`). Corrigido: o id do comentário vem de `commentId`; a rede de termos não quebra com amostra minúscula. Gasto dos 3 testes ≈ US$ 0,02 (manifestos em `data/kwai/comentarios/`).
- Sem vídeos de @Lulaoficial, o lado de Lula teria só 24 comentários (@podeespalhar). Modo `--videos-lula`: o natanielsantos/kwai-scraper (que lista a conta oficial, teste 1) lê até 250 vídeos do perfil (teto US$ 0,55, dentro dos US$ 4 dos comentários) e os junta ao acervo do Kwai, com capas, temas e análises refeitos no mesmo run.
- Carga: cota igual por candidato (1.700 comentários), dividida entre os vídeos do período (5 a 50 por vídeo), um run da Apify por candidato, tudo dentro do que resta do teto.
- `kwai-comentarios.yml`: entrada `modo` (teste · videos-lula · carga). Testes: suíte OK.

## C18.8 — Comentários do Kwai: teste 1 e ajuste de formato; página "Comentários · Kwai" (2026-10-17) 🔜

- Teste 1 (run 39081371929, US$ 0,0161 pela Apify e pela tabela): 8 itens, **0 comentários**. Vídeos pedidos como `/@perfil/video/ID`; o README do ator mostra comentários como itens próprios (`content`, `videoId`, `timestamp`, `likedCount`, `replyToCommentId`) e vídeos como `/video/ID`. O coletor agora lê esse formato e pede `/video/ID`; só marca como lido o vídeo que trouxe comentário (a lista do teste 1 foi zerada no repositório privado). Teste 2: 2 vídeos × 5 comentários.
- Achado: este ator **lista os vídeos de @Lulaoficial** (5 mais recentes, de 15 a 18/10, até 537.497 visualizações), que o unfenced-group/kwai-scraper não devolve.
- `build_rede_comentarios.py` para com ⛔ quando há menos de 2 comentários (o teste 1 quebrou com lista vazia).
- Página: subaba **Kwai** em Comentários, gerada da página do YouTube (mesmos blocos: números, sentimento, nuvens, intolerância/incivilidade, populismo, aderência ao tema, série diária, CHD, redes Gephi, IRaMuTeQ no privado, método), lendo `data/kwai/comentarios/`. Botão do menu: "Comentários · YouTube e Kwai".
- Teste 2 (run 39081622751, US$ 0,0001): com `/video/ID` o ator não devolve nada. O natanielsantos/kwai-scraper não entregou comentários em nenhum formato; o coletor passa para **zen-studio/kwai-comments-scraper** (US$ 0,00099/comentário, entrada `videoUrls`), mesmo teto de US$ 4 e mesma chave. Leitura dos campos do comentário tolerante a nomes diferentes; o log mostra só as chaves e tipos do 1º item quando nada for reconhecido.
- Testes: suíte OK.

## C18.7 — Comentários do Kwai: coletor e análises com as regras do YouTube (2026-10-17) 🔜

- Run do Google com o recorte (39075625107): 30 anúncios lidos, 28 fora do recorte (21/08/2022 a 01/03/2024; anunciantes "ELEIÇÃO 2022 LUIZ INACIO LULA DA SILVA PRESIDENTE" e "Partido dos trabalhadores" saem inteiros), 2 anúncios de 2026 de 2 anunciantes ficam na página.
- Loja Apify (run de `teste-apify-loja`, 17/10): coletores de comentários do Kwai — natanielsantos/kwai-scraper (US$ 0,002/vídeo + US$ 0,001/comentário; 224 usuários em 30 dias, 1.638/1.657 execuções com sucesso) e zen-studio/kwai-comments-scraper (US$ 0,00099/comentário; 2 usuários). Escolhido o primeiro.
- Volume (acervo `data/kwai/videos.csv.gz`, desde 16/08): Flávio 72 vídeos e 159.608 comentários (3.565 com limite de 50 por vídeo); @podeespalhar 86 vídeos e 24 comentários; @Lulaoficial sem vídeos.
- Autorização do usuário: teto de US$ 4 com a chave `APIFY_TOKEN_3` (`data/config/kwai_comentarios.json`); teste de US$ 0,10 dentro do mesmo teto.
- `collect_comentarios_kwai.py` (+ `kwai-comentarios.yml`): teste com 3 vídeos × 10 comentários e 5 vídeos de @Lulaoficial (para ver se este ator lista a conta oficial); carga com até 50 comentários por vídeo, vídeos que cabem no teto pela tabela de preços. Custo de cada execução = maior entre o informado pela Apify e a estimativa pela tabela. Texto e autor só no repositório privado.
- `build_comentarios.py`, `build_rede_comentarios.py` e `build_sentimento_comentarios.py` aceitam `--plataforma kwai` (mesmas regras do YouTube; saída em `data/kwai/comentarios/`); `sentimento-youtube.yml` classifica também o Kwai quando houver comentários.
- Testes: `tests/test_comentarios_kwai.py` (formato, recorte de data, nada de texto ou nome no público, custo estimado); suíte OK.
- Pendente: run de teste e carga; página "Comentários do Kwai".

## C18.6 — Anúncios: Google sem os anúncios de 2022; busca de coletor de comentários do Kwai (2026-10-17) ✅ (Google executado no run 39075625107)

- Pedido do usuário: "na página de anúncios retira 2022". A Central do Google trazia 27 anúncios de 2022 (anunciante "ELEIÇÃO 2022 LUIZ INACIO LULA DA SILVA PRESIDENTE" e vídeos do PT), mais 1 de 2024. `collect_google_transparencia.py` passa a recortar por `exibir_desde` = 01/01/2026 (`data/config/google_transparencia.json`): anunciantes, prévias, contagem por domínio e `anuncios.csv` só com anúncios de 2026; o que saiu é contado em `fora_do_recorte` e citado na nota da página. Teste novo (`TestRecorte`). Na Meta não havia anúncio de 2022 (datas de início: 2024–2026).
- `teste-apify-loja.yml`: termos de busca, filtro e trecho do README viram entradas, para procurar coletores de comentários do Kwai.
- Pendente: run do Google com o recorte; preço do coletor de comentários do Kwai.

## C18.5 — Kwai: arestas das redes invisíveis (2026-10-17) ✅

- Erro apontado pelo usuário: na rede de coocorrência de palavras-chave do Kwai as arestas não apareciam. Causa: o CSS das redes e da linha do tempo do TikTok é preso ao id do elemento (`#tkNet line{stroke:…}`); a página do Kwai, gerada a partir do bloco do TikTok, ganhou ids `kw…` sem as regras, e as linhas ficaram sem cor. As 22 regras foram copiadas para os ids do Kwai.
- Rede de menções: o Kwai mantém maiúsculas no nome do perfil, então "@flaviobolsonaro" na legenda de @FlavioBolsonaro aparecia como conta marcada (automenção). Agora a comparação ignora maiúsculas. Regerado: Flávio marca 4 contas em 107 menções; Lula, nenhuma.
- Teste: Chromium 1300 px — rede de coocorrência do Kwai com 939 arestas visíveis, rede de menções e linha do tempo desenhadas, sem erro de JavaScript. `python -m unittest discover -s tests` OK.

## C18.4 — Kwai: página no padrão do TikTok, capas; Panorama com Kwai e WhatsApp (2026-10-17) ⚠️

- Run 39073285546 (carga histórica, teto US$ 4,50): 1.279 itens, 925 vídeos novos, acervo de 1.270 vídeos — @FlavioBolsonaro 955 de 958, @podeespalhar 315 de 321, **@Lulaoficial 0 de 916**: o ator devolve o perfil (7.452.649 seguidores) mas nenhum vídeo dessa conta, em todas as execuções. ⛔ a investigar. A Apify registrou 0 eventos cobrados e uso US$ 0 (`run_apify` no manifesto).
- Capas: 286 miniaturas (3,6 MB) em `data/kwai/miniaturas/`, 0 falhas. Bruto (`apify_2026-10-17_220043.jsonl.gz`) e banco tratado (`kwai/banco/`) no repositório privado.
- Análises do Kwai geradas no run: CHD de Reinert (1.542 segmentos, 6 classes), livro de códigos (1.270 vídeos), rede de coocorrência e rede de menções.
- Página do Kwai refeita a partir do bloco do TikTok (mesma estrutura e regras): perfis, período (campanha desde 16/08 ou acervo completo), filtros de tema/voto/adversário, linha do tempo, nuvens e hashtags, listas com capa, detalhe com capa e link para o Kwai (o Kwai não tem player incorporável), Bardin + CHD, rede de coocorrência e rede de menções com downloads. O card de contas por hashtag do TikTok não tem equivalente no Kwai e ficou fora.
- Panorama: chips **Kwai** e **WhatsApp** nos cards dos candidatos (seguidores, perfis/canais, vídeos e visualizações desde 16/08, interação mediana; composição da audiência marcada ⛔ sem fonte) e linhas do Kwai na tabela "da busca ao voto" (seguidores, vídeos e visualizações desde 16/08, interação mediana). WhatsApp: só canais do lado de Lula têm link; Flávio aparece como ⛔.
- Teste: Chromium 1300 px e 390 px sem erro de JavaScript e sem rolagem horizontal; capas carregadas na lista e no detalhe. `python -m unittest discover -s tests` OK.

## C18.3 — Kwai: carga histórica completa, capas e análises iguais às do TikTok (2026-10-17) ⚠️ (executado em C18.4)

- Autorização do usuário (17/10, 18h56): "pode completar, temos 5 dólares na conta". Teto da carga histórica US$ 4,50; teto mensal da conta secundária elevado a US$ 5 (`data/config/kwai.json`).
- `collect_kwai_apify.py --historico`: sem data mínima, `onlyNewVideos` desligado (reentrega os vídeos já vistos para obter a capa), até 2.400 itens. Nova coluna `capa_url` (coverUrl do ator).
- Bug corrigido: o bruto no repositório privado era gravado como `apify_AAAA-MM-DD_HH` e runs na mesma hora se sobrescreviam (só restou um dos 3 brutos de hoje). Agora inclui minuto e segundo.
- Banco tratado (`videos.csv.gz`, `perfis.csv`) copiado também para `odi-atlas-interno/kwai/banco/` a cada run.
- `build_miniaturas_kwai.py`: capas em JPEG de 180 px (`data/kwai/miniaturas/`), para vídeos desde 20/07 e os 60 de maior audiência de cada perfil; logo após a coleta, porque a URL da CDN expira.
- Análises do Kwai com as mesmas regras do TikTok/YouTube (`plataformas.py` aceita `kwai`, acervo completo sem corte de data): livro de códigos, corpus IRaMuTeQ, CHD de Reinert, rede de coocorrência e rede de menções (`build_rede_mencoes_tiktok.py --kwai`). Execução local com o acervo atual (345 vídeos) rodou sem erro; os arquivos serão gerados pelo run da carga.
- Testes: `python -m unittest discover -s tests` OK (inclui modo histórico e seleção de miniaturas).
- Pendente: o run da carga histórica (ID e números na próxima entrada).

## C18.2 — Kwai: contas oficiais corretas e seguidores nos cards (2026-10-17) ⚠️

- Correção de C18.1: o nome de usuário do Kwai diferencia maiúsculas. O TSE grava as URLs em maiúsculas e a 1ª carga pediu os nomes em minúsculas, o que trouxe outras contas ("Mateus Café" em `lulaoficial`; "Apoio Flávio Bolsonaro" em `flaviobolsonaro`). As grafias das páginas já indexadas no Atlas (`@Lulaoficial`, `@FlavioBolsonaro`) resolvem as contas oficiais. Os 8 vídeos da conta de apoio foram removidos do acervo e de `perfis.csv`; a comparação de nomes passou a respeitar maiúsculas.
- Run 39072776525 (modo diário, teto US$ 0,10): @Lulaoficial 7.452.635 seguidores e 916 vídeos no perfil; @FlavioBolsonaro 755.997 seguidores e 958 vídeos; @podeespalhar 953. Vieram 30 vídeos de Flávio desde 16/08 (limite diário) e nenhum de Lula desde 16/08. A Apify informou 0 eventos cobrados.
- Seguidores do Kwai em `data/seguidores/kwai_latest.csv` e `kwai_AAAA-MM-DD.csv` (URL declarada ao TSE, para casar com o card); `build_variacao_seguidores.py` inclui o Kwai. Página "Quem acompanha": cards do Kwai passam de "indexado" (estimativa) para "Coleta automática (Kwai via Apify)". Chromium: cards de Lula (7,45 mi; 953) e Flávio (756 mil) exibidos, sem erro. Testes OK.
- Pendente: carga histórica das contas oficiais (916 + 958 vídeos ≈ US$ 2,80 pela tabela do ator) — aguarda autorização de teto.

## C18.1 — Kwai: carga histórica com data dos posts (2026-10-17) ⚠️

- Usuário cadastrou `APIFY_TOKEN_2` e pediu a carga histórica com a data dos posts.
- 1º run (39072298655, desde 16/08): 89 itens, mas 0 vídeos gravados — o ator não traz o dono do vídeo num campo de nome de usuário; agora vem da URL (`/@perfil/video/…`). Legendas com entidades HTML (`&eacute;`) passam a ser decodificadas.
- Achados nos perfis: o link curto de LULA no TSE leva a `@lulaoficial`, que no Kwai é outra pessoa ("Mateus Café", 3 vídeos) — retirado da coleta; `@flaviobolsonaro`, declarado por FLAVIO BOLSONARO, é a conta "Apoio Flávio Bolsonaro" (85 seguidores, bio pede doação via Pix) — mantida e descrita na página por ser a URL declarada.
- 2º run (39072422892, carga histórica sem data mínima, reprocessando o bruto anterior): acervo de 323 vídeos — @podeespalhar 315 de 321 (17/06/2025 a 16/10/2026; 86 desde 16/08) e @flaviobolsonaro 8 (todos antes de 16/08). Datas em `publicado_em` (createTime do Kwai).
- `build_tiktok.py --kwai` usa o acervo completo (`desde` nulo), com contagem por mês e quantos desde 16/08. Lula: 315 vídeos, 233.155 visualizações, interação mediana 4,8%, 33 citam o adversário, 26 pedem voto; Flávio: 8 vídeos, 6.997 visualizações.
- Página: título "acervo histórico", vídeos por mês, 30 mais recentes com data; quebra de palavras longas (rolagem a 390 px corrigida). Testes OK.
- Ressalva: o custo apareceu como US$ 0,00 no manifesto (o objeto da execução não trouxe os eventos cobrados); o teto da Apify (`maxTotalChargeUsd`) segue valendo; o manifesto passa a guardar `eventos_cobrados` e `uso_plataforma_usd` para conferência.

## C18.0 — Subpágina Kwai no caderno 02 (Apify, conta secundária) (2026-10-17) ⚠️ (atualizado em C18.1)

- Pedido do usuário: página "O que as campanhas dizem · Kwai" usando a conta secundária da Apify (segredo `APIFY_TOKEN_2`). Tetos: os propostos na conversa (teste US$ 0,50; diário US$ 0,10; mensal US$ 3), em `data/config/kwai.json`.
- `scripts/collect_kwai_apify.py` + `.github/workflows/kwai.yml` (diário 10h10; manual com "teste") + `tests/test_kwai.py`: ator `unfenced-group/kwai-scraper`, perfis @lulaoficial, @podeespalhar (chapa 13) e @flaviobolsonaro (chapa 22) — nomes de usuário tirados das URLs do TSE; o vice Alfredo Gaspar fica fora (link curto quebrado pelo TSE). Acervo no formato do TikTok (`data/kwai/videos.csv.gz`), seguidores por dia (`data/kwai/perfis.csv`), manifestos com custo; bruto no privado. Mapeamento de campos tolerante a nomes alternativos, a confirmar no primeiro run real.
- `scripts/build_tiktok.py --kwai`: mesmas regras de tema, nuvem, "cita o adversário", "pede voto" e taxa de interação, saída `data/kwai/conteudo.json`.
- Página: subpágina "Kwai" entre TikTok e Anúncios pagos.
- Run 39071862408 (teste): ⛔ "APIFY_TOKEN_2 ausente" — o segredo ainda não existe no repositório; nada foi cobrado. Chromium: subpágina abre, mostra o bloqueio, sem erro, sem rolagem a 390 px. Testes OK.

## C17.2 — Criativos dos anúncios com miniatura (Meta) e prévias (Google) (2026-10-17) ✅

- Pedido do usuário: mostrar o criativo e a miniatura dos anúncios. Decisão registrada: o texto dos anúncios da Meta, antes só no privado, passa a ser publicado para os 24 de maior alcance por busca (anúncios políticos, públicos na Biblioteca da Meta), limitado a 400 caracteres.
- `scripts/build_criativos_meta.py` + `tests/test_criativos_meta.py`: a partir do último bruto (privado), os 24 anúncios de maior alcance por busca (empates ">1M" desfeitos pelo maior gasto); miniatura reduzida a 320 px em `data/meta/miniaturas/<id>.jpg` (os links fbcdn expiram em dias); `data/meta/criativos.json`. Passo no `meta-anuncios-apify.yml`, com a opção `apenas_criativos` (sem custo na Apify).
- Google: `collect_google_transparencia.py` guarda a URL da imagem de prévia (tpc.googlesyndication.com) e `anuncios_previas` no JSON; vídeo e texto a Central só mostra por script na página.
- Página (Anúncios pagos): card "Os anúncios que mais circularam" com seleção por busca, miniatura, página, quem pagou, texto, datas, faixas e link para a Biblioteca; prévias do Google na tabela da Central.
- Execuções: criativos (só reprocessamento) — 24 + 24 criativos, todos com miniatura, 46 arquivos (1,2 MB); Google — 5 anúncios com prévia de imagem. Chromium: miniaturas carregam, sem erro, sem rolagem a 390 px. Testes OK.
- Ressalva: na busca "Lula", os anúncios de maior alcance são em boa parte de outros candidatos que citam Lula (ex.: Elton Welter, Nilto Tatto) — é o que a busca por palavra-chave da Biblioteca devolve.

## C17.1 — Filtro de período em todo o caderno de Buscas; diagnóstico do Kwai (2026-10-17) ⚠️

**Filtro de período**
- `build_noticias_texto.py` passa a gerar o universo das notícias em três recortes: período todo, últimos 7 dias e últimas 24 horas (por data de publicação), com sufixos `_7d` e `_24h` em todos os arquivos (texto, redes, GEXF, CSVs, corpus). Limiares menores nos recortes curtos (< 1.500 títulos). O passo roda a cada execução do `google-busca.yml` (antes 1x por dia).
- Página: o card "O que a imprensa escreveu" (números, nuvens, CHD, rede de palavras, rede de veículos e downloads) segue o filtro de período do Trends (24 horas → `_24h`, 7 dias → `_7d`, demais → período todo). Relacionados do Trends passam a incluir `now 1-d`.
- Execução local: período todo 6.155 títulos (rede 150 palavras; 35 veículos); 7 dias 1.025 (150; 24); 24 horas 247 (135; 13). Na janela de 24 horas a CHD fica em ⛔ (122 e 125 títulos, abaixo do mínimo de 200). Chromium: troca de período atualiza tudo, sem erro.

**Kwai (pedido do usuário: avaliar github.com/Joaopedrobs7/kwai-video-scraper e testar uma versão 2026)**
- O repositório (1 arquivo, 118 linhas, último commit 25/10/2024, sem licença, chromedriver de Windows embutido) só baixa arquivos de vídeo; não coleta métricas. Não foi executado.
- `scripts/diag_kwai.py` + `teste-kwai.yml` (Playwright, sem login, não grava): nos perfis declarados ao TSE, o site devolve só o menu (resposta `antispamPluginRsp` do Kwai) — sem perfil, vídeos ou números. Links curtos do TSE (k.kwai.com/u/…/XGXCOK66, s.kw.ai/u/ECB8-VMN) falham com `KEY_FORMAT_ERR`: o TSE grava a URL em maiúsculas e o código do link diferencia maiúsculas.
- Conclusão: coleta gratuita do Kwai ⛔ bloqueada a partir do GitHub; alternativa paga avaliada: ator `unfenced-group/kwai-scraper` (perfis, vídeos com visualizações, curtidas, comentários e compartilhamentos; a partir de US$ 1,49/mil itens de lista; "onlyNewVideos" não cobra o que já veio). Aguarda autorização e teto do usuário.

## C17.0 — Biblioteca de Anúncios da Meta via Apify (2026-10-17) ⚠️

**Decisão e autorização**
- O token oficial da Meta volta com "Application does not have permission for this action" (run 39064748507); o usuário pediu a coleta pela Apify, no ator mais econômico, e autorizou: teste US$ 0,50 no total; depois US$ 0,30 por dia (teto mensal configurado em US$ 9).
- Atores comparados pela API pública da loja (workflow `teste-apify-loja.yml`, só leitura): escolhido `jmlp/meta-ad-library-scraper` — US$ 0,00015 por anúncio no plano gratuito (US$ 0,15/mil), 565 usuários em 30 dias, nota 5 (11), 339.254 de 340.265 execuções bem-sucedidas; o README informa gasto e alcance dos anúncios políticos. O ator oficial `apify/facebook-ads-scraper` custa US$ 0,0058 por anúncio no mesmo plano.

**O que mudou**
- `scripts/collect_meta_anuncios_apify.py` + `data/config/meta_anuncios_apify.json` + `.github/workflows/meta-anuncios-apify.yml` (diário 09h50; manual com "teste") + `tests/test_meta_anuncios_apify.py`: uma execução por candidato com `maxTotalChargeUsd` (teto dividido entre as buscas), custo calculado pelos eventos cobrados, teto mensal somando os manifestos `data/meta/manifesto-*.json`; faixas "R$20K - R$25K", ">1M" etc. convertidas; acumulado público sem texto em `data/meta/anuncios_apify.csv`; bruto só no privado. Mesmo formato de `data/meta/anuncios.json` da coleta oficial, então a página não mudou de estrutura; o status mostra custo, teto e o aviso de amostra.
- `meta-anuncios.yml` (token oficial): agenda pausada até a Meta liberar o app.

**Execuções**
- Teste 1 (17/10 17h30, uma execução com as duas buscas): 1.600 anúncios, US$ 0,2376 — descartado na página porque não dava para saber de qual busca vinha cada anúncio (617 não citam nenhum nome no texto); motivou a execução por consulta. Revelou também que o ator ignora o filtro de data de início: os anúncios vêm com exibição no período, ordenados pelo alcance.
- Teste 2 (run 39067390195, teto restante US$ 0,26): 850 anúncios por candidato (limite), US$ 0,2538. Total gasto no teste: US$ 0,4914 (≤ US$ 0,50).
  - Busca "Lula": 266 páginas; página Lula 175 anúncios, R$ 1.585.800 a 1.920.295.
  - Busca "Flávio Bolsonaro": 220 páginas; página Flavio Bolsonaro 132 anúncios, R$ 4.436.100 a 5.165.986; página Lula aparece com 162 anúncios que citam Flávio.
- Chromium: página de anúncios com os dados, sem erro, sem rolagem a 390 px. Testes OK.

**Ressalvas**
- É amostra: o teto limita aos ~850 anúncios de maior alcance por busca na carga inicial e ~1.000 por dia (exibidos desde ontem) nas execuções diárias; o acumulado cresce a cada dia. Somas de gasto são faixas e contam "ou mais" quando a Meta informa só o piso.
- Fases contam anúncios pela data de início; anúncios iniciados antes de 20/07 com exibição no período não entram em nenhuma fase.

## C16.0 — Variação diária de seguidores e filtro "24 horas" no Trends (2026-10-17) ✅

- `scripts/build_variacao_seguidores.py` + `tests/test_variacao_seguidores.py`: compara, por conta (candidate_id + endereço normalizado como na página), a coleta mais recente com a anterior (`coleta_*.csv` da Apify e `youtube_*.csv`), em `data/seguidores/variacao.json`. Roda nos workflows de seguidores Meta e YouTube. Página "Quem acompanha": cada card mostra ▲/▼ %, a diferença absoluta e a data comparada.
- Execução local: 84 contas com duas coletas; a comparação de hoje é 17/10 × 15/10 (2 dias), porque a coleta de 16/10 falhou (C14.1). Ex.: @lulaoficial +1,06% (+185.173), @brasilcomlula +6,41%, @evangelicoscomlula +9,15%, Facebook /LULA +0,34%.
- Trends: período `now 1-d` (últimas 24 horas, um ponto a cada 8 minutos) na config, no `build_trends_caderno.py` (fora do método de picos, como o de 7 dias) e na página (botão "24 horas", eixo em hh:mm). `trends.yml` passa a rodar 3x ao dia (08h40, 14h40, 20h40).
- Run 39065205773: 12 consultas, 181/181/180 pontos nas séries de 24 horas. Chromium: botão e eixo (17:00 … 13:48) corretos, sem erro; cards com a variação, sem rolagem a 390 px. Testes OK.
- Ressalva: contagens arredondadas pela plataforma (ex.: "90 mil") podem esconder variação real.

## C15.1 — Google Transparência consulta todos os sites declarados ao TSE (2026-10-17) ✅

- Correção apontada pelo usuário: a primeira versão consultava só 4 domínios escritos à mão (dois deles, lula.com.br e flaviobolsonaro.com.br, por suposição). Agora os domínios vêm de `data/tse/redes_presidencia_2026.json` — sites declarados pelas chapas 13 e 22 (titular e vice), sem redes sociais, encurtadores e plataformas genéricas, reduzidos ao domínio registrado — mais pt.org.br e partidoliberal.org.br: 41 domínios (13 da chapa 13, 26 da chapa 22 incluindo o vice Alfredo Gaspar).
- Saída ganha `dominios_consultados` (domínio, chapa, nº de anúncios); a página lista todos.
- Run 39063937210: 41 domínios lidos, nenhum sem leitura; com anúncios só lula.com.br (25, a campanha de 2022) e pt.org.br (3). Nenhum anúncio exibido desde 16/08/2026. Testes OK; Chromium a 390 px sem erro.

## C15.0 — Anúncios: Google (Central de Transparência) em produção; Meta segue sem token (2026-10-17) ⚠️

**O que mudou**
- Diagnóstico `scripts/diag_google_transparencia.py` + `teste-google-transparencia.yml` (não grava): a busca da Central devolve anunciantes pelo RPC `SearchSuggestions` e os anúncios pelo `SearchCreatives` nas páginas de anunciante e de domínio, sem login.
- `scripts/collect_google_transparencia.py` + `data/config/google_transparencia.json` + `.github/workflows/google-transparencia.yml` (diário 09h35) + `tests/test_google_transparencia.py`: busca por partidos e candidatos, aceita só anunciantes do Brasil com nome verificado da lista (homônimos pessoas físicas ficam fora — a busca "Lula" devolve vários), lê os anúncios das páginas de anunciante e dos domínios oficiais. Saídas: `data/google_ads/transparencia.json` e `data/google_ads/anuncios.csv` (histórico).
- Página (caderno 02 · Anúncios pagos): o bloco do Google passa a mostrar a tabela de anunciantes, anúncios, formatos, datas e quantos foram exibidos desde 16/08/2026.

**Testes executados**
- Run do `google-transparencia.yml` (17/10, 15h22): status ok, 4 anunciantes e 30 anúncios — "ELEIÇÃO 2022 LUIZ INACIO LULA DA SILVA PRESIDENTE" (25 anúncios, 21/08 a 28/10/2022), "Partido dos trabalhadores" (3, 27/10/2022 a 01/03/2024) e duas contas "PARTIDO DOS TRABALHADORES - PT" (1 imagem cada, exibidas entre 17 e 24/03/2026). Nenhum anúncio exibido desde 16/08/2026. Nenhum anunciante de Flávio Bolsonaro ou do PL; o domínio partidoliberal.org.br retornou 0 anúncios.
- Meta: run 39057347549 terminou com ⛔ "falta o segredo META_AD_LIBRARY_TOKEN".
- `python -m unittest discover -s tests` sem falhas; Chromium sem erro, sem rolagem a 390 px.

**Ressalvas**
- Códigos de formato (1 texto, 2 imagem, 3 vídeo) seguem o mapeamento usado por raspadores públicos da Central; não são documentados pelo Google.
- A Central não tem API pública; a coleta depende da página e pode quebrar se o Google mudar o site.
- Pendente: token da Meta (`META_AD_LIBRARY_TOKEN`).

## C14.1 — Coletas paradas no passo "Testes" desde 16/10 (correção) ⚠️

- Desde 16/10 ~11h47 (Brasília), Trends, TikTok (chapas e hashtags), Seguidores (YouTube e Meta), Comentários e Sentimento falharam no passo "Testes" e não coletaram (runs 38918628605, 38919511864, 38920163024, 38920522670, 38924412568, 38924663601, 38933719945, 38987759138, 38989936728). Pedido do usuário: forçar a coleta do Trends.
- Causa encontrada: `tests/test_comentarios.py` importa módulos que exigem numpy; num ambiente sem numpy (Python 3.12 limpo) a descoberta de testes quebra. Correção: o módulo é pulado quando a dependência falta (roda no workflow de comentários, que instala numpy).
- `scripts/testes_ci.sh`: os workflows passam a publicar cada teste que falhar como anotação (o log completo não é legível por aqui), para diagnosticar se houver outra causa.
- Testes: suíte completa OK no Python 3.13 com dependências e OK (10 pulados) num venv Python 3.12 limpo.
- Run 38990134816 (Trends, 17/10 01h16 UTC): testes OK, coleta OK — 9 consultas em `data/trends/2026-10-17/011626`.
- As anotações novas mostraram a causa principal nos demais workflows: `test_noticias_texto` falhava com `No module named 'scipy'` — a rede de veículos (C13.1) usava `kamada_kawai_layout`, que exige scipy, e os workflows instalam só networkx e numpy. O mesmo erro fazia a análise do universo das notícias falhar em silêncio no `google-busca.yml` (passo com continue-on-error). Correção: layout Fruchterman-Reingold (sem scipy) no componente principal. Recalculado com os dados atuais: 35 veículos, 130 ligações, 6 comunidades, modularidade 0,171.
- Teste: suíte completa OK num venv Python 3.12 com só networkx 3.6.1 e numpy 2.3.4 (como nos workflows).
- Redisparos após a correção: google-busca, seguidores-youtube, tiktok e tiktok-hashtags OK; comentarios-youtube coletou e publicou agregados, mas o push no repositório privado foi recusado (provável concorrência) — o passo agora faz pull --rebase e tenta 3 vezes.
- Lição registrada: dependência nova em script coberto por teste precisa entrar nos workflows ou o teste precisa pular quando ela falta.

## C14.0 — Reuters Digital News Report 2022 e 2026: dados do Brasil (2026-10-16) ✅

**O que mudou**
- `.github/workflows/reuters-dnr.yml`: baixa os PDFs (URLs dadas pelo usuário), registra SHA-256 e grava texto extraído (`pdftotext -layout`) e imagens das páginas do Brasil SÓ no repositório privado (`reuters/`). Download validado pelo `pdfinfo`, com novas tentativas (o servidor cortou a transferência de 2022 em dois runs).
- `data/reuters/brasil.json`: só Brasil (pedido do usuário), transcrito das páginas do país — DNR 2022 p. 116–117 (PDF 116–117, SHA-256 fa7608e2…), DNR 2026 p. 126–127 (PDF 129–130, SHA-256 39a8e895…): confiança geral, evitação, pagamento, penetração de internet, fontes (2013 e ano da edição), dispositivos (2022), redes para notícias, chatbots de IA, podcasts, criadores/influenciadores, RSF, alcance semanal das marcas e confiança por marca.
- `scripts/conferir_reuters.py` (roda com o repositório privado) e `tests/test_reuters.py`.
- Página: subpágina "Consumo de notícias (Reuters)" no caderno 06, entre PNAD e Contas × eleitorado: 8 indicadores, comparações 2022 → 2026 (fontes, redes, confiança por marca, alcance), fonte com página e SHA-256.

**Testes executados**
- Conferência visual das 4 páginas renderizadas (run do workflow com imagens) e `conferir_reuters.py`: 107 números de 2022 e 119 de 2026, todos presentes no texto das páginas; SHA-256 iguais aos do download.
- `python -m unittest discover -s tests` sem falhas; Chromium sem erro de JS, sem rolagem a 390 px.

**Ressalvas**
- Amostra online e urbana (YouGov), não representativa da população geral.
- Alcance das marcas: 2022 "uso semanal", 2026 "uso semanal para notícias" — pergunta diferente. Telegram 2022 vem do texto da página, não da tabela. Fontes de notícias de 2013 lidas no gráfico (rótulos do início das linhas).
- Dados do Brasil em gráficos comparativos de outras seções dos relatórios ainda não foram extraídos.

## C13.1 — Rede (Gephi) dos veículos que publicaram (2026-10-16) ✅

- `build_noticias_texto.py`: `rede_veiculos()` — nó = veículo com 10+ títulos; aresta = semelhança de agenda (cosseno entre perfis TF-IDF de palavras dos títulos, idf suavizado), cada veículo ligado aos 5 mais parecidos com cosseno ≥ 0,15; Louvain; Kamada-Kawai no componente principal (distância = 1 − cosseno), componentes soltos em fila na base. Palavras distintivas por veículo (TF-IDF sem suavização). Saídas: `rede_veiculos.json/.gexf`, `rede_veiculos_nos.csv`, `rede_veiculos_arestas.csv`. Teste ampliado.
- Página: bloco "Gephi · rede dos veículos que publicaram" no card do universo das notícias, com grupos e downloads.
- Execução local sobre `data/trends/noticias/universo.csv.gz` (o mesmo do run 38901902789): 36 veículos, 134 ligações, 6 comunidades, modularidade 0,187 (agendas parecidas: a separação entre grupos é fraca). Grupos: núcleo de grandes veículos (G1, Valor, Folha, Brasil de Fato, CNN, Gazeta do Povo); VEJA, CartaCapital, UOL Notícias, JOTA; O Globo, BBC, Estadão; imprensa gaúcha (Sul 21, Jornal do Comércio) com UOL, R7, Band; jurídicos e oficiais (Agência Brasil, ConJur, Migalhas, TSE); CUT e Fundação Perseu Abramo (componente separado).
- Chromium: 36 nós e rótulos, sem erro, sem rolagem a 390 px. `python -m unittest discover -s tests` sem falhas.
- Ressalva: mede semelhança de pauta e vocabulário nos títulos, não linha editorial nem posição política.

## C13.0 — Universo das notícias no caderno 05: nuvem, CHD (IRaMuTeQ), rede (Gephi), corpus (2026-10-16) ✅

**O que mudou**
- `collect_google_noticias_diario.py` guarda todos os itens do dia (não só os 5 primeiros) em `data/trends/noticias/universo.csv.gz`; `--refazer` recoleta dias fechados. Teste ampliado.
- `scripts/build_noticias_texto.py` + `tests/test_noticias_texto.py`: título único por candidato; nuvem (sem os nomes dos candidatos), CHD de Reinert (títulos com 4+ palavras, formas em 10+ títulos), rede de coocorrência (Louvain, cosseno de Salton), corpus IRaMuTeQ com `*cand_ *fase_ *mes_ *veic_`, `titulos_unicos.csv`, GEXF e CSVs de nós e arestas.
- `google-busca.yml`: análise 1x por dia (07h) e em execução manual; removidos os passos de diagnóstico de segredos e de teste da chave (geravam anotações "não" e "400" que pareciam erro).
- Página (caderno 05): card "O que a imprensa escreveu sobre cada candidato" com números, nuvens, classes da CHD com 3 manchetes de exemplo, rede e downloads. Cobre o período todo (não segue o filtro de período).

**Testes executados**
- `python -m unittest discover -s tests` sem falhas.
- Run 38901445572 (`desde=2026-07-20`): 6.046 itens no universo (Lula 3.075, Flávio 2.971); máximo de 83 itens num dia, nenhum dia no limite de 100 do feed.
- Run 38901902789 (análise): Lula 3.058 títulos únicos, 115 veículos, CHD com 6 classes; Flávio 2.954 títulos, 132 veículos, CHD com 6 classes; rede com 150 palavras, 754 ligações, 6 comunidades, modularidade 0,421.
- Chromium com os dados reais: 150 nós, 70 palavras na nuvem de Lula, 12 classes; sem erro de JS; sem rolagem horizontal a 390 px.

**Ressalvas**
- A ordem e a cobertura são as do Google Notícias no momento da coleta (reconstituição retroativa para dias antes de 16/10).
- CHD sem lematização; nomes das classes ficam para o pesquisador. O nome do adversário fica na CHD (é informativo), mas sai da nuvem e da rede.

## C12.4 — Primeiros números de sentimento dos comentários do YouTube (2026-10-16) ⚠️

- Run 38854095565 (versão que gravava só no fim): cancelado no limite de 2 h, nada gravado.
- Run 38862215596 (grava a cada 2.000, para em 75 min): 48.000 de 128.104 comentários classificados (os mais recentes primeiro), cache no repositório privado, agregados em `data/youtube/comentarios/sentimento.json`. Ritmo observado: ~2.000 a cada ~195 s.
  - Lula: 30.281 classificados (40,5% dos coletados) — 50,6% positivo, 32,5% neutro, 16,8% negativo; 160 de 370 vídeos com ≥ 30 classificados.
  - Flávio Bolsonaro: 17.719 (33,2%) — 41,5% positivo, 40,5% neutro, 18,0% negativo; 114 de 268 vídeos.
  - Por fase (data do comentário): 1º turno Lula 55,4% pos./16,1% neg. (n 3.913), Flávio 43,1%/15,8% (n 3.255); 2º turno Lula 49,9%/16,9% (n 26.368), Flávio 41,1%/18,5% (n 14.464).
- Página: na tabela de fases, a pré-campanha passa a dizer "fora da coleta (comentários desde 16/08)" em vez de ⛔.
- Chromium com os dados reais: card do caderno 04 e detalhe do vídeo (ex.: "Conquistamos o fim da escala 6x1…", n = 212, 76,4% positivo) renderizados, sem erro, sem rolagem a 390 px.
- Ressalvas: parcial (faltam 80.079; novo run disparado; os diários seguintes completam) e enviesado para o 2º turno até completar; `revisoes_modelo` veio vazio (o hash da revisão do modelo não foi capturado); sem validação humana; o modelo lê tom, não posição política, e ironia tende a ser lida pelo sentido literal.

## C12.3 — 5 primeiros do Google Notícias por dia, ligados ao filtro de período (2026-10-16) ✅

- `scripts/collect_google_noticias_diario.py` + `tests/test_google_noticias_diario.py`: por dia e candidato, os 5 primeiros do RSS do Google Notícias publicados naquele dia (horário de Brasília), via `after:`/`before:`. A cada hora refaz ontem e hoje; o `workflow_dispatch` aceita `desde` para reconstituir dias anteriores. Dias anteriores a 16/10 são reconstituição retroativa (ordem do momento da coleta).
- `google-busca.yml`: passo novo e entrada `desde`.
- Página (caderno 05): card "As manchetes de cada dia no período do filtro" — seletor de dia e ranking de veículos no top 5, que mudam com o filtro de período do Trends (evento `gt:periodo`).
- Testes: `python -m unittest discover -s tests` sem falhas; Chromium a 390 px sem erro de JS (ainda sem o arquivo de dados: mostra ⛔).
- Run 38863725033 (`desde=2026-07-20`): 89 dias (20/07–16/10) em `data/trends/google_noticias_diario.json`, 0 erros; Lula com 5 itens em 86 dias (4 em 2, 1 em 1); Flávio com 5 em 88 (2 em 1).
- Chromium com os dados reais: período eleitoral = 88 dias até 15/10 (fim da série do Trends); trocar para "últimos 7 dias" muda dias e ranking; seletor de dia funciona; sem erro, sem rolagem a 390 px.
- Ressalva: notícias mais antigas vêm do RSS com data sem hora (07:00 UTC); a atribuição ao dia é por data.

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
