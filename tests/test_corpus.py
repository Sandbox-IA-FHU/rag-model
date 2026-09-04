"""Tests de la lecture du corpus.

Un corpus à moitié chargé produit un score faux qu'on met une heure à
comprendre : la lecture échoue sur la première ligne douteuse, en la nommant.
"""

from pathlib import Path

import pytest

from rag.corpus import loadCorpus
from rag.errors import CorpusError

REPO_ROOT = Path(__file__).resolve().parents[1]
DEMO_CORPUS = REPO_ROOT / "evaluations" / "jeux" / "corpus_demo.jsonl"


def writeLines(tmp_path: Path, lines: list[str]) -> Path:
    """Écrit un fichier JSONL temporaire."""
    path = tmp_path / "corpus.jsonl"
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def test_demoCorpusLoads() -> None:
    documents = loadCorpus(DEMO_CORPUS)

    assert len(documents) == 8
    assert {document.docId for document in documents} >= {"doc-01", "doc-07"}


def test_missingFileIsReported(tmp_path: Path) -> None:
    with pytest.raises(CorpusError, match="introuvable"):
        loadCorpus(tmp_path / "absent.jsonl")


def test_emptyCorpusIsRefused(tmp_path: Path) -> None:
    path = tmp_path / "vide.jsonl"
    path.write_text("", encoding="utf-8")

    with pytest.raises(CorpusError, match="vide"):
        loadCorpus(path)


def test_malformedLineIsReportedWithItsNumber(tmp_path: Path) -> None:
    path = writeLines(
        tmp_path,
        [
            '{"doc_id": "doc-01", "titre": "T", "texte": "ok"}',
            "ceci n'est pas du json",
        ],
    )

    with pytest.raises(CorpusError, match="ligne 2"):
        loadCorpus(path)


def test_missingFieldIsReported(tmp_path: Path) -> None:
    path = writeLines(tmp_path, ['{"doc_id": "doc-01", "titre": "T"}'])

    with pytest.raises(CorpusError, match="texte"):
        loadCorpus(path)


def test_duplicateIdIsRefused(tmp_path: Path) -> None:
    # Deux documents de même identifiant rendent le rappel ininterprétable.
    path = writeLines(
        tmp_path,
        [
            '{"doc_id": "doc-01", "titre": "T", "texte": "a"}',
            '{"doc_id": "doc-01", "titre": "T", "texte": "b"}',
        ],
    )

    with pytest.raises(CorpusError, match="double"):
        loadCorpus(path)
