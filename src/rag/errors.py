"""Exceptions de la chaîne.

Un message d'exception ne contient jamais le contenu d'un document, d'un
prompt ou d'une réponse de modèle : seulement des identifiants et des
compteurs. Une trace d'erreur finit dans un ticket, une capture d'écran ou un
canal de discussion.
"""


class ConfigError(Exception):
    """Configuration absente ou invalide au démarrage."""


class CorpusError(Exception):
    """Corpus illisible, vide, ou mal formé."""


class ChunkingError(Exception):
    """Paramètres de découpage incohérents."""


class ModelCallError(Exception):
    """L'appel au fournisseur de modèle a échoué de façon définitive."""
