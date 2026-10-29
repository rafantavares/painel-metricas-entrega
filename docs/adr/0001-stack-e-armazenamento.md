# ADR 0001 — Stack e armazenamento

- **Status:** Aceito
- **Data:** 29/10/2026

## Contexto

O projeto precisa coletar dados da API do GitHub, guardar histórico, calcular métricas agregadas e exibir um dashboard, com infraestrutura gratuita e mantido por uma pessoa.

## Opções consideradas

1. **PostgreSQL + FastAPI + frontend React** — robusto, mas exige hospedar banco e duas aplicações.
2. **DuckDB + Streamlit** — banco em arquivo, ótimo para consultas analíticas, dashboard em Python puro.
3. **Planilha/Google Sheets + Looker Studio** — rápido, mas pouco demonstrável como engenharia e difícil de testar.

## Decisão

Opção 2: **DuckDB** como armazenamento analítico e **Streamlit** para o dashboard.

## Consequências

- ✅ Sem servidor de banco; o arquivo pode ser gerado no GitHub Actions.
- ✅ SQL analítico rápido para janelas de tempo e percentis.
- ✅ Uma única linguagem (Python) em todo o projeto.
- ⚠️ Não suporta escrita concorrente; aceitável porque só o coletor escreve.
- ⚠️ Streamlit limita personalização visual; se virar problema, reavaliar em novo ADR.
