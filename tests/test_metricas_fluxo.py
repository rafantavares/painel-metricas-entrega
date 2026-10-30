from datetime import date, datetime

import pytest

from painel.metricas.fluxo import (
    ContagemSemanal,
    concluido_em,
    cycle_time,
    duracoes_cycle_time,
    inicio_da_semana,
    percentil,
    throughput_semanal,
)

# --- concluido_em -----------------------------------------------------------------------


def test_issue_fechada_conclui_no_fechamento(novo_item):
    assert concluido_em(novo_item(fechado=datetime(2026, 10, 3))) == datetime(2026, 10, 3)


def test_pr_conclui_no_merge(novo_item):
    pr = novo_item(
        tipo="pull_request", fechado=datetime(2026, 10, 3), mesclado=datetime(2026, 10, 3)
    )
    assert concluido_em(pr) == datetime(2026, 10, 3)


def test_pr_fechado_sem_merge_nao_e_entrega(novo_item):
    assert concluido_em(novo_item(tipo="pull_request", fechado=datetime(2026, 10, 3))) is None


def test_item_sem_data_de_fechamento_nao_e_entrega(novo_item):
    assert concluido_em(novo_item()) is None


def test_item_reaberto_nao_e_entrega_mesmo_com_fechamento_antigo(novo_item):
    reaberto = novo_item(fechado=datetime(2026, 10, 3), estado="open")
    assert concluido_em(reaberto) is None


def test_item_fechado_sem_data_e_ignorado(novo_item):
    assert concluido_em(novo_item(estado="closed")) is None


# --- percentil --------------------------------------------------------------------------


def test_percentil_com_interpolacao_linear():
    valores = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]
    assert percentil(valores, 50) == pytest.approx(5.5)
    assert percentil(valores, 85) == pytest.approx(8.65)
    assert percentil(valores, 0) == 1
    assert percentil(valores, 100) == 10


def test_percentil_nao_depende_da_ordem_e_aceita_um_valor():
    assert percentil([3, 1, 2], 50) == 2
    assert percentil([4.5], 85) == 4.5


def test_percentil_vazio():
    assert percentil([], 85) is None


@pytest.mark.parametrize("p", [-1, 101])
def test_percentil_fora_do_intervalo(p):
    with pytest.raises(ValueError):
        percentil([1], p)


# --- throughput -------------------------------------------------------------------------


def test_inicio_da_semana_e_segunda_feira():
    assert inicio_da_semana(date(2026, 10, 29)) == date(2026, 10, 26)  # quinta → segunda
    assert inicio_da_semana(date(2026, 10, 26)) == date(2026, 10, 26)
    assert inicio_da_semana(date(2026, 11, 1)) == date(2026, 10, 26)  # domingo


def test_throughput_agrupa_por_semana_e_preenche_semanas_vazias(novo_item):
    itens = [
        novo_item(1, fechado=datetime(2026, 10, 5, 9)),  # semana de 05/10
        novo_item(2, fechado=datetime(2026, 10, 11, 23, 59)),  # domingo, mesma semana
        novo_item(3, fechado=datetime(2026, 10, 21)),  # semana de 19/10
    ]

    assert throughput_semanal(itens) == [
        ContagemSemanal(date(2026, 10, 5), 2),
        ContagemSemanal(date(2026, 10, 12), 0),
        ContagemSemanal(date(2026, 10, 19), 1),
    ]


def test_throughput_ignora_abertos_reabertos_e_prs_sem_merge(novo_item):
    itens = [
        novo_item(1, fechado=datetime(2026, 10, 5)),
        novo_item(2),  # aberto, sem data de fechamento
        novo_item(3, fechado=datetime(2026, 10, 5), estado="open"),  # reaberto
        novo_item(4, tipo="pull_request", fechado=datetime(2026, 10, 5)),  # sem merge
    ]

    assert throughput_semanal(itens) == [ContagemSemanal(date(2026, 10, 5), 1)]


def test_throughput_respeita_o_periodo_e_mostra_semanas_sem_entrega(novo_item):
    itens = [
        novo_item(1, fechado=datetime(2026, 9, 30)),  # antes do período
        novo_item(2, fechado=datetime(2026, 10, 14)),
    ]

    resultado = throughput_semanal(itens, inicio=date(2026, 10, 5), fim=date(2026, 10, 25))

    assert resultado == [
        ContagemSemanal(date(2026, 10, 5), 0),
        ContagemSemanal(date(2026, 10, 12), 1),
        ContagemSemanal(date(2026, 10, 19), 0),
    ]


def test_throughput_filtra_por_tipo(novo_item):
    itens = [
        novo_item(1, fechado=datetime(2026, 10, 5)),
        novo_item(
            2, tipo="pull_request", fechado=datetime(2026, 10, 5), mesclado=datetime(2026, 10, 5)
        ),
    ]

    assert throughput_semanal(itens, tipo="pull_request") == [ContagemSemanal(date(2026, 10, 5), 1)]


def test_throughput_sem_itens():
    assert throughput_semanal([]) == []


def test_throughput_sem_itens_com_periodo_retorna_semanas_zeradas():
    resultado = throughput_semanal([], inicio=date(2026, 10, 5), fim=date(2026, 10, 12))
    assert [semana.concluidos for semana in resultado] == [0, 0]


# --- cycle time -------------------------------------------------------------------------


def test_cycle_time_em_dias_da_criacao_a_conclusao(novo_item):
    itens = [
        novo_item(1, criado=datetime(2026, 10, 1), fechado=datetime(2026, 10, 2, 12)),  # 1,5 dia
        novo_item(
            2,
            tipo="pull_request",
            criado=datetime(2026, 10, 1),
            fechado=datetime(2026, 10, 4),
            mesclado=datetime(2026, 10, 3),  # o merge define a conclusão
        ),
    ]

    assert duracoes_cycle_time(itens) == pytest.approx([1.5, 2.0])


def test_cycle_time_mediana_e_p85(novo_item):
    itens = [
        novo_item(n, criado=datetime(2026, 10, 1), fechado=datetime(2026, 10, 1 + dias))
        for n, dias in enumerate([1, 2, 3, 4, 10], start=1)
    ]

    resumo = cycle_time(itens)

    assert resumo.quantidade == 5
    assert resumo.mediana_dias == pytest.approx(3.0)
    assert resumo.p85_dias == pytest.approx(6.4)  # 4 + 0,4 × (10 − 4)


def test_cycle_time_ignora_itens_nao_concluidos(novo_item):
    itens = [
        novo_item(1, criado=datetime(2026, 10, 1), fechado=datetime(2026, 10, 3)),
        novo_item(2),
        novo_item(3, fechado=datetime(2026, 10, 20), estado="open"),
        novo_item(4, tipo="pull_request", fechado=datetime(2026, 10, 20)),
    ]

    resumo = cycle_time(itens)

    assert resumo.quantidade == 1
    assert resumo.mediana_dias == pytest.approx(2.0)


def test_cycle_time_filtra_pelo_periodo_de_conclusao(novo_item):
    itens = [
        novo_item(1, criado=datetime(2026, 9, 1), fechado=datetime(2026, 9, 30)),
        novo_item(2, criado=datetime(2026, 10, 1), fechado=datetime(2026, 10, 2)),
    ]

    resumo = cycle_time(itens, inicio=date(2026, 10, 1), fim=date(2026, 10, 31))

    assert resumo.quantidade == 1
    assert resumo.mediana_dias == pytest.approx(1.0)


def test_cycle_time_sem_itens(novo_item):
    assert cycle_time([]) == cycle_time([novo_item()])
    assert cycle_time([]).mediana_dias is None
    assert cycle_time([]).p85_dias is None
