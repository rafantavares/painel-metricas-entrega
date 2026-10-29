# 📊 Painel de Métricas de Entrega

> Dashboard que transforma dados do GitHub em indicadores de entrega — lead time, throughput, burndown e métricas DORA — para times que querem decidir com dados, não com achismo.

[![CI](https://github.com/rafantavares/painel-metricas-entrega/actions/workflows/ci.yml/badge.svg)](https://github.com/rafantavares/painel-metricas-entrega/actions/workflows/ci.yml) ![status](https://img.shields.io/badge/status-em%20desenvolvimento-yellow) ![python](https://img.shields.io/badge/python-3.12-blue) ![licença](https://img.shields.io/badge/licen%C3%A7a-MIT-green)

## Por que este projeto existe

Gerentes de projeto e tech leads costumam responder perguntas como *"estamos entregando mais rápido?"* ou *"o que está travando o time?"* com base em percepção. Os dados para responder já existem no GitHub (issues, PRs, releases, workflows), mas ficam espalhados.

Este painel coleta esses dados, calcula os indicadores e mostra tendências em um só lugar.

**Este repositório também é um estudo de caso de gestão:** o próprio projeto é conduzido com termo de abertura, roadmap, board no GitHub Projects, milestones, registros de decisão (ADRs) e retrospectivas — tudo versionado em [`docs/gestao`](docs/gestao).

## Métricas

| Grupo | Indicador | Pergunta que responde |
|---|---|---|
| **DORA** | Frequência de deploy | Com que frequência entregamos em produção? |
| | Lead time de mudanças | Quanto tempo do primeiro commit ao merge/deploy? |
| | Taxa de falha de mudanças | Quantas entregas geram correção ou revert? |
| | Tempo de restauração (MTTR) | Quanto tempo levamos para resolver incidentes? |
| **Fluxo** | Throughput | Quantos itens concluímos por semana? |
| | Cycle time | Quanto tempo um item leva de "em andamento" a "pronto"? |
| | WIP e itens envelhecidos | O que está parado há tempo demais? |
| **Planejamento** | Burndown por milestone | Vamos cumprir o prazo da entrega? |
| | Previsibilidade | Quanto do planejado foi realmente entregue? |

## Arquitetura

```
GitHub API (REST/GraphQL)
        │
        ▼
  coletor (Python) ──► DuckDB (camadas bruta → tratada → métricas)
                                   │
                                   ▼
                       dashboard (Streamlit) + exportação CSV
```

- **Coleta incremental** com controle de rate limit e cache.
- **Cálculo das métricas** isolado em funções puras, com testes unitários.
- **Atualização agendada** via GitHub Actions.

## Stack

Python 3.12 · httpx · DuckDB · pandas · Streamlit · Plotly · pytest · Ruff · GitHub Actions

## Roadmap

| Milestone | Entrega | Status |
|---|---|---|
| **M1 – Fundação** | Estrutura do projeto, CI, coletor de issues e PRs | ⏳ |
| **M2 – Métricas de fluxo** | Throughput, cycle time, WIP, aging | ⏳ |
| **M3 – DORA** | As quatro métricas DORA a partir de releases/workflows | ⏳ |
| **M4 – Dashboard** | Painel Streamlit com filtros por repo e período, deploy público | ⏳ |
| **M5 – Planejamento** | Burndown por milestone, previsibilidade, relatório semanal | ⏳ |

O detalhamento está nas [issues](../../issues) e no [board do projeto](../../projects).

## Como rodar

Pré-requisito: Python 3.12 ou superior.

```bash
git clone https://github.com/rafantavares/painel-metricas-entrega
cd painel-metricas-entrega
python -m venv .venv && source .venv/bin/activate   # no Windows: .venv\Scripts\activate
pip install -e ".[dev]"
cp .env.example .env   # informe GITHUB_TOKEN e os repositórios a analisar
```

As variáveis aceitas estão documentadas em [`.env.example`](.env.example).

### Coletar os dados

```bash
python -m painel.coletar
```

O coletor lê issues e pull requests de cada repositório em `PAINEL_REPOSITORIOS` e grava no arquivo DuckDB indicado em `PAINEL_BANCO` (padrão `data/painel.duckdb`):

- `bruta_itens`: uma linha por issue/PR, com datas de criação, atualização, fechamento e merge, labels e milestone;
- `controle_coleta`: até onde cada repositório já foi coletado.

A coleta é incremental: a partir da segunda execução, só busca o que mudou desde a anterior. Quando a API devolve rate limit, o coletor espera e tenta de novo. Os detalhes estão no [ADR 0002](docs/adr/0002-coleta-incremental.md).

### Verificações de qualidade

```bash
ruff check .           # lint
ruff format --check .  # formatação
pytest                 # testes
```

Os mesmos comandos rodam no [CI](.github/workflows/ci.yml) a cada push na `main` e em todo pull request.

> O dashboard (`streamlit run app/painel.py`) chega no milestone M4.

## Gestão do projeto

- [Termo de abertura](docs/gestao/termo-de-abertura.md) — objetivo, escopo, riscos e critérios de sucesso
- [Decisões de arquitetura (ADRs)](docs/adr)
- [Retrospectivas](docs/gestao/retrospectivas)

## Autor

**Rafael Nunes Tavares** — estudante de Engenharia de Software (ULBRA Palmas)
[GitHub](https://github.com/rafantavares)

## Licença

[MIT](LICENSE)
