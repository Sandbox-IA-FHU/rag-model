"""Tests de la configuration.

La configuration doit échouer **au démarrage**, avec un message qui dit quoi
faire. Une clé absente qui devient un `None` casse trois couches plus loin,
dans un message qui ne parle pas de configuration.
"""

import pytest

from rag.config import loadConfig
from rag.errors import ConfigError


def test_missingApiKeyFailsImmediately(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)

    with pytest.raises(ConfigError, match="ANTHROPIC_API_KEY"):
        loadConfig()


def test_blankApiKeyIsTreatedAsMissing(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ANTHROPIC_API_KEY", "   ")

    with pytest.raises(ConfigError):
        loadConfig()


def test_invalidLogLevelIsRefused(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ANTHROPIC_API_KEY", "cle-de-test")
    monkeypatch.setenv("LOG_LEVEL", "BAVARD")

    with pytest.raises(ConfigError, match="LOG_LEVEL"):
        loadConfig()


def test_unreadableCorpusPathIsRefused(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ANTHROPIC_API_KEY", "cle-de-test")
    monkeypatch.delenv("LOG_LEVEL", raising=False)
    monkeypatch.setenv("CORPUS_PATH", "chemin/qui/nexiste/pas.jsonl")

    with pytest.raises(ConfigError, match="CORPUS_PATH"):
        loadConfig()


def test_validConfigurationIsAccepted(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ANTHROPIC_API_KEY", "cle-de-test")
    monkeypatch.setenv("LOG_LEVEL", "debug")
    monkeypatch.delenv("CORPUS_PATH", raising=False)

    config = loadConfig()

    assert config.apiKey == "cle-de-test"
    assert config.logLevel == "DEBUG"
    assert config.corpusPath is None
