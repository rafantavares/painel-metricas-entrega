from datetime import datetime

import pytest

from painel.coleta.normalizacao import (
    converter_data,
    normalizar_execucao_workflow,
    normalizar_item,
    normalizar_release,
    normalizar_tag,
    tag_casa_com_padrao,
)


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


# --- Deploys ----------------------------------------------------------------------------


def test_release_publicada_vira_deploy():
    dados = {
        "tag_name": "v1.0",
        "draft": False,
        "prerelease": False,
        "published_at": "2026-10-10T12:00:00Z",
    }

    deploy = normalizar_release("dono/repo", "release", dados)

    assert deploy.identificador == "v1.0"
    assert deploy.implantado_em == datetime(2026, 10, 10, 12)
    assert deploy.regra == "release"


@pytest.mark.parametrize(
    "extra",
    [{"draft": True}, {"prerelease": True}, {"published_at": None}],
)
def test_rascunho_pre_release_e_nao_publicada_sao_ignoradas(extra):
    dados = {
        "tag_name": "v1.0",
        "draft": False,
        "prerelease": False,
        "published_at": "2026-10-10T12:00:00Z",
    } | extra

    assert normalizar_release("dono/repo", "release", dados) is None


def test_tag_e_datada_pelo_commit():
    tag = {"name": "v2.0", "commit": {"sha": "abc123"}}
    commit = {"commit": {"committer": {"date": "2026-10-11T08:30:00Z"}}}

    deploy = normalizar_tag("dono/repo", "tag:v*", tag, commit)

    assert deploy.identificador == "v2.0"
    assert deploy.sha == "abc123"
    assert deploy.implantado_em == datetime(2026, 10, 11, 8, 30)


@pytest.mark.parametrize(
    ("nome", "padrao", "casa"),
    [("v1.2.3", "v*", True), ("release-1", "v*", False), ("V1", "v*", False), ("x", "*", True)],
)
def test_tag_casa_com_padrao(nome, padrao, casa):
    assert tag_casa_com_padrao(nome, padrao) is casa


def test_execucao_bem_sucedida_vira_deploy_no_fim_da_execucao():
    dados = {
        "id": 42,
        "conclusion": "success",
        "head_sha": "def456",
        "created_at": "2026-10-12T10:00:00Z",
        "updated_at": "2026-10-12T10:07:00Z",
    }

    deploy = normalizar_execucao_workflow("dono/repo", "workflow:deploy.yml@main", dados)

    assert deploy.identificador == "42"
    assert deploy.sha == "def456"
    assert deploy.implantado_em == datetime(2026, 10, 12, 10, 7)


@pytest.mark.parametrize("conclusao", ["failure", "cancelled", None])
def test_execucao_sem_sucesso_e_ignorada(conclusao):
    dados = {"id": 42, "conclusion": conclusao, "updated_at": "2026-10-12T10:07:00Z"}

    assert normalizar_execucao_workflow("dono/repo", "workflow:x.yml@main", dados) is None
