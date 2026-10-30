"""Métricas de trabalho em andamento: WIP diário e itens envelhecidos (aging).

O início do trabalho é a criação do item (ver ADR 0003). Um item sai do WIP quando é
fechado, com ou sem merge: um PR descartado também deixa de estar em andamento.
"""

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date, datetime, timedelta

from painel.metricas.fluxo import SEGUNDOS_POR_DIA, ItemDeTrabalho, cycle_time


@dataclass(frozen=True)
class ContagemDiaria:
    """Quantidade de itens em andamento ao fim do dia `dia`."""

    dia: date
    em_andamento: int


@dataclass(frozen=True)
class ItemEnvelhecido[T: ItemDeTrabalho]:
    """Item aberto há mais tempo que o limite, com a idade em dias."""

    item: T
    idade_dias: float


def _saida(item: ItemDeTrabalho) -> datetime | None:
    """Momento em que o item deixou de estar em andamento; `None` se continua aberto.

    Um item reaberto conta como aberto desde a criação, porque a data da reabertura
    não é coletada.
    """
    return item.fechado_em if item.estado == "closed" else None


def wip_diario(
    itens: Iterable[ItemDeTrabalho],
    inicio: date,
    fim: date,
    tipo: str | None = None,
) -> list[ContagemDiaria]:
    """Itens em andamento ao fim de cada dia entre `inicio` e `fim` (inclusivos).

    Um item está em andamento no dia `d` se foi criado até `d` e não foi fechado até `d`.
    """
    if fim < inicio:
        raise ValueError("O fim do período não pode ser anterior ao início.")
    intervalos = []
    for item in itens:
        if tipo is not None and item.tipo != tipo:
            continue
        saida = _saida(item)
        if item.estado == "closed" and saida is None:
            continue  # fechado sem data: não dá para saber até quando esteve em andamento
        intervalos.append((item.criado_em.date(), saida.date() if saida else None))

    contagens = []
    dia = inicio
    while dia <= fim:
        em_andamento = sum(
            1 for entrada, saida in intervalos if entrada <= dia and (saida is None or saida > dia)
        )
        contagens.append(ContagemDiaria(dia, em_andamento))
        dia += timedelta(days=1)
    return contagens


def itens_envelhecidos[T: ItemDeTrabalho](
    itens: Iterable[T],
    referencia: datetime,
    limite_dias: float | None = None,
    tipo: str | None = None,
) -> list[ItemEnvelhecido[T]]:
    """Itens abertos há mais tempo que o limite, do mais antigo para o mais novo.

    Sem `limite_dias`, o limite é o percentil 85 do cycle time dos itens concluídos.
    Se não houver itens concluídos para calcular o limite, retorna lista vazia.
    `referencia` é o "agora" da análise (UTC, sem fuso).
    """
    selecionados = [item for item in itens if tipo is None or item.tipo == tipo]
    if limite_dias is None:
        limite_dias = cycle_time(selecionados).p85_dias
        if limite_dias is None:
            return []

    envelhecidos = []
    for item in selecionados:
        if item.estado == "closed":
            continue
        idade = (referencia - item.criado_em).total_seconds() / SEGUNDOS_POR_DIA
        if idade > limite_dias:
            envelhecidos.append(ItemEnvelhecido(item, idade))
    return sorted(envelhecidos, key=lambda envelhecido: envelhecido.idade_dias, reverse=True)
