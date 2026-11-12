
import logging
from typing import Optional

from config.settings import settings

logger = logging.getLogger(__name__)

# Tenta importar a SDK da Tavily
try:
    from tavily import TavilyClient

    TAVILY_DISPONIVEL = True
except ImportError:
    TAVILY_DISPONIVEL = False


def buscar_tavily(query: str, timeout: int = 5) -> Optional[str]:
    """
    Realiza busca web via Tavily para validar expressões e collocations C1 em inglês.

    Retorna um resumo com trechos reais ou None em caso de falha/timeout
    (degradação graciosa).
    """

    api_key = settings.tavily_api_key

    if not api_key or not TAVILY_DISPONIVEL:
        logger.warning(
            "⚠️ API Key da Tavily não configurada ou biblioteca não instalada."
        )
        return None

    try:
        client = TavilyClient(api_key=api_key)

        # Busca focada em contexto de inglês e notícias/artigos reais
        resultado = client.search(
            query=f"English usage example collocation '{query}'",
            search_depth="basic",
            max_results=3,
            timeout=timeout,
        )

        snippets = []

        for item in resultado.get("results", []):
            title = item.get("title", "")
            content = item.get("content", "")

            snippets.append(f"• {title}: {content}")

        resumo = "\n".join(snippets)

        logger.info(
            f"🔍 [TAVILY] {len(snippets)} exemplos encontrados para: '{query}'"
        )

        return resumo

    except Exception as e:
        logger.warning(
            f"⚠️ Falha na busca Tavily (degradação graciosa ativada): {e}"
        )
        return None
