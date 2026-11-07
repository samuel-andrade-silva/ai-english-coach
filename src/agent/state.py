import operator
from typing import Annotated, List, Optional, TypedDict


class CoachState(TypedDict):
    """
    Estado oficial do assistente AI English Coach.
    """

    usuario_id: str
    thread_id: str
    canal_entrada: str

    frase_atual_texto: str
    historico_mensagens: List[dict]
    contexto_rag_memoria: List[str]

    decisao_jev: Optional[dict]

    erros_friccao: Annotated[List[dict], operator.add]
    expressoes_c1: Annotated[List[dict], operator.add]

    pesquisa_tavily_contexto: Optional[str]
    resposta_agente_texto: str
    feedback_registro: Optional[dict]

    arquivo_audio_resposta: Optional[str]
    sessao_ativa: bool