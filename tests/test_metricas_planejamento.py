from dataclasses import replace
from datetime import date, datetime

import pytest

from painel.coleta.normalizacao import Milestone
from painel.metricas.planejamento import (
    PontoBurndown,
    burndown,
    indice_previsibilidade,
    itens_do_milestone,
    previsibilidade,
)


def milestone(
    titulo="M1",
    criado=datetime(2026, 10, 1, 9),
    prazo=date(2026, 10, 5),
    fechado=None,
    repositorio="dono/repo",
):
    return Milestone(
        repositorio, 1, titulo, "closed" if fechado else "open", criado, prazo, fechado
    )


def test_itens_do_milestone_compara_repositorio_e_titulo(novo_item):
    m1 = novo_item(1, milestone="M1")
    outro_titulo = novo_item(2, milestone="M2")
    sem_milestone = novo_item(3)
    outro_repo = replace(novo_item(4, milestone="M1"), repositorio="dono/outro")

    assert itens_do_milestone([m1, outro_titulo, sem_milestone, outro_repo], milestone()) == [m1]


# --- Burndown ---------------------------------------------------------------------------


def test_burndown_conta_restantes_por_dia_e_traca_a_linha_ideal(novo_item):
    itens = [
        novo_item(
            1, milestone="M1", criado=datetime(2026, 9, 20), fechado=datetime(2026, 10, 2, 15)
        ),
        novo_item(2, milestone="M1", criado=datetime(2026, 9, 25), fechado=datetime(2026, 10, 4)),
        novo_item(3, milestone="M1", criado=datetime(2026, 9, 28)),
        novo_item(4, milestone="M1", criado=datetime(2026, 10, 1)),
    ]

    pontos = burndown(itens, milestone(), hoje=date(2026, 10, 5))

    assert [p.restantes for p in pontos] == [4, 3, 3, 2, 2]  # 01/10 a 05/10
    assert [p.ideal for p in pontos] == pytest.approx([4, 3, 2, 1, 0])


def test_item_criado_durante_o_milestone_aumenta_o_escopo(novo_item):
    itens = [
        novo_item(1, milestone="M1", criado=datetime(2026, 9, 20)),
        novo_item(2, milestone="M1", criado=datetime(2026, 10, 3, 10)),  # entrou depois
    ]

    pontos = burndown(itens, milestone(), hoje=date(2026, 10, 5))

    assert [p.restantes for p in pontos] == [1, 1, 2, 2, 2]
    assert pontos[0].ideal == 1  # a linha ideal parte do escopo inicial


def test_dias_futuros_ficam_sem_restantes(novo_item):
    itens = [novo_item(1, milestone="M1", criado=datetime(2026, 9, 20))]

    pontos = burndown(itens, milestone(), hoje=date(2026, 10, 3))

    assert [p.restantes for p in pontos] == [1, 1, 1, None, None]
    assert pontos[-1] == PontoBurndown(date(2026, 10, 5), None, 0.0)


def test_milestone_atrasado_estende_o_grafico_depois_do_prazo(novo_item):
    itens = [novo_item(1, milestone="M1", criado=datetime(2026, 9, 20))]

    pontos = burndown(itens, milestone(), hoje=date(2026, 10, 7))

    assert pontos[-1].dia == date(2026, 10, 7)
    assert [p.ideal for p in pontos[-2:]] == [None, None]  # depois do prazo
    assert pontos[-1].restantes == 1


def test_milestone_fechado_para_no_fechamento(novo_item):
    itens = [
        novo_item(1, milestone="M1", criado=datetime(2026, 9, 20), fechado=datetime(2026, 10, 2))
    ]
    fechado = milestone(prazo=date(2026, 10, 3), fechado=datetime(2026, 10, 2, 18))

    pontos = burndown(itens, fechado, hoje=date(2026, 10, 20))

    assert [p.dia for p in pontos] == [date(2026, 10, 1), date(2026, 10, 2), date(2026, 10, 3)]
    assert [p.restantes for p in pontos] == [1, 0, None]


def test_item_reaberto_continua_restante(novo_item):
    reaberto = novo_item(
        1,
        milestone="M1",
        criado=datetime(2026, 9, 20),
        fechado=datetime(2026, 10, 2),
        estado="open",
    )

    pontos = burndown([reaberto], milestone(), hoje=date(2026, 10, 5))

    assert {p.restantes for p in pontos} == {1}


def test_milestone_sem_prazo_nao_tem_linha_ideal(novo_item):
    itens = [novo_item(1, milestone="M1", criado=datetime(2026, 9, 20))]

    pontos = burndown(itens, milestone(prazo=None), hoje=date(2026, 10, 3))

    assert len(pontos) == 3
    assert all(p.ideal is None for p in pontos)


def test_prazo_no_dia_da_criacao(novo_item):
    itens = [novo_item(1, milestone="M1", criado=datetime(2026, 9, 20))]

    pontos = burndown(itens, milestone(prazo=date(2026, 10, 1)), hoje=date(2026, 10, 1))

    assert pontos == [PontoBurndown(date(2026, 10, 1), 1, 0.0)]


# --- Previsibilidade --------------------------------------------------------------------


def test_previsibilidade_conta_entregas_ate_o_fim_do_dia_do_prazo(novo_item):
    itens = [
        novo_item(1, milestone="M1", fechado=datetime(2026, 10, 5, 23, 59)),  # no prazo
        novo_item(2, milestone="M1", fechado=datetime(2026, 10, 6)),  # atrasado
        novo_item(3, milestone="M1"),  # não entregue
        novo_item(
            4, milestone="M1", tipo="pull_request", fechado=datetime(2026, 10, 2)
        ),  # sem merge
        novo_item(
            5,
            milestone="M1",
            tipo="pull_request",
            fechado=datetime(2026, 10, 2),
            mesclado=datetime(2026, 10, 2),
        ),  # no prazo
    ]

    resumo = previsibilidade(itens, milestone())

    assert resumo.planejados == 5
    assert resumo.entregues_no_prazo == 2
    assert resumo.percentual == pytest.approx(0.4)


def test_previsibilidade_sem_prazo_ou_sem_itens():
    assert previsibilidade([], milestone(prazo=None)) is None
    vazio = previsibilidade([], milestone())
    assert (vazio.planejados, vazio.percentual) == (0, None)


def test_indice_soma_os_milestones(novo_item):
    itens = [
        novo_item(1, milestone="M1", fechado=datetime(2026, 10, 1)),
        novo_item(2, milestone="M1"),
        novo_item(3, milestone="M2", fechado=datetime(2026, 10, 1)),
    ]
    resumos = [
        previsibilidade(itens, milestone("M1")),
        previsibilidade(itens, milestone("M2")),
        previsibilidade(itens, milestone("M3", prazo=None)),
    ]

    assert indice_previsibilidade(resumos) == pytest.approx(2 / 3)


def test_indice_sem_itens_planejados():
    assert indice_previsibilidade([]) is None
    assert indice_previsibilidade([previsibilidade([], milestone())]) is None


def test_linha_ideal_parte_do_escopo_do_inicio_mesmo_com_entregas_no_primeiro_dia(novo_item):
    itens = [
        novo_item(
            1, milestone="M1", criado=datetime(2026, 9, 20), fechado=datetime(2026, 10, 1, 18)
        ),
        novo_item(2, milestone="M1", criado=datetime(2026, 9, 20)),
        novo_item(3, milestone="M1", criado=datetime(2026, 9, 20), fechado=datetime(2026, 9, 30)),
    ]

    pontos = burndown(itens, milestone(), hoje=date(2026, 10, 5))

    assert pontos[0].restantes == 1  # o item 1 foi entregue no primeiro dia
    assert pontos[0].ideal == 2  # o item 3 já estava fechado antes do início
