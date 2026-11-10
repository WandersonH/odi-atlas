-- C19.375: economia de espaço (plano gratuito, 500 MB): sem coluna tsv guardada; índice GIN sobre a expressão;
-- trava de tamanho para a carga. Depois: VACUUM FULL public.corpus (fora de transação). 001: 20 MB → 11 MB.
create or replace function odi_interno.tsv_simples(t text) returns tsvector language sql immutable parallel safe set search_path = '' as $$
  select to_tsvector('simple'::regconfig, extensions.unaccent('extensions.unaccent'::regdictionary, lower(coalesce(t, ''))))
$$;
grant execute on function odi_interno.tsv_simples(text) to authenticated;
drop trigger if exists corpus_tsv on public.corpus;
drop function if exists public.corpus_tsv();
drop index if exists public.corpus_tsv;
alter table public.corpus drop column if exists tsv cascade;
create index if not exists corpus_tsv_expr on public.corpus using gin (odi_interno.tsv_simples(texto));

create or replace function public._filtro(p_q text, p_emoji text, p_casos text[], p_redes text[], p_fonte text, p_de date, p_ate date)
returns setof public.corpus language sql stable security invoker set search_path = public as $$
  select c.* from public.corpus c
  where (p_q is null or p_q = '' or odi_interno.tsv_simples(c.texto) @@ websearch_to_tsquery('simple', extensions.unaccent(lower(p_q))))
    and (p_emoji is null or p_emoji = '' or c.emojis @> array[p_emoji])
    and (p_casos is null or cardinality(p_casos) = 0 or c.caso = any(p_casos))
    and (p_redes is null or cardinality(p_redes) = 0 or c.rede = any(p_redes))
    and (p_fonte is null or p_fonte = '' or c.fonte = p_fonte)
    and (p_de is null or c.publicado_em >= p_de) and (p_ate is null or c.publicado_em < p_ate + 1)
$$;

do $$
declare def text;
begin
  def := pg_get_functiondef('public.frequencia(text,text,text[],text[],text,date,date,integer)'::regprocedure);
  def := replace(def, 'select tsv from public._filtro(', 'select odi_interno.tsv_simples(texto) from public._filtro(');
  execute def;
end $$;

create or replace function public.tamanho_banco_mb() returns numeric language sql stable security definer set search_path = public as $$
  select round(pg_database_size(current_database()) / 1048576.0, 1)
$$;
revoke execute on function public.tamanho_banco_mb() from public, anon, authenticated;
grant execute on function public.tamanho_banco_mb() to service_role;
