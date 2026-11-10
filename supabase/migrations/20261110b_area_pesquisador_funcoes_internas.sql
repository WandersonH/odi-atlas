-- C19.374: funções auxiliares fora do schema exposto pela API (o pesquisador não as chama direto).
-- Aplicada depois do aviso do linter do Supabase (security definer executável por usuário logado).
create schema if not exists odi_interno;
revoke all on schema odi_interno from public, anon;
grant usage on schema odi_interno to authenticated;
alter function public._registrar(text, jsonb) set schema odi_interno;
alter function public.eh_pesquisador() set schema odi_interno;
alter function odi_interno._registrar(text, jsonb) set search_path = public;
create or replace function odi_interno.eh_pesquisador() returns boolean language sql stable security definer set search_path = public as $$
  select exists (select 1 from public.pesquisadores p where p.user_id = auth.uid() and p.ativo and p.termo_aceito_em is not null)
$$;
drop policy if exists corpus_so_pesquisador on public.corpus;
create policy corpus_so_pesquisador on public.corpus for select to authenticated using (odi_interno.eh_pesquisador());
do $$
declare f text; def text;
begin
  foreach f in array array['public.buscar(text,text,text[],text[],text,date,date,integer,integer)','public.frequencia(text,text,text[],text[],text,date,date,integer)',
                          'public.matriz(text,text,text,text[],text[],text,date,date,integer)','public.resumo_corpus()'] loop
    def := pg_get_functiondef(f::regprocedure);
    def := replace(replace(def, 'public.eh_pesquisador()', 'odi_interno.eh_pesquisador()'), 'public._registrar(', 'odi_interno._registrar(');
    execute def;
  end loop;
end $$;
revoke execute on function odi_interno._registrar(text, jsonb), odi_interno.eh_pesquisador() from public, anon;
grant execute on function odi_interno._registrar(text, jsonb), odi_interno.eh_pesquisador() to authenticated;
