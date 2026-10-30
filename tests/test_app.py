"""Executa o dashboard com o `AppTest` do Streamlit, sem navegador."""

import shutil
from datetime import UTC, datetime, timedelta
from pathlib import Path

import httpx
import pytest
from streamlit.testing.v1 import AppTest

import painel.publicacao
from painel.coleta.armazenamento import (
    conectar,
    gravar_deploys,
    gravar_itens,
    substituir_milestones,
)
from painel.coleta.normalizacao import Deploy, Milestone

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
            novo_item(
                n,
                tipo="pull_request",
                criado=criado,
                fechado=mesclado,
                mesclado=mesclado,
                milestone="Sprint 1",
            )
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
    sprint = Milestone(
        REPO,
        1,
        "Sprint 1",
        "open",
        agora - timedelta(days=45),
        (agora - timedelta(days=5)).date(),
        None,
    )
    substituir_milestones(conexao, REPO, [sprint])
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


@pytest.mark.parametrize(
    ("pagina", "titulo"), [("fluxo", "Fluxo"), ("dora", "DORA"), ("planejamento", "Planejamento")]
)
def test_paginas_abrem_sem_erro(banco, pagina, titulo):
    app = rodar(pagina)

    assert app.title[0].value.endswith(titulo)


def test_planejamento_mostra_burndown_e_previsibilidade(banco):
    app = rodar("planejamento")

    metricas = {metrica.label: metrica.value for metrica in app.metric}
    assert metricas["Itens no milestone"] == "10"
    assert metricas["Entregues no prazo"] == "10"
    assert metricas["Índice de previsibilidade"] == "100%"


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


def test_com_url_baixa_o_banco_publicado_antes_de_abrir(banco, tmp_path, monkeypatch):
    destino = tmp_path / "baixado" / "painel.duckdb"
    urls = []

    def baixar_falso(url, caminho, *args, **kwargs):
        urls.append(url)
        caminho.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy(banco, caminho)
        return True

    monkeypatch.setattr(painel.publicacao, "baixar_banco", baixar_falso)
    monkeypatch.setenv("PAINEL_BANCO", str(destino))
    monkeypatch.setenv("PAINEL_BANCO_URL", "https://exemplo/painel.duckdb")

    app = rodar()

    assert urls == ["https://exemplo/painel.duckdb"]
    assert app.metric[0].value == "11"


def test_falha_no_download_sem_copia_local_mostra_erro(tmp_path, monkeypatch):
    def baixar_falho(url, caminho, *args, **kwargs):
        raise httpx.ConnectError("sem rede")

    monkeypatch.setattr(painel.publicacao, "baixar_banco", baixar_falho)
    monkeypatch.setenv("PAINEL_BANCO", str(tmp_path / "painel.duckdb"))
    monkeypatch.setenv("PAINEL_BANCO_URL", "https://exemplo/falha.duckdb")
    monkeypatch.chdir(tmp_path)

    app = rodar()

    assert "Não foi possível baixar" in app.error[0].value
