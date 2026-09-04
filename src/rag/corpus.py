"""Lecture du corpus.

Le corpus vit dans un fichier JSONL, une ligne par document :

    {"doc_id": "doc-01", "titre": "...", "texte": "..."}

Les clés du fichier sont en français et en `snake_case` : c'est un contrat de
données, pas du code Python. La conversion vers les attributs `camelCase` de
`Document` se fait ici, et nulle part ailleurs.
"""

import json
from pathlib import Path

from rag.errors import CorpusError
from rag.models import Document

REQUIRED_FIELDS = ("doc_id", "titre", "texte")


def loadCorpus(path: Path) -> list[Document]:
    """Lit un corpus JSONL et rend la liste des documents.

    Échoue sur la première ligne mal formée, en indiquant son numéro : un
    corpus à moitié chargé produit un score faux qu'on met une heure à
    comprendre.
    """
    if not path.is_file():
        raise CorpusError(f"Corpus introuvable : {path}")

    documents: list[Document] = []
    seenIds: set[str] = set()

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

            docId = str(record["doc_id"])
            if docId in seenIds:
                raise CorpusError(
                    f"{path.name} ligne {lineNumber} : doc_id en double ({docId})."
                )
            seenIds.add(docId)

            documents.append(
                Document(
                    docId=docId,
                    title=str(record["titre"]),
                    text=str(record["texte"]),
                )
            )

    if not documents:
        raise CorpusError(f"Corpus vide : {path}")

    return documents
