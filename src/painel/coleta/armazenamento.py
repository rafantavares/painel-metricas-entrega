"""Gravação dos itens coletados na camada bruta do DuckDB."""

from collections.abc import Iterable
from datetime import datetime
from pathlib import Path

import duckdb

from painel.coleta.normalizacao import Item

ESQUEMA = """
CREATE TABLE IF NOT EXISTS bruta_itens (
    repositorio   VARCHAR   NOT NULL,
    numero        INTEGER   NOT NULL,
    tipo          VARCHAR   NOT NULL,
    titulo        VARCHAR   NOT NULL,
    estado        VARCHAR   NOT NULL,
    criado_em     TIMESTAMP NOT NULL,
    atualizado_em TIMESTAMP NOT NULL,
    fechado_em    TIMESTAMP,
    mesclado_em   TIMESTAMP,
    labels        VARCHAR[] NOT NULL,
    milestone     VARCHAR,
    PRIMARY KEY (repositorio, numero)
);

CREATE TABLE IF NOT EXISTS controle_coleta (
    repositorio         VARCHAR PRIMARY KEY,
    ultima_atualizacao  TIMESTAMP NOT NULL,
    executado_em        TIMESTAMP NOT NULL
);
"""


def conectar(caminho: str | Path) -> duckdb.DuckDBPyConnection:
    """Abre (ou cria) o banco e garante que as tabelas existem."""
    if str(caminho) != ":memory:":
        Path(caminho).parent.mkdir(parents=True, exist_ok=True)
    conexao = duckdb.connect(str(caminho))
    conexao.execute(ESQUEMA)
    return conexao


def gravar_itens(conexao: duckdb.DuckDBPyConnection, itens: Iterable[Item]) -> int:
    """Insere ou atualiza itens pela chave (repositório, número). Retorna quantos foram gravados."""
    linhas = [
        (
            item.repositorio,
            item.numero,
            item.tipo,
            item.titulo,
            item.estado,
            item.criado_em,
            item.atualizado_em,
            item.fechado_em,
            item.mesclado_em,
            list(item.labels),
            item.milestone,
        )
        for item in itens
    ]
    if linhas:
        conexao.executemany(
            "INSERT OR REPLACE INTO bruta_itens VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", linhas
        )
    return len(linhas)


def ler_ultima_atualizacao(conexao: duckdb.DuckDBPyConnection, repositorio: str) -> datetime | None:
    """Maior `updated_at` já coletado do repositório, ou `None` na primeira execução."""
    linha = conexao.execute(
        "SELECT ultima_atualizacao FROM controle_coleta WHERE repositorio = ?", [repositorio]
    ).fetchone()
    return linha[0] if linha else None


def registrar_coleta(
    conexao: duckdb.DuckDBPyConnection,
    repositorio: str,
    ultima_atualizacao: datetime,
    executado_em: datetime,
) -> None:
    """Salva o ponto de partida da próxima coleta incremental do repositório."""
    conexao.execute(
        "INSERT OR REPLACE INTO controle_coleta VALUES (?, ?, ?)",
        [repositorio, ultima_atualizacao, executado_em],
    )
