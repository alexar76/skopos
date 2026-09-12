"""Unit tests for the headless agent chat service (input handling / fallback order)."""

from __future__ import annotations

import pytest

from skopos.agent.config import AgentConfig, ProviderConfig
from skopos.agent.providers import LLMProviderError
from skopos.agent.service import _attempt_chain, _coerce_history, answer_agent_message


def _cfg() -> AgentConfig:
    return AgentConfig(
        default_provider="deepseek",
        providers={
            "openrouter": ProviderConfig(id="openrouter", kind="openai_compatible", base_url="x", model="m1"),
            "deepseek": ProviderConfig(id="deepseek", kind="openai_compatible", base_url="y", model="m2"),
        },
        system_prompt="sys",
    )


def test_coerce_history_filters_and_trims():
    raw = [
        {"role": "user", "content": "hi"},
        {"role": "assistant", "content": "hello"},
        {"role": "system", "content": "ignored"},
        {"role": "user", "content": ""},
        "not-a-dict",
    ]
    out = _coerce_history(raw)
    assert [m.role for m in out] == ["user", "assistant"]
    assert out[0].content == "hi"


def test_attempt_chain_puts_default_first():
    chain = _attempt_chain(_cfg())
    ids = [pid for pid, _ in chain]
    assert ids[0] == "deepseek"
    assert set(ids) == {"deepseek", "openrouter"}


def test_answer_requires_trailing_user_message():
    with pytest.raises(LLMProviderError):
        answer_agent_message([{"role": "assistant", "content": "hello"}])
    with pytest.raises(LLMProviderError):
        answer_agent_message([])
