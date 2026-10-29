# ADR 0002 — Coleta incremental de issues e pull requests

- **Status:** Aceito
- **Data:** 29/10/2026

## Contexto

O coletor roda de forma agendada e precisa buscar issues e PRs de vários repositórios sem esgotar o limite da API do GitHub (60 requisições/hora sem token e 5.000 com token). Uma segunda execução não pode duplicar registros e precisa captar mudanças em itens antigos, como uma issue fechada ou um PR mesclado.

## Opções consideradas

1. **Recoletar tudo a cada execução** — simples, mas o custo cresce com o histórico e esgota o rate limit em repositórios grandes.
2. **Endpoints `/issues` e `/pulls` separados** — `/pulls` traz mais detalhes, mas não aceita filtro por data de atualização, então seria preciso paginar tudo.
3. **Só o endpoint `/issues` com `since`** — devolve issues e PRs juntos (PRs vêm com a chave `pull_request`, que inclui `merged_at`) e aceita `since` para trazer apenas o que foi atualizado.
4. **API GraphQL** — consultas mais enxutas, mas exige token sempre e torna os mocks dos testes mais complexos.

## Decisão

Opção 3, com estas regras:

- Para cada repositório, a tabela `controle_coleta` guarda o maior `updated_at` já coletado, que vira o `since` da próxima execução.
- Como `since` é inclusivo, o último item volta na resposta seguinte. A tabela `bruta_itens` tem chave primária `(repositorio, numero)` e a gravação é `INSERT OR REPLACE`, então um item repetido apenas é sobrescrito com a versão mais recente.
- A gravação dos itens e o avanço do controle acontecem na mesma transação. Se a execução falhar, o controle não avança e nada se perde.
- Datas são gravadas em UTC.
- Rate limit (403/429): o coletor respeita `Retry-After` ou espera até `X-RateLimit-Reset`. Erros 5xx e falhas de rede usam backoff exponencial. O limite é de 5 tentativas.

## Consequências

- ✅ Depois da carga inicial, cada execução faz poucas requisições: uma página para cada 100 itens alterados.
- ✅ Reexecutar é seguro (idempotente).
- ✅ Um único endpoint e um único formato de resposta simplificam a normalização e os testes.
- ⚠️ O endpoint `/issues` não traz commits nem revisões dos PRs. O lead time de mudanças (M3) vai exigir uma coleta complementar, a ser decidida em novo ADR.
- ⚠️ Itens apagados ou transferidos de repositório continuam na camada bruta. O impacto é baixo para as métricas do time.
