"""Tests for Observability markdown injected into the LLM agent context."""

from __future__ import annotations

from skopos.observability.context_fmt import format_observability_context


def test_format_observability_unreachable_does_not_invent_kpis(monkeypatch):
    monkeypatch.setenv("SKOPOS_PROMETHEUS_URL", "http://127.0.0.1:9/prometheus")

    def _boom(*_a, **_k):
        return {"status": "error", "error": "connection refused"}

    monkeypatch.setattr("skopos.observability.prom.query_instant", _boom)
    text = format_observability_context()
    assert "## Observability" in text
    assert "unreachable" in text.lower()
    assert "0.42" not in text  # demo invoke_rps must not leak into LLM context
    assert "do **not** treat demo" in text.lower() or "do not invent" in text.lower() or "Do not invent" in text


def test_format_observability_live_includes_kpis(monkeypatch):
    monkeypatch.setenv("SKOPOS_PROMETHEUS_URL", "http://prom.test/prometheus")

    def fake_collect():
        return (
            {
                "hub_up": 1.0,
                "factory_up": 1.0,
                "metis_up": 0.0,
                "invoke_rps": 1.25,
                "payment_required_rps": 0.1,
                "p99_s": 0.8,
            },
            True,
        )

    monkeypatch.setattr("skopos.observability.context_fmt.collect_overview_kpis", fake_collect)
    monkeypatch.setattr(
        "skopos.observability.context_fmt.query_instant",
        lambda *_a, **_k: {
            "status": "success",
            "data": {
                "result": [
                    {
                        "metric": {"capability": "platon.oracle@v1", "result": "payment_required"},
                        "value": [1, "0.12"],
                    }
                ]
            },
        },
    )
    text = format_observability_context()
    assert "Status: **live**" in text
    assert "Hub: UP" in text
    assert "Metis: DOWN" in text
    assert "1.25" in text
    assert "platon.oracle@v1" in text
    assert "payment_required" in text


def test_skopos_knowledge_mentions_observability():
    from skopos.agent.context import _SKOPOS_KNOWLEDGE

    assert "Observability" in _SKOPOS_KNOWLEDGE
    assert "Prometheus" in _SKOPOS_KNOWLEDGE
