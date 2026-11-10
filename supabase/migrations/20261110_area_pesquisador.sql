-- Área do pesquisador (C19.374, 10/11/2026). Pedido e aprovação do responsável em 10/11: "a área do pesquisador
-- deve conter os corpus também". Exceção registrada no CLAUDE.md: textos de pessoas comuns passam a existir também
-- neste banco (região sa-east-1), legíveis SÓ por pesquisador convidado, ativo e com o termo aceito.
-- Autores comuns não entram (autor = @conta só com 10 mil seguidores ou mais); 020 chega anonimizado; 028 sem áudios.

create schema if not exists extensions;
create extension if not exists unaccent with schema extensions;

create table if not exists public.pesquisadores (
  user_id uuid primary key references auth.users(id) on delete cascade,
  nome text,
  papel text not null default 'pesquisador' check (papel in ('pesquisador', 'responsavel')),
  ativo boolean not null default true,
  termo_aceito_em timestamptz,
  criado_em timestamptz not null default now()
);

create table if not exists public.corpus (
  id bigint generated always as identity primary key,
  caso text not null,
  rede text not null,
  fonte text not null check (fonte in ('post', 'comentario')),
  item_id text not null,
  publicado_em timestamptz,
  autor text,              -- só contas com 10 mil seguidores ou mais; demais: null
  texto text not null,
  emojis text[] not null default '{}',
  candidato text,          -- comentários do YouTube: candidato do canal
  ofensivo boolean,        -- triagem automática HateBR (não validada); null = sem escore
  odio text,               -- triagem automática BERTabaporu (alvo); null = nada marcado ou sem escore
  carregado_em timestamptz not null default now(),
  unique (caso, fonte, item_id)
);
alter table public.corpus add column if not exists tsv tsvector;
create index if not exists corpus_tsv on public.corpus using gin (tsv);
create index if not exists corpus_emojis on public.corpus using gin (emojis);
create index if not exists corpus_caso on public.corpus (caso, rede, publicado_em);

create or replace function public.corpus_tsv() returns trigger language plpgsql set search_path = public as $$
begin new.tsv := to_tsvector('simple', extensions.unaccent(lower(coalesce(new.texto, '')))); return new; end $$;
drop trigger if exists corpus_tsv on public.corpus;
create trigger corpus_tsv before insert or update of texto on public.corpus for each row execute function public.corpus_tsv();

create table if not exists public.acessos (
  id bigint generated always as identity primary key,
  user_id uuid not null default auth.uid(),
  em timestamptz not null default now(),
  acao text not null,
  parametros jsonb
);

-- quem pode ler: convidado, ativo e com termo aceito
create or replace function public.eh_pesquisador() returns boolean language sql stable security definer set search_path = public as $$
  select exists (select 1 from public.pesquisadores p where p.user_id = auth.uid() and p.ativo and p.termo_aceito_em is not null)
$$;

alter table public.pesquisadores enable row level security;
alter table public.corpus enable row level security;
alter table public.acessos enable row level security;

drop policy if exists pesq_le_a_propria on public.pesquisadores;
create policy pesq_le_a_propria on public.pesquisadores for select to authenticated using (user_id = auth.uid());
drop policy if exists corpus_so_pesquisador on public.corpus;
create policy corpus_so_pesquisador on public.corpus for select to authenticated using (public.eh_pesquisador());
drop policy if exists acessos_le_o_proprio on public.acessos;
create policy acessos_le_o_proprio on public.acessos for select to authenticated using (user_id = auth.uid());
-- nenhuma política de escrita: só o service role (carga diária) e as funções abaixo escrevem

revoke all on public.corpus, public.pesquisadores, public.acessos from anon;

create or replace function public.aceitar_termo() returns boolean language plpgsql security definer set search_path = public as $$
begin
  update public.pesquisadores set termo_aceito_em = now() where user_id = auth.uid() and ativo and termo_aceito_em is null;
  insert into public.acessos (user_id, acao) select auth.uid(), 'aceitou_termo' where exists (select 1 from public.pesquisadores where user_id = auth.uid());
  return exists (select 1 from public.pesquisadores where user_id = auth.uid() and termo_aceito_em is not null);
end $$;

create or replace function public.minha_situacao() returns jsonb language sql stable security definer set search_path = public as $$
  select jsonb_build_object('convidado', p.user_id is not null, 'ativo', coalesce(p.ativo, false), 'termo_aceito', p.termo_aceito_em is not null, 'papel', p.papel)
  from (select auth.uid() as u) x left join public.pesquisadores p on p.user_id = x.u
$$;

-- registro de cada consulta (quem, quando, o quê); o pesquisador não escreve direto na tabela
create or replace function public._registrar(p_acao text, p_parametros jsonb) returns void language sql security definer set search_path = public as $$
  insert into public.acessos (user_id, acao, parametros) values (auth.uid(), p_acao, p_parametros)
$$;

-- filtro comum às consultas (texto, emoji, casos, redes, fonte, período)
create or replace function public._filtro(p_q text, p_emoji text, p_casos text[], p_redes text[], p_fonte text, p_de date, p_ate date)
returns setof public.corpus language sql stable security invoker set search_path = public as $$
  select c.* from public.corpus c
  where (p_q is null or p_q = '' or c.tsv @@ websearch_to_tsquery('simple', extensions.unaccent(lower(p_q))))
    and (p_emoji is null or p_emoji = '' or c.emojis @> array[p_emoji])
    and (p_casos is null or cardinality(p_casos) = 0 or c.caso = any(p_casos))
    and (p_redes is null or cardinality(p_redes) = 0 or c.rede = any(p_redes))
    and (p_fonte is null or p_fonte = '' or c.fonte = p_fonte)
    and (p_de is null or c.publicado_em >= p_de) and (p_ate is null or c.publicado_em < p_ate + 1)
$$;

create or replace function public.buscar(p_q text default null, p_emoji text default null, p_casos text[] default null, p_redes text[] default null,
  p_fonte text default null, p_de date default null, p_ate date default null, p_lim int default 50, p_pagina int default 0)
returns table (id bigint, caso text, rede text, fonte text, publicado_em timestamptz, autor text, texto text, emojis text[], candidato text,
  ofensivo boolean, odio text, total bigint)
language plpgsql security invoker set search_path = public as $$
#variable_conflict use_column
declare l int := least(greatest(p_lim, 1), 200);
begin
  if not public.eh_pesquisador() then raise exception 'acesso restrito a pesquisadores convidados com termo aceito'; end if;
  perform public._registrar('buscar', jsonb_build_object('q', p_q, 'emoji', p_emoji, 'casos', p_casos, 'redes', p_redes, 'fonte', p_fonte, 'de', p_de, 'ate', p_ate, 'pagina', p_pagina));
  return query select f.id, f.caso, f.rede, f.fonte, f.publicado_em, f.autor, f.texto, f.emojis, f.candidato, f.ofensivo, f.odio, count(*) over ()
    from public._filtro(p_q, p_emoji, p_casos, p_redes, p_fonte, p_de, p_ate) f order by f.publicado_em desc nulls last
    limit l offset greatest(p_pagina, 0) * l;
end $$;

-- frequência (NVivo: Word Frequency) sobre o recorte: palavras e emojis, em quantos textos aparecem
create or replace function public.frequencia(p_q text default null, p_emoji text default null, p_casos text[] default null, p_redes text[] default null,
  p_fonte text default null, p_de date default null, p_ate date default null, p_top int default 80)
returns table (tipo text, termo text, textos bigint)
language plpgsql security invoker set search_path = public as $$
#variable_conflict use_column
begin
  if not public.eh_pesquisador() then raise exception 'acesso restrito a pesquisadores convidados com termo aceito'; end if;
  perform public._registrar('frequencia', jsonb_build_object('q', p_q, 'emoji', p_emoji, 'casos', p_casos, 'redes', p_redes, 'fonte', p_fonte, 'de', p_de, 'ate', p_ate));
  return query
    (select 'emoji'::text, e, count(distinct r.id) from public._filtro(p_q, p_emoji, p_casos, p_redes, p_fonte, p_de, p_ate) r, unnest(r.emojis) e
      group by e order by 3 desc limit p_top)
    union all
    (select 'palavra'::text, w.word, w.ndoc::bigint
      from ts_stat(format('select tsv from public._filtro(%L,%L,%L::text[],%L::text[],%L,%L::date,%L::date)', p_q, p_emoji, p_casos, p_redes, p_fonte, p_de, p_ate)) w
      where length(w.word) >= 3 and w.word !~ '^[0-9]+$' and w.word <> all (array['que','nao','para','com','uma','por','mais','como','mas','dos','das','ele','ela','isso','esse','essa','tem','sao','foi','vai','ser','esta','seu','sua','nos','aos','pra','pro','tudo','muito','quem','quando','sem','sobre','entre','depois','ainda','voce','aqui','the','and','https','http','www','com','todos','vamos','porque'])
      order by w.ndoc desc limit p_top);
end $$;

-- matriz (NVivo: Matrix Coding Query): emojis mais usados no recorte × dimensão (caso, rede, candidato, fonte, mês)
create or replace function public.matriz(p_dimensao text, p_q text default null, p_emoji text default null, p_casos text[] default null, p_redes text[] default null,
  p_fonte text default null, p_de date default null, p_ate date default null, p_top int default 20)
returns table (emoji text, coluna text, textos bigint)
language plpgsql security invoker set search_path = public as $$
#variable_conflict use_column
begin
  if not public.eh_pesquisador() then raise exception 'acesso restrito a pesquisadores convidados com termo aceito'; end if;
  if p_dimensao not in ('caso', 'rede', 'candidato', 'fonte', 'mes') then raise exception 'dimensão inválida'; end if;
  perform public._registrar('matriz', jsonb_build_object('dimensao', p_dimensao, 'q', p_q, 'emoji', p_emoji, 'casos', p_casos, 'redes', p_redes));
  return query
    with u as (select r.id as rid, e as em, case p_dimensao when 'caso' then r.caso when 'rede' then r.rede when 'candidato' then coalesce(r.candidato, '—')
            when 'fonte' then r.fonte else to_char(r.publicado_em, 'YYYY-MM') end as col
          from public._filtro(p_q, p_emoji, p_casos, p_redes, p_fonte, p_de, p_ate) r, unnest(r.emojis) e),
    t as (select u.em from u group by u.em order by count(distinct u.rid) desc limit p_top)
    select u.em, u.col, count(distinct u.rid) from u join t on t.em = u.em group by u.em, u.col;
end $$;

-- resumo do que está carregado (universo do banco), para a página mostrar
create or replace function public.resumo_corpus() returns table (caso text, rede text, fonte text, textos bigint, com_emoji bigint, de timestamptz, ate timestamptz, carregado_em timestamptz)
language sql stable security invoker set search_path = public as $$
  select caso, rede, fonte, count(*), count(*) filter (where cardinality(emojis) > 0), min(publicado_em), max(publicado_em), max(carregado_em)
  from public.corpus where public.eh_pesquisador() group by 1, 2, 3 order by 1, 2, 3
$$;

revoke execute on function public._registrar, public.buscar, public.frequencia, public.matriz, public.resumo_corpus, public.aceitar_termo, public.minha_situacao, public._filtro, public.eh_pesquisador from anon, public;
grant execute on function public._registrar, public.buscar, public.frequencia, public.matriz, public.resumo_corpus, public.aceitar_termo, public.minha_situacao, public._filtro, public.eh_pesquisador to authenticated;
grant select on public.corpus, public.pesquisadores, public.acessos to authenticated;
