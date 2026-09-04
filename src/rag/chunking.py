"""Découpage des documents en passages.

Découpage par fenêtre glissante sur les mots, avec recouvrement. C'est le
découpage le plus simple qui fonctionne, et il faut le mesurer avant d'en
essayer un plus malin : un découpage sémantique coûte un appel modèle par
document et n'améliore pas toujours le rappel.
"""

from rag.errors import ChunkingError
from rag.models import Chunk, Document

CHUNK_SIZE_WORDS = 120
CHUNK_OVERLAP_WORDS = 30


def chunkDocument(
    document: Document,
    chunkSize: int = CHUNK_SIZE_WORDS,
    overlap: int = CHUNK_OVERLAP_WORDS,
) -> list[Chunk]:
    """Découpe un document en passages qui se recouvrent.

    Le recouvrement évite qu'une réponse tombe pile sur une frontière de
    passage — un mode d'échec fréquent, et invisible tant qu'on ne mesure pas
    le rappel de la recherche séparément.
    """
    if chunkSize <= 0:
        raise ChunkingError(f"chunkSize doit être positif, reçu {chunkSize}.")
    if overlap < 0:
        raise ChunkingError(f"overlap ne peut pas être négatif, reçu {overlap}.")
    if overlap >= chunkSize:
        raise ChunkingError(
            f"overlap ({overlap}) doit être strictement inférieur à "
            f"chunkSize ({chunkSize}), sinon le découpage ne progresse pas."
        )

    words = document.text.split()
    if not words:
        return []

    step = chunkSize - overlap
    chunks: list[Chunk] = []

    for start in range(0, len(words), step):
        window = words[start : start + chunkSize]
        if not window:
            break
        chunks.append(
            Chunk(
                chunkId=f"{document.docId}#{len(chunks):03d}",
                docId=document.docId,
                title=document.title,
                text=" ".join(window),
            )
        )
        if start + chunkSize >= len(words):
            break

    return chunks


def chunkAll(
    documents: list[Document],
    chunkSize: int = CHUNK_SIZE_WORDS,
    overlap: int = CHUNK_OVERLAP_WORDS,
) -> list[Chunk]:
    """Découpe tout un corpus."""
    chunks: list[Chunk] = []
    for document in documents:
        chunks.extend(chunkDocument(document, chunkSize=chunkSize, overlap=overlap))
    return chunks
