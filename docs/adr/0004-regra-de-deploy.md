# ADR 0004 — Regra configurável para identificar deploy

- **Status:** Aceito
- **Data:** 30/10/2026

## Contexto

As métricas DORA dependem de saber **quando houve um deploy em produção**. Cada time marca isso de um jeito: alguns publicam releases, outros criam tags de versão, outros fazem deploy contínuo por um workflow do GitHub Actions a cada merge na `main`. O termo de abertura já apontava "dados de deploy inconsistentes entre repositórios" como risco de probabilidade alta.

## Opções consideradas

1. **Uma regra fixa para todos (só releases)** — simples, mas zera as métricas de quem faz deploy contínuo sem releases.
2. **Detectar automaticamente** (usar releases se houver; senão, tags; senão, workflow) — sem configuração, mas o resultado muda sozinho quando aparece a primeira release, e fica difícil explicar o número.
3. **Uma regra explícita por repositório, com padrão `release`** — exige uma linha de configuração para quem não usa releases, mas deixa claro o que está sendo medido.

## Decisão

Opção 3. A variável `PAINEL_REGRAS_DEPLOY` define a regra de cada repositório (`dono/repo=regra`, separados por `;`). Repositórios não listados usam `release`.

| Regra | Conta como deploy | Momento do deploy | Coleta incremental |
|---|---|---|---|
| `release` | release publicada (sem rascunhos nem pré-releases) | `published_at` | lê todas as releases, porque a API não filtra por data e costumam ser poucas |
| `tag[:padrão]` | tag cujo nome casa com o padrão glob (padrão `*`) | data do commit da tag | só consulta o commit das tags ainda não gravadas (1 requisição por tag nova) |
| `workflow:arquivo[@branch]` | execução do workflow concluída com sucesso na branch (padrão `main`) | fim da execução (`updated_at`) | filtro `created` da API a partir do último deploy, com 1 dia de folga para execuções longas |

Regras adicionais:
- Os deploys ficam em `bruta_deploys` com a regra que os identificou. A chave `(repositorio, regra, identificador)` torna a coleta idempotente.
- **Ao mudar a regra de um repositório**, os deploys da regra anterior são removidos na próxima coleta. Assim as métricas nunca misturam critérios.
- O SHA do commit é guardado para tags e workflows. Releases não têm SHA confiável, porque `target_commitish` pode ser o nome de uma branch.

## Consequências

- ✅ Atende os três estilos de entrega mais comuns no GitHub sem código específico por time.
- ✅ A regra usada aparece no log da coleta e fica gravada junto de cada deploy, então o número é explicável.
- ⚠️ Tags são datadas pelo commit, não pelo momento em que foram criadas. Uma tag criada dias depois do commit antecipa o deploy. Tags anotadas poderiam dar a data exata, ao custo de mais requisições.
- ⚠️ Uma tag movida para outro commit (`git tag -f`) não é atualizada, porque tags já gravadas não são consultadas de novo.
- ⚠️ Deploys fora do GitHub (por exemplo, um pipeline em outra ferramenta) não são vistos. Se for necessário, uma regra nova pode ser adicionada em outro ADR.
