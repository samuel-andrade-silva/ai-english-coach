import logging
import os

from groq import Groq

from config.settings import settings


logger = logging.getLogger(__name__)


def transcrever_audio_groq(caminho_arquivo_audio: str) -> str:
    """
    Envia um arquivo de áudio (.ogg, .mp3, .wav) para a API Groq Whisper
    e retorna o texto transcrito em inglês.
    """

    if not settings.groq_api_key:
        raise ValueError("GROQ_API_KEY não configurada no .env!")

    client = Groq(api_key=settings.groq_api_key)

    logger.info(
        f"Enviando arquivo '{caminho_arquivo_audio}' "
        "para transcrição no Groq Whisper..."
    )

    with open(caminho_arquivo_audio, "rb") as audio_file:
        transcription = client.audio.transcriptions.create(
            file=(
                os.path.basename(caminho_arquivo_audio),
                audio_file.read(),
            ),
            model="whisper-large-v3-turbo",
            response_format="json",
            language="en",  # Força a transcrição focada em inglês
            temperature=0.0,
        )

    return transcription.text