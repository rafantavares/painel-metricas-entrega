"""Estado e utilidades compartilhados entre as páginas do dashboard."""

from dataclasses import dataclass
from datetime import date, datetime

import pandas as pd
import plotly.express as px
import streamlit as st
from plotly.graph_objects import Figure

from painel.coleta.normalizacao import Deploy, Item, Milestone

URL_ADRS = "https://github.com/rafantavares/painel-metricas-entrega/tree/main/docs/adr"


@dataclass(frozen=True)
class Contexto:
    """Dados já filtrados pela barra lateral, montados em `dashboard.py` a cada execução."""

    repositorios: list[str]
    inicio: date
    fim: date
    tipo: str | None
    agora: datetime
    itens: list[Item]
    deploys: list[Deploy]
    milestones: list[Milestone]


def definir_contexto(contexto: Contexto) -> None:
    st.session_state["contexto"] = contexto


def contexto() -> Contexto:
    return st.session_state["contexto"]


def baixar_csv(tabela: pd.DataFrame, nome: str) -> None:
    # utf-8-sig: o Excel em português reconhece os acentos sem configuração extra.
    st.download_button(
        "Baixar CSV",
        tabela.to_csv(index=False).encode("utf-8-sig"),
        file_name=f"{nome}.csv",
        mime="text/csv",
        key=f"csv-{nome}",
    )


def formatar(valor: float | None, sufixo: str = "", casas: int = 1) -> str:
    """Número no formato brasileiro (vírgula decimal); travessão quando não há valor."""
    if valor is None or pd.isna(valor):
        return "—"
    return f"{valor:.{casas}f}".replace(".", ",") + sufixo


def formatar_duracao(dias: float | None) -> str:
    """Duração na unidade mais legível: minutos, horas ou dias."""
    if dias is None or pd.isna(dias):
        return "—"
    if dias < 1 / 24:
        return formatar(dias * 24 * 60, " min", 0)
    if dias < 1:
        return formatar(dias * 24, " h")
    return formatar(dias, " d")


def metrica(coluna, rotulo: str, valor: str, classificacao: str | None = None) -> None:
    """Cartão com o valor e, abaixo, a classificação de desempenho DORA."""
    coluna.metric(rotulo, valor)
    if classificacao is not None:
        coluna.caption(f"Desempenho: **{classificacao}**")


def barras_semanais(
    tabela: pd.DataFrame, y: str, rotulo_y: str, labels: dict | None = None, **opcoes
) -> Figure:
    """Gráfico de barras por semana, com o eixo rotulado pela segunda-feira (dd/mm/aa)."""
    dados = tabela.assign(semana=pd.to_datetime(tabela["semana"]).dt.strftime("%d/%m/%y"))
    rotulos = {"semana": "Semana de", y: rotulo_y} | (labels or {})
    figura = px.bar(dados, x="semana", y=y, labels=rotulos, **opcoes)
    figura.update_xaxes(type="category")
    return figura


CONFIG_COLUNAS_ITENS = {
    "repositorio": "Repositório",
    "numero": st.column_config.NumberColumn("Nº", format="%d"),
    "titulo": "Título",
    "tipo": "Tipo",
    "criado_em": st.column_config.DatetimeColumn("Criado em", format="DD/MM/YYYY HH:mm"),
    "concluido_em": st.column_config.DatetimeColumn("Concluído em", format="DD/MM/YYYY HH:mm"),
    "cycle_time_dias": st.column_config.NumberColumn("Cycle time (dias)", format="%.1f"),
    "idade_dias": st.column_config.NumberColumn("Idade (dias)", format="%.1f"),
}


def tabela_dora_legivel(tabela: pd.DataFrame) -> pd.DataFrame:
    """Versão da tabela DORA para exibição, com valores formatados em português.

    O CSV continua usando a tabela original, com números sem formatação.
    """
    return pd.DataFrame(
        {
            "Repositório": tabela["repositorio"],
            "Deploys": tabela["deploys"],
            "Deploys/semana": tabela["deploys_por_semana"].map(lambda v: formatar(v, casas=2)),
            "Frequência": tabela["frequencia"],
            "Lead time (mediana)": tabela["lead_time_mediana_dias"].map(formatar_duracao),
            "Lead time": tabela["lead_time"],
            "Taxa de falha": (tabela["taxa_falha"] * 100).map(lambda v: formatar(v, "%", 0)),
            "Falha": tabela["falha"],
            "Restauração (mediana)": (tabela["restauracao_mediana_horas"] / 24).map(
                formatar_duracao
            ),
            "Restauração": tabela["restauracao"],
        }
    )
