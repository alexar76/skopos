"""Unit tests for the floating agent's HMAC session token."""

from __future__ import annotations

import time

import skopos.agent_token as at


def _use_fixed_secret(monkeypatch, secret="test-secret-abc123"):
    monkeypatch.setenv("SKOPOS_AGENT_TOKEN_SECRET", secret)
    at.reset_cache()


def test_issue_and_verify_roundtrip(monkeypatch):
    _use_fixed_secret(monkeypatch)
    token = at.issue_token()
    assert "." in token
    assert at.verify_token(token) is True


def test_tampered_token_rejected(monkeypatch):
    _use_fixed_secret(monkeypatch)
    token = at.issue_token()
    exp, _, sig = token.partition(".")
    forged = f"{exp}.{'0' * len(sig)}"
    assert at.verify_token(forged) is False


def test_expired_token_rejected(monkeypatch):
    _use_fixed_secret(monkeypatch)
    past = int(time.time()) - 10
    sig = at._sign(at.agent_secret(), str(past))
    assert at.verify_token(f"{past}.{sig}") is False


def test_wrong_secret_rejected(monkeypatch):
    _use_fixed_secret(monkeypatch, "secret-one")
    token = at.issue_token()
    _use_fixed_secret(monkeypatch, "secret-two")
    assert at.verify_token(token) is False


def test_malformed_tokens_rejected(monkeypatch):
    _use_fixed_secret(monkeypatch)
    for bad in (None, "", "no-dot", "abc.def", ".", "123."):
        assert at.verify_token(bad) is False
