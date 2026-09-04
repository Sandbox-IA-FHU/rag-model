"""Accès au fournisseur de modèle.

Seul module qui connaît le SDK. Le reste de la chaîne ne manipule que le
protocole `ModelClient` — c'est ce qui permet aux tests d'injecter un faux
client, et à la CI de tourner avec une clé volontairement invalide.
"""

import logging
from dataclasses import dataclass
from typing import Protocol

import anthropic

from rag.errors import ModelCallError
from rag.models import Usage

# Identifiant de modèle figé, jamais écrit en ligne dans le code appelant.
# Les identifiants Anthropic actuels ne portent pas de suffixe de date :
# la reproductibilité repose sur le fichier de run, qui consigne l'identifiant
# ET la date d'exécution. Voir CONVENTIONS-PYTHON.md § 5.
ANSWER_MODEL = "claude-opus-5"

MAX_OUTPUT_TOKENS = 1024
REQUEST_TIMEOUT_SECONDS = 60.0
MAX_RETRIES = 2

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ModelReply:
    """Réponse d'un appel modèle, réduite à ce dont la chaîne a besoin."""

    text: str
    usage: Usage


class ModelClient(Protocol):
    """Ce que la chaîne attend d'un client modèle. Rien de plus."""

    def complete(self, system: str, userText: str) -> ModelReply:
        """Un aller-retour : consignes système, message utilisateur, réponse."""
        ...


class AnthropicClient:
    """Implémentation réelle, au-dessus du SDK Anthropic."""

    def __init__(
        self,
        apiKey: str,
        model: str = ANSWER_MODEL,
        maxOutputTokens: int = MAX_OUTPUT_TOKENS,
        timeoutSeconds: float = REQUEST_TIMEOUT_SECONDS,
        maxRetries: int = MAX_RETRIES,
    ) -> None:
        # Délai et réessais explicites : le défaut du SDK est de dix minutes
        # et deux réessais, ce n'est pas une valeur qu'on subit sans le savoir.
        self._client = anthropic.Anthropic(
            api_key=apiKey,
            timeout=timeoutSeconds,
            max_retries=maxRetries,
        )
        self.model = model
        self.maxOutputTokens = maxOutputTokens

    def complete(self, system: str, userText: str) -> ModelReply:
        """Appelle le modèle et rend le texte avec la consommation de jetons.

        Les exceptions du SDK sont converties en `ModelCallError`. Le message
        ne contient ni le prompt ni la réponse : seulement de quoi diagnostiquer.
        """
        try:
            response = self._client.messages.create(
                model=self.model,
                max_tokens=self.maxOutputTokens,
                system=system,
                messages=[{"role": "user", "content": userText}],
            )
        except anthropic.AuthenticationError as error:
            raise ModelCallError(
                "Authentification refusée. Vérifier ANTHROPIC_API_KEY."
            ) from error
        except anthropic.RateLimitError as error:
            raise ModelCallError(
                "Quota atteint chez le fournisseur. Réessayer plus tard."
            ) from error
        except anthropic.APIStatusError as error:
            raise ModelCallError(
                f"Appel modèle refusé (HTTP {error.status_code})."
            ) from error
        except anthropic.APIConnectionError as error:
            raise ModelCallError("Le fournisseur est injoignable.") from error

        # Un refus du modèle arrive en HTTP 200 : on le distingue d'une réponse.
        if response.stop_reason == "refusal":
            raise ModelCallError(
                "Le modèle a refusé de répondre (stop_reason=refusal)."
            )

        text = "".join(block.text for block in response.content if block.type == "text")
        usage = Usage(
            inputTokens=response.usage.input_tokens,
            outputTokens=response.usage.output_tokens,
        )
        logger.info(
            "appel modèle model=%s jetons_entree=%d jetons_sortie=%d",
            self.model,
            usage.inputTokens,
            usage.outputTokens,
        )
        return ModelReply(text=text, usage=usage)
