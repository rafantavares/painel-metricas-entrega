"""Conversão das respostas da API do GitHub em registros da camada bruta."""

from dataclasses import dataclass
from datetime import UTC, datetime
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
