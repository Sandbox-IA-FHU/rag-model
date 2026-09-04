"""Index lexical BM25, en mémoire.

Pourquoi pas une base vectorielle : sur quelques centaines de passages, BM25
tient en soixante lignes, ne demande aucune dépendance, aucun serveur et
aucune seconde clé d'API, et il est déterministe — donc testable hors ligne.

Quand en changer : quand la mesure le dit. Le signal est un rappel qui plafonne
alors que les passages pertinents existent, avec des échecs concentrés sur les
questions qui n'emploient pas les mots du document. Voir README.md.
"""

import math
import re
import unicodedata
from collections import Counter

from rag.models import Chunk, Passage

# Paramètres BM25 usuels. Les toucher se mesure, comme le reste.
BM25_K1 = 1.5
BM25_B = 0.75

TOKEN_PATTERN = re.compile(r"[a-z0-9]+")

# Mots trop fréquents pour discriminer quoi que ce soit en français.
# Écrits sans accent : ils sont comparés après `normalizeText`.
STOP_WORDS = frozenset({
    "a", "au", "aux", "avec", "avoir", "c", "ce", "ces", "cette", "d", "dans",
    "de", "des", "du", "elle", "en", "est", "et", "etre", "eux", "il", "ils",
    "j", "je", "l", "la", "le", "les", "leur", "lui", "ma", "mais", "me",
    "meme", "mes", "moi", "mon", "n", "ne", "nos", "notre", "nous", "on", "ou",
    "par", "pas", "pour", "qu", "que", "quel", "quelle", "quelles", "quels",
    "qui", "s", "sa", "se", "ses", "son", "sont", "sur", "ta", "te", "tes",
    "toi", "ton", "tu", "un", "une", "vos", "votre", "vous", "y",
})  # fmt: skip


def normalizeText(text: str) -> str:
    """Passe en minuscules et retire les accents.

    « Remboursé » et « rembourse » doivent tomber sur le même jeton, sinon la
    recherche lexicale échoue sur des questions parfaitement raisonnables.
    """
    lowered = text.lower()
    decomposed = unicodedata.normalize("NFD", lowered)
    return "".join(char for char in decomposed if not unicodedata.combining(char))


def tokenize(text: str) -> list[str]:
    """Découpe un texte en jetons comparables."""
    return [
        token
        for token in TOKEN_PATTERN.findall(normalizeText(text))
        if token not in STOP_WORDS
    ]


class LexicalIndex:
    """Index BM25 construit une fois, interrogé plusieurs fois.

    L'index porte le titre du passage en plus de son texte : sur un corpus de
    documentation, le titre est souvent le seul endroit où figure le terme
    métier exact.
    """

    def __init__(self, chunks: list[Chunk]) -> None:
        self.chunks = list(chunks)
        self._termFrequencies: list[Counter[str]] = []
        self._lengths: list[int] = []
        documentFrequencies: Counter[str] = Counter()

        for chunk in self.chunks:
            tokens = tokenize(f"{chunk.title} {chunk.text}")
            frequencies = Counter(tokens)
            self._termFrequencies.append(frequencies)
            self._lengths.append(len(tokens))
            documentFrequencies.update(frequencies.keys())

        self._documentCount = len(self.chunks)
        self._averageLength = (
            sum(self._lengths) / self._documentCount if self._documentCount else 0.0
        )
        self._inverseDocumentFrequencies = {
            term: math.log(
                1.0 + (self._documentCount - frequency + 0.5) / (frequency + 0.5)
            )
            for term, frequency in documentFrequencies.items()
        }

    def scoreChunk(self, queryTokens: list[str], position: int) -> float:
        """Score BM25 d'un passage pour une requête déjà découpée."""
        frequencies = self._termFrequencies[position]
        length = self._lengths[position]
        score = 0.0

        for term in queryTokens:
            frequency = frequencies.get(term, 0)
            if frequency == 0:
                continue
            inverseFrequency = self._inverseDocumentFrequencies.get(term, 0.0)
            lengthPenalty = (
                1.0
                - BM25_B
                + BM25_B
                * (length / self._averageLength if self._averageLength else 1.0)
            )
            score += inverseFrequency * (
                frequency * (BM25_K1 + 1.0) / (frequency + BM25_K1 * lengthPenalty)
            )

        return score

    def search(self, question: str, topK: int) -> list[Passage]:
        """Rend les `topK` passages les mieux notés, score strictement positif.

        Un score nul signifie qu'aucun terme de la question n'apparaît dans le
        passage. Ces passages ne sont pas rendus : c'est ce qui permet à la
        chaîne de refuser de répondre plutôt que d'inventer sur du bruit.
        """
        if topK <= 0:
            return []

        queryTokens = tokenize(question)
        if not queryTokens:
            return []

        scored = [
            Passage(chunk=chunk, score=self.scoreChunk(queryTokens, position))
            for position, chunk in enumerate(self.chunks)
        ]
        relevant = [passage for passage in scored if passage.score > 0.0]
        relevant.sort(key=lambda passage: (-passage.score, passage.chunk.chunkId))
        return relevant[:topK]
