"""Non-régression du rappel de la recherche, sur le vrai corpus.

Le rappel se mesure **sans appeler le moindre modèle** : c'est gratuit,
instantané et déterministe. Il n'y a donc aucune raison de le laisser hors des
tests — une modification du découpage, de la liste de mots vides ou des
paramètres BM25 se verrait ici avant d'être payée en appels modèle.

Le seuil est volontairement un peu sous la valeur mesurée : ce test attrape une
régression franche, il n'est pas là pour figer un chiffre au centième.
"""

from pathlib import Path

from rag.chunking import chunkAll
from rag.corpus import loadCorpus
from rag.evaluation import loadEvalSet
from rag.index import LexicalIndex
from rag.pipeline import TOP_K

REPO_ROOT = Path(__file__).resolve().parents[1]
JEUX = REPO_ROOT / "evaluations" / "jeux"

# Relevé le 2026-09-04 : 18/19 sur le jeu principal, 6/6 sur la réserve.
MIN_RECALL = 0.85


def buildDemoIndex() -> LexicalIndex:
    """Index construit sur le corpus d'exemple."""
    documents = loadCorpus(JEUX / "corpus_demo.jsonl")
    return LexicalIndex(chunkAll(documents))


def measureRecall(indexName: str) -> tuple[int, int]:
    """Rend (cas réussis, cas concernés) pour un jeu donné."""
    index = buildDemoIndex()
    cases = [case for case in loadEvalSet(JEUX / indexName) if not case.mustRefuse]

    hits = 0
    for case in cases:
        retrieved = {
            passage.chunk.docId for passage in index.search(case.question, TOP_K)
        }
        if case.expectedDocId in retrieved:
            hits += 1

    return hits, len(cases)


def test_recallOnMainSetStaysAboveThreshold() -> None:
    hits, total = measureRecall("questions_demo.jsonl")

    assert hits / total >= MIN_RECALL, f"rappel tombé à {hits}/{total}"


def test_recallOnReserveSetStaysAboveThreshold() -> None:
    # Un écart entre les deux jeux signalerait un réglage spécialisé sur le
    # jeu principal — ici sur les paramètres de recherche, pas sur le prompt.
    hits, total = measureRecall("questions_reserve.jsonl")

    assert hits / total >= MIN_RECALL, f"rappel tombé à {hits}/{total}"


def test_poisonedDocumentIsActuallyRetrieved() -> None:
    # Si la recherche cessait de remonter doc-07, le test d'injection
    # deviendrait vert pour la mauvaise raison : le système ne serait pas
    # robuste, il serait simplement épargné.
    index = buildDemoIndex()
    injectionCase = next(
        case
        for case in loadEvalSet(JEUX / "questions_demo.jsonl")
        if case.caseId == "q-24"
    )

    retrieved = {
        passage.chunk.docId for passage in index.search(injectionCase.question, TOP_K)
    }

    assert "doc-07" in retrieved
