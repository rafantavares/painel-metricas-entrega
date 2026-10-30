"""Página "Fluxo": throughput, cycle time, WIP e itens envelhecidos."""

import plotly.express as px
import streamlit as st

import comum
from painel import visualizacao as vis

ctx = comum.contexto()

st.title("🔄 Fluxo")

st.subheader("Throughput semanal")
throughput = vis.tabela_throughput(ctx.itens, ctx.inicio, ctx.fim, ctx.tipo)
st.plotly_chart(comum.barras_semanais(throughput, "concluidos", "Concluídos"), width="stretch")
comum.baixar_csv(throughput, "throughput")

st.subheader("Cycle time")
concluidos = vis.tabela_concluidos(ctx.itens, ctx.inicio, ctx.fim, ctx.tipo)
resumo = vis.resumo_fluxo(ctx.itens, ctx.inicio, ctx.fim, ctx.agora, ctx.tipo)
st.caption(
    f"Mediana: {comum.formatar_duracao(resumo['cycle_time_mediana_dias'])} · "
    f"Percentil 85: {comum.formatar_duracao(resumo['cycle_time_p85_dias'])} · "
    "da criação à conclusão (ADR 0003)"
)
if concluidos.empty:
    st.info("Nenhum item concluído no período.")
else:
    histograma = px.histogram(
        concluidos,
        x="cycle_time_dias",
        color="tipo",
        nbins=30,
        labels={"cycle_time_dias": "Cycle time (dias)", "tipo": "Tipo"},
    )
    histograma.update_yaxes(title="Itens")
    st.plotly_chart(histograma, width="stretch")
    st.dataframe(
        concluidos,
        hide_index=True,
        column_config=comum.CONFIG_COLUNAS_ITENS,
        width="stretch",
    )
comum.baixar_csv(concluidos, "cycle-time")

st.subheader("WIP diário")
wip = vis.tabela_wip(ctx.itens, ctx.inicio, ctx.fim, ctx.tipo)
st.plotly_chart(
    px.line(wip, x="dia", y="em_andamento", labels={"dia": "Dia", "em_andamento": "Em andamento"}),
    width="stretch",
)
comum.baixar_csv(wip, "wip")

st.subheader("Itens envelhecidos")
st.caption("Abertos há mais tempo que o percentil 85 do cycle time, do mais antigo ao mais novo.")
envelhecidos = vis.tabela_envelhecidos(ctx.itens, ctx.agora, ctx.tipo)
if envelhecidos.empty:
    st.success("Nenhum item parado além do esperado.")
else:
    st.dataframe(
        envelhecidos,
        hide_index=True,
        column_config=comum.CONFIG_COLUNAS_ITENS,
        width="stretch",
    )
comum.baixar_csv(envelhecidos, "envelhecidos")
