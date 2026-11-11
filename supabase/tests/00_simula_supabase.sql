-- Simula o mínimo do Supabase (papéis, auth.uid, storage) num Postgres local, para testar as migrações da área do pesquisador.
-- Uso (C19.377): criar um banco vazio; rodar este arquivo; rodar supabase/migrations/2026111*.sql em ordem;
-- rodar `grant usage on schema extensions to authenticated;`; rodar supabase/tests/01_area_validacao.sql e conferir a saída.
do $$ begin
  if not exists (select 1 from pg_roles where rolname='anon') then create role anon; end if;
  if not exists (select 1 from pg_roles where rolname='authenticated') then create role authenticated; end if;
  if not exists (select 1 from pg_roles where rolname='service_role') then create role service_role bypassrls; end if;
end $$;
create schema auth; create table auth.users(id uuid primary key, email text);
create function auth.uid() returns uuid language sql stable as $$ select nullif(current_setting('request.jwt.claim.sub', true),'')::uuid $$;
grant usage on schema auth to authenticated, anon; grant execute on function auth.uid() to authenticated, anon; grant usage on schema public to authenticated, anon, service_role;
create schema storage; create table storage.buckets(id text primary key, name text, public boolean, file_size_limit bigint);
create table storage.objects(id uuid default gen_random_uuid() primary key, bucket_id text, name text); alter table storage.objects enable row level security;
create function storage.foldername(name text) returns text[] language sql immutable as $$ select (string_to_array(name,'/'))[1:array_length(string_to_array(name,'/'),1)-1] $$;
grant usage on schema storage to authenticated; grant select, insert on storage.objects to authenticated;
