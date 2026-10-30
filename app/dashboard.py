"""Dashboard do Painel de Métricas de Entrega: `streamlit run app/dashboard.py`.

Lê o DuckDB gerado por `python -m painel.coletar`, aplica os filtros da barra lateral e
entrega os dados às páginas em `app/paginas/`. A preparação das tabelas está em
`painel.visualizacao`, testada sem o Streamlit.
"""

from datetime import UTC, datetime
from pathlib import Path

import duckdb
import httpx
import streamlit as st

import comum
from painel import visualizacao as vis
from painel.coleta.armazenamento import (
    ler_deploys,
    ler_itens,
    ler_milestones,
    listar_repositorios,
)
from painel.config import carregar_configuracao
from painel.publicacao import IDADE_MAXIMA_PADRAO, baixar_banco

PERIODO_PADRAO_DIAS = 90

st.set_page_config(page_title="Painel de Métricas de Entrega", page_icon="📊", layout="wide")


@st.cache_data(ttl=600, show_spinner="Carregando dados…")
def carregar_dados(caminho: str):
    """Lê itens, deploys e milestones do banco. O cache evita reler o arquivo a cada interação."""
    with duckdb.connect(caminho, read_only=True) as conexao:
        return (
            listar_repositorios(conexao),
            ler_itens(conexao),
            ler_deploys(conexao),
            ler_milestones(conexao),
        )


@st.cache_resource(ttl=IDADE_MAXIMA_PADRAO, show_spinner="Baixando os dados publicados…")
def atualizar_banco(url: str, caminho: str) -> None:
    """Baixa o banco publicado pelo workflow de coleta, no máximo uma vez por hora."""
    try:
        if baixar_banco(url, Path(caminho)):
            carregar_dados.clear()
    except httpx.HTTPError as erro:
        st.error(f"Não foi possível baixar os dados publicados: {erro}")
        st.stop()


# --- Dados e filtros --------------------------------------------------------------------

config = carregar_configuracao()
if config.url_banco:
    atualizar_banco(config.url_banco, str(config.caminho_banco))
if not Path(config.caminho_banco).exists():
    st.title("📊 Painel de Métricas de Entrega")
    st.info(
        f"Nenhum dado encontrado em `{config.caminho_banco}`. "
        "Rode `python -m painel.coletar` para coletar os dados do GitHub."
    )
    st.stop()

repositorios_disponiveis, todos_itens, todos_deploys, todos_milestones = carregar_dados(
    str(config.caminho_banco)
)
if not repositorios_disponiveis:
    st.title("📊 Painel de Métricas de Entrega")
    st.info("O banco ainda não tem itens coletados. Rode `python -m painel.coletar`.")
    st.stop()

hoje = datetime.now(UTC).date()
with st.sidebar:
    st.header("Filtros")
    repositorios = st.multiselect(
        "Repositórios", repositorios_disponiveis, default=repositorios_disponiveis
    )
    periodo = st.date_input(
        "Período",
        value=(vis.inicio_padrao(todos_itens, hoje, PERIODO_PADRAO_DIAS), hoje),
        max_value=hoje,
        format="DD/MM/YYYY",
    )
    rotulo_tipo = st.radio("Itens de fluxo", list(vis.TIPOS), horizontal=True)
    st.caption(f"Definições das métricas nos [ADRs do projeto]({comum.URL_ADRS}).")

if not repositorios:
    st.warning("Selecione ao menos um repositório.")
    st.stop()
if len(periodo) != 2:
    st.info("Escolha a data final do período.")
    st.stop()

inicio, fim = periodo
comum.definir_contexto(
    comum.Contexto(
        repositorios=repositorios,
        inicio=inicio,
        fim=fim,
        tipo=vis.TIPOS[rotulo_tipo],
        agora=datetime.now(UTC).replace(tzinfo=None),
        itens=[item for item in todos_itens if item.repositorio in repositorios],
        deploys=[deploy for deploy in todos_deploys if deploy.repositorio in repositorios],
        milestones=[m for m in todos_milestones if m.repositorio in repositorios],
    )
)

st.navigation(
    [
        st.Page("paginas/visao_geral.py", title="Visão geral", icon="📊", default=True),
        st.Page("paginas/fluxo.py", title="Fluxo", icon="🔄"),
        st.Page("paginas/dora.py", title="DORA", icon="🚀"),
        st.Page("paginas/planejamento.py", title="Planejamento", icon="🎯"),
    ]
).run()
