# ADR 0007 — Burndown por milestone e índice de previsibilidade

- **Status:** Aceito
- **Data:** 30/10/2026

## Contexto

O M5 pede um burndown por milestone e um indicador de quanto do planejado foi entregue no prazo. Os milestones do GitHub têm data de criação, prazo (`due_on`) e data de fechamento. A API não informa **quando** um item entrou ou saiu de um milestone; isso só existe nos eventos de cada issue, ao custo de uma requisição por item.

## Opções consideradas

**Escopo do milestone ao longo do tempo**
1. **Ler os eventos `milestoned`/`demilestoned` de cada item** — o escopo seria exato, mas a coleta deixaria de ser incremental e barata (ADR 0002).
2. **Usar os itens que estão no milestone hoje**, entrando no escopo na criação ou no início do milestone, o que vier depois — sem custo extra. Não mostra itens que saíram do milestone, e um item antigo adicionado no meio do caminho parece ter estado lá desde o início.

**Linha ideal**
1. Partir dos itens restantes no fim do primeiro dia.
2. **Partir do escopo comprometido no início** (itens existentes e ainda não fechados no primeiro dia) e chegar a zero no prazo.

## Decisão

- **Escopo** = opção 2: os itens (issues e PRs) que estão no milestone hoje.
- **Restantes no dia d** = itens do escopo criados até d e ainda não fechados ao fim de d. Um item reaberto continua restante, e um PR fechado sem merge sai do restante (mesma regra do WIP, ADR 0003).
- **Linha ideal** = opção 2, porque, com a opção 1, um milestone cujos itens fecham no primeiro dia teria uma linha ideal sem sentido, começando em zero. Itens criados depois do início aparecem como aumento de escopo acima da linha.
- O gráfico vai do início do milestone até o prazo. Se o milestone estiver atrasado, o gráfico continua até hoje ou até o fechamento. Os dias futuros ficam sem valor.
- **Previsibilidade de um milestone** = itens do escopo entregues (issue fechada ou PR mesclado) **até o fim do dia do prazo** ÷ itens do escopo. Milestones sem prazo não entram.
- **Índice de previsibilidade** = soma dos entregues no prazo ÷ soma dos planejados, **só nos milestones com prazo já encerrado**. Antes do prazo, o percentual aparece no painel como "entregue até agora", mas não entra no índice.
- Os milestones são coletados por completo a cada execução (`bruta_milestones`): são poucos e podem ser apagados ou renomeados no GitHub.

## Consequências

- ✅ Sem custo extra de API, e com as mesmas regras de entrega das outras métricas.
- ✅ O aumento de escopo durante o milestone fica visível no gráfico.
- ⚠️ Itens retirados do milestone somem do histórico, e o burndown pode parecer melhor do que foi. Se isso atrapalhar a análise, adotar a opção 1 (eventos) em novo ADR.
- ⚠️ A previsibilidade conta itens, não esforço. Um item grande pesa o mesmo que um pequeno.
