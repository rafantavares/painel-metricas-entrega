# ADR 0005 — Definições das métricas DORA

- **Status:** Aceito
- **Data:** 30/10/2026

## Contexto

As quatro métricas DORA precisam ser calculadas só com o que o coletor já tem: issues e PRs (ADR 0002) e deploys identificados pela regra de cada repositório (ADR 0004). A issue #7 pede que cada métrica venha acompanhada da classificação de desempenho (elite/alto/médio/baixo). O GitHub não liga um deploy aos PRs que ele levou nem a uma falha em produção, então essas ligações precisam ser inferidas.

## Decisão

As métricas são funções puras em `painel.metricas.dora`. Elas recebem itens e deploys como objetos simples (`Protocol`), sem depender do coletor nem do banco.

| Métrica | Definição | Período filtra por |
|---|---|---|
| **Frequência de deploy** | deploys ÷ dias do período (inclusivo) | data do deploy |
| **Lead time de mudanças** | da **criação do PR** ao **primeiro deploy no momento do merge ou depois**; mediana e p85 | data desse deploy |
| **Taxa de falha de mudanças** | deploys com sinal de falha ÷ deploys do período | data do deploy |
| **Tempo de restauração** | da abertura ao fechamento das issues com label `incidente`; mediana e p85 | data do fechamento |

**Ligação PR → deploy por tempo:** um PR é considerado implantado no primeiro deploy cujo horário é igual ou posterior ao merge. Isso vale para as três regras de deploy sem precisar comparar commits. Em repositórios com várias branches de longa duração, pode atribuir um PR a um deploy que não o continha.

**Sinal de falha:** um PR mesclado cujo título começa com "Revert" (o padrão do botão de revert do GitHub) ou uma issue com label `bug` ou `incidente` (configurável). O sinal é atribuído ao **deploy mais recente antes dele**. Vários sinais entre dois deploys contam como uma falha só. Para o último deploy, a janela fica aberta.

**Início do lead time:** a criação do PR, e não o primeiro commit. Isso segue a aproximação do ADR 0003 e evita uma requisição por PR. Como o primeiro commit costuma vir antes da abertura do PR, o lead time tende a ficar um pouco subestimado.

**Classificação** (faixas do relatório State of DevOps, adaptadas para limites objetivos):

| Desempenho | Frequência | Lead time (mediana) | Taxa de falha | Restauração (mediana) |
|---|---|---|---|---|
| Elite | ≥ 1 por dia | < 1 dia | ≤ 5% | < 1 hora |
| Alto | ≥ 1 por semana | ≤ 1 semana | ≤ 10% | < 1 dia |
| Médio | ≥ 1 por mês | ≤ 1 mês | ≤ 15% | ≤ 1 semana |
| Baixo | menos | mais de 1 mês | > 15% | mais de 1 semana |

Sem dados (nenhum deploy, PR implantado ou incidente), a métrica retorna `None` em vez de uma classificação. Assim, a falta de dados não aparece como "elite".

## Consequências

- ✅ Funciona com qualquer uma das três regras de deploy e com os dados já coletados.
- ✅ As regras de ligação são explícitas e testadas, então o número pode ser explicado no dashboard.
- ⚠️ A ligação por tempo e os sinais por label dependem da disciplina do time (rotular bugs e incidentes). Isso precisa aparecer ao lado das métricas no dashboard (M4).
- ⚠️ Um bug antigo, só descoberto depois de vários deploys, é atribuído ao deploy errado. Uma melhoria futura seria ligar a issue ao PR que a causou.
- ⚠️ Os limites das faixas mudam entre as edições do relatório DORA. Revisar quando houver uma edição nova.
