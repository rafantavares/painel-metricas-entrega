from datetime import date, datetime

import pandas as pd
import pytest

from painel import visualizacao as vis
from painel.coleta.normalizacao import Deploy


def deploy(repositorio, momento):
    return Deploy(repositorio, "release", momento.isoformat(), None, momento)


def no_repo(item, repositorio):
    return item.__class__(**{**item.__dict__, "repositorio": repositorio})


def test_throughput_vira_tabela_com_semanas_vazias(novo_item):
    itens = [
        novo_item(1, fechado=datetime(2026, 10, 5)),
        novo_item(2, fechado=datetime(2026, 10, 19)),
    ]

    tabela = vis.tabela_throughput(itens, date(2026, 10, 5), date(2026, 10, 25))

    assert tabela.to_dict("list") == {
        "semana": [date(2026, 10, 5), date(2026, 10, 12), date(2026, 10, 19)],
        "concluidos": [1, 0, 1],
    }


def test_concluidos_lista_cada_item_com_cycle_time(novo_item):
    itens = [
        novo_item(1, criado=datetime(2026, 10, 1), fechado=datetime(2026, 10, 3)),
        novo_item(
            2,
            tipo="pull_request",
            criado=datetime(2026, 10, 1),
            fechado=datetime(2026, 10, 2),
            mesclado=datetime(2026, 10, 2),
        ),
        novo_item(3, criado=datetime(2026, 9, 1), fechado=datetime(2026, 9, 2)),  # fora
        novo_item(4),  # aberto
    ]

    tabela = vis.tabela_concluidos(itens, date(2026, 10, 1), date(2026, 10, 31))

    assert tabela["numero"].tolist() == [1, 2]
    assert tabela["tipo"].tolist() == ["Issue", "Pull request"]
    assert tabela["cycle_time_dias"].tolist() == pytest.approx([2.0, 1.0])


def test_concluidos_filtra_por_tipo_e_tem_colunas_mesmo_vazio(novo_item):
    itens = [novo_item(1, criado=datetime(2026, 10, 1), fechado=datetime(2026, 10, 3))]

    tabela = vis.tabela_concluidos(itens, date(2026, 10, 1), date(2026, 10, 31), "pull_request")

    assert tabela.empty
    assert "cycle_time_dias" in tabela.columns


def test_wip_e_envelhecidos(novo_item):
    itens = [
        novo_item(1, criado=datetime(2026, 9, 1), fechado=datetime(2026, 9, 3)),  # 2 dias
        novo_item(2, criado=datetime(2026, 10, 1)),  # aberto há 30 dias
    ]

    wip = vis.tabela_wip(itens, date(2026, 10, 30), date(2026, 10, 31))
    envelhecidos = vis.tabela_envelhecidos(itens, datetime(2026, 10, 31))

    assert wip["em_andamento"].tolist() == [1, 1]
    assert envelhecidos["numero"].tolist() == [2]
    assert envelhecidos["idade_dias"].tolist() == pytest.approx([30.0])


def test_envelhecidos_vazio_mantem_colunas():
    assert list(vis.tabela_envelhecidos([], datetime(2026, 10, 31)).columns) == [
        "repositorio",
        "numero",
        "titulo",
        "tipo",
        "criado_em",
        "idade_dias",
    ]


def test_resumo_fluxo(novo_item):
    itens = [
        novo_item(1, criado=datetime(2026, 10, 5), fechado=datetime(2026, 10, 6)),
        novo_item(2, criado=datetime(2026, 10, 5), fechado=datetime(2026, 10, 8)),
        novo_item(3, criado=datetime(2026, 8, 1)),  # aberto e envelhecido
    ]

    resumo = vis.resumo_fluxo(itens, date(2026, 10, 5), date(2026, 10, 18), datetime(2026, 10, 18))

    assert resumo["concluidos"] == 2
    assert resumo["throughput_medio_semanal"] == pytest.approx(1.0)  # 2 itens em 2 semanas
    assert resumo["cycle_time_mediana_dias"] == pytest.approx(2.0)
    assert resumo["wip_atual"] == 1
    assert resumo["envelhecidos"] == 1


def test_dora_e_calculado_por_repositorio(novo_item):
    # O PR de "dono/b" é mesclado antes do deploy de "dono/a", mas não pode ser
    # atribuído a ele: cada repositório só olha os próprios deploys.
    pr_b = no_repo(
        novo_item(
            1,
            tipo="pull_request",
            criado=datetime(2026, 10, 1),
            fechado=datetime(2026, 10, 1, 12),
            mesclado=datetime(2026, 10, 1, 12),
        ),
        "dono/b",
    )
    deploys = [deploy("dono/a", datetime(2026, 10, 2)), deploy("dono/b", datetime(2026, 10, 11))]

    tabela = vis.tabela_dora([pr_b], deploys, date(2026, 10, 1), date(2026, 10, 31))

    assert tabela["repositorio"].tolist() == ["dono/a", "dono/b"]
    a, b = tabela.to_dict("records")
    assert a["lead_time"] == "sem dados"
    assert b["lead_time_mediana_dias"] == pytest.approx(10.0)
    assert b["lead_time"] == "médio"
    assert a["deploys"] == b["deploys"] == 1
    assert a["restauracao"] == "sem dados"
    assert pd.isna(a["restauracao_mediana_horas"])  # NaN, não None


def test_dora_sem_dados_tem_colunas():
    tabela = vis.tabela_dora([], [], date(2026, 10, 1), date(2026, 10, 31))

    assert tabela.empty
    assert list(tabela.columns) == vis.COLUNAS_DORA


def test_deploys_semanais_agrupa_por_semana_e_repositorio():
    deploys = [
        deploy("dono/a", datetime(2026, 10, 5)),
        deploy("dono/a", datetime(2026, 10, 7)),
        deploy("dono/b", datetime(2026, 10, 7)),
        deploy("dono/a", datetime(2026, 9, 1)),  # fora do período
    ]

    tabela = vis.tabela_deploys_semanais(deploys, date(2026, 10, 1), date(2026, 10, 31))

    registros = tabela.to_dict("records")
    assert {"semana": date(2026, 10, 5), "repositorio": "dono/a", "deploys": 2} in registros
    assert {"semana": date(2026, 10, 5), "repositorio": "dono/b", "deploys": 1} in registros
    # Semanas sem deploy aparecem com zero, para cada repositório com deploys no período.
    assert {"semana": date(2026, 10, 12), "repositorio": "dono/b", "deploys": 0} in registros
    assert len(registros) == 5 * 2  # semanas de 28/09 a 26/10 × 2 repositórios


def test_deploys_semanais_vazio():
    assert vis.tabela_deploys_semanais([], date(2026, 10, 1), date(2026, 10, 31)).empty
