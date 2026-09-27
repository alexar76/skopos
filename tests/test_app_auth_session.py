"""Remember-me session token — signing, expiry, tamper + credential-rotation."""

from __future__ import annotations

import time

import pytest

from skopos import app_auth


@pytest.fixture
def fixed_secret(monkeypatch):
    monkeypatch.setenv("SKOPOS_DASHBOARD_SESSION_SECRET", "unit-test-secret")
    return "unit-test-secret"


def test_sign_and_validate_roundtrip(fixed_secret):
    exp = int(time.time() + 3600)
    token = app_auth._sign_token(exp)
    assert app_auth._token_valid(token)
    assert token.startswith(f"{exp}.")


def test_expired_token_is_invalid(fixed_secret):
    token = app_auth._sign_token(int(time.time() - 1))
    assert not app_auth._token_valid(token)


def test_tampered_signature_is_invalid(fixed_secret):
    exp = int(time.time() + 3600)
    token = app_auth._sign_token(exp)
    body, sig = token.split(".", 1)
    forged = f"{body}.{'0' * len(sig)}"
    assert not app_auth._token_valid(forged)


def test_tampered_expiry_is_invalid(fixed_secret):
    # Extend the expiry without re-signing → signature must no longer match.
    exp = int(time.time() + 60)
    token = app_auth._sign_token(exp)
    _, sig = token.split(".", 1)
    forged = f"{exp + 999999}.{sig}"
    assert not app_auth._token_valid(forged)


def test_malformed_tokens_are_invalid(fixed_secret):
    for bad in (None, "", "no-dot", "notanint.deadbeef", "123", ".", "abc.def"):
        assert not app_auth._token_valid(bad)


def test_credential_rotation_invalidates_token(monkeypatch):
    monkeypatch.setenv("SKOPOS_DASHBOARD_SESSION_SECRET", "secret-A")
    token = app_auth._sign_token(int(time.time() + 3600))
    assert app_auth._token_valid(token)
    # Rotating the credential (new secret material) must reject the old cookie.
    monkeypatch.setenv("SKOPOS_DASHBOARD_SESSION_SECRET", "secret-B")
    assert not app_auth._token_valid(token)


def test_secret_bound_to_env_password_when_no_override(monkeypatch):
    monkeypatch.delenv("SKOPOS_DASHBOARD_SESSION_SECRET", raising=False)
    monkeypatch.setenv("SKOPOS_DASHBOARD_PASSWORD", "hunter2-abcdef")
    token = app_auth._sign_token(int(time.time() + 3600))
    assert app_auth._token_valid(token)
    # Changing the dashboard password rotates the derived secret → old token dead.
    monkeypatch.setenv("SKOPOS_DASHBOARD_PASSWORD", "different-password-99")
    assert not app_auth._token_valid(token)
