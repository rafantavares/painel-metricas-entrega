"""Página "Planejamento": burndown por milestone e índice de previsibilidade."""

import plotly.graph_objects as go
import streamlit as st

import comum
from painel import visualizacao as vis
from painel.metricas.planejamento import itens_do_milestone, previsibilidade

ctx = comum.contexto()

st.title("🎯 Planejamento")
st.caption(
    "Escopo de cada milestone: os itens que estão nele hoje. "
    "Entrega no prazo: issue fechada ou PR mesclado até o fim do dia do prazo (ADR 0007)."
)

if not ctx.milestones:
    st.info("Nenhum milestone coletado nos repositórios selecionados.")
    st.stop()

st.subheader("Burndown")
hoje = ctx.agora.date()
milestones = vis.ordenar_milestones(ctx.milestones)
escolhido = st.selectbox(
    "Milestone",
    milestones,
    format_func=lambda m: (
        f"{m.titulo} · {m.repositorio}"
        + (f" · prazo {m.prazo:%d/%m/%Y}" if m.prazo else " · sem prazo")
    ),
)
burndown = vis.tabela_burndown(ctx.itens, escolhido, hoje)
figura = go.Figure()
figura.add_scatter(
    x=burndown["dia"], y=burndown["restantes"], name="Restantes", mode="lines+markers"
)
figura.add_scatter(
    x=burndown["dia"], y=burndown["ideal"], name="Ideal", mode="lines", line={"dash": "dash"}
)
figura.update_layout(xaxis_title="Dia", yaxis_title="Itens restantes", xaxis_tickformat="%d/%m")
figura.update_yaxes(rangemode="tozero")
st.plotly_chart(figura, width="stretch")

resumo = previsibilidade(ctx.itens, escolhido)
colunas = st.columns(3)
colunas[0].metric("Itens no milestone", len(itens_do_milestone(ctx.itens, escolhido)))
if resumo is not None:
    colunas[1].metric("Entregues no prazo", resumo.entregues_no_prazo)
    taxa = resumo.percentual * 100 if resumo.percentual is not None else None
    rotulo = "Previsibilidade" if resumo.prazo < hoje else "Entregue até agora"
    colunas[2].metric(rotulo, comum.formatar(taxa, "%", 0))
comum.baixar_csv(burndown, "burndown")

st.subheader("Previsibilidade")
st.caption(
    "Milestones com prazo a partir do início do período. O índice considera só os prazos já "
    "encerrados; nos em andamento, o percentual mostra o que já foi entregue."
)
tabela = vis.tabela_previsibilidade(ctx.itens, ctx.milestones, ctx.inicio, hoje)
if tabela.empty:
    st.info("Nenhum milestone com prazo no período.")
else:
    indice = vis.indice_dos_encerrados(tabela)
    st.metric(
        "Índice de previsibilidade",
        comum.formatar(indice * 100 if indice is not None else None, "%", 0),
        help="Itens entregues até o prazo ÷ itens planejados, nos milestones já encerrados.",
    )
    st.dataframe(
        tabela,
        hide_index=True,
        width="stretch",
        column_config={
            "repositorio": "Repositório",
            "milestone": "Milestone",
            "prazo": st.column_config.DateColumn("Prazo", format="DD/MM/YYYY"),
            "situacao": "Situação",
            "planejados": "Planejados",
            "entregues_no_prazo": "Entregues no prazo",
            "percentual": st.column_config.NumberColumn("Previsibilidade", format="percent"),
        },
    )
comum.baixar_csv(tabela, "previsibilidade")
