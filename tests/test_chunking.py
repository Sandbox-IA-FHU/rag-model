"""Tests du découpage."""

import pytest

from rag.chunking import chunkAll, chunkDocument
from rag.errors import ChunkingError
from rag.models import Document


def buildDocument(wordCount: int) -> Document:
    """Fabrique un document de `wordCount` mots distincts."""
    return Document(
        docId="doc-99",
        title="Document de test",
        text=" ".join(f"mot{index}" for index in range(wordCount)),
    )


def test_chunkingRespectsSizeAndOverlap() -> None:
    chunks = chunkDocument(buildDocument(200), chunkSize=120, overlap=30)

    assert len(chunks) == 2
    assert len(chunks[0].text.split()) == 120
    # Le pas est de 90 mots : le second passage reprend 30 mots du premier.
    assert chunks[1].text.split()[0] == "mot90"


def test_chunkingKeepsDocumentIdentity() -> None:
    chunks = chunkDocument(buildDocument(50), chunkSize=20, overlap=5)

    assert all(chunk.docId == "doc-99" for chunk in chunks)
    assert all(chunk.title == "Document de test" for chunk in chunks)
    assert len({chunk.chunkId for chunk in chunks}) == len(chunks)


def test_chunkingOfShortDocumentGivesOneChunk() -> None:
    chunks = chunkDocument(buildDocument(10), chunkSize=120, overlap=30)

    assert len(chunks) == 1


def test_chunkingOfEmptyDocumentGivesNothing() -> None:
    empty = Document(docId="doc-00", title="Vide", text="   ")

    assert chunkDocument(empty) == []


def test_overlapGreaterThanSizeIsRefused() -> None:
    # Sans ce garde-fou, la fenêtre n'avance pas et le découpage boucle.
    with pytest.raises(ChunkingError):
        chunkDocument(buildDocument(50), chunkSize=10, overlap=10)


def test_chunkAllCoversEveryDocument(sampleDocuments: list[Document]) -> None:
    chunks = chunkAll(sampleDocuments, chunkSize=10, overlap=2)

    assert {chunk.docId for chunk in chunks} == {"doc-01", "doc-02", "doc-03"}
