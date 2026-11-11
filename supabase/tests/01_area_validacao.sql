-- Teste funcional das regras de leitura e das funções de validação (C19.377). Dados inventados; nenhum texto real.
-- Esperado: não convidado vê 0 textos e não avalia; amostra 10+10 no caso 001; avaliar junta campos, limpa alvo e emoji;
-- valores fora do livro de códigos são recusados; B não vê avaliações de A; concordância só lista itens com 2 pesquisadores;
-- arquivo só entra na pasta do próprio usuário; anon sem acesso.
insert into auth.users(id) values ('11111111-1111-1111-1111-111111111111'),('22222222-2222-2222-2222-222222222222'),('33333333-3333-3333-3333-333333333333');
insert into public.pesquisadores(user_id,nome,termo_aceito_em) values ('11111111-1111-1111-1111-111111111111','A',now()),('22222222-2222-2222-2222-222222222222','B',now());
insert into public.corpus(caso,rede,fonte,item_id,publicado_em,texto,emojis,ofensivo)
select case when g%2=0 then '001' else '002' end, case when g%3=0 then 'x' else 'youtube' end, case when g%3=0 then 'post' else 'comentario' end, 'i'||g,
       timestamptz '2026-10-01' + g*interval '1 hour', 'texto '||g||case when g%4=0 then ' fraude 🤡' else ' brasil' end, case when g%4=0 then array['🤡'] else '{}'::text[] end, g%5=0
from generate_series(1,400) g;
select public.preparar_area(20) as preparar;
select caso, estrato, count(*) from public.amostra_validacao group by 1,2 order by 1,2;
set role authenticated;
select set_config('request.jwt.claim.sub','33333333-3333-3333-3333-333333333333',false);
select 'nao_convidado_corpus', count(*) from public.corpus;
select public.avaliar(1, '{"ofensivo":"sim"}');
select set_config('request.jwt.claim.sub','11111111-1111-1111-1111-111111111111',false);
select caso, textos, com_emoji, triagem, amostra, avaliados_amostra, arquivos, pesquisadores from public.painel_casos();
select id, rede, fonte, na_amostra, avaliacao, total from public.textos('001','amostra',p_lim=>3);
select public.avaliar((select corpus_id from public.amostra_validacao where caso='001' order by ordem limit 1), '{"ofensivo":"sim","tom":"ataque","emojis":{"🤡":"ataque"}}') - 'criado_em' - 'atualizado_em' as a1;
select public.avaliar((select corpus_id from public.amostra_validacao where caso='001' order by ordem limit 1), '{"odio":"sim","odio_alvo":"ideologia"}') - 'criado_em' - 'atualizado_em' as a2;
select public.avaliar((select corpus_id from public.amostra_validacao where caso='001' order by ordem limit 1), '{"odio":"nao","emojis":{"🤡":null}}') - 'criado_em' - 'atualizado_em' as a3_limpa_alvo_e_emoji;
select public.avaliar((select corpus_id from public.amostra_validacao where caso='001' order by ordem limit 1), '{"emojis":{"🤡":"ironia"}}') ->> 'emojis' as a4;
select public.avaliar(1, '{"tom":"xyz"}');
select public.avaliar(1, '{"emojis":{"🤡":"qualquer"}}');
select public.avaliar(1, '{"hack":"1"}');
select count(*) pendentes_amostra from public.textos('001','amostra',p_pendentes=>true,p_lim=>100);
select count(*) busca_fraude_corpus, max(total) total from public.textos(null,'corpus',p_q=>'fraude',p_lim=>100);
select * from public.buscar_resumo('fraude') order by 1,2;
select count(*) pendentes_corpus, max(total) total from public.textos('001','corpus',p_pendentes=>true,p_lim=>100);
select count(*) from odi_interno.busca_contagem('fraude',null,null,null);
select public.avaliar_emoji('001','🤡','{"tipo":"simbolico","funcao":"ataque","sentimento":"negativo","alinhamento":"disputado"}') - 'atualizado_em' as e1;
insert into storage.objects(bucket_id,name) values ('validacao','001/11111111-1111-1111-1111-111111111111/a.gexf');
insert into storage.objects(bucket_id,name) values ('validacao','001/22222222-2222-2222-2222-222222222222/a.gexf');
insert into public.arquivos(caso,programa,nome,caminho,tamanho) values ('001','gephi','a.gexf','001/11111111-1111-1111-1111-111111111111/a.gexf',10);
insert into public.arquivos(caso,programa,nome,caminho,tamanho) values ('001','gephi','b.gexf','001/22222222-2222-2222-2222-222222222222/b.gexf',10);
update public.arquivos set parecer='confere', nota='ok';
update public.arquivos set nome='x';
select set_config('request.jwt.claim.sub','22222222-2222-2222-2222-222222222222',false);
select 'B_ve_avaliacoes_de_A', count(*) from public.avaliacoes;
select public.avaliar((select corpus_id from public.amostra_validacao where caso='001' order by ordem limit 1), '{"ofensivo":"nao","tom":"ataque","emojis":{"🤡":"ironia"}}') ->> 'tom' as b1;
select * from public.concordancia('001') order by 1,2,3;
select caso, avaliados_amostra, arquivos, pesquisadores from public.painel_casos();
update public.arquivos set nota='de outro';
select nota from public.arquivos;
select * from public.triagem_x_humano('001');
reset role; set role anon;
select count(*) from public.avaliacoes;
select count(*) from odi_interno.busca_contagem('fraude',null,null,null);
