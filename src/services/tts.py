import logging

import edge_tts


logger = logging.getLogger(__name__)


async def gerar_audio_resposta(
    texto: str,
    caminho_saida: str,
    voz: str = "en-US-AvaNeural",
) -> str:
    """
    Sintetiza o texto em áudio usando Microsoft Edge TTS.

    Vozes em inglês recomendadas:
    - en-US-AvaNeural: Feminina, muito natural.
    - en-US-ChristopherNeural: Masculina, natural.
    - en-US-GuyNeural: Masculina, natural.
    """

    logger.info(f"Sintetizando áudio ({voz}) para o texto...")

    communicate = edge_tts.Communicate(texto, voz)

    await communicate.save(caminho_saida)

    return caminho_saida