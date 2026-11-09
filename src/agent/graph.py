import os
import sqlite3

from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.graph import END, START, StateGraph

from src.agent.nodes import (
    no_conversador,
    no_evaluator_c1,
    no_persistencia_rag,  # Nó de persistência no Qdrant
    no_recuperacao_rag,
    no_tavily_search,
    no_triagem_jev,
)

from src.agent.state import CoachState


def decidir_rota_jev(state: CoachState) -> str:
    """
    Aresta condicional: lê a decisão do Jev e indica o próximo nó.
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


# Registro de todos os nós
builder.add_node("rag_recovery", no_recuperacao_rag)
builder.add_node("triagem", no_triagem_jev)
builder.add_node("evaluator", no_evaluator_c1)
builder.add_node("tavily", no_tavily_search)
builder.add_node("conversador", no_conversador)
builder.add_node("persistencia_rag", no_persistencia_rag)


# ==========================================
# CONEXÕES DO GRAFO
# ==========================================

# 1. Nó 0: Recuperação do histórico no Qdrant Cloud
# assim que a mensagem entra
builder.add_edge(START, "rag_recovery")

# 2. Envia o estado (frase + histórico recuperado)
# para a triagem do Jev
builder.add_edge("rag_recovery", "triagem")

# 3. Roteamento condicional baseado na decisão do JEV
# (evaluator, tavily ou conversador)
builder.add_conditional_edges(
    "triagem",
    decidir_rota_jev,
    {
        "evaluator": "evaluator",
        "tavily": "tavily",
        "conversador": "conversador",
    },
)

# 4. Fluxo após a pesquisa da Tavily vai para a avaliação C1
builder.add_edge("tavily", "evaluator")

# 5. Ambos os fluxos passam pelo nó de persistência
# no Qdrant antes do encerramento
builder.add_edge("evaluator", "persistencia_rag")
builder.add_edge("conversador", "persistencia_rag")

# 6. Encerramento oficial do fluxo do grafo
builder.add_edge("persistencia_rag", END)


# ==========================================
# COMPILAÇÃO DO GRAFO
# ==========================================

def obter_app_grafo(
    caminho_banco: str = "scratch/banco_coach.sqlite3",
):
    """
    Compila o grafo com persistência SQLite passando
    a conexão direta ao SqliteSaver.
    """
    diretorio = os.path.dirname(caminho_banco)

    if diretorio:
        os.makedirs(diretorio, exist_ok=True)

    conn = sqlite3.connect(
        caminho_banco,
        check_same_thread=False,
    )

    checkpointer = SqliteSaver(conn)

    return builder.compile(checkpointer=checkpointer)


# Instância compilada do grafo para o bot do Telegram
app = obter_app_grafo()