from __future__ import annotations

import pytest

from skopos.agent.config import ProviderConfig
from skopos.agent.providers import (
    LLMProviderError,
    _extract_openai_message_content,
    _is_reasoning_model,
    _openrouter_reasoning_payload,
)


def test_is_reasoning_model_detects_minimax():
    assert _is_reasoning_model("minimax/minimax-m3")
    assert not _is_reasoning_model("gpt-4o-mini")


def test_openrouter_reasoning_payload_for_minimax():
    prov = ProviderConfig(
        id="openrouter",
        kind="openai_compatible",
        base_url="https://openrouter.ai/api/v1",
        model="minimax/minimax-m3",
        api_key="x",
    )
    assert _openrouter_reasoning_payload(prov) == {"reasoning": {"effort": "low", "exclude": True}}


def test_openrouter_reasoning_payload_skips_non_openrouter():
    prov = ProviderConfig(
        id="openai",
        kind="openai_compatible",
        base_url="https://api.openai.com/v1",
        model="minimax/minimax-m3",
        api_key="x",
    )
    assert _openrouter_reasoning_payload(prov) == {}


def test_extract_openai_message_content_reads_content():
    data = {
        "choices": [
            {"finish_reason": "stop", "message": {"role": "assistant", "content": "Привет"}},
        ]
    }
    assert _extract_openai_message_content(data) == "Привет"


def test_extract_openai_message_content_rejects_empty_reasoning_only():
    data = {
        "choices": [
            {
                "finish_reason": "length",
                "message": {
                    "role": "assistant",
                    "content": "",
                    "reasoning": "internal chain of thought",
                },
            }
        ]
    }
    with pytest.raises(LLMProviderError, match="no text"):
        _extract_openai_message_content(data)
