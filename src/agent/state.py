from typing import List, Optional, TypedDict


class CoachState(TypedDict):
    """
    Estado oficial do assistente AI English Coach.

    IMPORTANTE: `erros_friccao` e `expressoes_c1` NÃO usam o reducer
    `operator.add` de propósito. Com o checkpointer (SqliteSaver) um
    reducer acumulador carregaria os erros de TODOS os turnos anteriores
    da thread para sempre, causando exportações duplicadas no Anki.
    Cada turno sobrescreve a lista com apenas os erros da mensagem atual.
    """

    usuario_id: str
    thread_id: str
    canal_entrada: str

    frase_atual_texto: str
    historico_mensagens: List[dict]

    # Contexto recuperado do Qdrant pelo nó `rag_recovery`
    # (injetado no prompt do evaluator como "erros passados do aluno")
    historico_erros_contexto: str

    decisao_jev: Optional[dict]

    # Erros detectados apenas NO TURNO ATUAL (sobrescrita, sem reducer)
    erros_friccao: List[dict]
    expressoes_c1: List[dict]

    # Contexto bruto da busca web (nó `tavily`)
    contexto_tavily: Optional[str]

    resposta_agente_texto: str
    feedback_registro: Optional[dict]

    # Dados do erro identificado no turno (nó `evaluator`),
    # consumidos pelo nó `persistencia_rag`
    tem_erro: bool
    correcao_c1: str
    categoria_erro: str
    explicacao_erro: str

    arquivo_audio_resposta: Optional[str]
    sessao_ativa: bool
