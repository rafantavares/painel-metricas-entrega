from datetime import datetime

import httpx
import pytest

from painel.coleta.armazenamento import conectar
from painel.coleta.deploys import coletar_deploys
from painel.coleta.github import ClienteGitHub
from painel.config import RegraDeploy

REPO = "dono/repo"


class ApiFalsa:
    """Simula os endpoints de releases, tags, commits e execuções de workflow."""

    def __init__(self):
        self.releases = []
        self.tags = []
        self.datas_commit = {}
        self.execucoes = []
        self.requisicoes = []

    def __call__(self, requisicao):
        self.requisicoes.append(requisicao)
        caminho = requisicao.url.path
        if caminho.endswith("/releases"):
            return httpx.Response(200, json=self.releases)
        if caminho.endswith("/tags"):
            return httpx.Response(200, json=self.tags)
        if "/commits/" in caminho:
            sha = caminho.rsplit("/", 1)[1]
            data = self.datas_commit[sha]
            return httpx.Response(200, json={"sha": sha, "commit": {"committer": {"date": data}}})
        if "/actions/workflows/" in caminho:
            criado = requisicao.url.params.get("created", ">=").removeprefix(">=")
            execucoes = [e for e in self.execucoes if e["created_at"] >= criado]
            return httpx.Response(200, json={"workflow_runs": execucoes})
        return httpx.Response(404)

    def caminhos(self):
        return [requisicao.url.path for requisicao in self.requisicoes]


@pytest.fixture
def api():
    return ApiFalsa()


@pytest.fixture
def cliente(api):
    return ClienteGitHub(transporte=httpx.MockTransport(api))


@pytest.fixture
def conexao():
    conexao = conectar(":memory:")
    yield conexao
    conexao.close()


def deploys_gravados(conexao):
    return conexao.execute(
        "SELECT regra, identificador, sha, implantado_em FROM bruta_deploys ORDER BY implantado_em"
    ).fetchall()


def release(tag, publicada, **extra):
    return {"tag_name": tag, "draft": False, "prerelease": False, "published_at": publicada} | extra


def execucao(numero, criada, terminada, conclusao="success"):
    return {
        "id": numero,
        "conclusion": conclusao,
        "head_sha": f"sha{numero}",
        "created_at": criada,
        "updated_at": terminada,
    }


def test_regra_release_grava_so_releases_publicadas_e_nao_duplica(api, cliente, conexao):
    api.releases = [
        release("v1.1", "2026-10-20T10:00:00Z"),
        release("v1.1-rc", "2026-10-18T10:00:00Z", prerelease=True),
        release("v1.0", "2026-10-10T10:00:00Z"),
    ]

    coletar_deploys(cliente, conexao, REPO, RegraDeploy("release"))
    coletar_deploys(cliente, conexao, REPO, RegraDeploy("release"))

    assert deploys_gravados(conexao) == [
        ("release", "v1.0", None, datetime(2026, 10, 10, 10)),
        ("release", "v1.1", None, datetime(2026, 10, 20, 10)),
    ]


def test_regra_tag_filtra_pelo_padrao_e_so_data_tags_novas(api, cliente, conexao):
    regra = RegraDeploy("tag", filtro="v*")
    api.tags = [
        {"name": "v1.0", "commit": {"sha": "a1"}},
        {"name": "experimento", "commit": {"sha": "b2"}},
    ]
    api.datas_commit = {"a1": "2026-10-10T09:00:00Z", "b2": "2026-10-11T09:00:00Z"}
    coletar_deploys(cliente, conexao, REPO, regra)

    api.tags.insert(0, {"name": "v1.1", "commit": {"sha": "c3"}})
    api.datas_commit["c3"] = "2026-10-15T09:00:00Z"
    api.requisicoes.clear()
    coletar_deploys(cliente, conexao, REPO, regra)

    assert [d[1] for d in deploys_gravados(conexao)] == ["v1.0", "v1.1"]
    commits_consultados = [c for c in api.caminhos() if "/commits/" in c]
    assert commits_consultados == ["/repos/dono/repo/commits/c3"]  # v1.0 já era conhecida


def test_regra_workflow_e_incremental_com_folga_e_sem_duplicar(api, cliente, conexao):
    regra = RegraDeploy("workflow", filtro="deploy.yml", branch="main")
    api.execucoes = [
        execucao(1, "2026-10-10T10:00:00Z", "2026-10-10T10:05:00Z"),
        execucao(2, "2026-10-12T10:00:00Z", "2026-10-12T10:05:00Z"),
    ]
    coletar_deploys(cliente, conexao, REPO, regra)

    api.execucoes.append(execucao(3, "2026-10-14T10:00:00Z", "2026-10-14T10:06:00Z"))
    api.requisicoes.clear()
    coletar_deploys(cliente, conexao, REPO, regra)

    (requisicao,) = api.requisicoes
    assert requisicao.url.params["created"] == ">=2026-10-11T10:05:00Z"  # último deploy − 1 dia
    assert [d[1] for d in deploys_gravados(conexao)] == ["1", "2", "3"]
    assert deploys_gravados(conexao)[0][2] == "sha1"


def test_execucoes_sem_sucesso_nao_sao_gravadas(api, cliente, conexao):
    api.execucoes = [execucao(1, "2026-10-10T10:00:00Z", "2026-10-10T10:05:00Z", "failure")]

    gravados = coletar_deploys(cliente, conexao, REPO, RegraDeploy("workflow", filtro="x.yml"))

    assert gravados == 0
    assert deploys_gravados(conexao) == []


def test_trocar_a_regra_remove_os_deploys_da_regra_anterior(api, cliente, conexao):
    api.releases = [release("v1.0", "2026-10-10T10:00:00Z")]
    coletar_deploys(cliente, conexao, REPO, RegraDeploy("release"))

    api.tags = [{"name": "v1.0", "commit": {"sha": "a1"}}]
    api.datas_commit = {"a1": "2026-10-09T09:00:00Z"}
    coletar_deploys(cliente, conexao, REPO, RegraDeploy("tag", filtro="v*"))

    assert deploys_gravados(conexao) == [("tag:v*", "v1.0", "a1", datetime(2026, 10, 9, 9))]


def test_repositorios_diferentes_nao_interferem(api, cliente, conexao):
    api.releases = [release("v1.0", "2026-10-10T10:00:00Z")]

    coletar_deploys(cliente, conexao, "dono/um", RegraDeploy("release"))
    coletar_deploys(cliente, conexao, "dono/dois", RegraDeploy("tag"))

    total = conexao.execute("SELECT count(*) FROM bruta_deploys").fetchone()[0]
    assert total == 1  # a regra de "dono/dois" não apagou os deploys de "dono/um"
