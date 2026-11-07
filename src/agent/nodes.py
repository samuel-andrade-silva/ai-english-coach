from src.agent.state import CoachState


def no_recuperacao_rag(state: CoachState) -> dict:
    """
    Nó 0: Resgata erros históricos do banco vetorial
    no início da conversa.
    """
    print(
        f"\n--- [NÓ 0: RAG RECOVERY] "
        f"Usuário: {state['usuario_id']} ---"
    )

    erros_passados = ["make a photo -> take a photo"]

    return {
        "contexto_rag_memoria": erros_passados
    }


def no_triagem_jev(state: CoachState) -> dict:
    """
    Nó 1: Classifica a intenção e detecta
    se a frase precisa de reescrita C1.
    """
    print(
        f"\n--- [NÓ 1: TRIAGEM JEV] "
        f"Analisando: '{state['frase_atual_texto']}' ---"
    )

    texto = state["frase_atual_texto"].lower()

    if "make a photo" in texto or "make a decision" in texto:
        rota = "C1_REWRITE"

    elif "mean" in texto or "express" in texto:
        rota = "NEED_SEARCH"

    else:
        rota = "CASUAL_CHAT"

    decisao = {
        "rota": rota,
        "confianca": 0.95
    }

    print(f"Decisão do Roteador: {decisao}")

    return {
        "decisao_jev": decisao
    }


def no_evaluator_c1(state: CoachState) -> dict:
    """
    Nó 2: Gera reescritas em 3 registros
    (Casual, Profissional, Idiomática).
    """
    print("\n--- [NÓ 2: EVALUATOR C1] ---")

    frase = state["frase_atual_texto"]

    feedback = {
        "casual": f"Snap a photo (em vez de '{frase}')",
        "profissional": "Capture an image",
        "idiomatica": "Take a picture",
    }

    erro_registrado = {
        "original": frase,
        "tipo": "literal_translation"
    }

    return {
        "resposta_agente_texto": f"Natural C1 feedback for: '{frase}'",
        "feedback_registro": feedback,
        "erros_friccao": [erro_registrado],
    }


def no_tavily_search(state: CoachState) -> dict:
    """
    Nó 3: Busca exemplos reais na web
    quando há dúvida de expressão.
    """
    print("\n--- [NÓ 3: TAVILY SEARCH] ---")

    exemplo_web = "Exemplo real encontrado: 'take a photo of the sunset'"

    return {
        "pesquisa_tavily_contexto": exemplo_web
    }


def no_conversador(state: CoachState) -> dict:
    """
    Nó 4: Resposta fluida para conversação casual
    sem erros graves.
    """
    print("\n--- [NÓ 4: CONVERSADOR CASUAL] ---")

    resposta = (
        f"That sounds great! Tell me more about "
        f"'{state['frase_atual_texto']}'."
    )

    return {
        "resposta_agente_texto": resposta
    }