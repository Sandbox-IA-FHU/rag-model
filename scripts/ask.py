"""Pose une question au corpus, en ligne de commande.

    uv run --env-file .env python scripts/ask.py "quel est le delai de retour ?"

Ce script est le seul endroit où l'on affiche : c'est son rôle. Le code de
`src/rag/` journalise, il n'affiche pas.
"""

import argparse
import logging
import sys
from pathlib import Path

from rag.chunking import chunkAll
from rag.client import ANSWER_MODEL, AnthropicClient
from rag.config import loadConfig
from rag.corpus import loadCorpus
from rag.costs import estimateCostUsd
from rag.errors import ConfigError, CorpusError, ModelCallError
from rag.generation import loadPrompt
from rag.index import LexicalIndex
from rag.pipeline import TOP_K, answerQuestion

DEFAULT_CORPUS = Path("evaluations/jeux/corpus_demo.jsonl")


def buildParser() -> argparse.ArgumentParser:
    """Décrit les arguments de la ligne de commande."""
    parser = argparse.ArgumentParser(description="Interroge le corpus indexé.")
    parser.add_argument("question", help="La question, entre guillemets.")
    parser.add_argument(
        "--corpus",
        type=Path,
        default=DEFAULT_CORPUS,
        help=f"Fichier JSONL du corpus (défaut : {DEFAULT_CORPUS}).",
    )
    parser.add_argument(
        "--top-k",
        type=int,
        default=TOP_K,
        dest="topK",
        help=f"Nombre de passages récupérés (défaut : {TOP_K}).",
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

    corpusPath = config.corpusPath or args.corpus
    try:
        documents = loadCorpus(corpusPath)
    except CorpusError as error:
        print(f"Corpus : {error}", file=sys.stderr)
        return 1

    index = LexicalIndex(chunkAll(documents))
    client = AnthropicClient(apiKey=config.apiKey)

    try:
        answer = answerQuestion(
            client=client,
            index=index,
            question=args.question,
            promptTemplate=loadPrompt(),
            topK=args.topK,
        )
    except ModelCallError as error:
        print(f"Appel modèle : {error}", file=sys.stderr)
        return 1

    print(answer.text)
    print()
    if answer.refused:
        print("(refus sans appel modèle : aucun passage pertinent trouvé)")
        return 0

    sources = ", ".join(passage.chunk.chunkId for passage in answer.passages)
    cost = estimateCostUsd(answer.usage, ANSWER_MODEL)
    print(f"Sources : {sources}")
    print(
        f"Jetons : {answer.usage.inputTokens} entrée / "
        f"{answer.usage.outputTokens} sortie — "
        f"{cost:.4f} USD — {answer.latencySeconds:.1f} s"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
