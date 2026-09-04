"""La chaîne complète : question → réponse, sources et coût.

Un seul point d'entrée, `answerQuestion`. Tout ce dont il a besoin lui est
passé en argument — index, client, prompt. Aucun état global, aucune lecture
d'environnement : c'est ce qui permet de le tester entièrement hors ligne.
"""

import logging
import time

from rag.client import ModelClient
from rag.generation import generateAnswer
from rag.index import LexicalIndex
from rag.models import EMPTY_USAGE, Answer

TOP_K = 4

REFUSAL_TEXT = (
    "Je ne sais pas : la documentation fournie ne contient pas de réponse "
    "à cette question."
)

logger = logging.getLogger(__name__)


def answerQuestion(
    client: ModelClient,
    index: LexicalIndex,
    question: str,
    promptTemplate: str,
    topK: int = TOP_K,
) -> Answer:
    """Répond à une question à partir du corpus indexé.

    Quand la recherche ne rend aucun passage, la chaîne refuse **sans appeler
    le modèle**. Deux raisons : un refus ne doit rien coûter, et un modèle à
    qui on ne donne aucun contexte répond quand même — avec ce qu'il croit
    savoir, ce qui est exactement le comportement qu'un RAG doit empêcher.
    """
    startedAt = time.monotonic()
    passages = tuple(index.search(question, topK=topK))

    if not passages:
        logger.info("refus sans appel modele : aucun passage pertinent")
        return Answer(
            text=REFUSAL_TEXT,
            passages=(),
            usage=EMPTY_USAGE,
            refused=True,
            latencySeconds=time.monotonic() - startedAt,
        )

    reply = generateAnswer(
        client=client,
        question=question,
        passages=passages,
        promptTemplate=promptTemplate,
    )

    return Answer(
        text=reply.text,
        passages=passages,
        usage=reply.usage,
        refused=False,
        latencySeconds=time.monotonic() - startedAt,
    )
