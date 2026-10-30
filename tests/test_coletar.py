from datetime import datetime

import httpx
import pytest

from painel.coleta.armazenamento import (
    conectar,
    gravar_deploys,
    ler_deploys,
    ler_itens,
    ler_ultima_atualizacao,
    listar_repositorios,
)
from painel.coleta.github import ClienteGitHub
from painel.coleta.normalizacao import Deploy
from painel.coletar import coletar_repositorio

REPO = "dono/repo"


class ApiFalsa:
    """Simula o endpoint `/issues`, aplicando o filtro `since` sobre os itens cadastrados."""

    def __init__(self, itens):
        self.itens = itens
        self.parametros_recebidos = []

    def __call__(self, requisicao):
        self.parametros_recebidos.append(dict(requisicao.url.params))
        desde = requisicao.url.params.get("since")
        itens = [item for item in self.itens if desde is None or item["updated_at"] >= desde]
        return httpx.Response(200, json=itens)


@pytest.fixture
def conexao():
    conexao = conectar(":memory:")
    yield conexao
    conexao.close()


def contar(conexao):
    return conexao.execute("SELECT count(*) FROM bruta_itens").fetchone()[0]


def test_primeira_execucao_grava_tudo(conexao, item_api):
    api = ApiFalsa(
        [
            item_api(1, atualizado="2026-10-01T12:00:00Z", labels=("bug",)),
            item_api(
                2, atualizado="2026-10-02T12:00:00Z", pr=True, mesclado="2026-10-02T12:00:00Z"
            ),
        ]
    )

    gravados = coletar_repositorio(
        ClienteGitHub(transporte=httpx.MockTransport(api)), conexao, REPO
    )

    assert gravados == 2
    assert contar(conexao) == 2
    assert "since" not in api.parametros_recebidos[0]
    assert ler_ultima_atualizacao(conexao, REPO) == datetime(2026, 10, 2, 12, 0)
    labels, tipo = conexao.execute(
        "SELECT labels, tipo FROM bruta_itens WHERE numero = 1"
    ).fetchone()
    assert labels == ["bug"]
    assert tipo == "issue"


def test_segunda_execucao_e_incremental_e_nao_duplica(conexao, item_api):
    api = ApiFalsa(
        [
            item_api(1, atualizado="2026-10-01T12:00:00Z"),
            item_api(2, atualizado="2026-10-02T12:00:00Z"),
        ]
    )
    cliente = ClienteGitHub(transporte=httpx.MockTransport(api))
    coletar_repositorio(cliente, conexao, REPO)

    # Entre as execuções, o item 1 é fechado e surge o item 3.
    api.itens = [
        item_api(
            1, atualizado="2026-10-03T08:00:00Z", estado="closed", fechado="2026-10-03T08:00:00Z"
        ),
        item_api(2, atualizado="2026-10-02T12:00:00Z"),
        item_api(3, atualizado="2026-10-03T09:00:00Z"),
    ]
    coletar_repositorio(cliente, conexao, REPO)

    assert api.parametros_recebidos[1]["since"] == "2026-10-02T12:00:00Z"
    assert contar(conexao) == 3
    estado = conexao.execute("SELECT estado FROM bruta_itens WHERE numero = 1").fetchone()[0]
    assert estado == "closed"
    assert ler_ultima_atualizacao(conexao, REPO) == datetime(2026, 10, 3, 9, 0)


def test_execucao_sem_novidades_mantem_o_controle(conexao, item_api):
    api = ApiFalsa([item_api(1, atualizado="2026-10-01T12:00:00Z")])
    cliente = ClienteGitHub(transporte=httpx.MockTransport(api))
    coletar_repositorio(cliente, conexao, REPO)

    api.itens = []
    gravados = coletar_repositorio(cliente, conexao, REPO)

    assert gravados == 0
    assert contar(conexao) == 1
    assert ler_ultima_atualizacao(conexao, REPO) == datetime(2026, 10, 1, 12, 0)


def test_repositorios_nao_se_misturam(conexao, item_api):
    api = ApiFalsa([item_api(1)])
    cliente = ClienteGitHub(transporte=httpx.MockTransport(api))

    coletar_repositorio(cliente, conexao, "dono/um")
    coletar_repositorio(cliente, conexao, "dono/dois")

    assert contar(conexao) == 2


def test_banco_em_arquivo_persiste_entre_conexoes(tmp_path, item_api):
    caminho = tmp_path / "dados" / "painel.duckdb"
    api = ApiFalsa([item_api(1)])

    conexao = conectar(caminho)
    coletar_repositorio(ClienteGitHub(transporte=httpx.MockTransport(api)), conexao, REPO)
    conexao.close()

    conexao = conectar(caminho)
    assert contar(conexao) == 1
    conexao.close()


def test_leitura_dos_itens_e_deploys_gravados(conexao, item_api):
    api = ApiFalsa([item_api(1, labels=("bug", "metricas")), item_api(2, pr=True)])
    cliente = ClienteGitHub(transporte=httpx.MockTransport(api))
    coletar_repositorio(cliente, conexao, "dono/um")
    coletar_repositorio(cliente, conexao, "dono/dois")
    gravar_deploys(conexao, [Deploy("dono/um", "release", "v1", None, datetime(2026, 10, 5))])

    assert listar_repositorios(conexao) == ["dono/dois", "dono/um"]
    itens = ler_itens(conexao, ["dono/um"])
    assert [(i.repositorio, i.numero, i.tipo) for i in itens] == [
        ("dono/um", 1, "issue"),
        ("dono/um", 2, "pull_request"),
    ]
    assert itens[0].labels == ("bug", "metricas")
    assert len(ler_itens(conexao)) == 4
    assert [d.identificador for d in ler_deploys(conexao, ["dono/um"])] == ["v1"]
    assert ler_deploys(conexao, ["dono/dois"]) == []
