
import operator
import os

from typing import Annotated, TypedDict
from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.sqlite import SqliteSaver


# ------------------------------------------------------------------------------
# 1. ESTADO (State) - A ficha de papel compartilhada
# ------------------------------------------------------------------------------

class MiniState(TypedDict):
    usuario_id: str
    mensagem: str
    historico_respostas: Annotated[list[str], operator.add]
    precisa_correcao: bool


# ------------------------------------------------------------------------------
# 2. NÓS (Nodes) - As funções em Python que fazem o trabalho
# ------------------------------------------------------------------------------

def no_triagem(state: MiniState) -> dict:
    """Analisa a mensagem recebida e decide se há erro de inglês."""

    print("\n--- [NÓ 1: TRIAGEM] ---")

    texto = state["mensagem"].lower()

    # Simulação: detecta erro de tradução literal
    tem_erro = "make a photo" in texto

    print(
        f"Mensagem analisada: '{state['mensagem']}' "
        f"| Detectou erro: {tem_erro}"
    )

    return {"precisa_correcao": tem_erro}


def no_evaluator(state: MiniState) -> dict:
    """Nó ativado apenas quando há erros de naturalidade."""

    print("\n--- [NÓ 2: EVALUATOR C1] ---")

    resposta = (
        f"Dica C1: Em vez de '{state['mensagem']}', "
        "use 'take a photo' ou 'snap a photo'."
    )

    return {"historico_respostas": [resposta]}


def no_conversador(state: MiniState) -> dict:
    """Nó ativado quando a conversa é neutra/casual."""

    print("\n--- [NÓ 3: CONVERSADOR] ---")

    resposta = (
        f"Great sentence! Let's keep talking about "
        f"'{state['mensagem']}'."
    )

    return {"historico_respostas": [resposta]}


# ------------------------------------------------------------------------------
# 3. ARESTA CONDICIONAL (Conditional Edge) - A função de decisão
# ------------------------------------------------------------------------------

def decidir_proximo_no(state: MiniState) -> str:
    """Decide o caminho do grafo baseado no estado."""

    if state["precisa_correcao"]:
        return "evaluator"

    return "conversador"


# ------------------------------------------------------------------------------
# 4. CONSTRUÇÃO E COMPILAÇÃO DO GRAFO
# ------------------------------------------------------------------------------

builder = StateGraph(MiniState)

# Adicionando os nós ao grafo
builder.add_node("triagem", no_triagem)
builder.add_node("evaluator", no_evaluator)
builder.add_node("conversador", no_conversador)

# Definindo o fluxo inicial
builder.add_edge(START, "triagem")

# Aresta condicional partindo da triagem
builder.add_conditional_edges(
    "triagem",
    decidir_proximo_no,
    {
        "evaluator": "evaluator",
        "conversador": "conversador",
    },
)

# Finalização dos caminhos
builder.add_edge("evaluator", END)
builder.add_edge("conversador", END)


# ------------------------------------------------------------------------------
# 5. EXECUÇÃO COM PERSISTÊNCIA (SqliteSaver)
# ------------------------------------------------------------------------------

if __name__ == "__main__":

    # Cria a pasta caso ela ainda não exista
    os.makedirs("scratch/mini_graph", exist_ok=True)

    # Abre e fecha o banco SQLite de forma segura
    with SqliteSaver.from_conn_string(
        "scratch/mini_graph/banco_teste.sqlite3"
    ) as checkpointer:

        # Compila o grafo com persistência
        app = builder.compile(checkpointer=checkpointer)

        # ----------------------------------------------------------------------
        # 6. MAPA VISUAL DO GRAFO (MERMAID)
        # ----------------------------------------------------------------------

        print("\n=== MAPA VISUAL DO GRAFO (MERMAID) ===")
        print(app.get_graph().draw_mermaid())

        # Identificador único da sessão (Thread ID)
        configuracao_thread = {
            "configurable": {
                "thread_id": "sessao_aluno_01"
            }
        }

        # ----------------------------------------------------------------------
        # TESTE 1: Mensagem com erro
        # ----------------------------------------------------------------------

        estado_inicial_1 = {
            "usuario_id": "user_123",
            "mensagem": "Yesterday I make a photo of the park.",
            "historico_respostas": [],
            "precisa_correcao": False,
        }

        print("\n=== EXECUTANDO PRIMEIRA MENSAGEM ===")

        resultado_1 = app.invoke(
            estado_inicial_1,
            config=configuracao_thread,
        )

        print(
            "Histórico acumulado até agora:",
            resultado_1["historico_respostas"],
        )

        # ----------------------------------------------------------------------
        # TESTE 2: Segunda mensagem na mesma sessão
        # ----------------------------------------------------------------------

        estado_inicial_2 = {
            "usuario_id": "user_123",
            "mensagem": "Today the weather is very good.",
            "historico_respostas": [],
            "precisa_correcao": False,
        }

        print("\n=== EXECUTANDO SEGUNDA MENSAGEM (MESMA THREAD) ===")

        resultado_2 = app.invoke(
            estado_inicial_2,
            config=configuracao_thread,
        )

        print(
            "Histórico total da sessão:",
            resultado_2["historico_respostas"],
        )
