# Guia para sessões do Claude Code

Projeto de portfólio público do Rafael. Qualidade e clareza importam mais que velocidade.

## Como trabalhar
- Pegue uma issue aberta do milestone mais antigo, trabalhe em uma branch `feat/<numero>-<slug>` e abra PR referenciando a issue (`Closes #N`).
- Uma issue por PR. Commits pequenos, mensagens em português no padrão Conventional Commits.
- Atualize o README (seção Roadmap) quando um milestone for concluído.
- Decisões técnicas relevantes viram um novo ADR em `docs/adr/` (siga o formato do 0001).

## Padrões técnicos
- Python 3.12, pacote em `src/painel/`, dashboard em `app/`.
- Gerenciamento com `pyproject.toml`; lint e formatação com Ruff; testes com pytest.
- Métricas em funções puras (`src/painel/metricas/`), sem acesso à rede, sempre com testes.
- Nunca commitar tokens. Configuração via `.env` (documentar em `.env.example`).
- Textos, docstrings e interface em português.

## Antes de abrir PR
```bash
ruff check . && ruff format --check . && pytest
```
