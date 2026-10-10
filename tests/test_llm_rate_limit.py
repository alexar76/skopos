from __future__ import annotations

import time

from skopos.agent.rate_limit import wait_before_llm_call


def test_rate_limit_waits(monkeypatch):
    monkeypatch.setenv("LLM_MIN_INTERVAL_SEC", "0.05")
    t0 = time.monotonic()
    wait_before_llm_call()
    wait_before_llm_call()
    assert time.monotonic() - t0 >= 0.04
