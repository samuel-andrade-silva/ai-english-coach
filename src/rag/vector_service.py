from datetime import datetime, timezone
import logging
import uuid
from typing import Any, Dict, List

from qdrant_client import QdrantClient
from qdrant_client.models import (
    Distance,
    FieldCondition,
    Filter,
    MatchValue,
    PayloadSchemaType,
    PointStruct,
    VectorParams,
)

from config.settings import settings
from src.rag.embeddings import gerar_embedding

logger = logging.getLogger(__name__)

COLLECTION_NAME = "erros_aluno"
VECTOR_SIZE = 384  # Dimensão do all-MiniLM-L6-v2


def obter_cliente_qdrant() -> QdrantClient:
    """Instancia o cliente Qdrant apontando para o Qdrant Cloud."""
    if not settings.qdrant_url or not settings.qdrant_api_key:
        raise ValueError(
            "❌ QDRANT_URL ou QDRANT_API_KEY não configurados no .env!"
        )

    return QdrantClient(
        url=settings.qdrant_url,
        api_key=settings.qdrant_api_key,
    )


def inicializar_colecao():
    """Garante que a coleção 'erros_aluno' e o índice de payload existam no Qdrant Cloud."""
    client = obter_cliente_qdrant()

    # Método nativo recomendado pela documentação do Qdrant
    if not client.collection_exists(collection_name=COLLECTION_NAME):
        logger.info(
            f"Criando coleção '{COLLECTION_NAME}' no Qdrant Cloud..."
        )

        client.create_collection(
            collection_name=COLLECTION_NAME,
            vectors_config=VectorParams(
                size=VECTOR_SIZE,
                distance=Distance.COSINE,
            ),
        )

        logger.info(f"Coleção '{COLLECTION_NAME}' criada com sucesso!")

    # Criação do índice de payload para o campo 'usuario_id'
    try:
        client.create_payload_index(
            collection_name=COLLECTION_NAME,
            field_name="usuario_id",
            field_schema=PayloadSchemaType.KEYWORD,
        )
    except Exception as e:
        logger.debug(f"Verificação do índice de payload: {e}")


def salvar_erro_memoria(
    usuario_id: str,
    frase_original: str,
    correcao_c1: str,
    categoria_erro: str,
    explicacao: str,
    registro_usado: str = "casual",
    recorrencias: int = 1,
):
    """Salva um erro de fricção do aluno no Qdrant Cloud no formato exigido pelo PRD."""
    client = obter_cliente_qdrant()

    inicializar_colecao()

    texto_vetorizar = (
        f"{frase_original} | erro: {categoria_erro} | {explicacao}"
    )

    vetor = gerar_embedding(texto_vetorizar)
    point_id = str(uuid.uuid4())

    payload = {
        "usuario_id": usuario_id,
        "tipo_erro": categoria_erro,
        "frase_original": frase_original,
        "correcao_c1": correcao_c1,
        "registro_usado": registro_usado,
        "explicacao": explicacao,
        "data": datetime.now(timezone.utc).isoformat(),
        "recorrencias": recorrencias,
    }

    client.upsert(
        collection_name=COLLECTION_NAME,
        points=[
            PointStruct(
                id=point_id,
                vector=vetor,
                payload=payload,
            )
        ],
    )

    logger.info(
        f"Erro salvo no Qdrant para o usuário {usuario_id}: "
        f"'{frase_original}'"
    )


def buscar_erros_recorrentes(
    usuario_id: str,
    texto_consulta: str,
    limite: int = 3,
) -> List[Dict[str, Any]]:
    """Recupera erros do histórico do aluno via busca semântica filtrada por usuario_id."""
    client = obter_cliente_qdrant()

    inicializar_colecao()

    vetor_consulta = gerar_embedding(texto_consulta)

    filtro_usuario = Filter(
        must=[
            FieldCondition(
                key="usuario_id",
                match=MatchValue(value=usuario_id),
            )
        ]
    )

    # API recomendada nas versões v1.10+ do Qdrant SDK (query_points com fallback)
    if hasattr(client, "query_points"):
        response = client.query_points(
            collection_name=COLLECTION_NAME,
            query=vetor_consulta,
            query_filter=filtro_usuario,
            limit=limite,
        )

        resultados = response.points

    else:
        resultados = client.search(
            collection_name=COLLECTION_NAME,
            query_vector=vetor_consulta,
            query_filter=filtro_usuario,
            limit=limite,
        )

    erros_encontrados = []

    for hit in resultados:
        erros_encontrados.append({
            "score": hit.score,
            "frase_original": hit.payload.get("frase_original"),
            "correcao_c1": hit.payload.get("correcao_c1"),
            "tipo_erro": hit.payload.get("tipo_erro"),
            "explicacao": hit.payload.get("explicacao"),
            "registro_usado": hit.payload.get("registro_usado"),
            "recorrencias": hit.payload.get("recorrencias", 1),
        })

    return erros_encontrados