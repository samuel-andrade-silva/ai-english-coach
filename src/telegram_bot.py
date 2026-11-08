import logging
import os

from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from config.settings import settings
from src.agent.graph import app as graph_app
from src.services.stt import transcrever_audio_groq
from src.services.tts import gerar_audio_resposta


# ==========================================
# CONFIGURAÇÃO DE LOGS
# ==========================================

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)

logger = logging.getLogger(__name__)


# ==========================================
# COMANDO /START
# ==========================================

async def start(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    """Responde ao comando /start no Telegram."""

    user_name = update.effective_user.first_name

    await update.message.reply_text(
        f"Hi {user_name}! 👋 I am your AI English Coach.\n"
        "Send me a text or record a voice note to practice your English!"
    )


# ==========================================
# PROCESSAMENTO DE MENSAGENS DE TEXTO
# ==========================================

async def processar_mensagem_texto(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    """Processa mensagens de texto enviadas pelo aluno."""

    texto_usuario = update.message.text
    user_id = str(update.effective_user.id)
    thread_id = f"telegram_{user_id}"

    logger.info(f"Texto recebido de {user_id}: '{texto_usuario}'")

    estado_inicial = {
        "usuario_id": user_id,
        "frase_atual_texto": texto_usuario,
    }

    config = {
        "configurable": {
            "thread_id": thread_id,
        }
    }

    try:
        resultado = graph_app.invoke(
            estado_inicial,
            config=config,
        )

        resposta_agente = resultado.get(
            "resposta_agente_texto",
            "Sorry, I couldn't process your message.",
        )

        await update.message.reply_text(resposta_agente)

    except Exception as e:
        logger.error(f"Erro no LangGraph (Texto): {e}")

        await update.message.reply_text(
            "⚠️ An error occurred while processing your request."
        )


# ==========================================
# PROCESSAMENTO DE MENSAGENS DE ÁUDIO
# ==========================================

async def processar_mensagem_audio(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    """
    Recebe o áudio, transcreve com Groq, processa no LangGraph
    e responde com voz usando Edge-TTS.
    """

    user_id = str(update.effective_user.id)
    thread_id = f"telegram_{user_id}"

    msg_status = await update.message.reply_text(
        "🎙️ *Listening to your voice note...*",
        parse_mode="Markdown",
    )

    os.makedirs("scratch", exist_ok=True)

    caminho_audio_temp = f"scratch/voice_{user_id}.ogg"
    caminho_resposta_audio = f"scratch/response_{user_id}.mp3"

    try:
        # 1. Baixa o áudio enviado pelo aluno
        voice_file = await context.bot.get_file(
            update.message.voice.file_id
        )

        await voice_file.download_to_drive(caminho_audio_temp)

        # 2. Transcreve com Groq Whisper
        texto_transcrito = transcrever_audio_groq(
            caminho_audio_temp
        )

        logger.info(
            f"Áudio de {user_id} transcrito: '{texto_transcrito}'"
        )

        await msg_status.edit_text(
            f"🗣️ *You said:* \"_{texto_transcrito}_\"\n\n"
            "🤔 *Analyzing and preparing voice response...*",
            parse_mode="Markdown",
        )

        # 3. Processa na esteira do LangGraph
        estado_inicial = {
            "usuario_id": user_id,
            "frase_atual_texto": texto_transcrito,
        }

        config = {
            "configurable": {
                "thread_id": thread_id,
            }
        }

        resultado = graph_app.invoke(
            estado_inicial,
            config=config,
        )

        resposta_agente = resultado.get(
            "resposta_agente_texto",
            "Sorry, I couldn't process your message.",
        )

        # 4. Envia a resposta em texto no Telegram
        await update.message.reply_text(resposta_agente)

        # 5. Gera a resposta em áudio com Edge-TTS
        await gerar_audio_resposta(
            resposta_agente,
            caminho_resposta_audio,
        )

        # 6. Envia o áudio como mensagem de voz no Telegram
        with open(caminho_resposta_audio, "rb") as audio_file:
            await update.message.reply_voice(
                voice=audio_file
            )

    except Exception as e:
        logger.error(f"Erro ao processar áudio: {e}")

        await msg_status.edit_text(
            "⚠️ Sorry, I could not process your audio message."
        )

    finally:
        # Limpeza dos arquivos temporários
        for caminho in [
            caminho_audio_temp,
            caminho_resposta_audio,
        ]:
            if os.path.exists(caminho):
                try:
                    os.remove(caminho)
                except Exception:
                    logger.warning(
                        f"Não foi possível remover o arquivo: {caminho}"
                    )


# ==========================================
# INICIALIZAÇÃO DO BOT
# ==========================================

def rodar_bot():
    """Inicia o servidor do bot do Telegram."""

    token = settings.telegram_bot_token

    if not token:
        raise ValueError(
            "❌ TELEGRAM_BOT_TOKEN não configurado no .env!"
        )

    application = (
        ApplicationBuilder()
        .token(token)
        .build()
    )

    # Registra os manipuladores
    application.add_handler(
        CommandHandler("start", start)
    )

    application.add_handler(
        MessageHandler(
            filters.TEXT & ~filters.COMMAND,
            processar_mensagem_texto,
        )
    )

    application.add_handler(
        MessageHandler(
            filters.VOICE,
            processar_mensagem_audio,
        )
    )

    logger.info(
        "🤖 Bot do Telegram rodando com Voz bidirecional "
        "(STT + TTS)! Pressione Ctrl+C para encerrar."
    )

    application.run_polling()


# ==========================================
# EXECUÇÃO PRINCIPAL
# ==========================================

if __name__ == "__main__":
    rodar_bot()