import os
from pathlib import Path

import pytest

from painel.config import RegraDeploy, carregar_configuracao, ler_regra_deploy

VARIAVEIS = (
    "GITHUB_TOKEN",
    "PAINEL_REPOSITORIOS",
    "PAINEL_BANCO",
    "PAINEL_REGRAS_DEPLOY",
    "PAINEL_BANCO_URL",
)


@pytest.fixture(autouse=True)
def ambiente_limpo(monkeypatch):
    # Cópia isolada do ambiente: o que o `load_dotenv` escrever não vaza para outros testes.
    ambiente = {chave: valor for chave, valor in os.environ.items() if chave not in VARIAVEIS}
    monkeypatch.setattr(os, "environ", ambiente)


def test_valores_padrao_sem_env():
    config = carregar_configuracao(arquivo_env=None)

    assert config.github_token is None
    assert config.repositorios == ()
    assert config.caminho_banco == Path("data/painel.duckdb")


def test_le_arquivo_env(tmp_path):
    arquivo = tmp_path / ".env"
    arquivo.write_text(
        "GITHUB_TOKEN=abc\nPAINEL_REPOSITORIOS= dono/um , dono/dois ,\nPAINEL_BANCO=x.duckdb\n"
    )

    config = carregar_configuracao(arquivo)

    assert config.github_token == "abc"
    assert config.repositorios == ("dono/um", "dono/dois")
    assert config.caminho_banco == Path("x.duckdb")


def test_ambiente_tem_prioridade_sobre_arquivo(tmp_path, monkeypatch):
    arquivo = tmp_path / ".env"
    arquivo.write_text("PAINEL_REPOSITORIOS=dono/arquivo\n")
    monkeypatch.setenv("PAINEL_REPOSITORIOS", "dono/ambiente")

    config = carregar_configuracao(arquivo)

    assert config.repositorios == ("dono/ambiente",)


@pytest.mark.parametrize("valor", ["sem-barra", "/repo", "dono/", "a/b/c"])
def test_repositorio_invalido(monkeypatch, valor):
    monkeypatch.setenv("PAINEL_REPOSITORIOS", valor)

    with pytest.raises(ValueError, match="dono/repo"):
        carregar_configuracao(arquivo_env=None)


# --- Regras de deploy -------------------------------------------------------------------


@pytest.mark.parametrize(
    ("texto", "esperado"),
    [
        ("release", RegraDeploy("release")),
        ("tag", RegraDeploy("tag", filtro="*")),
        ("tag:v*", RegraDeploy("tag", filtro="v*")),
        ("workflow:deploy.yml", RegraDeploy("workflow", filtro="deploy.yml", branch="main")),
        (
            " workflow: cd.yml @ producao ",
            RegraDeploy("workflow", filtro="cd.yml", branch="producao"),
        ),
    ],
)
def test_ler_regra_deploy(texto, esperado):
    assert ler_regra_deploy(texto) == esperado


@pytest.mark.parametrize(
    "texto", ["", "deploy", "release:x", "workflow", "workflow:", "workflow:@main"]
)
def test_regra_deploy_invalida(texto):
    with pytest.raises(ValueError, match="Regra de deploy inválida"):
        ler_regra_deploy(texto)


@pytest.mark.parametrize(
    "texto", ["release", "tag:v*", "workflow:deploy.yml@main", "workflow:cd.yml@producao"]
)
def test_regra_deploy_ida_e_volta_pelo_texto(texto):
    assert str(ler_regra_deploy(texto)) == texto


def test_regras_deploy_por_repositorio_com_padrao_release(monkeypatch):
    monkeypatch.setenv("PAINEL_REGRAS_DEPLOY", "dono/api=workflow:deploy.yml; dono/app = tag:v* ;")

    config = carregar_configuracao(arquivo_env=None)

    assert config.regra_deploy("dono/api") == RegraDeploy("workflow", filtro="deploy.yml")
    assert config.regra_deploy("dono/app") == RegraDeploy("tag", filtro="v*")
    assert config.regra_deploy("dono/outro") == RegraDeploy("release")


@pytest.mark.parametrize("valor", ["release", "repo-invalido=release", "dono/api=invalida"])
def test_regras_deploy_mal_formadas(monkeypatch, valor):
    monkeypatch.setenv("PAINEL_REGRAS_DEPLOY", valor)

    with pytest.raises(ValueError):
        carregar_configuracao(arquivo_env=None)


def test_url_do_banco_publicado(monkeypatch):
    assert carregar_configuracao(arquivo_env=None).url_banco is None

    monkeypatch.setenv("PAINEL_BANCO_URL", "https://exemplo/painel.duckdb")

    assert carregar_configuracao(arquivo_env=None).url_banco == "https://exemplo/painel.duckdb"
