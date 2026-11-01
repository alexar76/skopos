"""The host agent rides out a server restart instead of leaving its unit failed.

2026-10-26..11-01 the report unit on skopos-vps failed 76 times, every time with the
server restarting under it (connection refused, 502, 503 from the proxy) and the next tick
five minutes later succeeding. A failed unit is what operators look at; it must mean
something is wrong, not that a container was being swapped.
"""

from __future__ import annotations

import urllib.error

import pytest

from skopos.node_agent import skopos_node as agent


def _http(code: int) -> urllib.error.HTTPError:
    return urllib.error.HTTPError("https://skopos.example/node/v1/report", code, "x", {}, None)


def _run(monkeypatch, outcomes):
    calls, waits = [], []

    def fake_send(cfg, credential, doc):
        calls.append(1)
        outcome = outcomes[len(calls) - 1]
        if isinstance(outcome, BaseException):
            raise outcome
        return outcome

    monkeypatch.setattr(agent, "send_report", fake_send)
    try:
        return agent.send_with_retry({}, {}, {}, waits=(5, 15, 30), sleep=waits.append), calls, waits
    except BaseException as exc:  # noqa: BLE001 - the test reads what escaped
        return exc, calls, waits


@pytest.mark.parametrize("failure", [
    urllib.error.URLError(ConnectionRefusedError(111, "Connection refused")),
    _http(502), _http(503), _http(504),
    ConnectionResetError(104, "Connection reset by peer"),
])
def test_a_restarting_server_is_retried_and_the_report_lands(monkeypatch, failure):
    result, calls, waits = _run(monkeypatch, [failure, failure, {"ok": True}])
    assert result == {"ok": True}
    assert len(calls) == 3 and waits == [5, 15]


def test_a_server_down_for_longer_still_fails_the_run(monkeypatch):
    down = _http(503)
    result, calls, waits = _run(monkeypatch, [down, down, down, down])
    assert result is down
    assert len(calls) == 4 and waits == [5, 15, 30]


@pytest.mark.parametrize("failure", [
    _http(401), _http(400), _http(500),
    urllib.error.URLError(TimeoutError("timed out")),
    agent.Unsafe("base_url must be https"),
])
def test_anything_else_fails_at_once(monkeypatch, failure):
    result, calls, waits = _run(monkeypatch, [failure, {"ok": True}])
    assert result is failure
    assert len(calls) == 1 and waits == []
