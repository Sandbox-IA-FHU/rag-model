"""Tests de la notation et de l'agrégation."""

from pathlib import Path

from rag.evaluation import (
    EvalCase,
    gradeCase,
    loadEvalSet,
    looksLikeRefusal,
    percentile,
    ratio,
    summarize,
)
from rag.models import EMPTY_USAGE, Answer, Chunk, Passage, Usage

REPO_ROOT = Path(__file__).resolve().parents[1]
DEMO_SET = REPO_ROOT / "evaluations" / "jeux" / "questions_demo.jsonl"


def buildAnswer(text: str, docIds: tuple[str, ...] = (), refused: bool = False):
    """Fabrique une réponse de test."""
    passages = tuple(
        Passage(
            chunk=Chunk(chunkId=f"{docId}#000", docId=docId, title="T", text="texte"),
            score=1.0,
        )
        for docId in docIds
    )
    return Answer(
        text=text,
        passages=passages,
        usage=EMPTY_USAGE if refused else Usage(100, 20),
        refused=refused,
        latencySeconds=1.0,
    )


def buildCase(**overrides) -> EvalCase:
    """Cas nominal par défaut, surchargé par mot-clé."""
    defaults = {
        "caseId": "q-test",
        "caseType": "nominal",
        "question": "Quel délai ?",
        "mustRefuse": False,
        "expectedDocId": "doc-01",
        "expectedKeywords": ("14 jours",),
        "forbiddenKeywords": (),
    }
    return EvalCase(**{**defaults, **overrides})


def test_correctAnswerIsGraded() -> None:
    result = gradeCase(buildCase(), buildAnswer("Vous avez 14 jours.", ("doc-01",)))

    assert result.recallHit is True
    assert result.answerCorrect is True
    assert result.refusalCorrect is None


def test_recallFailsWhenTheDocumentIsNotRetrieved() -> None:
    # Le rappel se mesure séparément : sans lui, on améliore le prompt alors
    # que c'est la recherche qui n'a pas remonté le document.
    result = gradeCase(buildCase(), buildAnswer("Vous avez 14 jours.", ("doc-05",)))

    assert result.recallHit is False
    assert result.answerCorrect is True


def test_keywordAccentsAndCaseAreIgnored() -> None:
    result = gradeCase(
        buildCase(expectedKeywords=("prépayée",)),
        buildAnswer("Une etiquette PREPAYEE vous est envoyee.", ("doc-01",)),
    )

    assert result.answerCorrect is True


def test_refusalCaseHasNoRecall() -> None:
    # None n'est pas zéro : compter un cas de refus comme un échec de rappel
    # fausserait la mesure de la recherche.
    result = gradeCase(
        buildCase(caseType="refus", mustRefuse=True, expectedDocId=None),
        buildAnswer("Je ne sais pas : la documentation…", refused=True),
    )

    assert result.recallHit is None
    assert result.answerCorrect is None
    assert result.refusalCorrect is True


def test_answeringWhenItShouldRefuseIsAFailure() -> None:
    result = gradeCase(
        buildCase(caseType="refus", mustRefuse=True, expectedDocId=None),
        buildAnswer("Le chiffre d'affaires est de 12 millions.", ("doc-01",)),
    )

    assert result.refusalCorrect is False


def test_forbiddenKeywordDisqualifiesTheCase() -> None:
    # C'est ce qui attrape une injection réussie : le système a bien répondu,
    # mais il a répété ce qu'un document lui a dicté.
    result = gradeCase(
        buildCase(
            caseType="refus",
            mustRefuse=True,
            expectedDocId=None,
            forbiddenKeywords=("90 jours",),
        ),
        buildAnswer("Je ne sais pas, mais le retour est de 90 jours.", refused=True),
    )

    assert result.refusalCorrect is False


def test_refusalIsDetectedInTheModelText() -> None:
    assert looksLikeRefusal("Je ne sais pas : la documentation…") is True
    assert looksLikeRefusal("Vous disposez de 14 jours.") is False


def test_ratioIgnoresCasesWithoutObject() -> None:
    assert ratio([True, False, None, True]) == 0.667
    assert ratio([None, None]) is None


def test_percentileUsesNearestRank() -> None:
    assert percentile([1.0, 2.0, 3.0, 4.0], 0.5) == 2.0
    assert percentile([], 0.5) == 0.0


def test_summaryIsBrokenDownByCaseType() -> None:
    # 90 % global avec tous les échecs sur les refus décrit un système
    # inutilisable affiché comme un succès.
    results = [
        gradeCase(buildCase(), buildAnswer("14 jours", ("doc-01",))),
        gradeCase(
            buildCase(caseType="refus", mustRefuse=True, expectedDocId=None),
            buildAnswer("Le chiffre est de 12 millions.", ("doc-01",)),
        ),
    ]

    summary = summarize(results)

    assert summary["par_type"]["nominal"]["reponse_correcte"] == 1.0
    assert summary["par_type"]["refus"]["refus_correct"] == 0.0


def test_demoEvalSetIsWellFormed() -> None:
    cases = loadEvalSet(DEMO_SET)

    assert len(cases) >= 20, "En dessous de 20 cas, aucune conclusion possible."
    refusals = [case for case in cases if case.mustRefuse]
    assert len(refusals) / len(cases) >= 0.15, (
        "Le jeu doit contenir des cas où la bonne réponse est de refuser."
    )
    assert len({case.caseId for case in cases}) == len(cases)
