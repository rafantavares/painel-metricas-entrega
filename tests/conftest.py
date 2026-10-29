from typing import Any

import pytest


def _item_api(
    numero: int,
    *,
    atualizado: str = "2026-10-01T12:00:00Z",
    estado: str = "open",
    pr: bool = False,
    mesclado: str | None = None,
    fechado: str | None = None,
    labels: tuple[str, ...] = (),
    milestone: str | None = None,
) -> dict[str, Any]:
    """Monta um item no formato devolvido pelo endpoint `/repos/{repo}/issues`."""
    dados: dict[str, Any] = {
        "number": numero,
        "title": f"Item {numero}",
        "state": estado,
        "created_at": "2026-10-01T10:00:00Z",
        "updated_at": atualizado,
        "closed_at": fechado,
        "labels": [{"name": nome} for nome in labels],
        "milestone": {"title": milestone} if milestone else None,
    }
    if pr:
        dados["pull_request"] = {"url": "https://api.github.com/x", "merged_at": mesclado}
    return dados


@pytest.fixture
def item_api():
    """Fábrica de itens da API do GitHub para montar cenários de teste."""
    return _item_api
