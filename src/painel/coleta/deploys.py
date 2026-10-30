"""Coleta de deploys conforme a regra configurada para cada repositório (ver ADR 0004)."""

from datetime import timedelta

import duckdb

from painel.coleta.armazenamento import (
    gravar_deploys,
    ler_identificadores_deploy,
    ler_ultimo_deploy,
    remover_deploys_de_outras_regras,
)
from painel.coleta.github import ClienteGitHub
from painel.coleta.normalizacao import (
    Deploy,
    normalizar_execucao_workflow,
    normalizar_release,
    normalizar_tag,
    tag_casa_com_padrao,
)
from painel.config import RegraDeploy

# Execuções criadas antes do último deploy gravado podem ter terminado depois dele.
FOLGA_WORKFLOW = timedelta(days=1)


def _buscar_deploys(
    cliente: ClienteGitHub,
    conexao: duckdb.DuckDBPyConnection,
    repositorio: str,
    regra: RegraDeploy,
) -> list[Deploy]:
    texto = str(regra)
    if regra.fonte == "release":
        # A API não filtra releases por data; elas costumam ser poucas, então lemos todas.
        deploys = (
            normalizar_release(repositorio, texto, r) for r in cliente.listar_releases(repositorio)
        )
        return [deploy for deploy in deploys if deploy is not None]

    if regra.fonte == "tag":
        # Datar uma tag custa uma requisição; só as tags ainda não gravadas são consultadas.
        conhecidas = ler_identificadores_deploy(conexao, repositorio, texto)
        return [
            normalizar_tag(
                repositorio, texto, tag, cliente.obter_commit(repositorio, tag["commit"]["sha"])
            )
            for tag in cliente.listar_tags(repositorio)
            if tag_casa_com_padrao(tag["name"], regra.filtro) and tag["name"] not in conhecidas
        ]

    ultimo = ler_ultimo_deploy(conexao, repositorio, texto)
    desde = ultimo - FOLGA_WORKFLOW if ultimo else None
    execucoes = cliente.listar_execucoes_workflow(repositorio, regra.filtro, regra.branch, desde)
    deploys = (normalizar_execucao_workflow(repositorio, texto, e) for e in execucoes)
    return [deploy for deploy in deploys if deploy is not None]


def coletar_deploys(
    cliente: ClienteGitHub,
    conexao: duckdb.DuckDBPyConnection,
    repositorio: str,
    regra: RegraDeploy,
) -> int:
    """Coleta os deploys do repositório segundo a regra e grava no banco.

    Se a regra mudou desde a última coleta, os deploys da regra anterior são removidos,
    para que as métricas DORA usem um único critério por repositório.
    Retorna quantos deploys vieram da API (novos ou atualizados).
    """
    deploys = _buscar_deploys(cliente, conexao, repositorio, regra)

    conexao.begin()
    try:
        remover_deploys_de_outras_regras(conexao, repositorio, str(regra))
        gravados = gravar_deploys(conexao, deploys)
        conexao.commit()
    except Exception:
        conexao.rollback()
        raise
    return gravados
