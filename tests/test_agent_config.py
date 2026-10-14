from __future__ import annotations

import os
from pathlib import Path

import pytest

from skopos.agent.config import load_agent_config


def test_load_agent_example():
    path = Path(__file__).resolve().parents[1] / "agent.example.yaml"
    cfg = load_agent_config(str(path))
    assert cfg.default_provider == "openrouter"
    assert "openrouter" in cfg.providers
    assert cfg.providers["openrouter"].model == "minimax/minimax-m3"
    assert cfg.providers["openrouter"].base_url.startswith("https://")


def test_provider_env_key(monkeypatch):
    path = Path(__file__).resolve().parents[1] / "agent.example.yaml"
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key-123")
    cfg = load_agent_config(str(path))
    from skopos.agent.config import get_provider

    prov = get_provider(cfg, "openrouter")
    assert prov.api_key == "test-key-123"
