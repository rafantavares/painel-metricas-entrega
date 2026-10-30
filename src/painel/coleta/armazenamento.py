"""Gravação dos itens coletados na camada bruta do DuckDB."""

from collections.abc import Iterable
from datetime import datetime
from pathlib import Path

import duckdb

from painel.coleta.normalizacao import Deploy, Item

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

CREATE TABLE IF NOT EXISTS bruta_deploys (
    repositorio    VARCHAR   NOT NULL,
    regra          VARCHAR   NOT NULL,
    identificador  VARCHAR   NOT NULL,
    sha            VARCHAR,
    implantado_em  TIMESTAMP NOT NULL,
    PRIMARY KEY (repositorio, regra, identificador)
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


def gravar_deploys(conexao: duckdb.DuckDBPyConnection, deploys: Iterable[Deploy]) -> int:
    """Insere ou atualiza deploys pela chave (repositório, regra, identificador)."""
    linhas = [(d.repositorio, d.regra, d.identificador, d.sha, d.implantado_em) for d in deploys]
    if linhas:
        conexao.executemany("INSERT OR REPLACE INTO bruta_deploys VALUES (?, ?, ?, ?, ?)", linhas)
    return len(linhas)


def remover_deploys_de_outras_regras(
    conexao: duckdb.DuckDBPyConnection, repositorio: str, regra: str
) -> int:
    """Apaga deploys do repositório identificados por uma regra diferente da atual."""
    removidos = conexao.execute(
        "DELETE FROM bruta_deploys WHERE repositorio = ? AND regra <> ? RETURNING identificador",
        [repositorio, regra],
    ).fetchall()
    return len(removidos)


def ler_identificadores_deploy(
    conexao: duckdb.DuckDBPyConnection, repositorio: str, regra: str
) -> set[str]:
    """Identificadores (tag, release ou execução) já gravados para o repositório e regra."""
    linhas = conexao.execute(
        "SELECT identificador FROM bruta_deploys WHERE repositorio = ? AND regra = ?",
        [repositorio, regra],
    ).fetchall()
    return {linha[0] for linha in linhas}


def ler_ultimo_deploy(
    conexao: duckdb.DuckDBPyConnection, repositorio: str, regra: str
) -> datetime | None:
    """Data do deploy mais recente já gravado, ou `None` se ainda não há nenhum."""
    return conexao.execute(
        "SELECT max(implantado_em) FROM bruta_deploys WHERE repositorio = ? AND regra = ?",
        [repositorio, regra],
    ).fetchone()[0]


def ler_itens(
    conexao: duckdb.DuckDBPyConnection, repositorios: Iterable[str] | None = None
) -> list[Item]:
    """Itens da camada bruta, opcionalmente só dos `repositorios` informados."""
    consulta = "SELECT * FROM bruta_itens"
    parametros: list = []
    if repositorios is not None:
        consulta += " WHERE list_contains(?, repositorio)"
        parametros.append(list(repositorios))
    linhas = conexao.execute(consulta + " ORDER BY repositorio, numero", parametros).fetchall()
    return [Item(*linha[:9], labels=tuple(linha[9]), milestone=linha[10]) for linha in linhas]


def ler_deploys(
    conexao: duckdb.DuckDBPyConnection, repositorios: Iterable[str] | None = None
) -> list[Deploy]:
    """Deploys da camada bruta, opcionalmente só dos `repositorios` informados."""
    consulta = "SELECT * FROM bruta_deploys"
    parametros: list = []
    if repositorios is not None:
        consulta += " WHERE list_contains(?, repositorio)"
        parametros.append(list(repositorios))
    linhas = conexao.execute(consulta + " ORDER BY repositorio, implantado_em", parametros)
    return [Deploy(*linha) for linha in linhas.fetchall()]


def listar_repositorios(conexao: duckdb.DuckDBPyConnection) -> list[str]:
    """Repositórios que já têm itens coletados, em ordem alfabética."""
    linhas = conexao.execute("SELECT DISTINCT repositorio FROM bruta_itens ORDER BY 1").fetchall()
    return [linha[0] for linha in linhas]
