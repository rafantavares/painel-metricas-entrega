"""Tabelas prontas para o dashboard, montadas a partir das métricas.

Fica separado de `app/painel.py` para que a preparação dos dados seja testada sem o
Streamlit. Cada função devolve um `DataFrame` com colunas em português, que vira
gráfico, tabela ou CSV no painel.
"""

from collections import Counter
from collections.abc import Iterable, Sequence
from datetime import date, datetime, timedelta

import pandas as pd

from painel.coleta.normalizacao import Deploy, Item, Milestone
from painel.metricas import dora
from painel.metricas.fluxo import (
    SEGUNDOS_POR_DIA,
    concluido_em,
    cycle_time,
    inicio_da_semana,
    throughput_semanal,
)
from painel.metricas.planejamento import burndown, previsibilidade
from painel.metricas.wip import itens_envelhecidos, wip_diario

TIPOS = {"Todos": None, "Issues": "issue", "Pull requests": "pull_request"}
NOMES_TIPO = {"issue": "Issue", "pull_request": "Pull request"}


def _filtrar_tipo(itens: Iterable[Item], tipo: str | None) -> list[Item]:
    return [item for item in itens if tipo is None or item.tipo == tipo]


def inicio_padrao(itens: Iterable[Item], hoje: date, dias: int) -> date:
    """Início do período padrão: os últimos `dias` dias, sem começar antes do item mais antigo.

    Evita gráficos quase vazios quando o histórico coletado é mais curto que o período.
    """
    janela = hoje - timedelta(days=dias - 1)
    mais_antigo = min((item.criado_em.date() for item in itens), default=janela)
    return max(janela, min(mais_antigo, hoje))


def tabela_throughput(
    itens: Iterable[Item], inicio: date, fim: date, tipo: str | None = None
) -> pd.DataFrame:
    """Itens concluídos por semana no período, incluindo semanas sem entrega."""
    semanas = throughput_semanal(itens, inicio, fim, tipo)
    return pd.DataFrame(
        {"semana": [s.semana for s in semanas], "concluidos": [s.concluidos for s in semanas]}
    )


def tabela_concluidos(
    itens: Iterable[Item], inicio: date, fim: date, tipo: str | None = None
) -> pd.DataFrame:
    """Um item concluído por linha, com o cycle time em dias."""
    linhas = []
    for item in _filtrar_tipo(itens, tipo):
        conclusao = concluido_em(item)
        if conclusao is None or not inicio <= conclusao.date() <= fim:
            continue
        linhas.append(
            {
                "repositorio": item.repositorio,
                "numero": item.numero,
                "titulo": item.titulo,
                "tipo": NOMES_TIPO[item.tipo],
                "criado_em": item.criado_em,
                "concluido_em": conclusao,
                "cycle_time_dias": (conclusao - item.criado_em).total_seconds() / SEGUNDOS_POR_DIA,
            }
        )
    colunas = [
        "repositorio",
        "numero",
        "titulo",
        "tipo",
        "criado_em",
        "concluido_em",
        "cycle_time_dias",
    ]
    return pd.DataFrame(linhas, columns=colunas)


def tabela_wip(
    itens: Iterable[Item], inicio: date, fim: date, tipo: str | None = None
) -> pd.DataFrame:
    """Itens em andamento ao fim de cada dia do período."""
    contagens = wip_diario(itens, inicio, fim, tipo)
    return pd.DataFrame(
        {"dia": [c.dia for c in contagens], "em_andamento": [c.em_andamento for c in contagens]}
    )


def tabela_envelhecidos(
    itens: Iterable[Item], referencia: datetime, tipo: str | None = None
) -> pd.DataFrame:
    """Itens abertos há mais tempo que o percentil 85 do cycle time."""
    colunas = ["repositorio", "numero", "titulo", "tipo", "criado_em", "idade_dias"]
    linhas = [
        {
            "repositorio": e.item.repositorio,
            "numero": e.item.numero,
            "titulo": e.item.titulo,
            "tipo": NOMES_TIPO[e.item.tipo],
            "criado_em": e.item.criado_em,
            "idade_dias": e.idade_dias,
        }
        for e in itens_envelhecidos(itens, referencia, tipo=tipo)
    ]
    return pd.DataFrame(linhas, columns=colunas)


def resumo_fluxo(
    itens: Sequence[Item], inicio: date, fim: date, referencia: datetime, tipo: str | None = None
) -> dict[str, float | int | None]:
    """Indicadores principais de fluxo no período, para os cartões da visão geral."""
    semanas = throughput_semanal(itens, inicio, fim, tipo)
    resumo = cycle_time(itens, inicio, fim, tipo)
    wip_final = wip_diario(itens, fim, fim, tipo)[0].em_andamento
    return {
        "concluidos": sum(s.concluidos for s in semanas),
        "throughput_medio_semanal": (
            sum(s.concluidos for s in semanas) / len(semanas) if semanas else 0
        ),
        "cycle_time_mediana_dias": resumo.mediana_dias,
        "cycle_time_p85_dias": resumo.p85_dias,
        "wip_atual": wip_final,
        "envelhecidos": len(itens_envelhecidos(itens, referencia, tipo=tipo)),
    }


def tabela_dora(
    itens: Iterable[Item], deploys: Iterable[Deploy], inicio: date, fim: date
) -> pd.DataFrame:
    """As quatro métricas DORA, com a classificação, em uma linha por repositório.

    São calculadas por repositório porque a ligação entre PR e deploy só faz sentido
    dentro do mesmo repositório (ADR 0005).
    """
    itens_por_repo: dict[str, list[Item]] = {}
    for item in itens:
        itens_por_repo.setdefault(item.repositorio, []).append(item)
    deploys_por_repo: dict[str, list[Deploy]] = {}
    for deploy in deploys:
        deploys_por_repo.setdefault(deploy.repositorio, []).append(deploy)

    linhas = []
    for repositorio in sorted(itens_por_repo.keys() | deploys_por_repo.keys()):
        do_repo = itens_por_repo.get(repositorio, [])
        implantados = deploys_por_repo.get(repositorio, [])
        frequencia = dora.frequencia_deploy(implantados, inicio, fim)
        lead_time = dora.lead_time_mudancas(do_repo, implantados, inicio, fim)
        falha = dora.taxa_falha_mudancas(do_repo, implantados, inicio, fim)
        restauracao = dora.tempo_restauracao(do_repo, inicio, fim)
        linhas.append(
            {
                "repositorio": repositorio,
                "deploys": frequencia.quantidade,
                "deploys_por_semana": frequencia.por_dia * 7,
                "frequencia": str(frequencia.classificacao),
                "lead_time_mediana_dias": lead_time.mediana_dias,
                "lead_time": _texto_classe(lead_time.classificacao),
                "taxa_falha": falha.taxa,
                "falha": _texto_classe(falha.classificacao),
                "restauracao_mediana_horas": (
                    restauracao.mediana_dias * 24 if restauracao.mediana_dias is not None else None
                ),
                "restauracao": _texto_classe(restauracao.classificacao),
            }
        )
    tabela = pd.DataFrame(linhas, columns=COLUNAS_DORA)
    numericas = [
        "deploys_por_semana",
        "lead_time_mediana_dias",
        "taxa_falha",
        "restauracao_mediana_horas",
    ]
    # `None` vira NaN, para o dashboard mostrar a célula vazia em vez de "None".
    tabela[numericas] = tabela[numericas].astype(float)
    return tabela


COLUNAS_DORA = [
    "repositorio",
    "deploys",
    "deploys_por_semana",
    "frequencia",
    "lead_time_mediana_dias",
    "lead_time",
    "taxa_falha",
    "falha",
    "restauracao_mediana_horas",
    "restauracao",
]


def _texto_classe(classificacao: dora.Desempenho | None) -> str:
    return str(classificacao) if classificacao is not None else "sem dados"


def tabela_deploys_semanais(deploys: Iterable[Deploy], inicio: date, fim: date) -> pd.DataFrame:
    """Deploys por semana e repositório no período, com zero nas semanas sem deploy.

    Só entram os repositórios que tiveram ao menos um deploy no período.
    """
    contagem = Counter(
        (inicio_da_semana(d.implantado_em.date()), d.repositorio)
        for d in deploys
        if inicio <= d.implantado_em.date() <= fim
    )
    repositorios = sorted({repositorio for _, repositorio in contagem})
    semanas = [s.semana for s in throughput_semanal([], inicio, fim)]
    linhas = [
        {"semana": semana, "repositorio": repositorio, "deploys": contagem[(semana, repositorio)]}
        for semana in semanas
        for repositorio in repositorios
    ]
    return pd.DataFrame(linhas, columns=["semana", "repositorio", "deploys"])


def ordenar_milestones(milestones: Iterable[Milestone]) -> list[Milestone]:
    """Abertos primeiro, do prazo mais próximo ao mais distante; depois os fechados,
    do mais recente ao mais antigo. Milestones sem prazo vão para o fim de cada grupo.
    """
    abertos = [m for m in milestones if m.estado == "open"]
    fechados = [m for m in milestones if m.estado != "open"]
    abertos.sort(key=lambda m: (m.prazo is None, m.prazo or date.max, m.titulo))
    fechados.sort(key=lambda m: (m.prazo is not None, m.prazo or date.min), reverse=True)
    return abertos + fechados


def tabela_burndown(itens: Iterable[Item], milestone: Milestone, hoje: date) -> pd.DataFrame:
    """Itens restantes e linha ideal por dia do milestone."""
    pontos = burndown(itens, milestone, hoje)
    return pd.DataFrame(
        {
            "dia": [p.dia for p in pontos],
            "restantes": pd.array([p.restantes for p in pontos], dtype="Int64"),
            "ideal": pd.array([p.ideal for p in pontos], dtype="Float64"),
        }
    )


def tabela_previsibilidade(
    itens: Sequence[Item], milestones: Iterable[Milestone], inicio: date, hoje: date
) -> pd.DataFrame:
    """Uma linha por milestone com prazo a partir de `inicio`, do prazo mais antigo ao mais novo.

    Inclui milestones com prazo futuro, marcados como "em andamento": para eles o
    percentual mostra o que já foi entregue, mas ainda não vale para o índice.
    """
    colunas = [
        "repositorio",
        "milestone",
        "prazo",
        "situacao",
        "planejados",
        "entregues_no_prazo",
        "percentual",
    ]
    linhas = [
        resumo.__dict__ | {"situacao": "prazo encerrado" if m.prazo < hoje else "em andamento"}
        for m in milestones
        if m.prazo is not None
        and m.prazo >= inicio
        and (resumo := previsibilidade(itens, m)) is not None
    ]
    tabela = pd.DataFrame(linhas, columns=colunas).sort_values(["prazo", "repositorio"])
    tabela["percentual"] = tabela["percentual"].astype(float)
    return tabela.reset_index(drop=True)


def indice_dos_encerrados(tabela: pd.DataFrame) -> float | None:
    """Índice de previsibilidade só dos milestones com prazo encerrado."""
    encerrados = tabela[tabela["situacao"] == "prazo encerrado"]
    planejados = encerrados["planejados"].sum()
    return encerrados["entregues_no_prazo"].sum() / planejados if planejados else None
