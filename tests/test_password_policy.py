from __future__ import annotations

import os

from skopos.config import AppConfig
from skopos.env_io import upsert_env_var
from skopos.password_policy import (
    min_password_length,
    password_rules,
    validate_dashboard_password,
)
from skopos.security.project_audit import audit_stats_project


def test_min_password_length_default():
    assert min_password_length() >= 12


def test_min_password_length_env(monkeypatch):
    monkeypatch.setenv("SKOPOS_DASHBOARD_PASSWORD_MIN_LENGTH", "16")
    assert min_password_length() == 16


def test_validate_strong_password():
    ok, failed = validate_dashboard_password("MySecurePass42")
    assert ok is True
    assert failed == []


def test_validate_weak_common():
    ok, failed = validate_dashboard_password("admin123")
    assert ok is False
    assert "auth.policy.not_weak" in failed


def test_validate_too_short():
    ok, failed = validate_dashboard_password("Ab1")
    assert ok is False
    assert "auth.policy.min_length" in failed


def test_validate_needs_digit():
    ok, failed = validate_dashboard_password("OnlyLettersHere")
    assert ok is False
    assert "auth.policy.has_digit" in failed


def test_password_rules_progress():
    rules = password_rules("abc")
    assert rules[0].passed is False
    rules2 = password_rules("MySecurePass42")
    assert all(r.passed for r in rules2)


def test_audit_weak_dashboard_password(monkeypatch, tmp_path):
    monkeypatch.setenv("SKOPOS_DASHBOARD_PASSWORD", "admin123")
    cfg = AppConfig(db_path=str(tmp_path / "skopos.sqlite3"), servers=[])
    issues = audit_stats_project(cfg)
    assert any("policy" in i.title.lower() or "weak" in i.title.lower() for i in issues)


def test_upsert_env_quotes_special_chars(tmp_path):
    env = tmp_path / ".env"
    upsert_env_var("SKOPOS_DASHBOARD_PASSWORD", 'p="ss#word', env_path=env)
    text = env.read_text(encoding="utf-8")
    assert "SKOPOS_DASHBOARD_PASSWORD=" in text
    assert '"' in text
