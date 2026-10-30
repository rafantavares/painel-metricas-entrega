"""Executa o dashboard com o `AppTest` do Streamlit, sem navegador."""

from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

from painel.coleta.armazenamento import conectar, gravar_deploys, gravar_itens
from painel.coleta.normalizacao import Deploy

APP = str(Path(__file__).parents[1] / "app" / "dashboard.py")
REPO = "dono/repo"


@pytest.fixture
def banco(tmp_path, monkeypatch, novo_item):
    """Banco com algumas semanas de itens e deploys recentes, apontado por PAINEL_BANCO."""
    agora = datetime.now(UTC).replace(tzinfo=None, microsecond=0)
    itens = []
    deploys = []
    for n in range(1, 11):
        criado = agora - timedelta(days=40 - 3 * n)
        mesclado = criado + timedelta(days=1)
        itens.append(
            novo_item(n, tipo="pull_request", criado=criado, fechado=mesclado, mesclado=mesclado)
        )
        deploys.append(Deploy(REPO, "release", f"v{n}", None, mesclado + timedelta(hours=2)))
    itens.append(novo_item(20, criado=agora - timedelta(days=60)))  # aberta e envelhecida
    itens.append(
        novo_item(
            21,
            labels=("incidente",),
            criado=agora - timedelta(days=5),
            fechado=agora - timedelta(days=5) + timedelta(hours=3),
        )
    )
    itens = [item.__class__(**{**item.__dict__, "repositorio": REPO}) for item in itens]

    caminho = tmp_path / "painel.duckdb"
    conexao = conectar(caminho)
    gravar_itens(conexao, itens)
    gravar_deploys(conexao, deploys)
    conexao.close()

    monkeypatch.setenv("PAINEL_BANCO", str(caminho))
    monkeypatch.setenv("PAINEL_REPOSITORIOS", REPO)
    monkeypatch.chdir(tmp_path)  # garante que nenhum .env do projeto interfira
    return caminho


def rodar(pagina: str | None = None) -> AppTest:
    app = AppTest.from_file(APP, default_timeout=30)
    app.run()
    if pagina is not None:
        app.switch_page(f"paginas/{pagina}.py")
        app.run()
    assert not app.exception, app.exception
    return app


def test_visao_geral_mostra_indicadores_e_dora(banco):
    app = rodar()

    rotulos = [metrica.label for metrica in app.metric]
    assert "Itens concluídos" in rotulos
    assert app.metric[0].value == "11"  # 10 PRs + o incidente fechado
    assert any("DORA" in sub.value for sub in app.subheader)


@pytest.mark.parametrize("pagina", ["fluxo", "dora"])
def test_paginas_abrem_sem_erro(banco, pagina):
    app = rodar(pagina)

    assert app.title[0].value.endswith(pagina.upper() if pagina == "dora" else "Fluxo")


def test_sem_banco_orienta_a_rodar_o_coletor(tmp_path, monkeypatch):
    monkeypatch.setenv("PAINEL_BANCO", str(tmp_path / "inexistente.duckdb"))
    monkeypatch.chdir(tmp_path)

    app = rodar()

    assert "python -m painel.coletar" in app.info[0].value


def test_banco_vazio_orienta_a_rodar_o_coletor(tmp_path, monkeypatch):
    caminho = tmp_path / "vazio.duckdb"
    conectar(caminho).close()
    monkeypatch.setenv("PAINEL_BANCO", str(caminho))
    monkeypatch.chdir(tmp_path)

    app = rodar()

    assert "ainda não tem itens" in app.info[0].value
