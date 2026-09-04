"""Tests de l'index lexical."""

from rag.index import LexicalIndex, normalizeText, tokenize
from rag.models import Chunk


def test_normalizationRemovesAccentsAndCase() -> None:
    assert normalizeText("Remboursé") == "rembourse"
    assert normalizeText("DÉLAI") == "delai"


def test_tokenizationDropsStopWords() -> None:
    tokens = tokenize("Quel est le délai de la livraison ?")

    assert "delai" in tokens
    assert "livraison" in tokens
    assert "le" not in tokens
    assert "de" not in tokens


def test_searchFindsTheRelevantChunk(sampleChunks: list[Chunk]) -> None:
    index = LexicalIndex(sampleChunks)

    passages = index.search("délai de remboursement", topK=1)

    assert passages
    assert passages[0].chunk.docId == "doc-02"


def test_searchIgnoresAccentsInQuestion(sampleChunks: list[Chunk]) -> None:
    index = LexicalIndex(sampleChunks)

    passages = index.search("livraison express samedi", topK=1)

    assert passages[0].chunk.docId == "doc-03"


def test_searchReturnsNothingWhenNoTermMatches(sampleChunks: list[Chunk]) -> None:
    # C'est ce comportement qui permet à la chaîne de refuser plutôt que
    # d'inventer sur du bruit.
    index = LexicalIndex(sampleChunks)

    assert index.search("cryptomonnaie blockchain", topK=4) == []


def test_searchReturnsNothingForStopWordsOnly(sampleChunks: list[Chunk]) -> None:
    index = LexicalIndex(sampleChunks)

    assert index.search("est-ce que le", topK=4) == []


def test_searchRespectsTopK(sampleChunks: list[Chunk]) -> None:
    index = LexicalIndex(sampleChunks)

    assert len(index.search("client livraison remboursement", topK=2)) <= 2
    assert index.search("client", topK=0) == []


def test_searchIsDeterministic(sampleChunks: list[Chunk]) -> None:
    # Deux exécutions identiques doivent rendre le même ordre : sans ça, deux
    # runs d'évaluation ne sont pas comparables.
    index = LexicalIndex(sampleChunks)

    first = [passage.chunk.chunkId for passage in index.search("client", topK=3)]
    second = [passage.chunk.chunkId for passage in index.search("client", topK=3)]

    assert first == second
