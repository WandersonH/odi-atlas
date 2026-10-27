# Instruções para qualquer IA ou pessoa que trabalhe neste repositório

1. **Atualize o `CHANGELOG.md` em toda mudança**, no mesmo commit. Nova entrada no topo com: o que mudou, por quê, o que foi **realmente** executado como teste (com ID do run ou comando), o que ficou pendente e onde está a evidência.
2. Não declare como pronto nada que não foi executado com dados reais. Dado ausente é bloqueio (⛔), não sucesso.
3. Não invente números. Todo número no CHANGELOG ou nos docs precisa vir de um arquivo, manifesto ou run identificável.
4. Rode `python -m unittest discover -s tests -v` antes de cada commit.
5. Preserve a identidade visual ODI no HTML. Não substitua pelo estilo de outros projetos.
6. Nunca coloque tokens ou chaves em código, commits ou mensagens.
7. Ordem do projeto: P1 Origem → P2 Ingestão → P3 Correspondência TSE↔IBGE → P4 Front-end → P5 Refatoração → P6 Automação → P7 Entrega.
8. **Nunca apagar ou limpar dados** (arquivos de `data/`, repositório privado, histórico do git), nem reescrever histórico, sem autorização explícita do responsável naquele momento. Dado sensível no lugar errado se move para o privado, nunca se descarta. (Regra do responsável, 20/10/2026.)
9. **Toda amostra aparece com o universo.** Em toda coleta e página: quanto a plataforma informa que existe (universo, com a fonte), quanto foi lido, o percentual e como a amostra foi tirada. Universo que a plataforma não informa é ⛔ desconhecido, nunca estimado. Percentuais de análise valem para a amostra lida. (Regra do responsável, 27/10/2026: "é sempre importante ter o universo e qual o real tamanho da amostra que temos".)
