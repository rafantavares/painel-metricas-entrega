from datetime import datetime

from painel.coleta.normalizacao import converter_data, normalizar_item


def test_converter_data_para_utc_sem_fuso():
    assert converter_data("2026-10-29T21:55:08Z") == datetime(2026, 10, 29, 21, 55, 8)
    assert converter_data("2026-10-29T18:55:08-03:00") == datetime(2026, 10, 29, 21, 55, 8)
    assert converter_data(None) is None


def test_normaliza_issue(item_api):
    dados = item_api(7, labels=("bug", "metricas"), milestone="M1 – Fundação")

    item = normalizar_item("dono/repo", dados)

    assert item.repositorio == "dono/repo"
    assert item.numero == 7
    assert item.tipo == "issue"
    assert item.estado == "open"
    assert item.criado_em == datetime(2026, 10, 1, 10, 0)
    assert item.fechado_em is None
    assert item.mesclado_em is None
    assert item.labels == ("bug", "metricas")
    assert item.milestone == "M1 – Fundação"


def test_normaliza_pull_request_mesclado(item_api):
    dados = item_api(
        8,
        pr=True,
        estado="closed",
        fechado="2026-10-02T09:00:00Z",
        mesclado="2026-10-02T09:00:00Z",
    )

    item = normalizar_item("dono/repo", dados)

    assert item.tipo == "pull_request"
    assert item.fechado_em == datetime(2026, 10, 2, 9, 0)
    assert item.mesclado_em == datetime(2026, 10, 2, 9, 0)
    assert item.milestone is None


def test_pull_request_fechado_sem_merge(item_api):
    item = normalizar_item("dono/repo", item_api(9, pr=True, estado="closed"))

    assert item.tipo == "pull_request"
    assert item.mesclado_em is None
