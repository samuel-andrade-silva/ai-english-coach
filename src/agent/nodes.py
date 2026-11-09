from langchain_groq import ChatGroq

from config.settings import settings
from src.agent.state import CoachState
from src.decision.jev_router import classificar_intencao_aluno

import logging
from typing import Dict, Any

from src.rag.vector_service import (
    buscar_erros_recorrentes,
    salvar_erro_memoria,
)

logger = logging.getLogger(__name__)





def obter_llm():
    """Instancia o cliente LLM da Groq com a chave do .env."""
    return ChatGroq(
        groq_api_key=settings.groq_api_key,
        model_name=settings.groq_model,
        temperature=0.7,
    )


def no_recuperacao_rag(state: CoachState) -> dict:
    """Nó 0: Resgata erros históricos do banco vetorial no início da conversa."""
    print(f"\n--- [NÓ 0: RAG RECOVERY] Usuário: {state['usuario_id']} ---")

    erros_passados = ["make a photo -> take a photo"]

    return {"contexto_rag_memoria": erros_passados}


def no_triagem_jev(state: CoachState) -> dict:
    """Nó 1: Roteador inteligente tipado Jev com Limiar de Confiança."""
    print(f"\n--- [NÓ 1: TRIAGEM JEV] Analisando: '{state['frase_atual_texto']}' ---")

    decisao = classificar_intencao_aluno(state["frase_atual_texto"])

    print(f"Decisão do Roteador: {decisao}")

    return {"decisao_jev": decisao}


def no_evaluator_c1(state: CoachState) -> dict:
    """Nó 2: Chama a LLM real da Groq para gerar reescritas C1 em 3 registros."""
    print("\n--- [NÓ 2: EVALUATOR C1 - LLM REAL GROQ] ---")

    frase = state["frase_atual_texto"]

    prompt = f"""You are an expert C1/C2 English Coach.
The student said: "{frase}"
Provide feedback and 3 natural C1 rewrites:
1. Casual / Natural
2. Professional / Formal
3. Idiomatic

Keep your answer brief, encouraging, and clear."""

    if settings.groq_api_key and settings.groq_api_key != "sua_chave_groq_aqui":
        llm = obter_llm()
        resposta = llm.invoke(prompt).content
    else:
        resposta = (
            f"[MODO STUB] Reescritas para '{frase}': "
            "Use 'take a photo' instead of 'make a photo'."
        )

    feedback = {
        "casual": "Snap a photo",
        "profissional": "Capture an image",
        "idiomatica": "Take a picture",
    }

    erro_registrado = {
        "original": frase,
        "tipo": "literal_translation",
    }

    return {
        "resposta_agente_texto": resposta,
        "feedback_registro": feedback,
        "erros_friccao": [erro_registrado],
    }


def no_tavily_search(state: CoachState) -> dict:
    """Nó 3: Busca exemplos reais na web quando há dúvida de expressão."""
    print("\n--- [NÓ 3: TAVILY SEARCH] ---")

    exemplo_web = "Exemplo real encontrado: 'take a photo of the sunset'"

    return {"pesquisa_tavily_contexto": exemplo_web}


def no_conversador(state: CoachState) -> dict:
    """Nó 4: LLM real para conversação casual quando não há erros graves."""
    print("\n--- [NÓ 4: CONVERSADOR CASUAL - LLM REAL GROQ] ---")

    frase = state["frase_atual_texto"]

    prompt = f"""You are a friendly, encouraging English conversation coach.
Respond naturally in fluent English to the student: "{frase}"
Keep the conversation engaging and ask an open follow-up question."""

    if settings.groq_api_key and settings.groq_api_key != "sua_chave_groq_aqui":
        llm = obter_llm()
        resposta = llm.invoke(prompt).content
    else:
        resposta = f"[MODO STUB] That sounds great! Tell me more about '{frase}'."

    return {"resposta_agente_texto": resposta}

def no_recuperacao_rag(state: CoachState) -> dict:
    """
    Nó 0: Busca no Qdrant Cloud histórico de erros
    similares cometidos pelo aluno.
    """
    usuario_id = state.get("usuario_id", "")
    frase_atual = state.get("frase_atual_texto", "")

    if not usuario_id or not frase_atual:
        return {"historico_erros_contexto": ""}

    erros = buscar_erros_recorrentes(
        usuario_id=usuario_id,
        texto_consulta=frase_atual,
        limite=3,
    )

    if not erros:
        return {"historico_erros_contexto": ""}

    linhas = []

    for idx, err in enumerate(erros, 1):
        linhas.append(
            f"{idx}. Frase com erro: '{err['frase_original']}' "
            f"-> Correção C1: '{err['correcao_c1']}' "
            f"[{err['tipo_erro']}]: {err['explicacao']}"
        )

    contexto = "\n".join(linhas)

    logger.info(
        f"🧠 RAG recuperou {len(erros)} erros do Qdrant "
        f"para o usuário {usuario_id}"
    )

    return {"historico_erros_contexto": contexto}


def no_persistencia_rag(state: CoachState) -> dict:
    """
    Nó 6: Grava no Qdrant Cloud o erro de fricção
    identificado na sessão atual.
    """
    usuario_id = state.get("usuario_id", "")
    frase_original = state.get("frase_atual_texto", "")
    correcao_c1 = state.get("correcao_c1", "")
    categoria_erro = state.get("categoria_erro", "")
    explicacao = state.get("explicacao_erro", "")
    tem_erro = state.get("tem_erro", False)

    if tem_erro and usuario_id and frase_original and correcao_c1:
        salvar_erro_memoria(
            usuario_id=usuario_id,
            frase_original=frase_original,
            correcao_c1=correcao_c1,
            categoria_erro=categoria_erro or "frictional_error",
            explicacao=explicacao or "Correção C1 aplicada pelo tutor.",
        )

        logger.info(
            f"💾 Novo erro salvo no Qdrant para o usuário {usuario_id}"
        )

    return {}