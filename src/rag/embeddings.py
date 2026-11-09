import logging
from typing import List

from sentence_transformers import SentenceTransformer

logger = logging.getLogger(__name__)

# Modelo leve e eficiente (384 dimensões)
MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"

_model_instance = None


def carregar_modelo_embeddings() -> SentenceTransformer:
    """Carrega o modelo de embeddings em memória de forma lazy."""
    global _model_instance

    if _model_instance is None:
        logger.info(f"Carregando modelo de embeddings '{MODEL_NAME}'...")
        _model_instance = SentenceTransformer(MODEL_NAME)

    return _model_instance


def gerar_embedding(texto: str) -> List[float]:
    """Gera um vetor numérico (embedding) para o texto fornecido."""
    model = carregar_modelo_embeddings()
    embedding = model.encode(texto, convert_to_numpy=True)

    return embedding.tolist()