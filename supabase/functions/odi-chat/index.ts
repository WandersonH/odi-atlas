// ODI Atlas · chat com os dados (Gemini). A chave fica só nos segredos do Supabase (GEMINI_API_KEY ou GEMINI).
// A IA recebe apenas o resumo PÚBLICO do Atlas (data/ia/resumo.json): agregados com fonte e data, sem texto de comentários.
const RESUMO = "https://wandersonh.github.io/odi-atlas/data/ia/resumo.json";
const ORIGENS = ["https://wandersonh.github.io", "http://localhost:8765"];
const MODELOS = [Deno.env.get("GEMINI_MODEL") ?? "gemini-flash-latest", "gemini-2.5-flash"];
let cache: { t: number; txt: string } | null = null;

function cors(origem: string | null) {
  const ok = origem && ORIGENS.some((o) => origem.startsWith(o));
  return {
    "Access-Control-Allow-Origin": ok ? origem! : ORIGENS[0],
    "Access-Control-Allow-Methods": "POST, OPTIONS",
    "Access-Control-Allow-Headers": "content-type, authorization, apikey, x-client-info",
    "Content-Type": "application/json; charset=utf-8",
  };
}

async function resumo(): Promise<string> {
  if (cache && Date.now() - cache.t < 30 * 60 * 1000) return cache.txt;
  const r = await fetch(RESUMO, { headers: { "cache-control": "no-cache" } });
  if (!r.ok) throw new Error("resumo indisponível (HTTP " + r.status + ")");
  cache = { t: Date.now(), txt: await r.text() };
  return cache.txt;
}

const INSTRUCOES = `Você é o assistente de dados do ODI Atlas (Observatório de Desinformação e Intolerância Digital, PPGCOM/UNIP), sobre a eleição presidencial brasileira de 2026.
Regras:
- Responda em português do Brasil, de forma curta e direta.
- Use SOMENTE os dados do JSON fornecido. Se a resposta não estiver nos dados, diga que o Atlas não tem esse dado. Nunca invente números.
- Cite a fonte (campo "fonte") e a data de coleta de cada número usado.
- Ordem: Lula primeiro (candidato à reeleição); isso não indica preferência. Seja equilibrado e não opine sobre em quem votar.
- Lembre que seguidores não são eleitores, interações não são votos e buscas não são intenção de voto, quando for pertinente.
- Não mencione custos de coleta.`;

Deno.serve(async (req: Request) => {
  const origem = req.headers.get("origin");
  const h = cors(origem);
  if (req.method === "OPTIONS") return new Response("ok", { headers: h });
  if (req.method !== "POST") return new Response(JSON.stringify({ erro: "use POST" }), { status: 405, headers: h });
  const chave = Deno.env.get("GEMINI_API_KEY") ?? Deno.env.get("GEMINI");
  if (!chave) return new Response(JSON.stringify({ erro: "chave do Gemini não cadastrada nos segredos do Supabase (GEMINI_API_KEY)" }), { status: 503, headers: h });
  let corpo: { pergunta?: string; historico?: { papel: string; texto: string }[] } = {};
  try { corpo = await req.json(); } catch { /* corpo vazio */ }
  const pergunta = (corpo.pergunta ?? "").toString().slice(0, 800).trim();
  if (!pergunta) return new Response(JSON.stringify({ erro: "pergunta vazia" }), { status: 400, headers: h });
  const hist = (corpo.historico ?? []).slice(-6).map((m) => ({ role: m.papel === "ia" ? "model" : "user", parts: [{ text: String(m.texto).slice(0, 1500) }] }));
  let dados = "";
  try { dados = await resumo(); } catch (e) { return new Response(JSON.stringify({ erro: String(e) }), { status: 502, headers: h }); }
  const payload = {
    systemInstruction: { parts: [{ text: INSTRUCOES + "\n\nDADOS (JSON público do Atlas):\n" + dados }] },
    contents: [...hist, { role: "user", parts: [{ text: pergunta }] }],
    generationConfig: { temperature: 0.2, maxOutputTokens: 900 },
  };
  let ultimoErro = "";
  for (const modelo of MODELOS) {
    const r = await fetch(`https://generativelanguage.googleapis.com/v1beta/models/${modelo}:generateContent?key=${chave}`, {
      method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload),
    });
    if (r.ok) {
      const j = await r.json();
      const texto = j?.candidates?.[0]?.content?.parts?.map((p: { text?: string }) => p.text ?? "").join("") ?? "";
      return new Response(JSON.stringify({ resposta: texto || "Sem resposta.", modelo }), { headers: h });
    }
    ultimoErro = `${modelo}: HTTP ${r.status}`;
    if (r.status !== 404 && r.status !== 400) break;
  }
  return new Response(JSON.stringify({ erro: "o serviço de IA não respondeu (" + ultimoErro + ")" }), { status: 502, headers: h });
});
