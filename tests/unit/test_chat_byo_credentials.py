"""BYO chat settings are fetched and decrypted only for explicitly allowed providers."""

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
API_ROOT = REPO_ROOT / "apps" / "cna-api"
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(API_ROOT))

from routers import chat as chat_router  # noqa: E402


def test_chat_settings_fetch_only_allowlisted_provider_keys(monkeypatch):
    monkeypatch.setenv("CNA_AI_MODE", "byo-api")
    monkeypatch.setenv("CNA_BYO_AI_PROVIDERS", '["anthropic"]')
    executed: list[tuple[str, list[str]]] = []

    class Cursor:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def execute(self, query, params):
            executed.append((query, params[0]))

        def fetchall(self):
            return []

    class Connection:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def cursor(self):
            return Cursor()

    monkeypatch.setattr(chat_router, "DATABASE_URL", "postgresql://test")
    monkeypatch.setattr(chat_router.db, "connection", lambda _url: Connection())

    assert chat_router._load_ai_settings(("anthropic",)) == {}
    assert executed[0][1] == [
        "ai.activeEngine",
        "ai.byo.anthropic.apiKey",
        "ai.byo.anthropic.model",
    ]


def test_chat_decrypts_only_allowlisted_provider_keys(monkeypatch):
    monkeypatch.setenv("CNA_AI_MODE", "byo-api")
    monkeypatch.setenv("CNA_BYO_AI_PROVIDERS", '["anthropic"]')
    decrypted: list[str] = []

    def fake_decrypt(blob: str) -> str:
        decrypted.append(blob)
        return "cleartext-key"

    monkeypatch.setattr(chat_router, "decrypt", fake_decrypt)
    keys, models = chat_router._load_byo_credentials(
        {
            "ai.byo.anthropic.apiKey": "anthropic-ciphertext",  # pragma: allowlist secret
            "ai.byo.anthropic.model": "claude-test",
            "ai.byo.openai.apiKey": "openai-ciphertext",  # pragma: allowlist secret
            "ai.byo.openai.model": "gpt-test",
        },
        ("anthropic",),
    )

    assert decrypted == ["anthropic-ciphertext"]
    assert keys == {"anthropic": "cleartext-key"}
    assert models == {"anthropic": "claude-test"}


def test_saas_does_not_decrypt_or_require_byo_provider_config(monkeypatch):
    monkeypatch.setenv("CNA_AI_MODE", "saas")
    monkeypatch.setenv("CNA_BYO_AI_PROVIDERS", "not-json")

    def fail_if_called(_blob: str) -> str:
        pytest.fail("SaaS mode must not decrypt BYO credentials")

    monkeypatch.setattr(chat_router, "decrypt", fail_if_called)
    assert chat_router._load_byo_credentials(
        {"ai.byo.anthropic.apiKey": "stored-ciphertext"}, ()  # pragma: allowlist secret
    ) == ({}, {})


def test_invalid_provider_config_fails_before_settings_database_access(monkeypatch):
    monkeypatch.setenv("CNA_AI_MODE", "byo-api")
    monkeypatch.delenv("CNA_BYO_AI_PROVIDERS", raising=False)

    def fail_if_called(_url):
        pytest.fail("invalid provider config must fail before reading settings")

    monkeypatch.setattr(chat_router, "DATABASE_URL", "postgresql://test")
    monkeypatch.setattr(chat_router.db, "connection", fail_if_called)

    with pytest.raises(chat_router.ChatConfigError, match="CNA_BYO_AI_PROVIDERS"):
        chat_router._load_ai_settings(())


@pytest.mark.parametrize("config", [None, "", " ", "not-json", "{}", "[]"])
def test_invalid_provider_config_fails_before_decrypt(monkeypatch, config):
    monkeypatch.setenv("CNA_AI_MODE", "byo-api")
    if config is None:
        monkeypatch.delenv("CNA_BYO_AI_PROVIDERS", raising=False)
    else:
        monkeypatch.setenv("CNA_BYO_AI_PROVIDERS", config)

    def fail_if_called(_blob: str) -> str:
        pytest.fail("invalid provider config must fail before decrypt")

    monkeypatch.setattr(chat_router, "decrypt", fail_if_called)
    with pytest.raises(chat_router.ChatConfigError, match="CNA_BYO_AI_PROVIDERS"):
        chat_router._load_byo_credentials({"ai.byo.anthropic.apiKey": "stored-ciphertext"}, ())
