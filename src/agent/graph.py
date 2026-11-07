from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.graph import END, START, StateGraph

from src.agent.nodes import (
    no_conversador,
    no_evaluator_c1,
    no_recuperacao_rag,
    no_tavily_search,
    no_triagem_jev,
)

from src.agent.state import CoachState


def decidir_rota_jev(state: CoachState) -> str:
    """
    Aresta condicional: lê a decisão do Jev
    e indica o próximo nó.
    """
    decisao = state.get("decisao_jev")

    if not decisao:
        return "conversador"

    rota = decisao.get("rota")

    if rota == "C1_REWRITE":
        return "evaluator"

    elif rota == "NEED_SEARCH":
        return "tavily"

    return "conversador"


# ==========================================
# CONSTRUÇÃO DO GRAFO
# ==========================================

builder = StateGraph(CoachState)

# Registro dos nós
builder.add_node("rag_recovery", no_recuperacao_rag)
builder.add_node("triagem", no_triagem_jev)
builder.add_node("evaluator", no_evaluator_c1)
builder.add_node("tavily", no_tavily_search)
builder.add_node("conversador", no_conversador)


# ==========================================
# CONEXÕES DO GRAFO
# ==========================================

builder.add_edge(START, "rag_recovery")

builder.add_edge("rag_recovery", "triagem")

# Roteamento condicional baseado na decisão do JEV
builder.add_conditional_edges(
    "triagem",
    decidir_rota_jev,
    {
        "evaluator": "evaluator",
        "tavily": "tavily",
        "conversador": "conversador",
    },
)

# Fluxo após pesquisa
builder.add_edge("tavily", "evaluator")

# Encerramento dos fluxos
builder.add_edge("evaluator", END)
builder.add_edge("conversador", END)


# ==========================================
# COMPILAÇÃO DO GRAFO
# ==========================================

def obter_app_grafo(
    caminho_banco: str = "scratch/banco_coach.sqlite3",
):
    """
    Compila o grafo com persistência SQLite
    para gerenciamento das sessões.
    """
    checkpointer = SqliteSaver.from_conn_string(caminho_banco)

    return builder.compile(checkpointer=checkpointer)