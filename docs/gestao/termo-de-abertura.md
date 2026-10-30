# Termo de Abertura do Projeto

| Campo | Valor |
|---|---|
| **Projeto** | Painel de Métricas de Entrega |
| **Responsável** | Rafael Nunes Tavares |
| **Início** | 29/10/2026 |
| **Previsão de MVP** | 13/12/2026 |
| **Metodologia** | Kanban com ciclos semanais e retrospectiva quinzenal |

## 1. Contexto

Times de software geram muitos dados no GitHub, mas raramente os usam para planejar. Sem indicadores, a conversa sobre prazos e gargalos fica baseada em percepção.

## 2. Objetivo

Entregar um painel que calcule e exiba métricas de fluxo e DORA para um ou mais repositórios do GitHub, com dados atualizados automaticamente.

## 3. Escopo

**Dentro do escopo**
- Coleta de issues, pull requests, releases e execuções de workflow via API do GitHub
- Cálculo de métricas de fluxo, DORA e burndown
- Dashboard web com filtros por repositório e período
- Atualização agendada e documentação de uso

**Fora do escopo (nesta versão)**
- Integração com Jira, Azure DevOps ou GitLab
- Autenticação multiusuário
- Métricas individuais por pessoa (o foco é o time, não o indivíduo)

## 4. Entregas e marcos

| Marco | Entrega | Data alvo |
|---|---|---|
| M1 | Fundação: estrutura, CI e coletor | 08/11/2026 |
| M2 | Métricas de fluxo | 18/11/2026 |
| M3 | Métricas DORA | 28/11/2026 |
| M4 | Dashboard e atualização agendada | 06/12/2026 |
| M5 | Burndown e previsibilidade | 13/12/2026 |

## 5. Partes interessadas

| Parte | Interesse |
|---|---|
| Recrutadores e gestores técnicos | Avaliar competência técnica e visão de gestão |
| Times pequenos e estudantes | Usar o painel nos próprios repositórios |

## 6. Premissas e restrições

- A API do GitHub tem limite de requisições; a coleta precisa ser incremental.
- Projeto conduzido por uma pessoa, em paralelo à graduação.
- Infraestrutura gratuita (GitHub Actions).

## 7. Riscos

| Risco | Prob. | Impacto | Resposta |
|---|---|---|---|
| Limite da API interromper a coleta | Média | Alto | Cache, coleta incremental e backoff |
| Dados de deploy inconsistentes entre repositórios | Alta | Médio | Regras configuráveis para identificar deploy (release, tag ou workflow) |
| Escopo crescer além do prazo | Média | Médio | Backlog priorizado com MoSCoW; itens "Could" ficam para v2 |
| Pouca disponibilidade no fim do semestre | Alta | Médio | Marcos curtos e entregas incrementais |

## 8. Critérios de sucesso

- Dashboard executável localmente, com dados atualizados automaticamente pela coleta agendada e capturas de tela no README
- As 4 métricas DORA e as métricas de fluxo calculadas e testadas
- Cobertura de testes ≥ 80% no módulo de métricas
- Documentação suficiente para outra pessoa rodar o projeto em menos de 10 minutos

## Histórico de revisões

| Data | Mudança | Motivo |
|---|---|---|
| 30/10/2026 | O dashboard deixa de ser publicado: objetivo, marco M4, restrições e critério de sucesso passam a tratar de execução local com dados atualizados automaticamente | Decisão do responsável de não divulgar um link público; o painel é demonstrado por capturas de tela no README ([ADR 0006](../adr/0006-atualizacao-e-publicacao.md)) |
