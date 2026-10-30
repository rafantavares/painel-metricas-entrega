"""Página "DORA": as quatro métricas por repositório, com a classificação."""

import streamlit as st

import comum
from painel import visualizacao as vis

ctx = comum.contexto()

st.title("🚀 DORA")
st.caption(
    "Deploys identificados pela regra de cada repositório (ADR 0004). "
    "Definições e faixas de desempenho no ADR 0005."
)

tabela = vis.tabela_dora(ctx.itens, ctx.deploys, ctx.inicio, ctx.fim)
for linha in tabela.itertuples():
    st.markdown(f"#### {linha.repositorio}")
    colunas = st.columns(4)
    comum.metrica(
        colunas[0],
        "Frequência de deploy",
        comum.formatar(linha.deploys_por_semana, "/sem"),
        linha.frequencia,
    )
    comum.metrica(
        colunas[1],
        "Lead time (mediana)",
        comum.formatar_duracao(linha.lead_time_mediana_dias),
        linha.lead_time,
    )
    comum.metrica(
        colunas[2], "Taxa de falha", comum.formatar(linha.taxa_falha * 100, "%", 0), linha.falha
    )
    comum.metrica(
        colunas[3],
        "Restauração (mediana)",
        comum.formatar_duracao(linha.restauracao_mediana_horas / 24),
        linha.restauracao,
    )

st.subheader("Deploys por semana")
semanais = vis.tabela_deploys_semanais(ctx.deploys, ctx.inicio, ctx.fim)
if semanais.empty:
    st.info("Nenhum deploy no período. Confira a regra de deploy em `PAINEL_REGRAS_DEPLOY`.")
else:
    grafico = comum.barras_semanais(
        semanais, "deploys", "Deploys", color="repositorio", labels={"repositorio": "Repositório"}
    )
    st.plotly_chart(grafico, width="stretch")

st.subheader("Tabela")
st.dataframe(comum.tabela_dora_legivel(tabela), hide_index=True, width="stretch")
comum.baixar_csv(tabela, "dora")
