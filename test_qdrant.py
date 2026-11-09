from src.rag.vector_service import (
    inicializar_colecao,
    salvar_erro_memoria,
    buscar_erros_recorrentes,
)


def testar_integracao_qdrant():
    print("🚀 Testando conexão e operações com Qdrant Cloud...")

    # 1. Inicializa a coleção no cluster
    inicializar_colecao()

    usuario_teste = "telegram_123456"

    # 2. Salva um erro de teste
    print("📥 Salvando erro de teste no Qdrant...")

    salvar_erro_memoria(
        usuario_id=usuario_teste,
        frase_original="I want to make a photo of this castle.",
        correcao_c1="I want to take a photo of this castle.",
        categoria_erro="literal_translation",
        explicacao="Em inglês usa-se 'take a photo' e não 'make a photo'.",
    )

    # 3. Busca semântica de um erro similar
    print("🔍 Realizando busca semântica por similaridade...")

    frase_nova = "Can you make a picture of us?"

    resultados = buscar_erros_recorrentes(
        usuario_id=usuario_teste,
        texto_consulta=frase_nova,
        limite=2,
    )

    print("\n✅ Resultados encontrados no Qdrant Cloud:")

    for res in resultados:
        print(
            f" - [Score: {res['score']:.4f}] "
            f"Original: '{res['frase_original']}' "
            f"-> Correção: '{res['correcao_c1']}'"
        )


if __name__ == "__main__":
    testar_integracao_qdrant()