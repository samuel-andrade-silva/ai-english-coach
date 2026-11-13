import logging
import re

from langchain_groq import ChatGroq

from config.settings import settings
from src.agent.state import CoachState
from src.decision.jev_router import classificar_intencao_aluno

from src.tools.tavily_search import buscar_tavily

from src.rag.vector_service import (
    buscar_erros_recorrentes,
    salvar_erro_memoria,
)

logger = logging.getLogger(__name__)

# Instância única do LLM (evita criar um cliente novo a cada chamada)
_llm_instance = None


def obter_llm() -> ChatGroq:
    """Instancia (e cacheia) o cliente LLM da Groq com a chave do .env."""
    global _llm_instance

    if _llm_instance is None:
        _llm_instance = ChatGroq(
            groq_api_key=settings.groq_api_key,
            model_name=settings.groq_model,
            temperature=0.7,
        )

    return _llm_instance


def _groq_configurada() -> bool:
    """Verifica se há uma chave real da Groq configurada no .env."""
    return bool(settings.groq_api_key) and settings.groq_api_key != "sua_chave_groq_aqui"


# ==========================================
# NÓ 0: RECUPERAÇÃO RAG (Qdrant)
# ==========================================

def no_recuperacao_rag(state: CoachState) -> dict:
    """
    Nó 0: Busca no Qdrant o histórico de erros similares do aluno
    e injeta o contexto no prompt do evaluator.

    Falhas de rede/credenciais NÃO derrubam o grafo (degradação graciosa).
    """
    usuario_id = state.get("usuario_id", "")
    frase_atual = state.get("frase_atual_texto", "")

    if not usuario_id or not frase_atual:
        return {"historico_erros_contexto": ""}

    try:
        erros = buscar_erros_recorrentes(
            usuario_id=usuario_id,
            texto_consulta=frase_atual,
            limite=3,
        )
    except Exception as e:
        logger.warning(
            "🧠 RAG indisponível no momento (degradação graciosa): %s", e
        )
        return {"historico_erros_contexto": ""}

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
        "🧠 RAG recuperou %d erro(s) do Qdrant para o usuário %s",
        len(erros),
        usuario_id,
    )

    return {"historico_erros_contexto": contexto}


# ==========================================
# NÓ 1: TRIAGEM JEV
# ==========================================

def no_triagem_jev(state: CoachState) -> dict:
    """Nó 1: Roteador inteligente tipado Jev com Limiar de Confiança."""
    logger.info(
        "🔎 [NÓ 1: TRIAGEM JEV] Analisando: '%s'", state["frase_atual_texto"]
    )

    decisao = classificar_intencao_aluno(state["frase_atual_texto"])

    logger.info("Decisão do Roteador: %s", decisao)

    return {"decisao_jev": decisao}


# ==========================================
# NÓ 2: EVALUATOR C1 (LLM Groq)
# ==========================================

_PADRAO_ITEM = re.compile(r"^\s*(?:\d+\s*[.)]|[-*•])\s*")

_ROTULOS_REESCRITAS = {
    "casual": ("casual", "natural"),
    "profissional": ("professional", "formal"),
    "idiomatica": ("idiomatic",),
}


def _extrair_reescritas(resposta: str) -> dict:
    """Extrai as 3 reescritas da resposta da LLM (formato pedindo no prompt)."""
    reescritas = {"casual": "", "profissional": "", "idiomatica": ""}

    for linha in resposta.splitlines():
        linha = linha.strip()

        if not linha:
            continue

        low = linha.lower()

        for registro, chaves in _ROTULOS_REESCRITAS.items():
            if reescritas[registro]:
                continue

            if any(chave in low for chave in chaves):
                valor = (
                    linha.split(":", 1)[1]
                    if ":" in linha
                    else _PADRAO_ITEM.sub("", linha)
                )
                reescritas[registro] = valor.strip().strip('"')

    return reescritas


def no_evaluator_c1(state: CoachState) -> dict:
    """
    Nó 2: Chama a LLM real da Groq para gerar reescritas C1 em 3 registros.

    Falha na API NÃO derruba o grafo: responde com mensagem de
    indisponibilidade e NÃO persiste erro no Qdrant.
    """
    frase = state["frase_atual_texto"]
    contexto_historico = state.get("historico_erros_contexto") or ""

    logger.info("🎓 [NÓ 2: EVALUATOR C1] frase=%r", frase)

    contexto_extra = ""
    if contexto_historico:
        contexto_extra = (
            "Known past mistakes of this student (avoid repeating them):\n"
            f"{contexto_historico}\n"
        )

    prompt = f"""You are an expert C1/C2 English Coach.
The student said: "{frase}"

{contexto_extra}
Provide 3 natural C1 rewrites, in EXACTLY this format:
1. Casual / Natural: <rewrite>
2. Professional / Formal: <rewrite>
3. Idiomatic: <rewrite>

Then finish with one short, encouraging sentence of feedback."""

    if _groq_configurada():
        try:
            resposta = obter_llm().invoke(prompt).content
        except Exception as e:
            logger.error("❌ Falha na chamada Groq (degradação graciosa): %s", e)
            resposta = ""
    else:
        logger.warning("GROQ_API_KEY não configurada — usando modo stub.")
        resposta = (
            f"[MODO STUB] Reescritas para '{frase}': "
            "Use 'take a photo' instead of 'make a photo'.\n"
            "1. Casual / Natural: take a photo\n"
            "2. Professional / Formal: capture an image\n"
            "3. Idiomatic: snap a picture"
        )

    if not resposta:
        return {
            "resposta_agente_texto": (
                "I couldn't analyze your sentence right now "
                "(the AI service is unavailable). Could you try again "
                "in a moment? 🙏"
            ),
            "tem_erro": False,
            "erros_friccao": [],
        }

    reescritas = _extrair_reescritas(resposta)

    correcao_c1 = (
        reescritas["casual"]
        or reescritas["profissional"]
        or reescritas["idiomatica"]
        or resposta.strip()
    )

    erro_registrado = {
        "original": frase,
        "tipo": "literal_translation",
        "correcao_c1": correcao_c1,
        "explicacao": resposta,
    }

    logger.info("🎴 Erro de fricção registrado: '%s' -> '%s'", frase, correcao_c1)

    return {
        "resposta_agente_texto": resposta,
        "feedback_registro": reescritas,
        "erros_friccao": [erro_registrado],
        "tem_erro": True,
        "correcao_c1": correcao_c1,
        "categoria_erro": "literal_translation",
        "explicacao_erro": resposta,
    }


# ==========================================
# NÓ 3: BUSCA WEB TAVILY
# ==========================================

def no_tavily_search(state: CoachState) -> dict:
    """Nó 3: Busca exemplos reais na web quando o Jev decide 'NEED_SEARCH'."""
    frase_aluno = state.get("frase_atual_texto", "")

    logger.info(
        "🌐 [NÓ 3: TAVILY SEARCH] Buscando exemplos reais para: '%s'",
        frase_aluno,
    )

    # Busca com degradação graciosa (timeout de 5s tratado na ferramenta)
    exemplos_web = buscar_tavily(frase_aluno)

    if exemplos_web:
        resposta = (
            "Here are some real-world examples of how native speakers use "
            "this context:\n\n"
            f"{exemplos_web}\n\n"
            "Would you like to practice creating a sentence with one of "
            "these structures?"
        )
    else:
        resposta = (
            "I searched for real-world usage examples, but couldn't retrieve "
            "them right now. However, let's practice this collocation "
            "directly! How would you use it in a work scenario?"
        )

    return {
        "resposta_agente_texto": resposta,
        "contexto_tavily": exemplos_web,
    }


# ==========================================
# NÓ 4: CONVERSADOR CASUAL (LLM Groq)
# ==========================================

def no_conversador(state: CoachState) -> dict:
    """
    Nó 4: LLM real para conversação casual quando não há erros graves.

    Falha na API NÃO derruba o grafo.
    """
    frase = state["frase_atual_texto"]

    logger.info("💬 [NÓ 4: CONVERSADOR CASUAL] frase=%r", frase)

    prompt = f"""You are a friendly, encouraging English conversation coach.
Respond naturally in fluent English to the student: "{frase}"
Keep the conversation engaging and ask an open follow-up question."""

    if _groq_configurada():
        try:
            resposta = obter_llm().invoke(prompt).content
        except Exception as e:
            logger.error("❌ Falha na chamada Groq (degradação graciosa): %s", e)
            resposta = ""
    else:
        logger.warning("GROQ_API_KEY não configurada — usando modo stub.")
        resposta = f"[MODO STUB] That sounds great! Tell me more about '{frase}'."

    return {
        "resposta_agente_texto": (
            resposta
            or "I'm having a little connection issue right now — "
            "let's keep practicing in a moment! 🙌"
        ),
        # Importante: resetar a flag para não persistir erro de turno anterior
        "tem_erro": False,
    }


# ==========================================
# NÓ 5: PERSISTÊNCIA RAG (Qdrant)
# ==========================================

def no_persistencia_rag(state: CoachState) -> dict:
    """
    Nó 5: Grava no Qdrant o erro de fricção identificado no turno atual.
    Só executa quando `tem_erro` foi marcado pelo evaluator (nó 2).
    """
    usuario_id = state.get("usuario_id", "")
    frase_original = state.get("frase_atual_texto", "")
    correcao_c1 = state.get("correcao_c1", "")
    categoria_erro = state.get("categoria_erro", "")
    explicacao = state.get("explicacao_erro", "")
    tem_erro = state.get("tem_erro", False)

    if tem_erro and usuario_id and frase_original and correcao_c1:
        try:
            salvar_erro_memoria(
                usuario_id=usuario_id,
                frase_original=frase_original,
                correcao_c1=correcao_c1,
                categoria_erro=categoria_erro or "frictional_error",
                explicacao=explicacao or "Correção C1 aplicada pelo tutor.",
            )

            logger.info("💾 Novo erro salvo no Qdrant para o usuário %s", usuario_id)

        except Exception as e:
            logger.error("❌ Falha ao salvar erro no Qdrant: %s", e)

    return {}
