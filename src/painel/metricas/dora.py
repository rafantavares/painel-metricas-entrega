"""As quatro métricas DORA, com a classificação de desempenho de cada uma (ver ADR 0005).

- Frequência de deploy: deploys por dia no período.
- Lead time de mudanças: da criação do PR ao primeiro deploy depois do merge.
- Taxa de falha de mudanças: fração dos deploys seguidos de revert ou de issue de falha.
- Tempo de restauração (MTTR): da abertura ao fechamento das issues de incidente.
"""

from bisect import bisect_left
from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass
from datetime import date, datetime
from enum import StrEnum
from typing import Protocol

from painel.metricas.fluxo import SEGUNDOS_POR_DIA, percentil

ROTULOS_FALHA = frozenset({"bug", "incidente"})
ROTULOS_INCIDENTE = frozenset({"incidente"})


class Desempenho(StrEnum):
    """Faixas de desempenho do relatório State of DevOps (DORA)."""

    ELITE = "elite"
    ALTO = "alto"
    MEDIO = "médio"
    BAIXO = "baixo"


class ItemDora(Protocol):
    """Campos de uma issue ou PR usados pelas métricas DORA (datas em UTC, sem fuso)."""

    tipo: str
    estado: str
    titulo: str
    labels: tuple[str, ...]
    criado_em: datetime
    fechado_em: datetime | None
    mesclado_em: datetime | None


class DeployDora(Protocol):
    """Campo de um deploy usado pelas métricas DORA."""

    implantado_em: datetime


@dataclass(frozen=True)
class FrequenciaDeploy:
    quantidade: int
    dias: int
    por_dia: float
    classificacao: Desempenho


@dataclass(frozen=True)
class ResumoDuracao:
    """Mediana e percentil 85, em dias; `classificacao` é `None` quando não há dados."""

    quantidade: int
    mediana_dias: float | None
    p85_dias: float | None
    classificacao: Desempenho | None


@dataclass(frozen=True)
class TaxaFalha:
    deploys: int
    com_falha: int
    taxa: float | None
    classificacao: Desempenho | None


def _no_periodo(momento: datetime, inicio: date | None, fim: date | None) -> bool:
    dia = momento.date()
    return (inicio is None or dia >= inicio) and (fim is None or dia <= fim)


def _dias(inicio: datetime, fim: datetime) -> float:
    return (fim - inicio).total_seconds() / SEGUNDOS_POR_DIA


def _tem_rotulo(item: ItemDora, rotulos: frozenset[str]) -> bool:
    return any(label.lower() in rotulos for label in item.labels)


def _resumir(
    duracoes: Sequence[float], classificar: Callable[[float], Desempenho]
) -> ResumoDuracao:
    mediana = percentil(duracoes, 50)
    return ResumoDuracao(
        quantidade=len(duracoes),
        mediana_dias=mediana,
        p85_dias=percentil(duracoes, 85),
        classificacao=classificar(mediana) if mediana is not None else None,
    )


# --- Classificação ----------------------------------------------------------------------


def classificar_frequencia(por_dia: float) -> Desempenho:
    """Elite: diário ou mais; alto: semanal; médio: mensal; baixo: menos que mensal."""
    if por_dia >= 1:
        return Desempenho.ELITE
    if por_dia >= 1 / 7:
        return Desempenho.ALTO
    if por_dia >= 1 / 30:
        return Desempenho.MEDIO
    return Desempenho.BAIXO


def classificar_lead_time(dias: float) -> Desempenho:
    """Elite: menos de 1 dia; alto: até 1 semana; médio: até 1 mês; baixo: mais de 1 mês."""
    if dias < 1:
        return Desempenho.ELITE
    if dias <= 7:
        return Desempenho.ALTO
    if dias <= 30:
        return Desempenho.MEDIO
    return Desempenho.BAIXO


def classificar_taxa_falha(taxa: float) -> Desempenho:
    """Elite: até 5%; alto: até 10%; médio: até 15%; baixo: acima de 15%."""
    if taxa <= 0.05:
        return Desempenho.ELITE
    if taxa <= 0.10:
        return Desempenho.ALTO
    if taxa <= 0.15:
        return Desempenho.MEDIO
    return Desempenho.BAIXO


def classificar_restauracao(dias: float) -> Desempenho:
    """Elite: menos de 1 hora; alto: menos de 1 dia; médio: até 1 semana; baixo: mais."""
    if dias < 1 / 24:
        return Desempenho.ELITE
    if dias < 1:
        return Desempenho.ALTO
    if dias <= 7:
        return Desempenho.MEDIO
    return Desempenho.BAIXO


# --- Métricas ---------------------------------------------------------------------------


def frequencia_deploy(deploys: Iterable[DeployDora], inicio: date, fim: date) -> FrequenciaDeploy:
    """Deploys por dia entre `inicio` e `fim` (inclusivos)."""
    if fim < inicio:
        raise ValueError("O fim do período não pode ser anterior ao início.")
    quantidade = sum(1 for deploy in deploys if _no_periodo(deploy.implantado_em, inicio, fim))
    dias = (fim - inicio).days + 1
    por_dia = quantidade / dias
    return FrequenciaDeploy(quantidade, dias, por_dia, classificar_frequencia(por_dia))


def lead_time_mudancas(
    itens: Iterable[ItemDora],
    deploys: Iterable[DeployDora],
    inicio: date | None = None,
    fim: date | None = None,
) -> ResumoDuracao:
    """Da criação de cada PR mesclado ao primeiro deploy no momento do merge ou depois.

    O período filtra pela data desse deploy. PRs mesclados que ainda não foram para
    produção ficam de fora até o próximo deploy.
    """
    momentos = sorted(deploy.implantado_em for deploy in deploys)
    duracoes = []
    for item in itens:
        if item.tipo != "pull_request" or item.mesclado_em is None:
            continue
        posicao = bisect_left(momentos, item.mesclado_em)
        if posicao == len(momentos):
            continue  # ainda não implantado
        implantado = momentos[posicao]
        if _no_periodo(implantado, inicio, fim):
            duracoes.append(_dias(item.criado_em, implantado))
    return _resumir(duracoes, classificar_lead_time)


def _sinais_de_falha(itens: Iterable[ItemDora], rotulos_falha: frozenset[str]) -> list[datetime]:
    """Momentos em que surgiu um sinal de falha: revert mesclado ou issue de falha aberta."""
    sinais = []
    for item in itens:
        if item.tipo == "pull_request":
            if item.mesclado_em is not None and item.titulo.lower().startswith("revert"):
                sinais.append(item.mesclado_em)
        elif _tem_rotulo(item, rotulos_falha):
            sinais.append(item.criado_em)
    return sorted(sinais)


def taxa_falha_mudancas(
    itens: Iterable[ItemDora],
    deploys: Iterable[DeployDora],
    inicio: date | None = None,
    fim: date | None = None,
    rotulos_falha: Iterable[str] = ROTULOS_FALHA,
) -> TaxaFalha:
    """Fração dos deploys do período que tiveram um sinal de falha antes do próximo deploy.

    Sinais de falha: PR de revert mesclado (título começando com "Revert") ou issue com
    um dos `rotulos_falha` aberta. Cada sinal é atribuído ao deploy mais recente antes dele.
    """
    momentos = sorted(deploy.implantado_em for deploy in deploys)
    sinais = _sinais_de_falha(itens, frozenset(r.lower() for r in rotulos_falha))

    no_periodo = com_falha = 0
    for posicao, implantado in enumerate(momentos):
        if not _no_periodo(implantado, inicio, fim):
            continue
        no_periodo += 1
        proximo = momentos[posicao + 1] if posicao + 1 < len(momentos) else None
        primeiro_sinal = bisect_left(sinais, implantado)
        if primeiro_sinal < len(sinais) and (proximo is None or sinais[primeiro_sinal] < proximo):
            com_falha += 1

    if no_periodo == 0:
        return TaxaFalha(0, 0, None, None)
    taxa = com_falha / no_periodo
    return TaxaFalha(no_periodo, com_falha, taxa, classificar_taxa_falha(taxa))


def tempo_restauracao(
    itens: Iterable[ItemDora],
    inicio: date | None = None,
    fim: date | None = None,
    rotulos_incidente: Iterable[str] = ROTULOS_INCIDENTE,
) -> ResumoDuracao:
    """Da abertura ao fechamento das issues de incidente fechadas no período."""
    rotulos = frozenset(r.lower() for r in rotulos_incidente)
    duracoes = [
        _dias(item.criado_em, item.fechado_em)
        for item in itens
        if item.tipo == "issue"
        and item.estado == "closed"
        and item.fechado_em is not None
        and _tem_rotulo(item, rotulos)
        and _no_periodo(item.fechado_em, inicio, fim)
    ]
    return _resumir(duracoes, classificar_restauracao)
