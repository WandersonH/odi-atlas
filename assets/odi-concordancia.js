/* ODI Atlas · concordância entre pesquisadores (C19.377, 11/11/2026).
   Alfa de Krippendorff para dado nominal, com qualquer número de pesquisadores e itens incompletos.
   Entrada: lista de itens, cada item = lista dos valores dados pelos pesquisadores (só os preenchidos).
   Itens com menos de 2 valores não entram. Fórmula (Krippendorff, 2004):
     o_ck = soma, nos itens, de (pares c-k no item) / (m_u - 1);  n_c = soma_k o_ck;  n = soma_c n_c
     alfa = 1 - (n - 1) * soma_{c≠k} o_ck / soma_{c≠k} n_c * n_k
   Conferido com o exemplo clássico de 4 observadores e 12 unidades (alfa nominal = 0,743): tests/test_concordancia.py. */
(function (raiz) {
  function alfaNominal(itens) {
    const o = new Map(); // "c\u0000k" -> valor
    const nc = new Map();
    let n = 0, usados = 0, pares = 0, paresIguais = 0;
    for (const vals of itens) {
      const m = vals.length;
      if (m < 2) continue;
      usados++;
      for (let i = 0; i < m; i++) {
        for (let j = 0; j < m; j++) {
          if (i === j) continue;
          const k = vals[i] + '\u0000' + vals[j];
          o.set(k, (o.get(k) || 0) + 1 / (m - 1));
          if (i < j) { pares++; if (vals[i] === vals[j]) paresIguais++; }
        }
      }
    }
    for (const [k, v] of o) { const c = k.split('\u0000')[0]; nc.set(c, (nc.get(c) || 0) + v); n += v; }
    let discObs = 0, discEsp = 0;
    for (const [k, v] of o) { const [c, d] = k.split('\u0000'); if (c !== d) discObs += v; }
    for (const [c, a] of nc) for (const [d, b] of nc) if (c !== d) discEsp += a * b;
    /* uma só categoria usada: não há discordância esperada e o alfa não se define (não é "concordância perfeita") */
    const alfa = usados === 0 || discEsp === 0 ? null : 1 - (n - 1) * discObs / discEsp;
    return { alfa, itens: usados, valores: n, categorias: nc.size, sem_variacao: usados > 0 && nc.size === 1, acordo_pares: pares ? paresIguais / pares : null };
  }
  /* linhas do banco [{dimensao,item,pesquisador,valor}] -> {dimensao: {alfa, itens, pesquisadores, ...}} */
  function porDimensao(linhas) {
    const g = {};
    for (const l of linhas) {
      const d = (g[l.dimensao] = g[l.dimensao] || { itens: new Map(), pesq: new Set() });
      if (!d.itens.has(l.item)) d.itens.set(l.item, []);
      d.itens.get(l.item).push(l.valor);
      d.pesq.add(l.pesquisador);
    }
    const out = {};
    for (const k of Object.keys(g)) out[k] = Object.assign(alfaNominal([...g[k].itens.values()]), { pesquisadores: g[k].pesq.size });
    return out;
  }
  const api = { alfaNominal, porDimensao };
  if (typeof module !== 'undefined' && module.exports) module.exports = api; else raiz.ODIConcordancia = api;
})(typeof window !== 'undefined' ? window : globalThis);
