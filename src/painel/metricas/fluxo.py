"""Métricas de fluxo: throughput semanal e cycle time.

Regras (ver ADR 0003):
- Um item está **concluído** quando está fechado e, se for pull request, foi mesclado.
  PRs fechados sem merge e itens reabertos (estado `open`) não contam como entrega.
- O **cycle time** vai da criação do item até a conclusão (merge do PR ou fechamento da issue).
"""

import math
from collections import Counter
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Protocol

SEGUNDOS_POR_DIA = 86_400


class ItemDeTrabalho(Protocol):
    """Campos de uma issue ou PR usados pelas métricas de fluxo (datas em UTC, sem fuso)."""

    tipo: str
    estado: str
    criado_em: datetime
    fechado_em: datetime | None
    mesclado_em: datetime | None


@dataclass(frozen=True)
class ContagemSemanal:
    """Quantidade de itens concluídos na semana que começa em `semana` (segunda-feira)."""

    semana: date
    concluidos: int


@dataclass(frozen=True)
class ResumoCycleTime:
    """Mediana e percentil 85 do cycle time, em dias. `None` quando não há itens."""

    quantidade: int
    mediana_dias: float | None
    p85_dias: float | None


def concluido_em(item: ItemDeTrabalho) -> datetime | None:
    """Momento em que o item foi entregue, ou `None` se ele não conta como entrega."""
    if item.estado != "closed":
        return None  # aberto ou reaberto: o fechamento anterior não vale
    if item.tipo == "pull_request":
        return item.mesclado_em  # PR fechado sem merge não é entrega
    return item.fechado_em


def inicio_da_semana(dia: date) -> date:
    """Segunda-feira da semana ISO que contém `dia`."""
    return dia - timedelta(days=dia.weekday())


def percentil(valores: Sequence[float], p: float) -> float | None:
    """Percentil `p` (0–100) com interpolação linear entre os vizinhos; `None` se vazio."""
    if not 0 <= p <= 100:
        raise ValueError(f"Percentil deve estar entre 0 e 100, recebido {p}.")
    if not valores:
        return None
    ordenados = sorted(valores)
    posicao = (len(ordenados) - 1) * p / 100
    abaixo, acima = math.floor(posicao), math.ceil(posicao)
    fracao = posicao - abaixo
    return ordenados[abaixo] + (ordenados[acima] - ordenados[abaixo]) * fracao


def _concluidos_no_periodo(
    itens: Iterable[ItemDeTrabalho],
    inicio: date | None,
    fim: date | None,
    tipo: str | None,
) -> list[tuple[ItemDeTrabalho, datetime]]:
    """Itens concluídos entre `inicio` e `fim` (inclusivos), com a data de conclusão."""
    selecionados = []
    for item in itens:
        if tipo is not None and item.tipo != tipo:
            continue
        conclusao = concluido_em(item)
        if conclusao is None:
            continue
        if inicio is not None and conclusao.date() < inicio:
            continue
        if fim is not None and conclusao.date() > fim:
            continue
        selecionados.append((item, conclusao))
    return selecionados


def throughput_semanal(
    itens: Iterable[ItemDeTrabalho],
    inicio: date | None = None,
    fim: date | None = None,
    tipo: str | None = None,
) -> list[ContagemSemanal]:
    """Itens concluídos por semana, incluindo as semanas sem entrega no intervalo.

    Sem `inicio`/`fim`, o intervalo vai da primeira à última semana com entrega.
    `tipo` restringe a `"issue"` ou `"pull_request"`.
    """
    concluidos = _concluidos_no_periodo(itens, inicio, fim, tipo)
    contagem = Counter(inicio_da_semana(conclusao.date()) for _, conclusao in concluidos)

    if inicio is not None:
        primeira = inicio_da_semana(inicio)
    elif contagem:
        primeira = min(contagem)
    else:
        return []
    if fim is not None:
        ultima = inicio_da_semana(fim)
    elif contagem:
        ultima = max(contagem)
    else:
        ultima = primeira

    semanas = []
    semana = primeira
    while semana <= ultima:
        semanas.append(ContagemSemanal(semana, contagem.get(semana, 0)))
        semana += timedelta(weeks=1)
    return semanas


def duracoes_cycle_time(
    itens: Iterable[ItemDeTrabalho],
    inicio: date | None = None,
    fim: date | None = None,
    tipo: str | None = None,
) -> list[float]:
    """Cycle time, em dias, de cada item concluído no período."""
    return [
        (conclusao - item.criado_em).total_seconds() / SEGUNDOS_POR_DIA
        for item, conclusao in _concluidos_no_periodo(itens, inicio, fim, tipo)
    ]


def cycle_time(
    itens: Iterable[ItemDeTrabalho],
    inicio: date | None = None,
    fim: date | None = None,
    tipo: str | None = None,
) -> ResumoCycleTime:
    """Mediana e percentil 85 do cycle time dos itens concluídos no período."""
    duracoes = duracoes_cycle_time(itens, inicio, fim, tipo)
    return ResumoCycleTime(
        quantidade=len(duracoes),
        mediana_dias=percentil(duracoes, 50),
        p85_dias=percentil(duracoes, 85),
    )
