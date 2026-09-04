"""Évaluation de la chaîne.

Trois mesures séparées, et c'est le point important :

- **le rappel de la recherche** — le bon document est-il remonté ?
- **la qualité de la réponse** — le modèle a-t-il su s'en servir ?
- **le refus** — le système sait-il dire qu'il ne sait pas ?

Un score global unique ne dit pas laquelle des trois étapes échoue, et on passe
alors des semaines à améliorer le prompt alors que c'est la recherche qui ne
remonte pas le document.

La méthode de notation est volontairement la plus bête qui réponde à la
question : présence de mots-clés attendus. Voir `EVALUATION.md` — une notation
par modèle juge se calibre contre du jugement humain avant d'avoir la moindre
valeur.
"""

import json
from dataclasses import dataclass
from pathlib import Path

from rag.errors import CorpusError
from rag.index import normalizeText
from rag.models import Answer

REQUIRED_FIELDS = ("cas_id", "type", "question", "doit_refuser")
VALID_TYPES = ("nominal", "difficile", "refus")

REFUSAL_MARKERS = ("je ne sais pas", "ne contient pas de reponse")


@dataclass(frozen=True)
class EvalCase:
    """Un cas du jeu d'évaluation."""

    caseId: str
    caseType: str
    question: str
    mustRefuse: bool
    expectedDocId: str | None
    expectedKeywords: tuple[str, ...]
    forbiddenKeywords: tuple[str, ...]


@dataclass(frozen=True)
class CaseResult:
    """Ce qu'on a mesuré sur un cas."""

    case: EvalCase
    retrievedDocIds: tuple[str, ...]
    recallHit: bool | None
    answerCorrect: bool | None
    refusalCorrect: bool | None
    latencySeconds: float
    inputTokens: int
    outputTokens: int


def loadEvalSet(path: Path) -> list[EvalCase]:
    """Lit un jeu d'évaluation JSONL."""
    if not path.is_file():
        raise CorpusError(f"Jeu d'évaluation introuvable : {path}")

    cases: list[EvalCase] = []
    with path.open(encoding="utf-8") as handle:
        for lineNumber, rawLine in enumerate(handle, start=1):
            line = rawLine.strip()
            if not line:
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError as error:
                raise CorpusError(
                    f"{path.name} ligne {lineNumber} : JSON invalide."
                ) from error

            missing = [field for field in REQUIRED_FIELDS if field not in record]
            if missing:
                raise CorpusError(
                    f"{path.name} ligne {lineNumber} : champs manquants {missing}."
                )
            if record["type"] not in VALID_TYPES:
                raise CorpusError(
                    f"{path.name} ligne {lineNumber} : type inconnu "
                    f"({record['type']!r}), attendu {VALID_TYPES}."
                )

            cases.append(
                EvalCase(
                    caseId=str(record["cas_id"]),
                    caseType=str(record["type"]),
                    question=str(record["question"]),
                    mustRefuse=bool(record["doit_refuser"]),
                    expectedDocId=record.get("doc_attendu"),
                    expectedKeywords=tuple(record.get("mots_cles_attendus", [])),
                    forbiddenKeywords=tuple(record.get("mots_cles_interdits", [])),
                )
            )

    return cases


def looksLikeRefusal(text: str) -> bool:
    """Dit si une réponse est un refus.

    La chaîne refuse à deux endroits : avant l'appel modèle quand la recherche
    ne rend rien, et dans la réponse du modèle quand les extraits ne répondent
    pas. Les deux comptent comme un refus.
    """
    normalized = normalizeText(text)
    return any(marker in normalized for marker in REFUSAL_MARKERS)


def gradeCase(case: EvalCase, answer: Answer) -> CaseResult:
    """Note un cas. Les champs sans objet pour ce cas valent None.

    None n'est pas zéro : un cas de refus n'a pas de « rappel », et le compter
    comme un échec de rappel fausserait la mesure de la recherche.
    """
    retrievedDocIds = tuple(
        dict.fromkeys(passage.chunk.docId for passage in answer.passages)
    )
    refused = answer.refused or looksLikeRefusal(answer.text)
    normalizedAnswer = normalizeText(answer.text)

    # Un mot-clé interdit disqualifie le cas, refus ou pas. C'est ce qui
    # attrape une injection réussie : le système a bien répondu quelque chose,
    # mais il a répété ce qu'un document lui a dicté.
    hasForbidden = any(
        normalizeText(keyword) in normalizedAnswer for keyword in case.forbiddenKeywords
    )

    recallHit: bool | None = None
    answerCorrect: bool | None = None
    refusalCorrect: bool | None = None

    if case.mustRefuse:
        refusalCorrect = refused and not hasForbidden
    else:
        if case.expectedDocId is not None:
            recallHit = case.expectedDocId in retrievedDocIds
        answerCorrect = (
            not refused
            and not hasForbidden
            and all(
                normalizeText(keyword) in normalizedAnswer
                for keyword in case.expectedKeywords
            )
        )

    return CaseResult(
        case=case,
        retrievedDocIds=retrievedDocIds,
        recallHit=recallHit,
        answerCorrect=answerCorrect,
        refusalCorrect=refusalCorrect,
        latencySeconds=answer.latencySeconds,
        inputTokens=answer.usage.inputTokens,
        outputTokens=answer.usage.outputTokens,
    )


def ratio(values: list[bool | None]) -> float | None:
    """Proportion de vrais, en ignorant les cas sans objet."""
    considered = [value for value in values if value is not None]
    if not considered:
        return None
    return round(sum(considered) / len(considered), 3)


def percentile(values: list[float], fraction: float) -> float:
    """Centile par rang le plus proche.

    Pas d'interpolation : sur trente cas, interpoler donne une fausse
    impression de précision.
    """
    if not values:
        return 0.0
    ordered = sorted(values)
    rank = max(0, min(len(ordered) - 1, round(fraction * len(ordered)) - 1))
    return round(ordered[rank], 3)


def summarize(results: list[CaseResult]) -> dict[str, object]:
    """Agrège les résultats, globalement et par type de cas.

    Le découpage par type n'est pas décoratif : 90 % global avec tous les
    échecs concentrés sur les refus décrit un système inutilisable.
    """
    latencies = [result.latencySeconds for result in results]
    byType: dict[str, object] = {}

    for caseType in VALID_TYPES:
        subset = [r for r in results if r.case.caseType == caseType]
        if not subset:
            continue
        byType[caseType] = {
            "nb_cas": len(subset),
            "rappel_recherche": ratio([r.recallHit for r in subset]),
            "reponse_correcte": ratio([r.answerCorrect for r in subset]),
            "refus_correct": ratio([r.refusalCorrect for r in subset]),
        }

    return {
        "rappel_recherche": ratio([r.recallHit for r in results]),
        "reponse_correcte": ratio([r.answerCorrect for r in results]),
        "refus_correct": ratio([r.refusalCorrect for r in results]),
        "jetons_entree": sum(r.inputTokens for r in results),
        "jetons_sortie": sum(r.outputTokens for r in results),
        "latence_mediane_s": percentile(latencies, 0.5),
        "latence_p95_s": percentile(latencies, 0.95),
        "par_type": byType,
    }
