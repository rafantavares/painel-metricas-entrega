"""Cliente mínimo da API REST do GitHub, com paginação e tratamento de rate limit."""

import time
from collections.abc import Callable, Iterator
from datetime import UTC, datetime
from typing import Any

import httpx

URL_API = "https://api.github.com"
VERSAO_API = "2022-11-28"


class ErroGitHub(RuntimeError):
    """Falha definitiva ao consultar a API do GitHub."""


class ClienteGitHub:
    """Faz requisições à API do GitHub, repetindo quando há rate limit ou erro temporário.

    `transporte` e `dormir` existem para que os testes substituam a rede e o relógio.
    """

    def __init__(
        self,
        token: str | None = None,
        *,
        url_base: str = URL_API,
        max_tentativas: int = 5,
        espera_inicial: float = 1.0,
        transporte: httpx.BaseTransport | None = None,
        dormir: Callable[[float], None] = time.sleep,
        agora: Callable[[], float] = time.time,
    ) -> None:
        cabecalhos = {
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": VERSAO_API,
            "User-Agent": "painel-metricas-entrega",
        }
        if token:
            cabecalhos["Authorization"] = f"Bearer {token}"
        self._http = httpx.Client(
            base_url=url_base, headers=cabecalhos, timeout=30.0, transport=transporte
        )
        self._max_tentativas = max_tentativas
        self._espera_inicial = espera_inicial
        self._dormir = dormir
        self._agora = agora

    def fechar(self) -> None:
        self._http.close()

    def __enter__(self) -> "ClienteGitHub":
        return self

    def __exit__(self, *_: object) -> None:
        self.fechar()

    def _espera_rate_limit(self, resposta: httpx.Response) -> float | None:
        """Segundos a aguardar se a resposta indica rate limit; `None` caso contrário."""
        if resposta.status_code not in (403, 429):
            return None
        if "Retry-After" in resposta.headers:
            return float(resposta.headers["Retry-After"])
        if resposta.headers.get("X-RateLimit-Remaining") == "0":
            reinicio = float(resposta.headers.get("X-RateLimit-Reset", self._agora()))
            return max(reinicio - self._agora(), 0) + 1
        return None

    def requisitar(self, url: str, params: dict[str, Any] | None = None) -> httpx.Response:
        """Faz um GET, repetindo com backoff em rate limit, erros 5xx e falhas de rede."""
        espera_backoff = self._espera_inicial
        for tentativa in range(1, self._max_tentativas + 1):
            ultima = tentativa == self._max_tentativas
            try:
                resposta = self._http.get(url, params=params)
            except httpx.TransportError as erro:
                if ultima:
                    raise ErroGitHub(f"Falha de rede ao acessar {url}: {erro}") from erro
                self._dormir(espera_backoff)
                espera_backoff *= 2
                continue

            espera = self._espera_rate_limit(resposta)
            temporario = resposta.status_code == 429 or resposta.status_code >= 500
            if espera is None and not temporario:
                if resposta.is_error:
                    raise ErroGitHub(
                        f"GitHub respondeu {resposta.status_code} para {url}: {resposta.text}"
                    )
                return resposta

            if ultima:
                break
            if espera is None:
                espera = espera_backoff
                espera_backoff *= 2
            self._dormir(espera)

        raise ErroGitHub(f"Desistindo de {url} após {self._max_tentativas} tentativas.")

    def paginar(
        self, url: str, params: dict[str, Any] | None = None, chave: str | None = None
    ) -> Iterator[dict[str, Any]]:
        """Percorre todas as páginas de um endpoint de listagem seguindo o cabeçalho `Link`.

        `chave` indica onde está a lista quando a resposta é um objeto
        (ex.: `workflow_runs`), e não uma lista direta.
        """
        proxima: str | None = url
        while proxima:
            resposta = self.requisitar(proxima, params)
            dados = resposta.json()
            yield from (dados[chave] if chave else dados)
            proxima = resposta.links.get("next", {}).get("url")
            params = None  # a URL `next` já traz os parâmetros

    def listar_issues(
        self, repositorio: str, desde: datetime | None = None
    ) -> Iterator[dict[str, Any]]:
        """Lista issues e pull requests do repositório, opcionalmente só os alterados `desde`.

        O endpoint `/issues` devolve os dois tipos; PRs vêm com a chave `pull_request`.
        """
        params: dict[str, Any] = {
            "state": "all",
            "sort": "updated",
            "direction": "asc",
            "per_page": 100,
        }
        if desde is not None:
            params["since"] = _formatar_data(desde)
        yield from self.paginar(f"/repos/{repositorio}/issues", params)

    def listar_releases(self, repositorio: str) -> Iterator[dict[str, Any]]:
        """Lista as releases do repositório, incluindo rascunhos e pré-releases."""
        yield from self.paginar(f"/repos/{repositorio}/releases", {"per_page": 100})

    def listar_milestones(self, repositorio: str) -> Iterator[dict[str, Any]]:
        """Lista os milestones do repositório, abertos e fechados."""
        yield from self.paginar(
            f"/repos/{repositorio}/milestones", {"state": "all", "per_page": 100}
        )

    def listar_tags(self, repositorio: str) -> Iterator[dict[str, Any]]:
        """Lista as tags do repositório (nome e SHA do commit, sem data)."""
        yield from self.paginar(f"/repos/{repositorio}/tags", {"per_page": 100})

    def obter_commit(self, repositorio: str, sha: str) -> dict[str, Any]:
        """Detalhes de um commit, usados para datar uma tag."""
        return self.requisitar(f"/repos/{repositorio}/commits/{sha}").json()

    def listar_execucoes_workflow(
        self,
        repositorio: str,
        workflow: str,
        branch: str,
        desde: datetime | None = None,
    ) -> Iterator[dict[str, Any]]:
        """Lista as execuções bem-sucedidas de um workflow na branch, opcionalmente `desde`."""
        params: dict[str, Any] = {"branch": branch, "status": "success", "per_page": 100}
        if desde is not None:
            params["created"] = f">={_formatar_data(desde)}"
        yield from self.paginar(
            f"/repos/{repositorio}/actions/workflows/{workflow}/runs", params, chave="workflow_runs"
        )


def _formatar_data(data: datetime) -> str:
    """Data no formato ISO 8601 em UTC aceito pela API. Datas sem fuso são tratadas como UTC."""
    if data.tzinfo is None:
        data = data.replace(tzinfo=UTC)
    return data.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
