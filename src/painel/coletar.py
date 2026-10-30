"""Ponto de entrada do coletor: `python -m painel.coletar`."""

import logging
from datetime import UTC, datetime

import duckdb

from painel.coleta.armazenamento import (
    conectar,
    gravar_itens,
    ler_ultima_atualizacao,
    registrar_coleta,
)
from painel.coleta.deploys import coletar_deploys
from painel.coleta.github import ClienteGitHub
from painel.coleta.normalizacao import normalizar_item
from painel.config import carregar_configuracao

logger = logging.getLogger(__name__)


def coletar_repositorio(
    cliente: ClienteGitHub, conexao: duckdb.DuckDBPyConnection, repositorio: str
) -> int:
    """Coleta os itens alterados desde a última execução e grava no banco.

    Retorna quantos itens vieram da API (novos ou atualizados).

    O filtro `since` do GitHub é inclusivo, então o item mais recente da coleta anterior
    volta na resposta; a gravação por chave evita a duplicação. O controle só avança
    depois que todos os itens foram gravados, na mesma transação.
    """
    desde = ler_ultima_atualizacao(conexao, repositorio)
    itens = [
        normalizar_item(repositorio, dados) for dados in cliente.listar_issues(repositorio, desde)
    ]

    conexao.begin()
    try:
        gravados = gravar_itens(conexao, itens)
        if itens:
            ultima = max(item.atualizado_em for item in itens)
            agora = datetime.now(UTC).replace(tzinfo=None)
            registrar_coleta(conexao, repositorio, ultima, agora)
        conexao.commit()
    except Exception:
        conexao.rollback()
        raise
    return gravados


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    logging.getLogger("httpx").setLevel(logging.WARNING)
    config = carregar_configuracao()
    if not config.repositorios:
        raise SystemExit("Nenhum repositório configurado. Defina PAINEL_REPOSITORIOS no .env.")
    if not config.github_token:
        logger.warning("GITHUB_TOKEN ausente: a API limita a 60 requisições por hora.")

    conexao = conectar(config.caminho_banco)
    try:
        with ClienteGitHub(config.github_token) as cliente:
            for repositorio in config.repositorios:
                gravados = coletar_repositorio(cliente, conexao, repositorio)
                logger.info("%s: %d itens recebidos e gravados.", repositorio, gravados)
                regra = config.regra_deploy(repositorio)
                deploys = coletar_deploys(cliente, conexao, repositorio, regra)
                logger.info(
                    "%s: %d deploys (%s) recebidos e gravados.", repositorio, deploys, regra
                )
    finally:
        conexao.close()


if __name__ == "__main__":
    main()
