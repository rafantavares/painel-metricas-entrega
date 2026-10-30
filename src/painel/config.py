"""Leitura da configuração do projeto a partir de variáveis de ambiente (`.env`)."""

import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv


@dataclass(frozen=True)
class RegraDeploy:
    """Como identificar um deploy em um repositório (ver ADR 0004).

    - `release`: cada release publicada (sem rascunhos nem pré-releases);
    - `tag`: cada tag cujo nome casa com `filtro` (padrão glob, ex.: `v*`);
    - `workflow`: cada execução bem-sucedida do workflow `filtro` (ex.: `deploy.yml`)
      na branch `branch`.
    """

    fonte: str = "release"
    filtro: str = "*"
    branch: str = "main"

    def __str__(self) -> str:
        if self.fonte == "release":
            return "release"
        if self.fonte == "tag":
            return f"tag:{self.filtro}"
        return f"workflow:{self.filtro}@{self.branch}"


REGRA_PADRAO = RegraDeploy()


@dataclass(frozen=True)
class Configuracao:
    """Configuração usada pelo coletor e pelo dashboard."""

    github_token: str | None
    repositorios: tuple[str, ...]
    caminho_banco: Path
    regras_deploy: dict[str, RegraDeploy] = field(default_factory=dict)
    url_banco: str | None = None

    def regra_deploy(self, repositorio: str) -> RegraDeploy:
        """Regra configurada para o repositório, ou a padrão (`release`)."""
        return self.regras_deploy.get(repositorio, REGRA_PADRAO)


def _ler_repositorios(valor: str) -> tuple[str, ...]:
    """Converte uma lista separada por vírgulas em uma tupla de `dono/repo`."""
    repositorios = tuple(item.strip() for item in valor.split(",") if item.strip())
    for repositorio in repositorios:
        dono, _, nome = repositorio.partition("/")
        if not dono or not nome or "/" in nome:
            raise ValueError(f"Repositório inválido: {repositorio!r}. Use o formato dono/repo.")
    return repositorios


def ler_regra_deploy(texto: str) -> RegraDeploy:
    """Interpreta uma regra no formato `release`, `tag[:padrão]` ou `workflow:arquivo[@branch]`."""
    fonte, _, resto = texto.strip().partition(":")
    fonte = fonte.strip()
    resto = resto.strip()
    if fonte == "release" and not resto:
        return RegraDeploy("release")
    if fonte == "tag":
        return RegraDeploy("tag", filtro=resto or "*")
    if fonte == "workflow" and resto:
        arquivo, _, branch = resto.partition("@")
        if arquivo.strip():
            return RegraDeploy("workflow", filtro=arquivo.strip(), branch=branch.strip() or "main")
    raise ValueError(
        f"Regra de deploy inválida: {texto!r}. "
        "Use release, tag[:padrão] ou workflow:arquivo.yml[@branch]."
    )


def _ler_regras_deploy(valor: str) -> dict[str, RegraDeploy]:
    """Converte `dono/a=release; dono/b=tag:v*` em um dicionário por repositório."""
    regras = {}
    for entrada in valor.split(";"):
        if not entrada.strip():
            continue
        repositorio, separador, regra = entrada.partition("=")
        if not separador:
            raise ValueError(f"Regra de deploy sem repositório: {entrada.strip()!r}.")
        (repositorio,) = _ler_repositorios(repositorio)
        regras[repositorio] = ler_regra_deploy(regra)
    return regras


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
        regras_deploy=_ler_regras_deploy(os.getenv("PAINEL_REGRAS_DEPLOY", "")),
        url_banco=os.getenv("PAINEL_BANCO_URL") or None,
    )
