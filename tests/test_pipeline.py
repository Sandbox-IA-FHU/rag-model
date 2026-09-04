"""Tests de la chaîne complète, sans aucun appel réseau."""

from rag.index import LexicalIndex
from rag.models import Chunk
from rag.pipeline import REFUSAL_TEXT, answerQuestion

PROMPT = "Consignes de test."


def test_refusalHappensWithoutCallingTheModel(
    sampleChunks: list[Chunk], explodingClient: object
) -> None:
    # Le test le plus important du dépôt : un refus ne doit rien coûter, et un
    # modèle sans contexte répond quand même — avec ce qu'il croit savoir.
    index = LexicalIndex(sampleChunks)

    answer = answerQuestion(
        client=explodingClient,
        index=index,
        question="cryptomonnaie blockchain",
        promptTemplate=PROMPT,
    )

    assert answer.refused is True
    assert answer.text == REFUSAL_TEXT
    assert answer.passages == ()
    assert answer.usage.inputTokens == 0
    assert answer.usage.outputTokens == 0


def test_answerCarriesSourcesAndUsage(
    sampleChunks: list[Chunk], fakeClient: object
) -> None:
    index = LexicalIndex(sampleChunks)

    answer = answerQuestion(
        client=fakeClient,
        index=index,
        question="délai de remboursement",
        promptTemplate=PROMPT,
    )

    assert answer.refused is False
    assert len(fakeClient.calls) == 1
    assert answer.passages
    assert answer.usage.inputTokens == 100
    assert answer.latencySeconds >= 0.0


def test_promptTemplateIsSentAsSystem(
    sampleChunks: list[Chunk], fakeClient: object
) -> None:
    index = LexicalIndex(sampleChunks)

    answerQuestion(
        client=fakeClient,
        index=index,
        question="délai de remboursement",
        promptTemplate=PROMPT,
    )

    system, userText = fakeClient.calls[0]
    assert system == PROMPT
    assert "délai de remboursement" in userText
