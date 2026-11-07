from langgraph.checkpoint.sqlite import SqliteSaver

from src.agent.graph import builder


if __name__ == "__main__":

    caminho_db = "scratch/banco_coach.sqlite3"

    # ==========================================
    # INICIALIZAÇÃO DO CHECKPOINTER SQLITE
    # ==========================================

    with SqliteSaver.from_conn_string(caminho_db) as checkpointer:

        app = builder.compile(checkpointer=checkpointer)

        # ==========================================
        # CONFIGURAÇÃO DA SESSÃO
        # ==========================================

        config = {
            "configurable": {
                "thread_id": "user_dev_01:2026-11-07"
            }
        }

        # ==========================================
        # ESTADO INICIAL DE ENTRADA
        # ==========================================

        estado_entrada = {
            "usuario_id": "user_dev_01",
            "thread_id": "user_dev_01:2026-11-07",
            "canal_entrada": "terminal",

            "frase_atual_texto": "I want to make a photo of this castle.",
            "historico_mensagens": [],
            "contexto_rag_memoria": [],

            "decisao_jev": None,

            "erros_friccao": [],
            "expressoes_c1": [],

            "pesquisa_tavily_contexto": None,
            "resposta_agente_texto": "",
            "feedback_registro": None,

            "arquivo_audio_resposta": None,
            "sessao_ativa": True,
        }

        # ==========================================
        # EXECUÇÃO DO GRAFO
        # ==========================================

        print("\n=== TESTANDO ESTRUTURA REATORA EM SRC/AGENT ===")

        resultado = app.invoke(
            estado_entrada,
            config=config
        )

        # ==========================================
        # RESULTADO FINAL
        # ==========================================

        print("\n=== RESULTADO FINAL DO ESTADO ===")

        print(
            f"Resposta do Agente: "
            f"{resultado['resposta_agente_texto']}"
        )

        print(
            f"Erros de Fricção Acumulados: "
            f"{resultado['erros_friccao']}"
        )