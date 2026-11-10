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
from src.tools.anki_service import adicionar_cartao_anki


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
# COMANDO /END_SESSION (ANKI EXPORT)
# ==========================================

async def end_session_handler(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    """
    Comando /end_session: Encerra a sessão atual e exporta os erros
    de fricção praticados para o Anki.
    """
    usuario_id = str(update.effective_user.id)
    chat_id = update.effective_chat.id

    await update.message.reply_text("⏳ Encerrando sessão de treino e exportando cartões para o Anki...")

    # Recupera o histórico/erros acumulados no contexto da sessão
    erros_sessao = context.user_data.get("erros_sessao", [])

    if not erros_sessao:
        await update.message.reply_text(
            "🏁 Sessão encerrada! Nenhum erro novo precisou ser registrado para o Anki hoje. Great job! 👏"
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

    # Limpa os erros da memória da sessão após exportar
    context.user_data["erros_sessao"] = []

    await update.message.reply_text(
        f"✅ Sessão finalizada com sucesso!\n\n"
        f"🎴 **{cartoes_criados} novos cartões** foram adicionados ao seu baralho **'English Coach::Errors'** no Anki."
    )


# ==========================================
# PROCESSAMENTO DE MENSAGENS DE TEXTO
# ==========================================

async def processar_mensagem_texto(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    """Processa mensagens de texto do aluno através da esteira do LangGraph."""
    usuario_id = str(update.effective_user.id)
    texto_aluno = update.message.text
    thread_id = f"telegram_{usuario_id}"

    logger.info(f"Texto recebido de {usuario_id}: '{texto_aluno}'")

    config = {"configurable": {"thread_id": thread_id}}
    estado_inicial = {
        "usuario_id": usuario_id,
        "frase_atual_texto": texto_aluno,
        "canal_entrada": "texto",
    }

    try:
        # Executa a esteira do LangGraph
        resultado = graph_app.invoke(estado_inicial, config=config)
        resposta_texto = resultado.get("resposta_tutor") or resultado.get(
            "resposta_agente_texto", "I'm sorry, I couldn't process your message."
        )

        # 🔍 Busca a correção C1 no estado (tenta correcao_c1, reescrita_c1 ou decisao_jev)
        correcao = resultado.get("correcao_c1") or resultado.get("reescrita_c1")
        decisao = resultado.get("decisao_jev") or {}

        if not correcao and isinstance(decisao, dict):
            correcao = decisao.get("correcao_c1") or decisao.get("reescrita_c1")

        tem_erro = resultado.get("tem_erro") or bool(correcao)

        # Se houver correção C1 identificada, salva para o Anki
        if tem_erro and correcao:
            context.user_data.setdefault("erros_sessao", []).append({
                "frase_original": texto_aluno,
                "correcao_c1": correcao,
                "explicacao": resultado.get("explicacao_erro") or resultado.get("motivo") or "Correção C1 aplicada pelo tutor.",
                "categoria_erro": resultado.get("categoria_erro", "Friction Error"),
            })
            logger.info(f"🎴 Erro capturado para a fila do Anki: '{texto_aluno}' -> '{correcao}'")

        await update.message.reply_text(resposta_texto)

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
            "canal_entrada": "audio",
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

        resposta_agente = resultado.get("resposta_tutor") or resultado.get(
            "resposta_agente_texto", "Sorry, I couldn't process your message."
        )

        # Captura de erros de áudio também para o Anki (opcional, mas recomendado)
        correcao = resultado.get("correcao_c1") or resultado.get("reescrita_c1")
        decisao = resultado.get("decisao_jev") or {}
        if not correcao and isinstance(decisao, dict):
            correcao = decisao.get("correcao_c1") or decisao.get("reescrita_c1")

        tem_erro = resultado.get("tem_erro") or bool(correcao)

        if tem_erro and correcao:
            context.user_data.setdefault("erros_sessao", []).append({
                "frase_original": texto_transcrito,
                "correcao_c1": correcao,
                "explicacao": resultado.get("explicacao_erro") or resultado.get("motivo") or "Correção C1 aplicada pelo tutor.",
                "categoria_erro": resultado.get("categoria_erro", "Friction Error"),
            })
            logger.info(f"🎴 Erro de áudio capturado para o Anki: '{texto_transcrito}' -> '{correcao}'")

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
            if os.path.exists(caminio if 'caminio' in locals() else caminho):
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
        CommandHandler("end_session", end_session_handler)
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