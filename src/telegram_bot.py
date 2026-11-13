import asyncio
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
from src.tools.anki_service import adicionar_cartao_anki, testar_conexao_anki

# Tenta importar módulos de áudio (STT e TTS) caso estejam disponíveis
try:
    from src.services.stt import transcrever_audio_groq
    from src.services.tts import gerar_audio_resposta

    AUDIO_DISPONIVEL = True

except ImportError:
    AUDIO_DISPONIVEL = False

logger = logging.getLogger(__name__)

if not AUDIO_DISPONIVEL:
    logger.warning(
        "Módulos de áudio (src.services.stt / src.services.tts) "
        "não puderam ser importados — mensagens de voz ficarão desativadas."
    )

PASTA_TEMP = "scratch"


# ==========================================
# Helpers (deduplicação entre handlers)
# ==========================================

def _extrair_dados_erro(erro) -> dict:
    """Normaliza um erro de fricção (dict ou objeto) para a fila do Anki."""
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
        correcao = getattr(erro, "correcao_c1", None) or str(erro)

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

    return {
        "correcao_c1": correcao,
        "explicacao": explicacao,
        "categoria_erro": categoria,
    }


def _registrar_erros_sessao(
    erros_friccao,
    frase_original: str,
    user_data: dict,
) -> int:
    """
    Adiciona os erros do turno à fila de exportação do Anki,
    ignorando duplicatas (mesma frase + mesma correção).
    Retorna a quantidade de erros NOVOS adicionados.
    """
    fila = user_data.setdefault("erros_sessao", [])
    novos = 0

    for erro in erros_friccao or []:
        dados = _extrair_dados_erro(erro)
        chave = (frase_original, dados["correcao_c1"])

        if any(
            (item.get("frase_original"), item.get("correcao_c1")) == chave
            for item in fila
        ):
            continue

        fila.append({"frase_original": frase_original, **dados})
        novos += 1

        logger.info(
            "🎴 [ANKI] Erro adicionado à fila da sessão: "
            "'%s' -> '%s'",
            frase_original,
            dados["correcao_c1"],
        )

    return novos


async def _processar_no_grafo(usuario_id: str, texto: str, canal: str) -> dict:
    """Executa a esteira LangGraph (async, sem travar o event loop)."""
    config = {"configurable": {"thread_id": usuario_id}}

    estado_inicial = {
        "usuario_id": usuario_id,
        "frase_atual_texto": texto,
        "canal_entrada": canal,
    }

    try:
        return await graph_app.ainvoke(estado_inicial, config=config)

    except Exception:
        logger.exception("Falha inesperada na esteira do LangGraph.")
        return {}


# ==========================================
# Comandos
# ==========================================

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
        "🎴 [END_SESSION] Total de erros acumulados na sessão: %d",
        len(erros_sessao),
    )

    if not erros_sessao:
        await msg_espera.edit_text(
            "🏁 **Sessão encerrada!**\n\n"
            "Nenhum erro novo precisou ser registrado hoje. Great job! 👏"
        )
        return

    # Verifica o Anki ANTES de tentar exportar (evita perder a fila)
    if not testar_conexao_anki():
        await msg_espera.edit_text(
            "⚠️ **Não consegui falar com o AnkiConnect.**\n\n"
            "Verifique se o Anki Desktop está aberto (com a extensão "
            "AnkiConnect ativa) e tente `/end_session` novamente.\n"
            "Seus erros **continuam salvos na fila** — nada foi perdido! 🔒"
        )
        return

    cartoes_criados = 0

    for erro in erros_sessao:
        # Chamada síncrona (urllib) roda em thread para não travar o bot
        note_id = await asyncio.to_thread(
            adicionar_cartao_anki,
            frase_original=erro.get("frase_original", ""),
            correcao_c1=erro.get("correcao_c1", ""),
            explicacao=erro.get("explicacao", ""),
            categoria_erro=erro.get("categoria_erro", "Friction Error"),
        )

        if note_id:
            cartoes_criados += 1

    if cartoes_criados == len(erros_sessao):
        # Limpa o histórico da sessão apenas se TUDO foi exportado
        context.user_data["erros_sessao"] = []

        await msg_espera.edit_text(
            "✅ **Sessão finalizada com sucesso!**\n\n"
            f"🎴 **{cartoes_criados} novo(s) cartão(ões)** foram adicionados "
            "ao seu baralho **'English Coach::Errors'** no Anki!\n\n"
            "Bons estudos! 📚🚀"
        )

    else:
        restantes = len(erros_sessao) - cartoes_criados

        await msg_espera.edit_text(
            f"⚠️ **{cartoes_criados} cartão(ões)** criado(s), mas "
            f"**{restantes}** falharam.\n\n"
            "Os que falharam **continuam na fila** — tente "
            "`/end_session` novamente."
        )


# ==========================================
# Mensagens
# ==========================================

async def handle_text_message(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    """Processa mensagens de texto do aluno através da esteira do LangGraph."""
    usuario_id = str(update.effective_user.id)
    texto_aluno = update.message.text

    resultado = await _processar_no_grafo(usuario_id, texto_aluno, "texto")

    resposta_texto = (
        resultado.get("resposta_agente_texto")
        or "I'm sorry, I couldn't process your message. Please try again."
    )

    novos = _registrar_erros_sessao(
        resultado.get("erros_friccao") or [],
        texto_aluno,
        context.user_data,
    )

    if not novos:
        logger.info(
            "ℹ️ [ANKI] Nenhum erro de fricção registrado para: '%s'",
            texto_aluno,
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

    os.makedirs(PASTA_TEMP, exist_ok=True)

    caminho_ogg = os.path.join(
        PASTA_TEMP,
        f"voice_{update.message.message_id}.ogg",
    )

    caminho_mp3 = os.path.join(
        PASTA_TEMP,
        f"resp_{update.message.message_id}.mp3",
    )

    await voice_file.download_to_drive(caminho_ogg)

    try:
        # 2. Transcrição STT (Groq Whisper) — função síncrona roda em
        #    thread para não travar o event loop do bot
        if AUDIO_DISPONIVEL:
            try:
                texto_transcrito = await asyncio.to_thread(
                    transcrever_audio_groq,
                    caminho_ogg,
                )
            except Exception as e:
                logger.error(
                    "❌ Falha na transcrição STT (degradação graciosa): %s", e
                )
                texto_transcrito = ""
        else:
            texto_transcrito = ""

        if not texto_transcrito:
            await update.message.reply_text(
                "I couldn't transcribe your audio right now. "
                "Could you type it instead? 🙏"
            )
            return

        # 3. Execução no LangGraph
        resultado = await _processar_no_grafo(
            usuario_id, texto_transcrito, "audio"
        )

        resposta_texto = resultado.get("resposta_agente_texto") or ""

        _registrar_erros_sessao(
            resultado.get("erros_friccao") or [],
            texto_transcrito,
            context.user_data,
        )

        # 4. Responde por texto
        await update.message.reply_text(
            resposta_texto
            or "I processed your message, but couldn't generate a response."
        )

        # 5. Envia áudio de resposta (TTS)
        if AUDIO_DISPONIVEL and resposta_texto:
            try:
                await gerar_audio_resposta(resposta_texto, caminho_mp3)

                with open(caminho_mp3, "rb") as audio_file:
                    await update.message.reply_voice(voice=audio_file)

            except Exception as e:
                logger.error(
                    "❌ Falha no TTS (resposta enviada apenas em texto): %s", e
                )

    finally:
        # Limpeza dos arquivos temporários de áudio
        for caminho in (caminho_ogg, caminho_mp3):
            try:
                os.remove(caminho)
            except OSError:
                pass


# ==========================================
# Inicialização
# ==========================================

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
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    )
    rodar_bot()
