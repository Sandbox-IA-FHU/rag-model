"""Configuration du projet.

Seul module du dépôt qui lit `os.environ`. Partout ailleurs, la configuration
arrive en argument — c'est ce qui rend le reste testable sans clé d'API.
"""

import os
from dataclasses import dataclass
from pathlib import Path

from rag.errors import ConfigError

VALID_LOG_LEVELS = ("DEBUG", "INFO", "WARNING", "ERROR")
DEFAULT_LOG_LEVEL = "INFO"


@dataclass(frozen=True)
class Config:
    """Configuration validée. Construite uniquement par `loadConfig`."""

    apiKey: str
    logLevel: str
    corpusPath: Path | None


def loadConfig() -> Config:
    """Lit la configuration depuis l'environnement et la valide.

    Échoue immédiatement si elle est incomplète. Un `os.environ.get` qui rend
    None produit une erreur trois couches plus loin, dans un message qui ne
    parle pas de configuration.
    """
    apiKey = os.environ.get("ANTHROPIC_API_KEY", "").strip()
    if not apiKey:
        raise ConfigError(
            "ANTHROPIC_API_KEY est absente. Copier .env.exemple en .env, "
            "la renseigner, puis lancer avec : uv run --env-file .env ..."
        )

    logLevel = os.environ.get("LOG_LEVEL", DEFAULT_LOG_LEVEL).strip().upper()
    if logLevel not in VALID_LOG_LEVELS:
        raise ConfigError(
            f"LOG_LEVEL vaut {logLevel!r}, attendu l'un de {VALID_LOG_LEVELS}."
        )

    rawCorpusPath = os.environ.get("CORPUS_PATH", "").strip()
    corpusPath = Path(rawCorpusPath) if rawCorpusPath else None
    if corpusPath is not None and not corpusPath.is_file():
        raise ConfigError(
            f"CORPUS_PATH ne désigne pas un fichier lisible : {corpusPath}"
        )

    return Config(apiKey=apiKey, logLevel=logLevel, corpusPath=corpusPath)
