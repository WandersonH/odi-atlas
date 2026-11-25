-- Área do pesquisador · preparo por caso (C19.385, 24/11/2026).
-- Com o plano Pro o banco passa a receber também os acervos gerais (mais de 1,9 milhão de textos). Refazer amostra, resumo e
-- nuvens do banco inteiro numa chamada só deixou de caber no tempo: o preparo passa a ser feito caso a caso, logo depois da
-- carga de cada um. Substitui a versão de 11/11 (que nunca chegou a ser aplicada no banco real).
create or replace function public.preparar_area(p_n int default 300, p_caso text default null) returns jsonb
language plpgsql security definer set search_path = public set statement_timeout = '900s' as $$
declare a int; f int;
begin
  -- só a carga (chave de serviço) ou o administrador do banco; pesquisador logado e visitante são recusados
  if coalesce(auth.role(), 'service_role') <> 'service_role' then raise exception 'acesso restrito à carga do corpus'; end if;
  -- amostra de validação: só para caso que ainda não tem (nunca muda depois de criada)
  insert into public.amostra_validacao (corpus_id, caso, estrato, ordem)
  select id, caso, estrato, (o - 1) * 2 + case estrato when 'com_emoji' then 1 else 2 end from (
    select c.id, c.caso, case when cardinality(c.emojis) > 0 then 'com_emoji' else 'sem_emoji' end as estrato,
           row_number() over (partition by c.caso, cardinality(c.emojis) > 0 order by md5(c.caso || ':' || c.fonte || ':' || c.item_id || ':odi-2026')) as o
    from public.corpus c
    where (p_caso is null or c.caso = p_caso) and not exists (select 1 from public.amostra_validacao a where a.caso = c.caso)) x
  where o <= p_n / 2;
  get diagnostics a = row_count;
  -- resumo por caso, rede e tipo
  insert into odi_interno.resumo_casos (caso, rede, fonte, textos, com_emoji, triagem, de, ate, carregado_em)
  select caso, rede, fonte, count(*), count(*) filter (where cardinality(emojis) > 0), count(*) filter (where ofensivo or odio is not null),
         min(publicado_em), max(publicado_em), max(carregado_em)
  from public.corpus where p_caso is null or caso = p_caso group by 1, 2, 3
  on conflict (caso, rede, fonte) do update set textos = excluded.textos, com_emoji = excluded.com_emoji, triagem = excluded.triagem,
    de = excluded.de, ate = excluded.ate, carregado_em = excluded.carregado_em;
  -- nuvens: as 400 palavras mais frequentes por caso, rede e tipo (dado derivado, refeito a cada carga)
  delete from odi_interno.freq_palavras where p_caso is null or caso = p_caso;
  insert into odi_interno.freq_palavras (caso, rede, fonte, palavra, textos)
  select caso, rede, fonte, w, c from (
    select caso, rede, fonte, w, count(*) c, row_number() over (partition by caso, rede, fonte order by count(*) desc) o
    from public.corpus, unnest(tsvector_to_array(odi_interno.tsv_simples(texto))) w
    where (p_caso is null or caso = p_caso) and length(w) >= 3 and w !~ '^[0-9]+$'
    group by caso, rede, fonte, w) x
  where o <= 400;
  get diagnostics f = row_count;
  return jsonb_build_object('caso', p_caso, 'amostra_novos', a, 'frequencias', f,
    'amostra_total', (select count(*) from public.amostra_validacao where p_caso is null or caso = p_caso));
end $$;
grant execute on function public.preparar_area(int, text) to service_role;
