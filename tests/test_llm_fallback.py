from __future__ import annotations

import pytest

from skopos.agent.config import AgentConfig, ProviderConfig
from skopos.agent.ecosystem_briefing import _briefing_attempt_chain, _pick_briefing_provider
from skopos.agent.providers import (
    ChatMessage,
    LLMEmptyResponseError,
    LLMProviderError,
    _extract_openai_message_content,
    chat_completion_with_fallback,
    is_transient_llm_error,
)


def _agent_cfg(**overrides) -> AgentConfig:
    providers = {
        "openrouter": ProviderConfig(
            id="openrouter",
            kind="openai_compatible",
            base_url="https://openrouter.ai/api/v1",
            model="minimax/minimax-m3",
            api_key="or-key",
            api_key_env="OPENROUTER_API_KEY",
        ),
        "deepseek": ProviderConfig(
            id="deepseek",
            kind="openai_compatible",
            base_url="https://api.deepseek.com/v1",
            model="deepseek-chat",
            api_key="ds-key",
            api_key_env="DEEPSEEK_API_KEY",
        ),
    }
    base = AgentConfig(
        default_provider="openrouter",
        providers=providers,
        system_prompt="test",
        briefing_provider=overrides.pop("briefing_provider", None),
        briefing_model=overrides.pop("briefing_model", None),
    )
    return base


def test_is_transient_llm_error_detects_connection_pool():
    assert is_transient_llm_error(
        LLMProviderError("LLM request failed: HTTPSConnectionPool(host='openrouter.ai', port=443)")
    )


def test_pick_briefing_provider_prefers_explicit_briefing_provider():
    cfg = _agent_cfg(briefing_provider="deepseek")
    assert _pick_briefing_provider(cfg) == "deepseek"


def test_briefing_attempt_chain_includes_openrouter_fast_model():
    cfg = _agent_cfg(briefing_provider="deepseek")
    chain = _briefing_attempt_chain(cfg)
    assert chain[0] == ("deepseek", None)
    assert ("openrouter", "deepseek/deepseek-chat") in chain
    assert ("openrouter", None) in chain


def test_chat_completion_with_fallback_tries_next_provider(monkeypatch):
    cfg = _agent_cfg(briefing_provider="deepseek")
    calls: list[tuple[str | None, str | None]] = []

    def fake_chat(_cfg, _messages, *, provider_id=None, model=None, temperature=0.2, max_tokens=4096):
        calls.append((provider_id, model))
        if provider_id == "deepseek":
            raise LLMProviderError("LLM request failed: HTTPSConnectionPool(host='api.deepseek.com')")
        if provider_id == "openrouter" and model == "deepseek/deepseek-chat":
            return "All good on factory."
        raise AssertionError(f"unexpected attempt {provider_id} {model}")

    monkeypatch.setattr("skopos.agent.providers.chat_completion", fake_chat)
    text, provider_id, model = chat_completion_with_fallback(
        cfg,
        [ChatMessage("user", "hi")],
        _briefing_attempt_chain(cfg),
    )
    assert text == "All good on factory."
    assert provider_id == "openrouter"
    assert model == "deepseek/deepseek-chat"
    assert calls[0][0] == "deepseek"


def test_no_text_response_is_an_empty_response_error():
    """finish_reason=length with no content is the case the deploy smoke hit."""
    data = {"choices": [{"message": {"content": ""}, "finish_reason": "length"}]}
    with pytest.raises(LLMEmptyResponseError):
        _extract_openai_message_content(data)


def test_fallback_moves_on_when_a_provider_returns_no_text(monkeypatch):
    """A provider that answers with no usable text must not abort the chain.

    Before, only a transient network error fell through; a finish_reason=length
    (reasoning ate the budget) raised on the first provider and never reached the
    next one, which may well have content.
    """
    cfg = _agent_cfg(briefing_provider="deepseek")
    calls: list[tuple[str | None, str | None]] = []

    def fake_chat(_cfg, _messages, *, provider_id=None, model=None, temperature=0.2, max_tokens=4096):
        calls.append((provider_id, model))
        if provider_id == "deepseek":
            raise LLMEmptyResponseError("Model returned no text (finish_reason=length).")
        if provider_id == "openrouter" and model == "deepseek/deepseek-chat":
            return "Recovered on the next provider."
        raise AssertionError(f"unexpected attempt {provider_id} {model}")

    monkeypatch.setattr("skopos.agent.providers.chat_completion", fake_chat)
    text, provider_id, model = chat_completion_with_fallback(
        cfg,
        [ChatMessage("user", "hi")],
        _briefing_attempt_chain(cfg),
    )
    assert text == "Recovered on the next provider."
    assert provider_id == "openrouter"
    assert calls[0][0] == "deepseek"


def test_fallback_raises_when_every_provider_returns_no_text(monkeypatch):
    """If nobody produces content, the chain still fails rather than hanging."""
    cfg = _agent_cfg(briefing_provider="deepseek")

    def fake_chat(_cfg, _messages, *, provider_id=None, model=None, temperature=0.2, max_tokens=4096):
        raise LLMEmptyResponseError("Model returned no text (finish_reason=length).")

    monkeypatch.setattr("skopos.agent.providers.chat_completion", fake_chat)
    with pytest.raises(LLMProviderError):
        chat_completion_with_fallback(cfg, [ChatMessage("user", "hi")], _briefing_attempt_chain(cfg))
