from src.tools.anki_service import (
    testar_conexao_anki,
    adicionar_cartao_anki,
)


def testar_criacao_cartao_anki():
    print("🚀 Testando conexão com o AnkiConnect...")

    if not testar_conexao_anki():
        print(
            "❌ O Anki Desktop não está rodando. "
            "Abra o Anki e tente novamente."
        )
        return

    print(
        "\n🎴 Criando cartão de teste no baralho "
        "'English Coach::Errors'..."
    )

    # Simula o envio de um erro de fricção capturado pelo bot
    note_id = adicionar_cartao_anki(
        frase_original="I want to make a photo of the party.",
        correcao_c1="I want to take a photo of the party.",
        explicacao=(
            "Em inglês, a colocação correta para fotos é "
            "'take a photo' ou 'take a picture', e não 'make'."
        ),
        categoria_erro="Collocation Error (B2 -> C1)",
    )

    if note_id:
        print(
            f"\n🎉 SUCESSO! Cartão criado no Anki "
            f"com Note ID: {note_id}"
        )
        print(
            "👉 Abra o Anki Desktop e confira o baralho "
            "'English Coach::Errors'."
        )
    else:
        print(
            "\n⚠️ Não foi possível criar o cartão. "
            "Verifique os logs de erro."
        )


if __name__ == "__main__":
    testar_criacao_cartao_anki()