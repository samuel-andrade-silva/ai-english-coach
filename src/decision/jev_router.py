import logging
from typing import Literal

from pydantic import BaseModel

from config.settings import settings

logger = logging.getLogger(__name__)


class RouterDecision(BaseModel):
    """Estrutura tipada de decisão retornada pelo Roteador."""

    rota: Literal["C1_REWRITE", "NEED_SEARCH", "CASUAL_CHAT"]
    confianca: float
    motivo: str


def classificar_intencao_aluno(texto_aluno: str) -> dict:
    """Classifica a intenção da frase e aplica o limiar de confiança (fail-safe)."""

    texto = texto_aluno.lower()

    # Lógica de triagem tipada (na Fase 2 com fallback/fail-safe)
    if "make a photo" in texto or "make a decision" in texto or "do a photo" in texto:
        rota = "C1_REWRITE"
        confianca = 0.95
        motivo = "Tradução literal ou vício de linguagem B2 detectado."

    elif "mean" in texto or "what is" in texto or "express" in texto:
        rota = "NEED_SEARCH"
        confianca = 0.88
        motivo = "Dúvida sobre significado ou expressão idiomática."

    else:
        rota = "CASUAL_CHAT"
        confianca = 0.90
        motivo = "Conversação casual sem vícios graves."

    # Aplicação do Limiar de Confiança (Fail-Safe Econômico)
    if confianca < settings.confianca_minima_router:
        logger.warning(
            "⚠️ Confiança (%.2f) abaixo do limiar (%.2f). "
            "Forçando CASUAL_CHAT.",
            confianca,
            settings.confianca_minima_router,
        )
        rota = "CASUAL_CHAT"

    decisao = RouterDecision(
        rota=rota,
        confianca=confianca,
        motivo=motivo,
    )

    return decisao.model_dump()