// ODI Atlas · área do pesquisador (C19.374, 10/11/2026): entrega à página o endereço do projeto e a chave PÚBLICA
// (anon/publishable) lida dos segredos do próprio Supabase, para que nenhuma chave fique no código nem nos commits
// (CLAUDE.md, regra 6). A chave pública só abre o login; os textos são protegidos por RLS (só pesquisador convidado,
// ativo e com termo aceito lê public.corpus).
const ORIGENS = ["https://wandersonh.github.io", "http://localhost:8765"];

Deno.serve((req) => {
  const origem = req.headers.get("origin");
  const ok = origem && ORIGENS.some((o) => origem.startsWith(o));
  const h = {
    "Access-Control-Allow-Origin": ok ? origem! : ORIGENS[0],
    "Access-Control-Allow-Methods": "GET, OPTIONS",
    "Access-Control-Allow-Headers": "content-type",
    "Content-Type": "application/json; charset=utf-8",
    "Cache-Control": "public, max-age=3600",
  };
  if (req.method === "OPTIONS") return new Response(null, { headers: h });
  return new Response(JSON.stringify({ url: Deno.env.get("SUPABASE_URL"), chave: Deno.env.get("SUPABASE_ANON_KEY") }), { headers: h });
});
