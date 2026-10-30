from datetime import date, datetime

import pytest

from painel.metricas.wip import ContagemDiaria, itens_envelhecidos, wip_diario

# --- WIP diário -------------------------------------------------------------------------


def test_wip_conta_itens_criados_e_ainda_nao_fechados_ao_fim_do_dia(novo_item):
    itens = [
        novo_item(1, criado=datetime(2026, 10, 1, 9), fechado=datetime(2026, 10, 3, 18)),
        novo_item(2, criado=datetime(2026, 10, 2, 15)),  # continua aberto
    ]

    assert wip_diario(itens, date(2026, 9, 30), date(2026, 10, 4)) == [
        ContagemDiaria(date(2026, 9, 30), 0),
        ContagemDiaria(date(2026, 10, 1), 1),
        ContagemDiaria(date(2026, 10, 2), 2),
        ContagemDiaria(date(2026, 10, 3), 1),  # item 1 fechou neste dia
        ContagemDiaria(date(2026, 10, 4), 1),
    ]


def test_item_criado_e_fechado_no_mesmo_dia_nao_entra_no_wip(novo_item):
    itens = [novo_item(criado=datetime(2026, 10, 1, 9), fechado=datetime(2026, 10, 1, 17))]

    assert wip_diario(itens, date(2026, 10, 1), date(2026, 10, 1)) == [
        ContagemDiaria(date(2026, 10, 1), 0)
    ]


def test_pr_fechado_sem_merge_sai_do_wip(novo_item):
    pr = novo_item(tipo="pull_request", criado=datetime(2026, 10, 1), fechado=datetime(2026, 10, 2))

    contagens = wip_diario([pr], date(2026, 10, 1), date(2026, 10, 3))

    assert [c.em_andamento for c in contagens] == [1, 0, 0]


def test_item_reaberto_conta_como_aberto_desde_a_criacao(novo_item):
    reaberto = novo_item(criado=datetime(2026, 10, 1), fechado=datetime(2026, 10, 2), estado="open")

    contagens = wip_diario([reaberto], date(2026, 10, 1), date(2026, 10, 3))

    assert [c.em_andamento for c in contagens] == [1, 1, 1]


def test_item_fechado_sem_data_fica_fora_do_wip(novo_item):
    contagens = wip_diario([novo_item(estado="closed")], date(2026, 10, 1), date(2026, 10, 2))

    assert [c.em_andamento for c in contagens] == [0, 0]


def test_wip_filtra_por_tipo(novo_item):
    itens = [novo_item(1), novo_item(2, tipo="pull_request")]

    contagens = wip_diario(itens, date(2026, 10, 1), date(2026, 10, 1), tipo="issue")

    assert contagens == [ContagemDiaria(date(2026, 10, 1), 1)]


def test_wip_periodo_invalido():
    with pytest.raises(ValueError):
        wip_diario([], date(2026, 10, 2), date(2026, 10, 1))


# --- Itens envelhecidos -----------------------------------------------------------------

REFERENCIA = datetime(2026, 10, 31)


def concluidos_com_cycle_time(novo_item, *dias: int) -> list:
    """Itens concluídos cujo cycle time, em dias, é cada valor de `dias`."""
    return [
        novo_item(100 + n, criado=datetime(2026, 9, 1), fechado=datetime(2026, 9, 1 + d))
        for n, d in enumerate(dias)
    ]


def test_lista_abertos_acima_do_p85_do_cycle_time_do_mais_antigo_ao_mais_novo(novo_item):
    # Cycle times de 1 a 10 dias: p85 = 8,65 dias.
    itens = concluidos_com_cycle_time(novo_item, *range(1, 11)) + [
        novo_item(1, criado=datetime(2026, 10, 26)),  # 5 dias: dentro do esperado
        novo_item(2, criado=datetime(2026, 10, 1)),  # 30 dias
        novo_item(3, criado=datetime(2026, 10, 21)),  # 10 dias
    ]

    envelhecidos = itens_envelhecidos(itens, REFERENCIA)

    assert [e.item.numero for e in envelhecidos] == [2, 3]
    assert envelhecidos[0].idade_dias == pytest.approx(30.0)
    assert envelhecidos[1].idade_dias == pytest.approx(10.0)


def test_limite_explicito_substitui_o_p85(novo_item):
    itens = [
        novo_item(1, criado=datetime(2026, 10, 28)),
        novo_item(2, criado=datetime(2026, 10, 30)),
    ]

    envelhecidos = itens_envelhecidos(itens, REFERENCIA, limite_dias=2)

    assert [e.item.numero for e in envelhecidos] == [1]


def test_item_exatamente_no_limite_nao_e_envelhecido(novo_item):
    itens = [novo_item(criado=datetime(2026, 10, 29))]

    assert itens_envelhecidos(itens, REFERENCIA, limite_dias=2) == []


def test_itens_fechados_nao_sao_envelhecidos(novo_item):
    itens = concluidos_com_cycle_time(novo_item, 1, 2, 3) + [
        novo_item(1, criado=datetime(2026, 1, 1), fechado=datetime(2026, 10, 30)),
        novo_item(
            2, tipo="pull_request", criado=datetime(2026, 1, 1), fechado=datetime(2026, 2, 1)
        ),
        novo_item(3, criado=datetime(2026, 1, 1), estado="closed"),  # fechado sem data
    ]

    assert itens_envelhecidos(itens, REFERENCIA) == []


def test_item_reaberto_e_avaliado_pela_idade_desde_a_criacao(novo_item):
    reaberto = novo_item(
        1, criado=datetime(2026, 10, 1), fechado=datetime(2026, 10, 2), estado="open"
    )

    envelhecidos = itens_envelhecidos([reaberto], REFERENCIA, limite_dias=10)

    assert [e.item.numero for e in envelhecidos] == [1]


def test_sem_itens_concluidos_nao_ha_limite_e_a_lista_fica_vazia(novo_item):
    itens = [novo_item(1, criado=datetime(2026, 1, 1))]

    assert itens_envelhecidos(itens, REFERENCIA) == []


def test_p85_e_calculado_so_com_o_tipo_filtrado(novo_item):
    itens = [
        # PRs rápidos (1 dia) e issues lentas (20 dias)
        novo_item(
            10,
            tipo="pull_request",
            criado=datetime(2026, 9, 1),
            fechado=datetime(2026, 9, 2),
            mesclado=datetime(2026, 9, 2),
        ),
        novo_item(11, criado=datetime(2026, 9, 1), fechado=datetime(2026, 9, 21)),
        novo_item(1, tipo="pull_request", criado=datetime(2026, 10, 26)),  # 5 dias
        novo_item(2, criado=datetime(2026, 10, 26)),  # 5 dias
    ]

    assert [e.item.numero for e in itens_envelhecidos(itens, REFERENCIA, tipo="pull_request")] == [
        1
    ]
    assert itens_envelhecidos(itens, REFERENCIA, tipo="issue") == []
