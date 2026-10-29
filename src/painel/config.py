"""Leitura da configuração do projeto a partir de variáveis de ambiente (`.env`)."""

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


@dataclass(frozen=True)
class Configuracao:
    """Configuração usada pelo coletor e pelo dashboard."""

    github_token: str | None
    repositorios: tuple[str, ...]
    caminho_banco: Path


def _ler_repositorios(valor: str) -> tuple[str, ...]:
    """Converte uma lista separada por vírgulas em uma tupla de `dono/repo`."""
    repositorios = tuple(item.strip() for item in valor.split(",") if item.strip())
    for repositorio in repositorios:
        dono, _, nome = repositorio.partition("/")
        if not dono or not nome or "/" in nome:
            raise ValueError(f"Repositório inválido: {repositorio!r}. Use o formato dono/repo.")
    return repositorios


def carregar_configuracao(arquivo_env: str | Path | None = ".env") -> Configuracao:
    """Carrega a configuração do ambiente, lendo antes o arquivo `.env` se ele existir.

    Variáveis já definidas no ambiente têm prioridade sobre o arquivo.
    """
    if arquivo_env is not None:
        load_dotenv(arquivo_env, override=False)

    return Configuracao(
        github_token=os.getenv("GITHUB_TOKEN") or None,
        repositorios=_ler_repositorios(os.getenv("PAINEL_REPOSITORIOS", "")),
        caminho_banco=Path(os.getenv("PAINEL_BANCO", "data/painel.duckdb")),
    )
