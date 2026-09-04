"""Lance l'évaluation et écrit un fichier de run daté.

    uv run --env-file .env python scripts/evaluate.py --etiquette prompt-v1

Chaque exécution produit `evaluations/runs/AAAA-MM-JJ-<etiquette>.json`. Ce
fichier est commité : c'est lui qui rend le score interprétable dans six mois.

Ce script appelle le modèle une fois par cas non refusé. Il affiche le nombre
d'appels prévus avant de commencer — un test sur trois cas (`--limite 3`) avant
de lancer les vingt-cinq coûte trente secondes et évite les mauvaises surprises.
"""

import argparse
import json
import logging
import sys
from datetime import date
from pathlib import Path

from rag.chunking import CHUNK_OVERLAP_WORDS, CHUNK_SIZE_WORDS, chunkAll
from rag.client import (
    ANSWER_MODEL,
    MAX_OUTPUT_TOKENS,
    AnthropicClient,
)
from rag.config import loadConfig
from rag.corpus import loadCorpus
from rag.costs import PRICES_DATE, estimateCostUsd
from rag.errors import ConfigError, CorpusError, ModelCallError
from rag.evaluation import gradeCase, loadEvalSet, summarize
from rag.generation import CURRENT_PROMPT, loadPrompt
from rag.index import LexicalIndex
from rag.models import Usage
from rag.pipeline import TOP_K, answerQuestion

DEFAULT_CORPUS = Path("evaluations/jeux/corpus_demo.jsonl")
DEFAULT_EVAL_SET = Path("evaluations/jeux/questions_demo.jsonl")
RUNS_DIR = Path("evaluations/runs")


def buildParser() -> argparse.ArgumentParser:
    """Décrit les arguments de la ligne de commande."""
    parser = argparse.ArgumentParser(description="Évalue la chaîne RAG.")
    parser.add_argument(
        "--corpus", type=Path, default=DEFAULT_CORPUS, help="Corpus JSONL."
    )
    parser.add_argument(
        "--jeu", type=Path, default=DEFAULT_EVAL_SET, help="Jeu d'évaluation JSONL."
    )
    parser.add_argument(
        "--etiquette",
        default="run",
        help="Suffixe du nom de fichier de run, sans espace.",
    )
    parser.add_argument(
        "--top-k", type=int, default=TOP_K, dest="topK", help="Passages récupérés."
    )
    parser.add_argument(
        "--limite",
        type=int,
        default=None,
        help="N'évalue que les N premiers cas. À utiliser avant un run complet.",
    )
    return parser


def main() -> int:
    """Point d'entrée. Rend 0 en succès, 1 sur une erreur attendue."""
    args = buildParser().parse_args()

    try:
        config = loadConfig()
    except ConfigError as error:
        print(f"Configuration : {error}", file=sys.stderr)
        return 1

    logging.basicConfig(level=config.logLevel, format="%(levelname)s %(message)s")

    try:
        documents = loadCorpus(config.corpusPath or args.corpus)
        cases = loadEvalSet(args.jeu)
    except CorpusError as error:
        print(f"Données : {error}", file=sys.stderr)
        return 1

    if args.limite is not None:
        cases = cases[: args.limite]

    index = LexicalIndex(chunkAll(documents))
    client = AnthropicClient(apiKey=config.apiKey)
    promptTemplate = loadPrompt()

    print(f"{len(cases)} cas, modèle {ANSWER_MODEL}, prompt {CURRENT_PROMPT}.")
    print("Un appel modèle par cas où la recherche remonte au moins un passage.")

    results = []
    for case in cases:
        try:
            answer = answerQuestion(
                client=client,
                index=index,
                question=case.question,
                promptTemplate=promptTemplate,
                topK=args.topK,
            )
        except ModelCallError as error:
            print(f"{case.caseId} : appel modèle échoué — {error}", file=sys.stderr)
            return 1

        result = gradeCase(case, answer)
        results.append(result)
        verdict = result.refusalCorrect if case.mustRefuse else result.answerCorrect
        print(f"  {case.caseId} [{case.caseType}] {'ok' if verdict else 'ECHEC'}")

    summary = summarize(results)
    totalUsage = Usage(
        inputTokens=int(summary["jetons_entree"]),
        outputTokens=int(summary["jetons_sortie"]),
    )
    totalCost = estimateCostUsd(totalUsage, ANSWER_MODEL)

    run = {
        "date": date.today().isoformat(),
        "modele": ANSWER_MODEL,
        "prompt": f"prompts/{CURRENT_PROMPT}",
        "jeu": str(args.jeu).replace("\\", "/"),
        "nb_cas": len(results),
        "parametres": {
            "top_k": args.topK,
            "chunk_size_words": CHUNK_SIZE_WORDS,
            "chunk_overlap_words": CHUNK_OVERLAP_WORDS,
            "max_output_tokens": MAX_OUTPUT_TOKENS,
        },
        "resultats": {
            **summary,
            "cout_total_usd": round(totalCost, 4),
            "cout_par_question_usd": round(totalCost / max(len(results), 1), 5),
            "tarifs_releves_le": PRICES_DATE,
        },
        "commentaire": "",
    }

    RUNS_DIR.mkdir(parents=True, exist_ok=True)
    runPath = RUNS_DIR / f"{run['date']}-{args.etiquette}.json"
    runPath.write_text(
        json.dumps(run, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )

    print()
    print(f"Rappel recherche   : {summary['rappel_recherche']}")
    print(f"Réponse correcte   : {summary['reponse_correcte']}")
    print(f"Refus correct      : {summary['refus_correct']}")
    print(f"Coût total         : {totalCost:.4f} USD")
    print(f"Latence médiane    : {summary['latence_mediane_s']} s")
    print()
    print(f"Run écrit dans {runPath}")
    print("Remplir le champ « commentaire » avant de commiter : c'est celui")
    print("qu'on relit dans six mois.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
