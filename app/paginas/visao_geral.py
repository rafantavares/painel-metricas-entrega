"""Página "Visão geral": indicadores principais de fluxo e DORA."""

import streamlit as st

import comum
from painel import visualizacao as vis

ctx = comum.contexto()

st.title("📊 Visão geral")
st.caption(f"{', '.join(ctx.repositorios)} · {ctx.inicio:%d/%m/%Y} a {ctx.fim:%d/%m/%Y}")

resumo = vis.resumo_fluxo(ctx.itens, ctx.inicio, ctx.fim, ctx.agora, ctx.tipo)
colunas = st.columns(5)
colunas[0].metric("Itens concluídos", resumo["concluidos"])
colunas[1].metric("Throughput médio", comum.formatar(resumo["throughput_medio_semanal"], "/sem"))
colunas[2].metric("Cycle time (mediana)", comum.formatar_duracao(resumo["cycle_time_mediana_dias"]))
colunas[3].metric("WIP no fim do período", resumo["wip_atual"])
colunas[4].metric("Itens envelhecidos", resumo["envelhecidos"])

throughput = vis.tabela_throughput(ctx.itens, ctx.inicio, ctx.fim, ctx.tipo)
st.plotly_chart(
    comum.barras_semanais(
        throughput, "concluidos", "Concluídos", title="Itens concluídos por semana"
    ),
    width="stretch",
)

st.subheader("DORA por repositório")
st.dataframe(
    comum.tabela_dora_legivel(vis.tabela_dora(ctx.itens, ctx.deploys, ctx.inicio, ctx.fim)),
    hide_index=True,
    width="stretch",
)
