"""Structures de données de la chaîne.

Aucune logique, aucun effet de bord, aucune dépendance : ce module est importé
par tous les autres et doit rester trivial.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class Document:
    """Un document du corpus, tel qu'il est lu depuis le fichier source."""

    docId: str
    title: str
    text: str


@dataclass(frozen=True)
class Chunk:
    """Un passage découpé, unité indexée et récupérée."""

    chunkId: str
    docId: str
    title: str
    text: str


@dataclass(frozen=True)
class Passage:
    """Un passage récupéré, accompagné de son score de pertinence."""

    chunk: Chunk
    score: float


@dataclass(frozen=True)
class Usage:
    """Jetons consommés par un appel modèle.

    Entrée et sortie sont comptées séparément : sans ça, le coût n'est pas
    recalculable quand les tarifs changent.
    """

    inputTokens: int
    outputTokens: int

    def plus(self, other: "Usage") -> "Usage":
        """Additionne deux consommations."""
        return Usage(
            inputTokens=self.inputTokens + other.inputTokens,
            outputTokens=self.outputTokens + other.outputTokens,
        )


EMPTY_USAGE = Usage(inputTokens=0, outputTokens=0)


@dataclass(frozen=True)
class Answer:
    """Réponse complète de la chaîne, avec de quoi la juger.

    `refused` vaut True quand la chaîne a refusé de répondre faute de contexte
    pertinent. Dans ce cas aucun appel modèle n'a eu lieu et `usage` est vide :
    c'est voulu, un refus ne doit rien coûter.
    """

    text: str
    passages: tuple[Passage, ...]
    usage: Usage
    refused: bool
    latencySeconds: float
