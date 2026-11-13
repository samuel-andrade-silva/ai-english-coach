"""
Integration smoke test: AnkiConnect connectivity and card creation.

Run from the project root:
    python -m tests.test_anki

Requires: Anki Desktop running with the AnkiConnect add-on active
(default endpoint: http://localhost:8765, configurable via ANKI_CONNECT_URL).
"""

import sys
from pathlib import Path

# Allows direct execution (python tests/test_anki.py) from any working directory
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

# Windows consoles default to cp1252 and crash on emoji output
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from src.tools.anki_service import (
    testar_conexao_anki,
    adicionar_cartao_anki,
)


def testar_criacao_cartao_anki():
    print("🚀 Testing AnkiConnect connection...")

    if not testar_conexao_anki():
        print(
            "❌ Anki Desktop is not running. "
            "Open Anki and try again."
        )
        return

    print(
        "\n🎴 Creating a test card in the "
        "'English Coach::Errors' deck..."
    )

    # Simulates a friction error captured by the bot
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
            f"\n🎉 SUCCESS! Card created in Anki "
            f"with Note ID: {note_id}"
        )
        print(
            "👉 Open Anki Desktop and check the "
            "'English Coach::Errors' deck."
        )
    else:
        print(
            "\n⚠️ Could not create the card. "
            "Check the error logs."
        )


if __name__ == "__main__":
    testar_criacao_cartao_anki()
