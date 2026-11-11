-- Área do pesquisador · validação na tela (C19.377, 11/11/2026).
-- Críticas do responsável em 11/11: a área tem de ser onde o pesquisador VALIDA — vê o corpus e avalia na tela — e aceitar
-- arquivos vindos do Iramuteq e do Gephi. Também corrige a lentidão que derrubava a área: a regra de leitura do corpus
-- chamava a função de permissão uma vez POR LINHA (529 mil vezes; 7,5 s de 8 s permitidos).

-- 1) leitura do corpus: permissão avaliada uma vez por consulta
alter policy corpus_so_pesquisador on public.corpus using ((select odi_interno.eh_pesquisador()));

-- 2) resumo pronto por caso × rede × tipo (refeito a cada carga), para o menu abrir na hora
create table if not exists odi_interno.resumo_casos (caso text, rede text, fonte text, textos int, com_emoji int, triagem int, de timestamptz, ate timestamptz,
  carregado_em timestamptz, primary key (caso, rede, fonte));
revoke all on odi_interno.resumo_casos from public, anon;
grant select on odi_interno.resumo_casos to authenticated;

-- 3) amostra de validação: a MESMA para todos os pesquisadores (sem isso não há concordância a medir).
--    Por caso: até p_n textos, metade com emoji e metade sem, na ordem de um sorteio fixo (md5 do identificador + semente).
--    Uma vez sorteado, o texto não sai da amostra; casos novos ganham amostra na carga seguinte.
create table if not exists public.amostra_validacao (
  corpus_id bigint primary key references public.corpus(id) on delete cascade,
  caso text not null, estrato text not null check (estrato in ('com_emoji', 'sem_emoji')), ordem int not null);
create index if not exists amostra_caso on public.amostra_validacao (caso, ordem);
alter table public.amostra_validacao enable row level security;
create policy amostra_so_pesquisador on public.amostra_validacao for select to authenticated using ((select odi_interno.eh_pesquisador()));
revoke all on public.amostra_validacao from anon;
grant select on public.amostra_validacao to authenticated;

create or replace function public.preparar_area(p_n int default 300) returns jsonb language plpgsql security definer set search_path = public set statement_timeout = '600s' as $$
declare a int; f int;
begin
  insert into public.amostra_validacao (corpus_id, caso, estrato, ordem)
  select id, caso, estrato, (o - 1) * 2 + case estrato when 'com_emoji' then 1 else 2 end from (
    select c.id, c.caso, case when cardinality(c.emojis) > 0 then 'com_emoji' else 'sem_emoji' end as estrato,
           row_number() over (partition by c.caso, cardinality(c.emojis) > 0 order by md5(c.caso || ':' || c.fonte || ':' || c.item_id || ':odi-2026')) as o
    from public.corpus c where not exists (select 1 from public.amostra_validacao a where a.caso = c.caso)) x
  where o <= p_n / 2;
  get diagnostics a = row_count;
  truncate odi_interno.resumo_casos;
  insert into odi_interno.resumo_casos
  select caso, rede, fonte, count(*), count(*) filter (where cardinality(emojis) > 0), count(*) filter (where ofensivo or odio is not null),
         min(publicado_em), max(publicado_em), max(carregado_em) from public.corpus group by 1, 2, 3;
  f := public.atualizar_frequencias();
  return jsonb_build_object('amostra_novos', a, 'frequencias', f, 'amostra_total', (select count(*) from public.amostra_validacao));
end $$;
revoke execute on function public.preparar_area(int) from public, anon, authenticated;
grant execute on function public.preparar_area(int) to service_role;

-- 4) avaliação do pesquisador, por texto (livro de códigos v0: data/config/livro_codigos_validacao.json)
create or replace function odi_interno.emojis_validos(j jsonb) returns boolean language sql immutable set search_path = '' as $$
  select jsonb_typeof(j) = 'object' and not exists (
    select 1 from jsonb_each(j) e where length(e.key) > 40 or jsonb_typeof(e.value) <> 'string'
      or (e.value #>> '{}') <> all (array['emocao', 'afeto', 'intensificador', 'substitui', 'ironia', 'alinhamento', 'ataque', 'mobilizacao', 'decorativo', 'nao_sei']))
$$;
grant execute on function odi_interno.emojis_validos(jsonb) to authenticated;
create table if not exists public.avaliacoes (
  corpus_id bigint not null references public.corpus(id) on delete cascade,
  user_id uuid not null default auth.uid() references auth.users(id) on delete cascade,
  ofensivo text check (ofensivo in ('sim', 'nao', 'nao_sei')),
  odio text check (odio in ('sim', 'nao', 'nao_sei')),
  odio_alvo text check (odio_alvo in ('sexismo', 'ideologia', 'homofobia', 'racismo', 'corpo', 'xenofobia', 'religiao', 'outro')),
  tom text check (tom in ('apoio', 'critica', 'ataque', 'ironia', 'informativo', 'nao_da')),
  emojis jsonb not null default '{}'::jsonb check (odi_interno.emojis_validos(emojis)),   -- {"🤡": "ataque", ...}
  obs text check (length(obs) <= 1000),
  criado_em timestamptz not null default now(), atualizado_em timestamptz not null default now(),
  primary key (corpus_id, user_id));
create index if not exists avaliacoes_user on public.avaliacoes (user_id);
alter table public.avaliacoes enable row level security;
create policy avaliacoes_le on public.avaliacoes for select to authenticated using (user_id = (select auth.uid()));
create policy avaliacoes_cria on public.avaliacoes for insert to authenticated with check (user_id = (select auth.uid()) and (select odi_interno.eh_pesquisador()));
create policy avaliacoes_muda on public.avaliacoes for update to authenticated using (user_id = (select auth.uid()))
  with check (user_id = (select auth.uid()) and (select odi_interno.eh_pesquisador()));
revoke all on public.avaliacoes from anon;
grant select, insert, update on public.avaliacoes to authenticated;

create or replace function public.avaliar(p_corpus_id bigint, p_dados jsonb) returns jsonb language plpgsql security invoker set search_path = public as $$
declare r public.avaliacoes;
begin
  if not odi_interno.eh_pesquisador() then raise exception 'acesso restrito a pesquisadores convidados com termo aceito'; end if;
  if not exists (select 1 from public.corpus where id = p_corpus_id) then raise exception 'texto não encontrado'; end if;
  if p_dados - array['ofensivo', 'odio', 'odio_alvo', 'tom', 'emojis', 'obs'] <> '{}'::jsonb then raise exception 'campo desconhecido'; end if;
  insert into public.avaliacoes as a (corpus_id, user_id, ofensivo, odio, odio_alvo, tom, emojis, obs)
  values (p_corpus_id, auth.uid(), p_dados ->> 'ofensivo', p_dados ->> 'odio', p_dados ->> 'odio_alvo', p_dados ->> 'tom',
          jsonb_strip_nulls(coalesce(p_dados -> 'emojis', '{}'::jsonb)), nullif(p_dados ->> 'obs', ''))
  on conflict (corpus_id, user_id) do update set
    ofensivo = case when p_dados ? 'ofensivo' then excluded.ofensivo else a.ofensivo end,
    odio = case when p_dados ? 'odio' then excluded.odio else a.odio end,
    odio_alvo = case when p_dados ? 'odio_alvo' then excluded.odio_alvo
                     when p_dados ? 'odio' and coalesce(excluded.odio, '') <> 'sim' then null else a.odio_alvo end,
    tom = case when p_dados ? 'tom' then excluded.tom else a.tom end,
    emojis = case when p_dados ? 'emojis' then jsonb_strip_nulls(a.emojis || coalesce(p_dados -> 'emojis', '{}'::jsonb)) else a.emojis end,
    obs = case when p_dados ? 'obs' then excluded.obs else a.obs end,
    atualizado_em = now()
  returning * into r;
  return to_jsonb(r) - 'user_id';
end $$;

-- 5) dicionário de emojis: avaliação do pesquisador por emoji, em cada caso
create table if not exists public.avaliacoes_emoji (
  caso text not null, emoji text not null check (length(emoji) <= 40),
  user_id uuid not null default auth.uid() references auth.users(id) on delete cascade,
  tipo text check (tipo in ('iconico', 'indicial', 'simbolico', 'nao_sei')),
  funcao text check (funcao in ('emocao', 'afeto', 'intensificador', 'substitui', 'ironia', 'alinhamento', 'ataque', 'mobilizacao', 'decorativo', 'nao_sei')),
  sentimento text check (sentimento in ('positivo', 'negativo', 'neutro', 'ambiguo')),
  alinhamento text check (alinhamento in ('lula', 'flavio', 'disputado', 'nenhum', 'outro')),
  obs text check (length(obs) <= 1000),
  atualizado_em timestamptz not null default now(),
  primary key (caso, emoji, user_id));
alter table public.avaliacoes_emoji enable row level security;
create policy avaliacoes_emoji_le on public.avaliacoes_emoji for select to authenticated using (user_id = (select auth.uid()));
create policy avaliacoes_emoji_cria on public.avaliacoes_emoji for insert to authenticated with check (user_id = (select auth.uid()) and (select odi_interno.eh_pesquisador()));
create policy avaliacoes_emoji_muda on public.avaliacoes_emoji for update to authenticated using (user_id = (select auth.uid()))
  with check (user_id = (select auth.uid()) and (select odi_interno.eh_pesquisador()));
revoke all on public.avaliacoes_emoji from anon;
grant select, insert, update on public.avaliacoes_emoji to authenticated;

create or replace function public.avaliar_emoji(p_caso text, p_emoji text, p_dados jsonb) returns jsonb language plpgsql security invoker set search_path = public as $$
declare r public.avaliacoes_emoji;
begin
  if not odi_interno.eh_pesquisador() then raise exception 'acesso restrito a pesquisadores convidados com termo aceito'; end if;
  if p_dados - array['tipo', 'funcao', 'sentimento', 'alinhamento', 'obs'] <> '{}'::jsonb then raise exception 'campo desconhecido'; end if;
  insert into public.avaliacoes_emoji as a (caso, emoji, user_id, tipo, funcao, sentimento, alinhamento, obs)
  values (p_caso, p_emoji, auth.uid(), p_dados ->> 'tipo', p_dados ->> 'funcao', p_dados ->> 'sentimento', p_dados ->> 'alinhamento', nullif(p_dados ->> 'obs', ''))
  on conflict (caso, emoji, user_id) do update set
    tipo = case when p_dados ? 'tipo' then excluded.tipo else a.tipo end,
    funcao = case when p_dados ? 'funcao' then excluded.funcao else a.funcao end,
    sentimento = case when p_dados ? 'sentimento' then excluded.sentimento else a.sentimento end,
    alinhamento = case when p_dados ? 'alinhamento' then excluded.alinhamento else a.alinhamento end,
    obs = case when p_dados ? 'obs' then excluded.obs else a.obs end,
    atualizado_em = now()
  returning * into r;
  return to_jsonb(r) - 'user_id';
end $$;

-- 6) arquivos vindos do Iramuteq e do Gephi (o arquivo fica no armazenamento privado "validacao")
create table if not exists public.arquivos (
  id uuid primary key default gen_random_uuid(),
  caso text not null,
  user_id uuid not null default auth.uid() references auth.users(id) on delete cascade,
  programa text not null check (programa in ('iramuteq', 'gephi', 'outro')),
  analise text check (length(analise) <= 80),
  nome text not null check (length(nome) <= 200),
  caminho text not null unique,
  tamanho bigint,
  resumo jsonb,                       -- lido do arquivo no navegador (ex.: nós e ligações de um GEXF)
  parecer text check (parecer in ('confere', 'parcial', 'diverge')),
  nota text check (length(nota) <= 2000),
  criado_em timestamptz not null default now());
create index if not exists arquivos_caso on public.arquivos (caso, criado_em desc);
alter table public.arquivos enable row level security;
create policy arquivos_le on public.arquivos for select to authenticated using ((select odi_interno.eh_pesquisador()));
create policy arquivos_envia on public.arquivos for insert to authenticated
  with check (user_id = (select auth.uid()) and (select odi_interno.eh_pesquisador()) and caminho like caso || '/' || (select auth.uid())::text || '/%');
create policy arquivos_anota on public.arquivos for update to authenticated using (user_id = (select auth.uid())) with check (user_id = (select auth.uid()));
revoke all on public.arquivos from anon;
grant select, insert on public.arquivos to authenticated;
grant update (parecer, nota, analise) on public.arquivos to authenticated;

insert into storage.buckets (id, name, public, file_size_limit) values ('validacao', 'validacao', false, 52428800) on conflict (id) do nothing;
create policy validacao_envia on storage.objects for insert to authenticated
  with check (bucket_id = 'validacao' and (select odi_interno.eh_pesquisador()) and (storage.foldername(name))[2] = (select auth.uid())::text);
create policy validacao_le on storage.objects for select to authenticated
  using (bucket_id = 'validacao' and (select odi_interno.eh_pesquisador()));

-- 7) consultas da tela (todas sem privilégio elevado; o que precisa ver avaliações de outros fica em odi_interno)
create or replace function odi_interno.pesquisadores_por_caso() returns table (caso text, n bigint) language sql stable security definer set search_path = public as $$
  select c.caso, count(distinct v.user_id) from public.avaliacoes v join public.corpus c on c.id = v.corpus_id group by 1
$$;
revoke execute on function odi_interno.pesquisadores_por_caso() from public, anon;
grant execute on function odi_interno.pesquisadores_por_caso() to authenticated;
-- menu de casos: o que há no banco, a amostra, o que EU já avaliei, arquivos e quantos pesquisadores já avaliaram
create or replace function public.painel_casos() returns table (caso text, textos bigint, com_emoji bigint, triagem bigint, carregado_em timestamptz,
  amostra bigint, avaliados_amostra bigint, avaliados bigint, emojis_avaliados bigint, arquivos bigint, pesquisadores bigint)
language plpgsql stable security invoker set search_path = public as $$
#variable_conflict use_column
begin
  if not odi_interno.eh_pesquisador() then raise exception 'acesso restrito a pesquisadores convidados com termo aceito'; end if;
  return query
  select r.caso, r.textos, r.com_emoji, r.triagem, r.carregado_em,
    coalesce((select count(*) from public.amostra_validacao a where a.caso = r.caso), 0),
    coalesce((select count(*) from public.avaliacoes v join public.amostra_validacao a on a.corpus_id = v.corpus_id where a.caso = r.caso and v.user_id = auth.uid()), 0),
    coalesce((select count(*) from public.avaliacoes v join public.corpus c on c.id = v.corpus_id where c.caso = r.caso and v.user_id = auth.uid()), 0),
    coalesce((select count(*) from public.avaliacoes_emoji e where e.caso = r.caso and e.user_id = auth.uid()), 0),
    coalesce((select count(*) from public.arquivos q where q.caso = r.caso), 0),
    coalesce((select p.n from odi_interno.pesquisadores_por_caso() p where p.caso = r.caso), 0)
  from (select s.caso, sum(s.textos)::bigint textos, sum(s.com_emoji)::bigint com_emoji, sum(s.triagem)::bigint triagem, max(s.carregado_em) carregado_em
        from odi_interno.resumo_casos s group by s.caso) r order by r.caso;
end $$;

create or replace function public.resumo_caso(p_caso text) returns table (rede text, fonte text, textos int, com_emoji int, triagem int, de timestamptz, ate timestamptz)
language sql stable security invoker set search_path = public as $$
  select s.rede, s.fonte, s.textos, s.com_emoji, s.triagem, s.de, s.ate from odi_interno.resumo_casos s
  where s.caso = p_caso and odi_interno.eh_pesquisador() order by s.textos desc
$$;

-- textos para ler e avaliar: amostra de validação (ordem do sorteio) ou corpus (mais recentes primeiro), com a MINHA avaliação junto
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
  if coalesce(p_caso, '') <> '' then w := array_append(w, 'c.caso = $1'); end if;
  if coalesce(p_q, '') <> '' then w := array_append(w, 'odi_interno.tsv_simples(c.texto) @@ websearch_to_tsquery(''simple'', extensions.unaccent(lower($2)))'); end if;
  if coalesce(p_emoji, '') <> '' then w := array_append(w, 'c.emojis @> array[$3]'); end if;
  if p_redes is not null and cardinality(p_redes) > 0 then w := array_append(w, 'c.rede = any($4)'); end if;
  if coalesce(p_fonte, '') <> '' then w := array_append(w, 'c.fonte = $5'); end if;
  if p_so_emoji then w := array_append(w, 'cardinality(c.emojis) > 0'); end if;
  if p_so_triagem then w := array_append(w, '(c.ofensivo or c.odio is not null)'); end if;
  if p_pendentes then w := array_append(w, 'v.corpus_id is null'); end if;
  perform odi_interno._registrar('textos', jsonb_build_object('caso', p_caso, 'modo', p_modo, 'q', p_q, 'emoji', p_emoji, 'redes', p_redes, 'fonte', p_fonte, 'pagina', p_pagina));
  sql := 'select c.id, c.caso, c.rede, c.fonte, c.publicado_em, c.autor, c.texto, c.emojis, c.candidato, c.ofensivo, c.odio, '
      || case when p_modo = 'amostra' then 'true' else 'exists (select 1 from public.amostra_validacao a2 where a2.corpus_id = c.id)' end
      || ', case when v.corpus_id is null then null else to_jsonb(v) - ''user_id'' - ''corpus_id'' end, count(*) over () from '
      || case when p_modo = 'amostra' then 'public.amostra_validacao a join public.corpus c on c.id = a.corpus_id' else 'public.corpus c' end
      || ' left join public.avaliacoes v on v.corpus_id = c.id and v.user_id = $6 where ' || array_to_string(w, ' and ')
      || case when p_modo = 'amostra' then ' order by a.ordem' else ' order by c.publicado_em desc nulls last, c.id' end
      || ' limit ' || l || ' offset ' || (greatest(p_pagina, 0) * l);
  return query execute sql using p_caso, p_q, p_emoji, p_redes, p_fonte, uid;
end $$;

-- busca geral: onde o termo aparece (por caso e por rede), antes de ler
create or replace function public.buscar_resumo(p_q text default null, p_emoji text default null, p_redes text[] default null, p_fonte text default null)
returns table (caso text, rede text, textos bigint)
language plpgsql security invoker set search_path = public as $$
#variable_conflict use_column
begin
  if not odi_interno.eh_pesquisador() then raise exception 'acesso restrito a pesquisadores convidados com termo aceito'; end if;
  if coalesce(p_q, '') = '' and coalesce(p_emoji, '') = '' then raise exception 'escreva uma palavra ou um emoji'; end if;
  perform odi_interno._registrar('buscar_resumo', jsonb_build_object('q', p_q, 'emoji', p_emoji, 'redes', p_redes, 'fonte', p_fonte));
  return query select f.caso, f.rede, count(*) from public._filtro(p_q, p_emoji, null, p_redes, p_fonte, null, null) f group by 1, 2;
end $$;

-- concordância: valores de cada pesquisador (numerado, sem identificar) nos itens com 2 ou mais avaliações
create or replace function odi_interno.concordancia_dados(p_caso text) returns table (dimensao text, item text, pesquisador int, valor text)
language sql stable security definer set search_path = public as $$
  with cod as (select u.user_id, dense_rank() over (order by u.user_id)::int n from (select user_id from public.avaliacoes union select user_id from public.avaliacoes_emoji) u),
  base as (select v.corpus_id, v.user_id, v.ofensivo, v.odio, v.tom, v.emojis from public.avaliacoes v join public.corpus c on c.id = v.corpus_id
           where p_caso is null or p_caso = '' or c.caso = p_caso),
  dic as (select * from public.avaliacoes_emoji where p_caso is null or p_caso = '' or caso = p_caso),
  longo as (
    select 'ofensivo'::text d, corpus_id::text i, user_id, ofensivo val from base where ofensivo is not null
    union all select 'odio', corpus_id::text, user_id, odio from base where odio is not null
    union all select 'tom', corpus_id::text, user_id, tom from base where tom is not null
    union all select 'emoji_funcao', base.corpus_id::text || ':' || e.key, base.user_id, e.value from base, jsonb_each_text(base.emojis) e
    union all select 'dic_tipo', caso || ':' || emoji, user_id, tipo from dic where tipo is not null
    union all select 'dic_funcao', caso || ':' || emoji, user_id, funcao from dic where funcao is not null
    union all select 'dic_sentimento', caso || ':' || emoji, user_id, sentimento from dic where sentimento is not null
    union all select 'dic_alinhamento', caso || ':' || emoji, user_id, alinhamento from dic where alinhamento is not null),
  cont as (select l.d, l.i, cod.n, l.val, count(*) over (partition by l.d, l.i) q from longo l join cod on cod.user_id = l.user_id)
  select d, i, n, val from cont where q >= 2
$$;
revoke execute on function odi_interno.concordancia_dados(text) from public, anon;
grant execute on function odi_interno.concordancia_dados(text) to authenticated;

create or replace function public.concordancia(p_caso text default null) returns table (dimensao text, item text, pesquisador int, valor text)
language plpgsql stable security invoker set search_path = public as $$
begin
  if not odi_interno.eh_pesquisador() then raise exception 'acesso restrito a pesquisadores convidados com termo aceito'; end if;
  return query select * from odi_interno.concordancia_dados(p_caso);
end $$;

-- triagem automática × avaliação humana (matriz de confusão do que EU avaliei), para validar HateBR no caso
create or replace function public.triagem_x_humano(p_caso text default null) returns table (triagem boolean, humano text, textos bigint)
language sql stable security invoker set search_path = public as $$
  select coalesce(c.ofensivo, false), v.ofensivo, count(*) from public.avaliacoes v join public.corpus c on c.id = v.corpus_id
  where odi_interno.eh_pesquisador() and v.user_id = auth.uid() and v.ofensivo is not null and c.ofensivo is not null
    and (p_caso is null or p_caso = '' or c.caso = p_caso) group by 1, 2
$$;

revoke execute on function public.avaliar(bigint, jsonb), public.avaliar_emoji(text, text, jsonb), public.painel_casos(), public.resumo_caso(text),
  public.textos(text, text, text, text, text[], text, boolean, boolean, boolean, int, int), public.buscar_resumo(text, text, text[], text),
  public.concordancia(text), public.triagem_x_humano(text) from public, anon;
grant execute on function public.avaliar(bigint, jsonb), public.avaliar_emoji(text, text, jsonb), public.painel_casos(), public.resumo_caso(text),
  public.textos(text, text, text, text, text[], text, boolean, boolean, boolean, int, int), public.buscar_resumo(text, text, text[], text),
  public.concordancia(text), public.triagem_x_humano(text) to authenticated;
