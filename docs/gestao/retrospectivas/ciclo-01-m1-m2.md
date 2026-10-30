# Retrospectiva — Ciclo 1 (29/10 a 30/10)

> Milestones **M1 – Fundação** e **M2 – Métricas de fluxo**. Os números foram calculados com as funções do próprio painel (`painel.metricas`), sobre a coleta de 30/10/2026 01:50 UTC, usando o CI na `main` como regra de deploy. Os horários estão em UTC.
>
> *Rascunho preparado a partir dos dados do painel e do histórico das PRs: revise as percepções e as ações antes de considerá-lo final.*

## Números do ciclo
| Indicador | Valor |
|---|---|
| Itens planejados | 5 issues (M1: 3 · M2: 2) |
| Itens concluídos | 5 de 5, todas antes do prazo (M1: 08/11 · M2: 18/11) |
| Throughput | 11 itens em 2 dias corridos: 5 issues + 6 PRs mesclados (#12 a #17) |
| Cycle time médio | Issues: 1,4 h (mediana 17 min) · PRs: 29 min (mediana 7 min) |
| Deploys (CI na `main`) | 4 para os 6 PRs, com lead time mediano de 7 min |
| Cobertura de testes em `painel.metricas` | 98% (meta do termo de abertura: ≥ 80%) |

**Como ler esses números:** o ciclo foi feito em uma única sessão de trabalho com um agente de código, a partir de issues criadas em lote. Por isso, o cycle time medido da criação (ADR 0003) ficou em minutos. Ele não serve de referência para os próximos ciclos. O outlier dos PRs é o #15 (2 h 26 min), que esperou uma decisão de merge, não trabalho.

## O que funcionou
- **Uma issue por PR, com PRs pequenas e empilhadas.** As 6 PRs passaram no CI na primeira execução e foram mescladas sem conflitos.
- **Decisões registradas junto com o código.** Os ADRs 0002 e 0003 fecharam os casos de borda (item reaberto, PR fechado sem merge, `since` inclusivo) antes de eles virarem bugs.
- **Testes com a API simulada mais uma execução contra a API real.** A execução real confirmou que a segunda coleta não duplica registros e mostrou o efeito do `since` inclusivo.
- **CI desde o M1.** A partir da #13, toda PR rodou lint, formatação e testes automaticamente.

## O que atrapalhou
- **PRs empilhadas exigem trocar a base à mão.** Como as branches não são apagadas no merge, o GitHub não troca a base da PR seguinte sozinho, e havia o risco de mesclar na branch errada.
- **Branches mescladas se acumulam.** O repositório não apaga a branch depois do merge, e a sessão de automação não tem permissão para apagá-las.
- **O cycle time medido da criação não reflete o trabalho real** quando as issues são criadas em lote, muito antes de começarem.
- **O `concurrency` do CI cancela execuções na `main`** quando os merges são seguidos. Com o CI como regra de deploy, isso subconta os deploys: 4 deploys para 6 PRs.

## O que vamos mudar no próximo ciclo
| Ação | Responsável | Prazo |
|---|---|---|
| Ativar *Automatically delete head branches* (Settings → General) e apagar as branches já mescladas | Rafael | 06/11/2026 |
| Cancelar execuções antigas do CI só em PRs, não na `main` (`cancel-in-progress: ${{ github.event_name == 'pull_request' }}`) | Rafael | 06/11/2026 |
| Concluir a publicação do painel (coleta manual inicial + app no Streamlit Community Cloud) para fechar o M4 | Rafael | 06/12/2026 |
| Avaliar registrar o início real do trabalho (status no GitHub Projects) para medir o cycle time sem a aproximação da criação | Rafael | Próxima retrospectiva |

## Riscos atualizados
- **Limite da API interromper a coleta** — *baixou*. A coleta incremental sem token coube com folga no limite de 60 requisições/hora para um repositório pequeno. Com o token do workflow, o limite sobe.
- **Dados de deploy inconsistentes** — *mitigado* pela regra configurável (ADR 0004). *Novo ponto:* o cancelamento de execuções do CI afeta a regra `workflow`, como mostrado acima.
- **Escopo crescer além do prazo** — *baixou*. M1 e M2 terminaram 10 e 19 dias antes dos prazos.
- **Novo: publicação depende de passos manuais** (Streamlit Community Cloud e a primeira coleta). Até eles serem feitos, o link público do README não funciona.
- **Novo: poucos dados.** Com 2 dias de histórico, as médias e classificações (DORA "elite") são frágeis. Reavaliar com algumas semanas de coleta agendada.
