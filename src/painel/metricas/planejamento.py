"""Métricas de planejamento: burndown por milestone e índice de previsibilidade (ADR 0007).

O escopo de um milestone são os itens (issues e PRs) que estão nele hoje. O GitHub não
informa quando um item entrou no milestone, então um item conta no escopo a partir da
criação ou do início do milestone, o que vier depois.
"""

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Protocol

from painel.metricas.fluxo import ItemDeTrabalho, concluido_em


class ItemPlanejado(ItemDeTrabalho, Protocol):
    """Item com o repositório e o título do milestone em que está."""

    repositorio: str
    milestone: str | None


class MilestonePlanejado(Protocol):
    """Campos de um milestone usados nas métricas de planejamento."""

    repositorio: str
    titulo: str
    criado_em: datetime
    prazo: date | None
    fechado_em: datetime | None


@dataclass(frozen=True)
class PontoBurndown:
    """Itens restantes ao fim do dia e a linha ideal; `None` onde não se aplica."""

    dia: date
    restantes: int | None
    ideal: float | None


@dataclass(frozen=True)
class Previsibilidade:
    """Itens planejados de um milestone e quantos foram entregues até o prazo."""

    repositorio: str
    milestone: str
    prazo: date
    planejados: int
    entregues_no_prazo: int
    percentual: float | None


def itens_do_milestone[T: ItemPlanejado](
    itens: Iterable[T], milestone: MilestonePlanejado
) -> list[T]:
    """Itens que estão hoje no milestone (mesmo repositório e mesmo título)."""
    return [
        item
        for item in itens
        if item.repositorio == milestone.repositorio and item.milestone == milestone.titulo
    ]


def _saida(item: ItemDeTrabalho) -> date | None:
    """Dia em que o item deixou de ser trabalho restante (fechado, com ou sem entrega)."""
    if item.estado == "closed" and item.fechado_em is not None:
        return item.fechado_em.date()
    return None


def burndown(
    itens: Iterable[ItemPlanejado], milestone: MilestonePlanejado, hoje: date
) -> list[PontoBurndown]:
    """Itens restantes por dia, do início do milestone até o prazo (ou além, se atrasado).

    - `restantes` só é calculado até hoje, ou até o fechamento do milestone;
      dias futuros ficam com `None`.
    - `ideal` vai em linha reta do escopo comprometido no início do milestone até zero
      no prazo; sem prazo, fica `None`.
    """
    escopo = itens_do_milestone(itens, milestone)
    inicio = milestone.criado_em.date()
    fim_real = milestone.fechado_em.date() if milestone.fechado_em else hoje
    ultimo = max(milestone.prazo, fim_real) if milestone.prazo else fim_real

    def restantes_em(dia: date) -> int:
        return sum(
            1
            for item in escopo
            if item.criado_em.date() <= dia and ((saida := _saida(item)) is None or saida > dia)
        )

    # Escopo comprometido no início: itens que já existiam e não tinham sido fechados antes
    # do primeiro dia. Fechamentos do próprio primeiro dia já aparecem como progresso.
    inicial = sum(
        1
        for item in escopo
        if item.criado_em.date() <= inicio and ((saida := _saida(item)) is None or saida >= inicio)
    )
    duracao = (milestone.prazo - inicio).days if milestone.prazo else None

    pontos = []
    dia = inicio
    while dia <= ultimo:
        decorridos = (dia - inicio).days
        if duracao is None or decorridos > duracao:
            ideal = None
        else:
            ideal = inicial * (1 - decorridos / duracao) if duracao > 0 else 0.0
        restantes = restantes_em(dia) if dia <= fim_real else None
        pontos.append(PontoBurndown(dia, restantes, ideal))
        dia += timedelta(days=1)
    return pontos


def previsibilidade(
    itens: Iterable[ItemPlanejado], milestone: MilestonePlanejado
) -> Previsibilidade | None:
    """Percentual dos itens do milestone entregues até o fim do dia do prazo.

    Retorna `None` para milestones sem prazo. Entrega segue o ADR 0003: issue fechada
    ou PR mesclado.
    """
    if milestone.prazo is None:
        return None
    escopo = itens_do_milestone(itens, milestone)
    no_prazo = sum(
        1
        for item in escopo
        if (conclusao := concluido_em(item)) is not None and conclusao.date() <= milestone.prazo
    )
    return Previsibilidade(
        repositorio=milestone.repositorio,
        milestone=milestone.titulo,
        prazo=milestone.prazo,
        planejados=len(escopo),
        entregues_no_prazo=no_prazo,
        percentual=no_prazo / len(escopo) if escopo else None,
    )


def indice_previsibilidade(resumos: Iterable[Previsibilidade | None]) -> float | None:
    """Entregues no prazo ÷ planejados, somando os milestones informados."""
    validos = [r for r in resumos if r is not None]
    planejados = sum(r.planejados for r in validos)
    if planejados == 0:
        return None
    return sum(r.entregues_no_prazo for r in validos) / planejados
