# ADR 0006 — Atualização agendada e publicação do dashboard

- **Status:** Aceito
- **Data:** 30/10/2026

## Contexto

O termo de abertura pede um dashboard **público** e **atualizado automaticamente**, com infraestrutura gratuita. O coletor (ADR 0002) grava tudo em um arquivo DuckDB (ADR 0001). Falta decidir onde esse arquivo fica entre uma coleta e outra e como o dashboard publicado chega até ele. O Streamlit Community Cloud não roda tarefas agendadas e não garante disco persistente.

## Opções consideradas

**Onde guardar o banco**
1. **Commit do arquivo na `main`** — simples, mas cada coleta gera um commit binário, o histórico cresce sem limite e o CI dispara à toa.
2. **Asset de uma release** — fica fora do histórico, mas exige apagar e recriar o asset a cada coleta, e poluiria a lista de releases. Isso conflita com a regra de deploy por release (ADR 0004).
3. **Branch órfã `dados` com push forçado** — guarda só a versão mais recente, sem acumular histórico. Usa só o `GITHUB_TOKEN` do workflow e fica acessível por uma URL estável (`raw.githubusercontent.com/.../dados/painel.duckdb`).
4. **Armazenamento externo** (S3, MotherDuck) — robusto, mas adiciona contas, segredos e possivelmente custo.

**Quem roda a coleta**
1. **O próprio dashboard, ao abrir** — deixaria a primeira visita lenta e gastaria cota da API a cada reinício do app.
2. **Workflow agendado no GitHub Actions** — gratuito para repositórios públicos, com logs, execução manual e o token já disponível.

## Decisão

- O workflow **`coleta.yml`** roda **a cada 6 horas** (e sob demanda, por `workflow_dispatch`). Ele recupera o banco da branch `dados`, roda o coletor (que é incremental) e publica o arquivo de volta na branch `dados` com push forçado. A branch tem sempre um único commit.
- O **dashboard publicado** recebe `PAINEL_BANCO_URL` (como segredo do Streamlit Community Cloud). Ele baixa o banco para o disco local e só baixa de novo quando a cópia passa de **1 hora**. O download é atômico. Se falhar com uma cópia local já existente, o painel continua com a cópia antiga.
- Os repositórios e as regras de deploy da coleta agendada são **variáveis do repositório** (`PAINEL_REPOSITORIOS`, `PAINEL_REGRAS_DEPLOY`). Por padrão, a coleta usa este próprio repositório, com o CI na `main` como regra de deploy.
- O app é publicado no **Streamlit Community Cloud** a partir da `main`, com `app/dashboard.py` como ponto de entrada. As dependências vêm do `pyproject.toml`, via `requirements.txt`.

## Consequências

- ✅ Custo zero e nenhuma conta além do GitHub e do Streamlit Community Cloud.
- ✅ O histórico da `main` fica limpo, e o CI não roda a cada coleta.
- ✅ O dashboard abre rápido, porque não consulta a API do GitHub.
- ⚠️ Os dados podem ter até cerca de 7 horas de atraso (6 h entre coletas + 1 h de cache). Para um painel de tendências semanais, isso é aceitável.
- ⚠️ Workflows agendados em repositórios sem atividade por 60 dias são desativados pelo GitHub. É preciso reativá-los manualmente na aba Actions.
- ⚠️ O link `raw.githubusercontent.com` só funciona em repositório público. Se o repositório virar privado, será preciso trocar a forma de download (por exemplo, a API com token).
