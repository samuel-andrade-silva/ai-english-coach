import logging
import json
import urllib.request

from typing import Any, Dict, Optional

from config.settings import settings

logger = logging.getLogger(__name__)

NOME_BARALHO = "English Coach::Errors"


def obter_url_ankiconnect() -> str:
    """
    URL do AnkiConnect, configurável via ANKI_CONNECT_URL no .env.

    - Padrão: http://localhost:8765 (Anki na mesma máquina do bot)
    - Remoto: http://<IP_DO_ANKI>:8765 (Anki em outra máquina da rede)

    Para aceitar conexões externas, no Anki Desktop acesse:
    Ferramentas > Complementos > AnkiConnect > Configurar e ajuste:
        "webCorsOriginList": ["*"]
    depois reinicie o Anki.
    """
    return settings.anki_connect_url


def _executar_request_ankiconnect(
    action: str,
    params: Optional[Dict[str, Any]] = None,
) -> Any:
    """Função utilitária para enviar requisições HTTP para a API do AnkiConnect."""

    payload = {
        "action": action,
        "version": 6,
        "params": params or {},
    }

    data_bytes = json.dumps(payload).encode("utf-8")

    req = urllib.request.Request(
        obter_url_ankiconnect(),
        data=data_bytes,
        headers={"Content-Type": "application/json"},
    )

    try:
        with urllib.request.urlopen(req, timeout=3) as response:
            res = json.loads(response.read().decode("utf-8"))

            if res.get("error"):
                raise Exception(
                    f"Erro AnkiConnect ({action}): {res['error']}"
                )

            return res.get("result")

    except Exception as e:
        logger.error(
            f"❌ Não foi possível comunicar com o AnkiConnect "
            f"em {obter_url_ankiconnect()}: {e}"
        )
        raise


def testar_conexao_anki() -> bool:
    """Verifica se o Anki Desktop e a extensão AnkiConnect estão ativos."""

    try:
        versao = _executar_request_ankiconnect("version")

        logger.info(
            f"✅ Conectado ao AnkiConnect! Versão da API: {versao}"
        )

        return True

    except Exception:
        return False


def garantir_baralho_existente(
    nome_baralho: str = NOME_BARALHO,
):
    """Garante que o baralho 'English Coach::Errors' exista no Anki do aluno."""

    try:
        _executar_request_ankiconnect(
            "createDeck",
            {"deck": nome_baralho},
        )

        logger.info(
            f"✅ Baralho '{nome_baralho}' verificado/criado com sucesso!"
        )

    except Exception as e:
        logger.warning(
            f"Não foi possível criar o baralho no Anki: {e}"
        )

def adicionar_cartao_anki(
    frase_original: str,
    correcao_c1: str,
    explicacao: str,
    categoria_erro: str = "Friction Error",
    nome_baralho: str = NOME_BARALHO,
) -> Optional[int]:
    """
    Cria uma nova nota (Flashcard) no Anki com o erro de fricção
    e a reescrita C1.

    Retorna o ID da nota criada no AnkiConnect.
    """

    garantir_baralho_existente(nome_baralho)

    # Formatação visual limpa em HTML para o cartão do Anki
    frente_html = f"""
    ⚠️ Complete / Corrija a frase:

    "{frase_original}"
    """

    verso_html = f"""
    ✨ Versão C1 Fluente:

    "{correcao_c1}"

    <hr>

    <b>Categoria:</b> {categoria_erro}<br>
    <b>Explicação:</b> {explicacao}
    """

    nota_payload = {
        "note": {
            "deckName": nome_baralho,
            "modelName": "Basic",
            "fields": {
                "Front": frente_html,
                "Back": verso_html,
            },
            "options": {
                "allowDuplicate": False,
                "duplicateScope": "deck",
            },
            "tags": [
                "ai-english-coach",
                "c1-fluency",
            ],
        }
    }

    try:
        note_id = _executar_request_ankiconnect(
            "addNote",
            nota_payload,
        )

        logger.info(
            f"✅ Cartão criado no Anki com sucesso! Note ID: {note_id}"
        )

        return note_id

    except Exception as e:
        logger.warning(
            f"Não foi possível adicionar cartão no Anki: {e}"
        )

        return None