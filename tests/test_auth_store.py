"""Tests for DB-backed hashed dashboard credentials + expiry tracking."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from skopos import auth_store
from skopos.db_connection import connect


@pytest.fixture()
def db(tmp_path):
    return str(tmp_path / "skopos.sqlite3")


def test_hash_roundtrip_and_no_plaintext():
    encoded = auth_store.hash_password("Sup3rSecret!pw")
    assert encoded.startswith("pbkdf2_sha256$")
    assert "Sup3rSecret!pw" not in encoded
    assert auth_store.verify_password("Sup3rSecret!pw", encoded)
    assert not auth_store.verify_password("wrong", encoded)


def test_verify_password_rejects_garbage():
    assert not auth_store.verify_password("x", None)
    assert not auth_store.verify_password("x", "not-a-hash")
    assert not auth_store.verify_password("x", "md5$1$aa$bb")


def test_generated_password_meets_policy():
    for _ in range(20):
        pw = auth_store.generate_strong_password()
        ok, failed = __import__("skopos.password_policy", fromlist=["validate_dashboard_password"]).validate_dashboard_password(pw)
        assert ok, (pw, failed)
        assert len(pw) >= 16


def test_set_verify_clear_uses_db_hash(db, monkeypatch):
    monkeypatch.delenv("SKOPOS_DASHBOARD_PASSWORD", raising=False)
    assert not auth_store.dashboard_hash_set(db_target=db)
    assert not auth_store.dashboard_password_configured(db_target=db)

    auth_store.set_dashboard_password("MyStrongPass9", db_target=db)
    assert auth_store.dashboard_hash_set(db_target=db)
    assert auth_store.dashboard_password_configured(db_target=db)
    assert auth_store.password_source(db_target=db) == "db"
    assert auth_store.verify_dashboard_password("MyStrongPass9", db_target=db)
    assert not auth_store.verify_dashboard_password("nope", db_target=db)

    # Only the hash is persisted — plaintext must not be in the DB.
    con = connect(db)
    rows = con.execute("SELECT value FROM app_settings").fetchall()
    con.close()
    values = " ".join(str(r[0] if not isinstance(r, dict) else r.get("value")) for r in rows)
    assert "MyStrongPass9" not in values

    auth_store.clear_dashboard_password(db_target=db)
    assert not auth_store.dashboard_hash_set(db_target=db)


def test_env_fallback_when_no_hash(db, monkeypatch):
    monkeypatch.setenv("SKOPOS_DASHBOARD_PASSWORD", "EnvBootstrap42")
    assert auth_store.dashboard_password_configured(db_target=db)
    assert auth_store.password_source(db_target=db) == "env"
    assert auth_store.verify_dashboard_password("EnvBootstrap42", db_target=db)
    assert not auth_store.verify_dashboard_password("other", db_target=db)


def test_db_hash_takes_precedence_over_env(db, monkeypatch):
    monkeypatch.setenv("SKOPOS_DASHBOARD_PASSWORD", "EnvBootstrap42")
    auth_store.set_dashboard_password("DbHashWins123", db_target=db)
    assert auth_store.password_source(db_target=db) == "db"
    assert auth_store.verify_dashboard_password("DbHashWins123", db_target=db)
    # env no longer accepted once a hash exists
    assert not auth_store.verify_dashboard_password("EnvBootstrap42", db_target=db)


def _force_set_at(db_target: str, dt: datetime) -> None:
    con = connect(db_target)
    con.execute(
        "UPDATE app_settings SET value = ? WHERE key = ?",
        (dt.isoformat(), "dashboard_password_set_at_utc"),
    )
    con.commit()
    con.close()


def test_expiry_tracking(db, monkeypatch):
    monkeypatch.setenv("SKOPOS_DASHBOARD_PASSWORD_MAX_AGE_DAYS", "90")
    auth_store.set_dashboard_password("FreshPass1234", db_target=db)

    remaining = auth_store.password_expires_in_days(db_target=db)
    assert remaining is not None and 89 <= remaining <= 90
    assert not auth_store.password_expired(db_target=db)

    # Age it 100 days → expired.
    _force_set_at(db, datetime.now(tz=timezone.utc) - timedelta(days=100))
    assert auth_store.password_expired(db_target=db)
    assert (auth_store.password_expires_in_days(db_target=db) or 0) < 0

    # Age it 87 days → expiring soon (within 7-day warn window).
    _force_set_at(db, datetime.now(tz=timezone.utc) - timedelta(days=87))
    assert auth_store.password_expiring_soon(db_target=db)


def test_expiry_disabled_when_max_age_zero(db, monkeypatch):
    monkeypatch.setenv("SKOPOS_DASHBOARD_PASSWORD_MAX_AGE_DAYS", "0")
    auth_store.set_dashboard_password("FreshPass1234", db_target=db)
    _force_set_at(db, datetime.now(tz=timezone.utc) - timedelta(days=999))
    assert auth_store.password_expires_in_days(db_target=db) is None
    assert not auth_store.password_expired(db_target=db)
