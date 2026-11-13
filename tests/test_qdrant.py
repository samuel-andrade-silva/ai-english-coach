"""
Integration smoke test: Qdrant Cloud collection, upsert and semantic search.

Run from the project root:
    python -m tests.test_qdrant

Requires: QDRANT_URL / QDRANT_API_KEY configured in the .env file.

⚠️  NOTE: this test writes data into the REAL `erros_aluno` collection
using the dedicated test user id `telegram_123456`.
"""

import sys
from pathlib import Path

# Allows direct execution (python tests/test_qdrant.py) from any working directory
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

# Windows consoles default to cp1252 and crash on emoji output
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from src.rag.vector_service import (
    inicializar_colecao,
    salvar_erro_memoria,
    buscar_erros_recorrentes,
)


def testar_integracao_qdrant():
    print("🚀 Testing Qdrant Cloud connection and operations...")

    # 1. Initializes the collection in the cluster
    inicializar_colecao()

    usuario_teste = "telegram_123456"

    # 2. Saves a test error
    print("📥 Saving test error to Qdrant...")

    salvar_erro_memoria(
        usuario_id=usuario_teste,
        frase_original="I want to make a photo of this castle.",
        correcao_c1="I want to take a photo of this castle.",
        categoria_erro="literal_translation",
        explicacao="Em inglês usa-se 'take a photo' e não 'make a photo'.",
    )

    # 3. Semantic search for a similar error
    print("🔍 Performing semantic similarity search...")

    frase_nova = "Can you make a picture of us?"

    resultados = buscar_erros_recorrentes(
        usuario_id=usuario_teste,
        texto_consulta=frase_nova,
        limite=2,
    )

    print("\n✅ Results found in Qdrant Cloud:")

    for res in resultados:
        print(
            f" - [Score: {res['score']:.4f}] "
            f"Original: '{res['frase_original']}' "
            f"-> Correction: '{res['correcao_c1']}'"
        )


if __name__ == "__main__":
    testar_integracao_qdrant()
