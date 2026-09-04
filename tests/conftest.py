"""Outillage commun aux tests.

Aucun test de ce dépôt n'appelle un fournisseur de modèle. C'est lent, c'est
facturé, et le résultat change d'une exécution à l'autre — un test qui échoue
une fois sur trois finit par être ignoré, et la CI avec lui.

Le faux client vit ici, et il est injecté. C'est la seule raison pour laquelle
`answerQuestion` prend un client en argument au lieu de le construire.
"""

import pytest

from rag.client import ModelReply
from rag.models import Chunk, Document, Usage


class FakeClient:
    """Client modèle simulé : rend un texte fixe et compte les appels."""

    def __init__(self, replyText: str = "Réponse simulée. [doc-01#000]") -> None:
        self.replyText = replyText
        self.calls: list[tuple[str, str]] = []

    def complete(self, system: str, userText: str) -> ModelReply:
        """Enregistre l'appel et rend la réponse fixe."""
        self.calls.append((system, userText))
        return ModelReply(
            text=self.replyText,
            usage=Usage(inputTokens=100, outputTokens=20),
        )


class ExplodingClient:
    """Client qui échoue si on l'appelle.

    Sert à prouver qu'un chemin de code n'appelle PAS le modèle — par exemple
    le refus quand la recherche ne rend aucun passage.
    """

    def complete(self, system: str, userText: str) -> ModelReply:
        """Ne doit jamais être appelée."""
        raise AssertionError("Le modèle a été appelé alors qu'il ne devait pas.")


@pytest.fixture
def fakeClient() -> FakeClient:
    """Client simulé, prêt à l'emploi."""
    return FakeClient()


@pytest.fixture
def explodingClient() -> ExplodingClient:
    """Client qui échoue si on l'appelle."""
    return ExplodingClient()


@pytest.fixture
def sampleDocuments() -> list[Document]:
    """Trois documents courts, inventés, suffisants pour la plupart des tests."""
    return [
        Document(
            docId="doc-01",
            title="Retours produits",
            text=(
                "Le client dispose de 14 jours calendaires pour demander un "
                "retour. Les frais sont à la charge du client sauf produit "
                "défectueux."
            ),
        ),
        Document(
            docId="doc-02",
            title="Remboursements",
            text=(
                "Le remboursement intervient sous 7 jours ouvrés sur le moyen "
                "de paiement d'origine."
            ),
        ),
        Document(
            docId="doc-03",
            title="Livraison",
            text=(
                "La livraison express est assurée sous 24 heures ouvrées. "
                "Aucune livraison le samedi."
            ),
        ),
    ]


@pytest.fixture
def sampleChunks(sampleDocuments: list[Document]) -> list[Chunk]:
    """Un passage par document, sans passer par le découpage."""
    return [
        Chunk(
            chunkId=f"{document.docId}#000",
            docId=document.docId,
            title=document.title,
            text=document.text,
        )
        for document in sampleDocuments
    ]
