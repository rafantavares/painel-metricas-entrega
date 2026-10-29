from datetime import UTC, datetime, timedelta, timezone

import httpx
import pytest

from painel.coleta.github import ClienteGitHub, ErroGitHub


def criar_cliente(tratador, esperas=None, **kwargs):
    """Cliente com rede e relógio falsos; as esperas pedidas são anotadas em `esperas`."""
    esperas = [] if esperas is None else esperas
    return ClienteGitHub(
        "token-de-teste",
        transporte=httpx.MockTransport(tratador),
        dormir=esperas.append,
        agora=lambda: 1_000.0,
        **kwargs,
    )


def test_envia_cabecalhos_e_parametros_da_listagem():
    requisicoes = []

    def tratador(requisicao):
        requisicoes.append(requisicao)
        return httpx.Response(200, json=[])

    desde = datetime(2026, 10, 29, 18, 0, tzinfo=timezone(timedelta(hours=-3)))
    list(criar_cliente(tratador).listar_issues("dono/repo", desde))

    (requisicao,) = requisicoes
    assert requisicao.url.path == "/repos/dono/repo/issues"
    assert requisicao.headers["Authorization"] == "Bearer token-de-teste"
    assert requisicao.url.params["state"] == "all"
    assert requisicao.url.params["since"] == "2026-10-29T21:00:00Z"


def test_data_sem_fuso_e_tratada_como_utc():
    requisicoes = []

    def tratador(requisicao):
        requisicoes.append(requisicao)
        return httpx.Response(200, json=[])

    list(criar_cliente(tratador).listar_issues("dono/repo", datetime(2026, 10, 29, 21, 0)))

    assert requisicoes[0].url.params["since"] == "2026-10-29T21:00:00Z"


def test_sem_token_nao_envia_autorizacao():
    def tratador(requisicao):
        assert "Authorization" not in requisicao.headers
        return httpx.Response(200, json=[])

    cliente = ClienteGitHub(transporte=httpx.MockTransport(tratador))
    assert list(cliente.listar_issues("dono/repo")) == []


def test_segue_paginacao_pelo_cabecalho_link():
    def tratador(requisicao):
        if requisicao.url.params.get("page") == "2":
            return httpx.Response(200, json=[{"number": 2}])
        proxima = "https://api.github.com/repos/dono/repo/issues?page=2"
        return httpx.Response(
            200, json=[{"number": 1}], headers={"Link": f'<{proxima}>; rel="next"'}
        )

    itens = list(criar_cliente(tratador).listar_issues("dono/repo"))

    assert [item["number"] for item in itens] == [1, 2]


def test_espera_retry_after_e_tenta_de_novo():
    respostas = iter(
        [
            httpx.Response(429, headers={"Retry-After": "7"}),
            httpx.Response(200, json=[{"number": 1}]),
        ]
    )
    esperas = []

    itens = list(criar_cliente(lambda _: next(respostas), esperas).listar_issues("dono/repo"))

    assert esperas == [7.0]
    assert len(itens) == 1


def test_espera_ate_o_reset_quando_a_cota_acaba():
    cabecalhos = {"X-RateLimit-Remaining": "0", "X-RateLimit-Reset": "1030"}
    respostas = iter([httpx.Response(403, headers=cabecalhos), httpx.Response(200, json=[])])
    esperas = []

    list(criar_cliente(lambda _: next(respostas), esperas).listar_issues("dono/repo"))

    assert esperas == [31.0]  # 30 s até o reset + 1 s de folga


def test_backoff_exponencial_em_erro_do_servidor():
    respostas = iter([httpx.Response(502), httpx.Response(503), httpx.Response(200, json=[])])
    esperas = []

    list(criar_cliente(lambda _: next(respostas), esperas).listar_issues("dono/repo"))

    assert esperas == [1.0, 2.0]


def test_repete_em_falha_de_rede():
    chamadas = []

    def tratador(requisicao):
        chamadas.append(requisicao)
        if len(chamadas) == 1:
            raise httpx.ConnectError("sem conexão", request=requisicao)
        return httpx.Response(200, json=[])

    esperas = []
    list(criar_cliente(tratador, esperas).listar_issues("dono/repo"))

    assert len(chamadas) == 2
    assert esperas == [1.0]


def test_desiste_apos_o_maximo_de_tentativas():
    esperas = []
    cliente = criar_cliente(lambda _: httpx.Response(500), esperas, max_tentativas=3)

    with pytest.raises(ErroGitHub, match="3 tentativas"):
        list(cliente.listar_issues("dono/repo"))
    assert esperas == [1.0, 2.0]


def test_erro_definitivo_nao_e_repetido():
    chamadas = []

    def tratador(requisicao):
        chamadas.append(requisicao)
        return httpx.Response(404, json={"message": "Not Found"})

    with pytest.raises(ErroGitHub, match="404"):
        list(criar_cliente(tratador).listar_issues("dono/inexistente"))
    assert len(chamadas) == 1


def test_403_sem_rate_limit_e_erro_definitivo():
    with pytest.raises(ErroGitHub, match="403"):
        list(criar_cliente(lambda _: httpx.Response(403)).listar_issues("dono/repo"))


def test_since_usa_utc_mesmo_com_fuso_local():
    requisicoes = []

    def tratador(requisicao):
        requisicoes.append(requisicao)
        return httpx.Response(200, json=[])

    list(criar_cliente(tratador).listar_issues("dono/repo", datetime(2026, 1, 1, tzinfo=UTC)))

    assert requisicoes[0].url.params["since"] == "2026-01-01T00:00:00Z"
