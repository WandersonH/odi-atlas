-- Área do pesquisador · busca geral dentro do tempo (C19.378, 11/11/2026).
-- Medido no banco real, como o usuário (papel authenticated): a busca geral levava 16,6 s (limite: 8 s) porque, com a regra de
-- leitura por linha (RLS) ligada, o Postgres não pode usar o índice de texto antes de checar a permissão (o operador de busca
-- não é "leakproof") e lia os 530 mil textos um a um. A mesma consulta sem RLS usa o índice e leva 0,09 s.
-- Solução: a permissão é checada UMA vez, no começo, e a seleção dos identificadores roda em funções internas (esquema
-- odi_interno, fora da API). O texto em si continua sendo lido pela tabela com RLS.

-- página de identificadores do corpus (mais recentes primeiro), com o total do filtro
create or replace function odi_interno.busca_ids(p_caso text, p_q text, p_emoji text, p_redes text[], p_fonte text, p_so_emoji boolean,
  p_so_triagem boolean, p_pendentes boolean, p_lim int, p_desloc int)
returns table (id bigint, total bigint, pos bigint) language plpgsql stable security definer set search_path = public as $$
#variable_conflict use_column
declare w text[] := array['true']; uid uuid := auth.uid();
begin
  if not odi_interno.eh_pesquisador() then raise exception 'acesso restrito a pesquisadores convidados com termo aceito'; end if;
  if coalesce(p_caso, '') <> '' then w := array_append(w, 'c.caso = $1'); end if;
  if coalesce(p_q, '') <> '' then w := array_append(w, 'odi_interno.tsv_simples(c.texto) @@ websearch_to_tsquery(''simple'', extensions.unaccent(lower($2)))'); end if;
  if coalesce(p_emoji, '') <> '' then w := array_append(w, 'c.emojis @> array[$3]'); end if;
  if p_redes is not null and cardinality(p_redes) > 0 then w := array_append(w, 'c.rede = any($4)'); end if;
  if coalesce(p_fonte, '') <> '' then w := array_append(w, 'c.fonte = $5'); end if;
  if p_so_emoji then w := array_append(w, 'cardinality(c.emojis) > 0'); end if;
  if p_so_triagem then w := array_append(w, '(c.ofensivo or c.odio is not null)'); end if;
  if p_pendentes then w := array_append(w, 'not exists (select 1 from public.avaliacoes v where v.corpus_id = c.id and v.user_id = $6)'); end if;
  return query execute 'select x.id, x.total, row_number() over (order by x.publicado_em desc nulls last, x.id) from ('
    || 'select c.id, c.publicado_em, count(*) over () as total from public.corpus c where ' || array_to_string(w, ' and ')
    || ' order by c.publicado_em desc nulls last, c.id limit ' || least(greatest(coalesce(p_lim, 20), 1), 100) || ' offset ' || greatest(coalesce(p_desloc, 0), 0) || ') x'
    using p_caso, p_q, p_emoji, p_redes, p_fonte, uid;
end $$;
grant execute on function odi_interno.busca_ids(text, text, text, text[], text, boolean, boolean, boolean, int, int) to authenticated;

-- onde o termo aparece: só contagens por caso e rede
create or replace function odi_interno.busca_contagem(p_q text, p_emoji text, p_redes text[], p_fonte text)
returns table (caso text, rede text, textos bigint) language plpgsql stable security definer set search_path = public as $$
#variable_conflict use_column
declare w text[] := array['true'];
begin
  if not odi_interno.eh_pesquisador() then raise exception 'acesso restrito a pesquisadores convidados com termo aceito'; end if;
  if coalesce(p_q, '') <> '' then w := array_append(w, 'odi_interno.tsv_simples(c.texto) @@ websearch_to_tsquery(''simple'', extensions.unaccent(lower($1)))'); end if;
  if coalesce(p_emoji, '') <> '' then w := array_append(w, 'c.emojis @> array[$2]'); end if;
  if p_redes is not null and cardinality(p_redes) > 0 then w := array_append(w, 'c.rede = any($3)'); end if;
  if coalesce(p_fonte, '') <> '' then w := array_append(w, 'c.fonte = $4'); end if;
  return query execute 'select c.caso, c.rede, count(*) from public.corpus c where ' || array_to_string(w, ' and ') || ' group by 1, 2'
    using p_q, p_emoji, p_redes, p_fonte;
end $$;
grant execute on function odi_interno.busca_contagem(text, text, text[], text) to authenticated;

-- textos: a amostra (300 por caso) segue como estava; o corpus passa a buscar os identificadores pela função interna
create or replace function public.textos(p_caso text default null, p_modo text default 'amostra', p_q text default null, p_emoji text default null,
  p_redes text[] default null, p_fonte text default null, p_so_emoji boolean default false, p_so_triagem boolean default false,
  p_pendentes boolean default false, p_lim int default 20, p_pagina int default 0)
returns table (id bigint, caso text, rede text, fonte text, publicado_em timestamptz, autor text, texto text, emojis text[], candidato text,
  ofensivo boolean, odio text, na_amostra boolean, avaliacao jsonb, total bigint)
language plpgsql security invoker set search_path = public as $$
#variable_conflict use_column
declare w text[] := array['true']; l int := least(greatest(p_lim, 1), 100); sql text; uid uuid := auth.uid();
begin
  if not odi_interno.eh_pesquisador() then raise exception 'acesso restrito a pesquisadores convidados com termo aceito'; end if;
  if p_modo not in ('amostra', 'corpus') then raise exception 'modo inválido'; end if;
  if p_modo = 'amostra' and coalesce(p_caso, '') = '' then raise exception 'a amostra é por caso'; end if;
  perform odi_interno._registrar('textos', jsonb_build_object('caso', p_caso, 'modo', p_modo, 'q', p_q, 'emoji', p_emoji, 'redes', p_redes, 'fonte', p_fonte, 'pagina', p_pagina));
  if p_modo = 'corpus' then
    return query
    select c.id, c.caso, c.rede, c.fonte, c.publicado_em, c.autor, c.texto, c.emojis, c.candidato, c.ofensivo, c.odio,
           exists (select 1 from public.amostra_validacao a2 where a2.corpus_id = c.id),
           case when v.corpus_id is null then null else to_jsonb(v) - 'user_id' - 'corpus_id' end, t.total
    from odi_interno.busca_ids(p_caso, p_q, p_emoji, p_redes, p_fonte, p_so_emoji, p_so_triagem, p_pendentes, l, greatest(p_pagina, 0) * l) t
    join public.corpus c on c.id = t.id
    left join public.avaliacoes v on v.corpus_id = c.id and v.user_id = uid
    order by t.pos;
    return;
  end if;
  w := array_append(w, 'c.caso = $1');
  if coalesce(p_q, '') <> '' then w := array_append(w, 'odi_interno.tsv_simples(c.texto) @@ websearch_to_tsquery(''simple'', extensions.unaccent(lower($2)))'); end if;
  if coalesce(p_emoji, '') <> '' then w := array_append(w, 'c.emojis @> array[$3]'); end if;
  if p_redes is not null and cardinality(p_redes) > 0 then w := array_append(w, 'c.rede = any($4)'); end if;
  if coalesce(p_fonte, '') <> '' then w := array_append(w, 'c.fonte = $5'); end if;
  if p_so_emoji then w := array_append(w, 'cardinality(c.emojis) > 0'); end if;
  if p_so_triagem then w := array_append(w, '(c.ofensivo or c.odio is not null)'); end if;
  if p_pendentes then w := array_append(w, 'v.corpus_id is null'); end if;
  sql := 'select c.id, c.caso, c.rede, c.fonte, c.publicado_em, c.autor, c.texto, c.emojis, c.candidato, c.ofensivo, c.odio, true, '
      || 'case when v.corpus_id is null then null else to_jsonb(v) - ''user_id'' - ''corpus_id'' end, count(*) over () '
      || 'from public.amostra_validacao a join public.corpus c on c.id = a.corpus_id '
      || 'left join public.avaliacoes v on v.corpus_id = c.id and v.user_id = $6 where ' || array_to_string(w, ' and ')
      || ' order by a.ordem limit ' || l || ' offset ' || (greatest(p_pagina, 0) * l);
  return query execute sql using p_caso, p_q, p_emoji, p_redes, p_fonte, uid;
end $$;

create or replace function public.buscar_resumo(p_q text default null, p_emoji text default null, p_redes text[] default null, p_fonte text default null)
returns table (caso text, rede text, textos bigint)
language plpgsql security invoker set search_path = public as $$
#variable_conflict use_column
begin
  if not odi_interno.eh_pesquisador() then raise exception 'acesso restrito a pesquisadores convidados com termo aceito'; end if;
  if coalesce(p_q, '') = '' and coalesce(p_emoji, '') = '' then raise exception 'escreva uma palavra ou um emoji'; end if;
  perform odi_interno._registrar('buscar_resumo', jsonb_build_object('q', p_q, 'emoji', p_emoji, 'redes', p_redes, 'fonte', p_fonte));
  return query select b.caso, b.rede, b.textos from odi_interno.busca_contagem(p_q, p_emoji, p_redes, p_fonte) b;
end $$;
