from dataclasses import dataclass
from datetime import date, datetime, timedelta

import pytest

from painel.metricas.dora import (
    Desempenho,
    classificar_frequencia,
    classificar_lead_time,
    classificar_restauracao,
    classificar_taxa_falha,
    frequencia_deploy,
    lead_time_mudancas,
    taxa_falha_mudancas,
    tempo_restauracao,
)


@dataclass(frozen=True)
class DeployFalso:
    implantado_em: datetime


def deploys(*momentos: datetime) -> list[DeployFalso]:
    return [DeployFalso(momento) for momento in momentos]


# --- Classificação ----------------------------------------------------------------------


@pytest.mark.parametrize(
    ("por_dia", "esperado"),
    [
        (3, Desempenho.ELITE),
        (1, Desempenho.ELITE),
        (1 / 7, Desempenho.ALTO),
        (1 / 8, Desempenho.MEDIO),
        (1 / 30, Desempenho.MEDIO),
        (1 / 31, Desempenho.BAIXO),
        (0, Desempenho.BAIXO),
    ],
)
def test_classificar_frequencia(por_dia, esperado):
    assert classificar_frequencia(por_dia) is esperado


@pytest.mark.parametrize(
    ("dias", "esperado"),
    [
        (0.5, Desempenho.ELITE),
        (1, Desempenho.ALTO),
        (7, Desempenho.ALTO),
        (8, Desempenho.MEDIO),
        (30, Desempenho.MEDIO),
        (31, Desempenho.BAIXO),
    ],
)
def test_classificar_lead_time(dias, esperado):
    assert classificar_lead_time(dias) is esperado


@pytest.mark.parametrize(
    ("taxa", "esperado"),
    [
        (0, Desempenho.ELITE),
        (0.05, Desempenho.ELITE),
        (0.10, Desempenho.ALTO),
        (0.15, Desempenho.MEDIO),
        (0.16, Desempenho.BAIXO),
    ],
)
def test_classificar_taxa_falha(taxa, esperado):
    assert classificar_taxa_falha(taxa) is esperado


@pytest.mark.parametrize(
    ("dias", "esperado"),
    [
        (0.5 / 24, Desempenho.ELITE),
        (1 / 24, Desempenho.ALTO),
        (0.9, Desempenho.ALTO),
        (1, Desempenho.MEDIO),
        (7, Desempenho.MEDIO),
        (8, Desempenho.BAIXO),
    ],
)
def test_classificar_restauracao(dias, esperado):
    assert classificar_restauracao(dias) is esperado


def test_classificacao_tem_rotulo_em_portugues():
    assert str(Desempenho.MEDIO) == "médio"


# --- Frequência de deploy ---------------------------------------------------------------


def test_frequencia_conta_deploys_do_periodo_inclusivo():
    lista = deploys(
        datetime(2026, 9, 30, 23),  # fora
        datetime(2026, 10, 1, 0, 5),
        datetime(2026, 10, 7, 23, 59),
        datetime(2026, 10, 8),  # fora
    )

    resultado = frequencia_deploy(lista, date(2026, 10, 1), date(2026, 10, 7))

    assert resultado.quantidade == 2
    assert resultado.dias == 7
    assert resultado.por_dia == pytest.approx(2 / 7)
    assert resultado.classificacao is Desempenho.ALTO


def test_frequencia_sem_deploys_e_baixa():
    resultado = frequencia_deploy([], date(2026, 10, 1), date(2026, 10, 31))

    assert resultado.quantidade == 0
    assert resultado.classificacao is Desempenho.BAIXO


def test_frequencia_periodo_invalido():
    with pytest.raises(ValueError):
        frequencia_deploy([], date(2026, 10, 2), date(2026, 10, 1))


# --- Lead time de mudanças --------------------------------------------------------------


def test_lead_time_vai_da_criacao_do_pr_ao_primeiro_deploy_apos_o_merge(novo_item):
    pr = novo_item(
        tipo="pull_request",
        criado=datetime(2026, 10, 1),
        fechado=datetime(2026, 10, 2),
        mesclado=datetime(2026, 10, 2),
    )
    lista = deploys(datetime(2026, 10, 1, 12), datetime(2026, 10, 3), datetime(2026, 10, 5))

    resumo = lead_time_mudancas([pr], lista)

    assert resumo.quantidade == 1
    assert resumo.mediana_dias == pytest.approx(2.0)  # deploy de 03/10, não o de 01/10
    assert resumo.classificacao is Desempenho.ALTO


def test_deploy_no_mesmo_instante_do_merge_conta(novo_item):
    merge = datetime(2026, 10, 2, 10)
    pr = novo_item(tipo="pull_request", criado=datetime(2026, 10, 2), fechado=merge, mesclado=merge)

    resumo = lead_time_mudancas([pr], deploys(merge))

    assert resumo.mediana_dias == pytest.approx(10 / 24)
    assert resumo.classificacao is Desempenho.ELITE


def test_lead_time_ignora_issues_prs_sem_merge_e_prs_ainda_nao_implantados(novo_item):
    itens = [
        novo_item(1, fechado=datetime(2026, 10, 2)),  # issue
        novo_item(2, tipo="pull_request", fechado=datetime(2026, 10, 2)),  # sem merge
        novo_item(
            3, tipo="pull_request", fechado=datetime(2026, 10, 9), mesclado=datetime(2026, 10, 9)
        ),  # depois do último deploy
    ]

    resumo = lead_time_mudancas(itens, deploys(datetime(2026, 10, 5)))

    assert resumo.quantidade == 0
    assert resumo.mediana_dias is None
    assert resumo.classificacao is None


def test_lead_time_filtra_pela_data_do_deploy(novo_item):
    itens = [
        novo_item(
            1,
            tipo="pull_request",
            criado=datetime(2026, 9, 1),
            fechado=datetime(2026, 9, 2),
            mesclado=datetime(2026, 9, 2),
        ),
        novo_item(
            2,
            tipo="pull_request",
            criado=datetime(2026, 10, 1),
            fechado=datetime(2026, 10, 2),
            mesclado=datetime(2026, 10, 2),
        ),
    ]
    lista = deploys(datetime(2026, 9, 3), datetime(2026, 10, 3))

    resumo = lead_time_mudancas(itens, lista, inicio=date(2026, 10, 1), fim=date(2026, 10, 31))

    assert resumo.quantidade == 1
    assert resumo.mediana_dias == pytest.approx(2.0)


# --- Taxa de falha de mudanças ----------------------------------------------------------


def test_deploy_seguido_de_revert_ou_bug_conta_como_falha(novo_item):
    lista = deploys(
        datetime(2026, 10, 1),  # seguido de revert
        datetime(2026, 10, 3),  # seguido de bug
        datetime(2026, 10, 5),  # limpo
        datetime(2026, 10, 7),  # limpo
    )
    itens = [
        novo_item(
            1,
            tipo="pull_request",
            titulo='Revert "feat: x"',
            criado=datetime(2026, 10, 2),
            fechado=datetime(2026, 10, 2),
            mesclado=datetime(2026, 10, 2),
        ),
        novo_item(2, labels=("Bug",), criado=datetime(2026, 10, 4)),  # maiúscula vale
        novo_item(3, labels=("documentação",), criado=datetime(2026, 10, 6)),  # não é falha
    ]

    resultado = taxa_falha_mudancas(itens, lista)

    assert resultado.deploys == 4
    assert resultado.com_falha == 2
    assert resultado.taxa == pytest.approx(0.5)
    assert resultado.classificacao is Desempenho.BAIXO


def test_varios_sinais_entre_dois_deploys_contam_uma_falha(novo_item):
    lista = deploys(datetime(2026, 10, 1), datetime(2026, 10, 10))
    itens = [
        novo_item(1, labels=("bug",), criado=datetime(2026, 10, 2)),
        novo_item(2, labels=("incidente",), criado=datetime(2026, 10, 3)),
    ]

    resultado = taxa_falha_mudancas(itens, lista)

    assert (resultado.deploys, resultado.com_falha) == (2, 1)


def test_sinal_antes_do_primeiro_deploy_e_ignorado_e_ultimo_deploy_fica_aberto(novo_item):
    lista = deploys(datetime(2026, 10, 5), datetime(2026, 10, 10))
    itens = [
        novo_item(1, labels=("bug",), criado=datetime(2026, 10, 1)),  # antes de tudo
        novo_item(2, labels=("bug",), criado=datetime(2026, 10, 20)),  # depois do último
    ]

    resultado = taxa_falha_mudancas(itens, lista)

    assert (resultado.deploys, resultado.com_falha) == (2, 1)  # só o último deploy falhou


def test_pr_de_revert_nao_mesclado_nao_e_falha(novo_item):
    revert = novo_item(tipo="pull_request", titulo="Revert x", fechado=datetime(2026, 10, 2))

    resultado = taxa_falha_mudancas([revert], deploys(datetime(2026, 10, 1)))

    assert resultado.com_falha == 0
    assert resultado.classificacao is Desempenho.ELITE


def test_periodo_conta_so_deploys_do_periodo_mas_usa_o_proximo_deploy_como_limite(novo_item):
    lista = deploys(datetime(2026, 9, 28), datetime(2026, 10, 1), datetime(2026, 10, 3))
    itens = [novo_item(1, labels=("bug",), criado=datetime(2026, 10, 2))]

    resultado = taxa_falha_mudancas(itens, lista, inicio=date(2026, 10, 1), fim=date(2026, 10, 1))

    assert (resultado.deploys, resultado.com_falha) == (1, 1)


def test_rotulos_de_falha_configuraveis(novo_item):
    itens = [novo_item(1, labels=("regressao",), criado=datetime(2026, 10, 2))]
    lista = deploys(datetime(2026, 10, 1))

    assert taxa_falha_mudancas(itens, lista).com_falha == 0
    assert taxa_falha_mudancas(itens, lista, rotulos_falha={"Regressao"}).com_falha == 1


def test_taxa_sem_deploys():
    resultado = taxa_falha_mudancas([], [])

    assert resultado.taxa is None
    assert resultado.classificacao is None


# --- Tempo de restauração ---------------------------------------------------------------


def test_mttr_usa_issues_de_incidente_fechadas(novo_item):
    inicio = datetime(2026, 10, 1, 8)
    itens = [
        novo_item(1, labels=("incidente",), criado=inicio, fechado=inicio + timedelta(hours=2)),
        novo_item(2, labels=("incidente",), criado=inicio, fechado=inicio + timedelta(hours=6)),
        novo_item(3, labels=("incidente",), criado=inicio),  # ainda aberto
        novo_item(4, labels=("bug",), criado=inicio, fechado=inicio + timedelta(days=9)),
    ]

    resumo = tempo_restauracao(itens)

    assert resumo.quantidade == 2
    assert resumo.mediana_dias == pytest.approx(4 / 24)
    assert resumo.classificacao is Desempenho.ALTO


def test_mttr_ignora_incidente_reaberto_e_filtra_pelo_fechamento(novo_item):
    itens = [
        novo_item(
            1,
            labels=("incidente",),
            criado=datetime(2026, 10, 1),
            fechado=datetime(2026, 10, 2),
            estado="open",
        ),  # reaberto
        novo_item(
            2, labels=("incidente",), criado=datetime(2026, 9, 1), fechado=datetime(2026, 9, 3)
        ),  # fora do período
        novo_item(
            3, labels=("incidente",), criado=datetime(2026, 10, 10), fechado=datetime(2026, 10, 20)
        ),
    ]

    resumo = tempo_restauracao(itens, inicio=date(2026, 10, 1), fim=date(2026, 10, 31))

    assert resumo.quantidade == 1
    assert resumo.mediana_dias == pytest.approx(10.0)
    assert resumo.classificacao is Desempenho.BAIXO


def test_mttr_sem_incidentes():
    resumo = tempo_restauracao([])

    assert resumo.quantidade == 0
    assert resumo.classificacao is None
