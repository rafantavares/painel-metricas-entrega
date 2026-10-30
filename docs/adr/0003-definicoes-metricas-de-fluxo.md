# ADR 0003 — Definições das métricas de fluxo

- **Status:** Aceito
- **Data:** 30/10/2026

## Contexto

Throughput, cycle time, WIP e aging dependem de duas datas por item: quando o trabalho **começou** e quando foi **entregue**. O GitHub não registra quando um item entrou em "em andamento". Esse dado só existiria no histórico do GitHub Projects, que o coletor (ADR 0002) não lê. Também é preciso decidir o que conta como entrega, porque nem todo item fechado foi entregue.

## Opções consideradas

**Início do trabalho**
1. **Criação do item** — disponível para todos os itens, sem coleta extra. Em issues, inclui o tempo parado no backlog.
2. **Primeiro commit ou PR vinculado** — mais fiel ao trabalho real, mas exige coletar commits e o vínculo entre issue e PR.
3. **Mudança de status no GitHub Projects** — o mais correto, mas depende de o time usar o board com disciplina e exige a API GraphQL.

**Entrega**
1. Qualquer item fechado.
2. **Issue fechada ou PR mesclado** — um PR fechado sem merge não entregou nada.

## Decisão

- **Início = criação do item** (opção 1), como aproximação documentada. Em PRs, a criação fica muito perto do início do trabalho. Em issues, o número se aproxima de um *lead time*. O dashboard deve deixar isso claro, e o filtro `tipo` permite olhar só os PRs.
- **Entrega = issue fechada ou PR mesclado.** O item precisa estar com estado `closed`: um item reaberto não conta, mesmo que tenha uma data de fechamento antiga.
- **Cycle time** = conclusão − criação, em dias, resumido por **mediana** e **percentil 85**. O percentil usa interpolação linear, igual ao padrão do NumPy e do pandas, para os números baterem com o dashboard.
- **Throughput** = itens concluídos por semana ISO (de segunda a domingo, em UTC). Semanas sem entrega aparecem com zero, para o gráfico não esconder paradas.
- As métricas são funções puras em `painel.metricas.fluxo`. Elas recebem qualquer objeto com os campos `tipo`, `estado`, `criado_em`, `fechado_em` e `mesclado_em`, então não dependem do coletor nem do DuckDB.

## Consequências

- ✅ Funciona com os dados já coletados, sem chamadas extras à API.
- ✅ Regras simples e fáceis de testar, com os casos de borda cobertos.
- ⚠️ O cycle time de issues fica inflado pelo tempo de backlog. Se isso atrapalhar as decisões, adotar a opção 2 ou 3 em um novo ADR.
- ⚠️ Issues fechadas como "não planejado" contam como entrega, porque o coletor não guarda o `state_reason`. Dá para corrigir depois coletando esse campo.
