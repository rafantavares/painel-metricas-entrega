"""Conversão das respostas da API do GitHub em registros da camada bruta."""

from dataclasses import dataclass
from datetime import UTC, datetime
from fnmatch import fnmatchcase
from typing import Any


@dataclass(frozen=True)
class Item:
    """Uma issue ou pull request, com as datas em UTC (sem fuso)."""

    repositorio: str
    numero: int
    tipo: str  # "issue" ou "pull_request"
    titulo: str
    estado: str
    criado_em: datetime
    atualizado_em: datetime
    fechado_em: datetime | None
    mesclado_em: datetime | None
    labels: tuple[str, ...]
    milestone: str | None


@dataclass(frozen=True)
class Deploy:
    """Uma entrega em produção, identificada pela regra do repositório (ver ADR 0004)."""

    repositorio: str
    regra: str
    identificador: str  # nome da release ou da tag, ou id da execução do workflow
    sha: str | None
    implantado_em: datetime


def converter_data(valor: str | None) -> datetime | None:
    """Converte uma data ISO 8601 do GitHub (`2026-10-29T21:55:08Z`) para UTC sem fuso."""
    if not valor:
        return None
    return datetime.fromisoformat(valor).astimezone(UTC).replace(tzinfo=None)


def normalizar_item(repositorio: str, dados: dict[str, Any]) -> Item:
    """Extrai os campos usados pelas métricas de um item do endpoint `/issues`."""
    pull_request = dados.get("pull_request")
    milestone = dados.get("milestone")
    return Item(
        repositorio=repositorio,
        numero=dados["number"],
        tipo="pull_request" if pull_request else "issue",
        titulo=dados["title"],
        estado=dados["state"],
        criado_em=converter_data(dados["created_at"]),
        atualizado_em=converter_data(dados["updated_at"]),
        fechado_em=converter_data(dados.get("closed_at")),
        mesclado_em=converter_data(pull_request.get("merged_at")) if pull_request else None,
        labels=tuple(label["name"] for label in dados.get("labels", [])),
        milestone=milestone["title"] if milestone else None,
    )


def normalizar_release(repositorio: str, regra: str, dados: dict[str, Any]) -> Deploy | None:
    """Converte uma release publicada em deploy. Rascunhos e pré-releases são ignorados."""
    if dados.get("draft") or dados.get("prerelease") or not dados.get("published_at"):
        return None
    return Deploy(
        repositorio=repositorio,
        regra=regra,
        identificador=dados["tag_name"],
        sha=None,  # `target_commitish` pode ser um nome de branch, não um SHA
        implantado_em=converter_data(dados["published_at"]),
    )


def tag_casa_com_padrao(nome: str, padrao: str) -> bool:
    """Indica se o nome da tag casa com o padrão glob (diferencia maiúsculas)."""
    return fnmatchcase(nome, padrao)


def normalizar_tag(
    repositorio: str, regra: str, tag: dict[str, Any], commit: dict[str, Any]
) -> Deploy:
    """Converte uma tag em deploy, datada pelo commit para o qual ela aponta."""
    return Deploy(
        repositorio=repositorio,
        regra=regra,
        identificador=tag["name"],
        sha=tag["commit"]["sha"],
        implantado_em=converter_data(commit["commit"]["committer"]["date"]),
    )


def normalizar_execucao_workflow(
    repositorio: str, regra: str, dados: dict[str, Any]
) -> Deploy | None:
    """Converte uma execução de workflow concluída com sucesso em deploy."""
    if dados.get("conclusion") != "success":
        return None
    return Deploy(
        repositorio=repositorio,
        regra=regra,
        identificador=str(dados["id"]),
        sha=dados.get("head_sha"),
        implantado_em=converter_data(dados["updated_at"]),  # fim da execução
    )
