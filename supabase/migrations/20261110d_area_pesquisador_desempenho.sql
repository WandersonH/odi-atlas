-- C19.375: desempenho no plano gratuito (limite de 8 s por consulta do usuário logado).
-- 1) frequência de palavras preparada por caso × rede × tipo (corpus inteiro ao vivo: 19 s → tabela de 64.990 linhas, 7,7 MB);
-- 2) _filtro monta o SQL só com os filtros usados (busca "fraude" no corpus inteiro: 17,5 s → 0,57 s).
create table if not exists odi_interno.freq_palavras (caso text, rede text, fonte text, palavra text, textos int, primary key (caso, rede, fonte, palavra));
revoke all on odi_interno.freq_palavras from public, anon;
grant select on odi_interno.freq_palavras to authenticated;

create or replace function public.atualizar_frequencias() returns int language plpgsql security definer set search_path = public set statement_timeout = '600s' as $$
declare n int;
begin
  truncate odi_interno.freq_palavras;
  insert into odi_interno.freq_palavras
  select caso, rede, fonte, w, c from (
    select caso, rede, fonte, w, count(*) c, row_number() over (partition by caso, rede, fonte order by count(*) desc) o
    from public.corpus, unnest(tsvector_to_array(odi_interno.tsv_simples(texto))) w
    where length(w) >= 3 and w !~ '^[0-9]+$'
    group by caso, rede, fonte, w) x
  where o <= 400;
  get diagnostics n = row_count;
  return n;
end $$;
revoke execute on function public.atualizar_frequencias() from public, anon, authenticated;
grant execute on function public.atualizar_frequencias() to service_role;

create or replace function public.frequencia(p_q text default null, p_emoji text default null, p_casos text[] default null, p_redes text[] default null,
  p_fonte text default null, p_de date default null, p_ate date default null, p_top int default 80)
returns table (tipo text, termo text, textos bigint)
language plpgsql security invoker set search_path = public as $$
#variable_conflict use_column
declare sw text[] := array['que','nao','para','com','uma','por','mais','como','mas','dos','das','ele','ela','isso','esse','essa','tem','sao','foi','vai','ser','esta','seu','sua','nos','aos','pra','pro','tudo','muito','quem','quando','sem','sobre','entre','depois','ainda','voce','aqui','the','and','https','http','www','todos','vamos','porque','meu','minha','ter','nem','tao','sim','bem','vem','esse','este','isto','pelo','pela','num','numa','ate','era','sei','faz','fazer','vou','vcs','ja'];
begin
  if not odi_interno.eh_pesquisador() then raise exception 'acesso restrito a pesquisadores convidados com termo aceito'; end if;
  perform odi_interno._registrar('frequencia', jsonb_build_object('q', p_q, 'emoji', p_emoji, 'casos', p_casos, 'redes', p_redes, 'fonte', p_fonte, 'de', p_de, 'ate', p_ate));
  return query
    (select 'emoji'::text, e, count(distinct r.id) from public._filtro(p_q, p_emoji, p_casos, p_redes, p_fonte, p_de, p_ate) r, unnest(r.emojis) e
      group by e order by 3 desc limit p_top);
  if coalesce(p_q, '') = '' and coalesce(p_emoji, '') = '' and p_de is null and p_ate is null then
    return query select 'palavra'::text, f.palavra, sum(f.textos)::bigint from odi_interno.freq_palavras f
      where (p_casos is null or cardinality(p_casos) = 0 or f.caso = any(p_casos)) and (p_redes is null or cardinality(p_redes) = 0 or f.rede = any(p_redes))
        and (p_fonte is null or p_fonte = '' or f.fonte = p_fonte) and f.palavra <> all (sw)
      group by f.palavra order by 3 desc limit p_top;
  else
    return query select 'palavra'::text, w, count(*)::bigint from public._filtro(p_q, p_emoji, p_casos, p_redes, p_fonte, p_de, p_ate) r,
        unnest(tsvector_to_array(odi_interno.tsv_simples(r.texto))) w
      where length(w) >= 3 and w !~ '^[0-9]+$' and w <> all (sw) group by w order by 3 desc limit p_top;
  end if;
end $$;

create or replace function public._filtro(p_q text, p_emoji text, p_casos text[], p_redes text[], p_fonte text, p_de date, p_ate date)
returns setof public.corpus language plpgsql stable security invoker set search_path = public as $$
declare w text[] := array['true'];
begin
  if coalesce(p_q, '') <> '' then w := array_append(w, 'odi_interno.tsv_simples(c.texto) @@ websearch_to_tsquery(''simple'', extensions.unaccent(lower($1)))'); end if;
  if coalesce(p_emoji, '') <> '' then w := array_append(w, 'c.emojis @> array[$2]'); end if;
  if p_casos is not null and cardinality(p_casos) > 0 then w := array_append(w, 'c.caso = any($3)'); end if;
  if p_redes is not null and cardinality(p_redes) > 0 then w := array_append(w, 'c.rede = any($4)'); end if;
  if coalesce(p_fonte, '') <> '' then w := array_append(w, 'c.fonte = $5'); end if;
  if p_de is not null then w := array_append(w, 'c.publicado_em >= $6'); end if;
  if p_ate is not null then w := array_append(w, 'c.publicado_em < $7 + 1'); end if;
  return query execute 'select c.* from public.corpus c where ' || array_to_string(w, ' and ')
    using p_q, p_emoji, p_casos, p_redes, p_fonte, p_de, p_ate;
end $$;
