
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
from src.tools.anki_service import adicionar_cartao_anki

# Tenta importar módulos de áudio (STT e TTS) caso estejam disponíveis
try:
    from src.audio.stt import transcrever_audio_groq
    from src.audio.tts import gerar_audio_resposta

    AUDIO_DISPONIVEL = True

except ImportError:
    AUDIO_DISPONIVEL = False

logger = logging.getLogger(__name__)


async def start_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    """Comando /start: Mensagem de boas-vindas ao aluno."""
    await update.message.reply_text(
        "👋 **Hello! I'm your AI English Coach!**\n\n"
        "Estou aqui para ajudar você a alcançar a fluência C1 no inglês.\n"
        "Você pode me enviar mensagens de **texto** ou **áudio**.\n\n"
        "📌 **Comandos disponíveis:**\n"
        "• `/end_session` - Encerra a sessão e exporta todos os erros "
        "praticados para o **Anki**!"
    )


async def end_session_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    """
    Comando /end_session:
    Encerra a sessão atual e exporta os erros de fricção
    para o baralho 'English Coach::Errors' no Anki.
    """
    msg_espera = await update.message.reply_text(
        "⏳ Encerrando sessão de treino e exportando cartões para o Anki..."
    )

    # Recupera os erros acumulados durante esta sessão no Telegram
    erros_sessao = context.user_data.get("erros_sessao", [])

    logger.info(
        f"🎴 [END_SESSION] Total de erros acumulados na sessão: "
        f"{len(erros_sessao)}"
    )

    if not erros_sessao:
        await msg_espera.edit_text(
            "🏁 **Sessão encerrada!**\n\n"
            "Nenhum erro novo precisou ser registrado hoje. Great job! 👏"
        )
        return

    cartoes_criados = 0

    for erro in erros_sessao:
        note_id = adicionar_cartao_anki(
            frase_original=erro.get("frase_original", ""),
            correcao_c1=erro.get("correcao_c1", ""),
            explicacao=erro.get("explicacao", ""),
            categoria_erro=erro.get("categoria_erro", "Friction Error"),
        )

        if note_id:
            cartoes_criados += 1

    # Limpa o histórico da sessão pós-exportação
    context.user_data["erros_sessao"] = []

    await msg_espera.edit_text(
        f"✅ **Sessão finalizada com sucesso!**\n\n"
        f"🎴 **{cartoes_criados} novo(s) cartão(ões)** foram adicionados "
        f"ao seu baralho **'English Coach::Errors'** no Anki!\n\n"
        f"Bons estudos! 📚🚀"
    )


async def handle_text_message(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    """Processa mensagens de texto do aluno através da esteira do LangGraph."""
    usuario_id = str(update.effective_user.id)
    texto_aluno = update.message.text

    config = {"configurable": {"thread_id": usuario_id}}

    estado_inicial = {
        "usuario_id": usuario_id,
        "frase_atual_texto": texto_aluno,
        "canal_entrada": "texto",
    }

    # Executa a esteira do LangGraph
    resultado = graph_app.invoke(estado_inicial, config=config)

    # 1. Recupera a resposta do tutor
    resposta_texto = (
        resultado.get("resposta_agente_texto")
        or resultado.get("resposta_tutor")
        or "I'm sorry, I couldn't process your message."
    )

    # 2. Recupera os erros de fricção retornados pelo Evaluator
    erros_friccao = resultado.get("erros_friccao") or []

    if erros_friccao:
        for erro in erros_friccao:

            # Garante a extração dos dados, seja dict ou objeto
            if isinstance(erro, dict):
                correcao = (
                    erro.get("correcao_c1")
                    or erro.get("reescrita_c1")
                    or erro.get("correcao")
                    or str(erro)
                )

                explicacao = (
                    erro.get("explicacao")
                    or erro.get("explicacao_erro")
                    or "Correção C1 aplicada pelo tutor."
                )

                categoria = (
                    erro.get("categoria_erro")
                    or erro.get("tipo_erro")
                    or "Friction Error"
                )

            else:
                correcao = getattr(
                    erro,
                    "correcao_c1",
                    getattr(erro, "reescrita_c1", str(erro)),
                )

                explicacao = getattr(
                    erro,
                    "explicacao",
                    "Correção C1 aplicada pelo tutor.",
                )

                categoria = getattr(
                    erro,
                    "categoria_erro",
                    "Friction Error",
                )

            context.user_data.setdefault("erros_sessao", []).append(
                {
                    "frase_original": texto_aluno,
                    "correcao_c1": correcao,
                    "explicacao": explicacao,
                    "categoria_erro": categoria,
                }
            )

            logger.info(
                f"🎴 [ANKI] Erro adicionado à fila da sessão: "
                f"'{texto_aluno}' -> '{correcao}'"
            )

    else:
        logger.info(
            f"ℹ️ [ANKI] Nenhum erro de fricção registrado para: "
            f"'{texto_aluno}'"
        )

    await update.message.reply_text(resposta_texto)


async def handle_voice_message(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    """Processa mensagens de voz (STT -> LangGraph -> Telegram -> TTS)."""
    usuario_id = str(update.effective_user.id)

    # 1. Download do áudio do Telegram
    voice_file = await update.message.voice.get_file()

    os.makedirs("scratch", exist_ok=True)

    caminho_ogg = os.path.join(
        "scratch",
        f"voice_{update.message.message_id}.ogg",
    )

    await voice_file.download_to_drive(caminho_ogg)

    # 2. Transcrição STT (Groq Whisper)
    if AUDIO_DISPONIVEL:
        texto_transcrito = await transcrever_audio_groq(caminho_ogg)
    else:
        texto_transcrito = "Voice input received."

    # 3. Execução no LangGraph
    config = {"configurable": {"thread_id": usuario_id}}

    estado_inicial = {
        "usuario_id": usuario_id,
        "frase_atual_texto": texto_transcrito,
        "canal_entrada": "audio",
    }

    resultado = graph_app.invoke(estado_inicial, config=config)

    # 4. Recupera a resposta do tutor
    resposta_texto = (
        resultado.get("resposta_agente_texto")
        or resultado.get("resposta_tutor")
        or ""
    )

    # 5. Recupera os erros de fricção
    erros_friccao = resultado.get("erros_friccao") or []

    if erros_friccao:
        for erro in erros_friccao:

            if isinstance(erro, dict):
                correcao = (
                    erro.get("correcao_c1")
                    or erro.get("reescrita_c1")
                    or erro.get("correcao")
                    or str(erro)
                )

                explicacao = (
                    erro.get("explicacao")
                    or erro.get("explicacao_erro")
                    or "Correção C1 aplicada pelo tutor."
                )

                categoria = (
                    erro.get("categoria_erro")
                    or erro.get("tipo_erro")
                    or "Friction Error"
                )

            else:
                correcao = getattr(
                    erro,
                    "correcao_c1",
                    getattr(erro, "reescrita_c1", str(erro)),
                )

                explicacao = getattr(
                    erro,
                    "explicacao",
                    "Correção C1 aplicada pelo tutor.",
                )

                categoria = getattr(
                    erro,
                    "categoria_erro",
                    "Friction Error",
                )

            context.user_data.setdefault("erros_sessao", []).append(
                {
                    "frase_original": texto_transcrito,
                    "correcao_c1": correcao,
                    "explicacao": explicacao,
                    "categoria_erro": categoria,
                }
            )

            logger.info(
                f"🎴 [ANKI VOICE] Erro adicionado à fila da sessão: "
                f"'{texto_transcrito}' -> '{correcao}'"
            )

    # 6. Responde por texto
    await update.message.reply_text(resposta_texto)

    # 7. Envia áudio de resposta (TTS)
    if AUDIO_DISPONIVEL and resposta_texto:
        caminho_mp3 = await gerar_audio_resposta(resposta_texto)

        with open(caminho_mp3, "rb") as audio_file:
            await update.message.reply_voice(voice=audio_file)


def rodar_bot():
    """Inicializa e roda o bot do Telegram."""
    token = settings.telegram_bot_token

    if not token:
        raise ValueError(
            "❌ TELEGRAM_BOT_TOKEN não configurado no .env!"
        )

    app_bot = ApplicationBuilder().token(token).build()

    # Registro de Handlers
    app_bot.add_handler(CommandHandler("start", start_command))
    app_bot.add_handler(CommandHandler("end_session", end_session_command))

    app_bot.add_handler(
        MessageHandler(
            filters.TEXT & ~filters.COMMAND,
            handle_text_message,
        )
    )

    app_bot.add_handler(
        MessageHandler(
            filters.VOICE,
            handle_voice_message,
        )
    )

    logger.info("🤖 Telegram Bot online! Aguardando mensagens...")

    app_bot.run_polling()


if __name__ == "__main__":
    rodar_bot()
