"""Telegram notification helpers."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import yaml

from skopos.config import AppConfig, load_config
from skopos.security.posture import SecurityAlert, SecurityPosture, ServerScore
from skopos.telegram_notify import (
    DEFAULT_TELEGRAM_NOTIFY_INTERVAL_MINUTES,
    format_security_message,
    maybe_send_password_expiry_telegram,
    maybe_send_security_telegram,
    send_telegram_message,
)


def _sample_posture(**overrides) -> SecurityPosture:
    alerts = overrides.pop("alerts", [])
    return SecurityPosture(
        fleet_score=overrides.get("fleet_score", 55),
        grade=overrides.get("grade", "D"),
        server_scores=[ServerScore(server_name="web1", score=55, grade="D")],
        alerts=alerts,
        remarks=overrides.get("remarks", []),
        computed_at_utc="2026-07-14T12:00:00+00:00",
    )


def test_telegram_config_defaults(tmp_path):
    p = tmp_path / "servers.yaml"
    p.write_text(
        yaml.safe_dump(
            {
                "servers": [
                    {
                        "name": "s1",
                        "source": "ssh_nginx_access_log",
                        "ssh": {"host": "1.2.3.4", "user": "root"},
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    cfg = load_config(str(p))
    assert cfg.telegram_enabled is False
    assert cfg.telegram_chat_id is None
    assert cfg.telegram_notify_interval_minutes == DEFAULT_TELEGRAM_NOTIFY_INTERVAL_MINUTES


def test_format_security_message_escapes_html():
    posture = _sample_posture(
        alerts=[
            SecurityAlert(
                id="a1",
                severity="critical",
                category="ports",
                title="<script>alert(1)</script>",
                message="bad",
                server_name="web&1",
            )
        ]
    )
    text = format_security_message(posture)
    assert "<script>" not in text
    assert "&lt;script&gt;" in text
    assert "web&amp;1" in text


@patch("skopos.telegram_notify.urllib.request.urlopen")
def test_send_telegram_message_ok(mock_urlopen):
    resp = MagicMock()
    resp.read.return_value = b'{"ok": true}'
    mock_urlopen.return_value.__enter__.return_value = resp

    ok, detail = send_telegram_message("token123", "999", "hello")
    assert ok is True
    assert detail == "ok"


@patch("skopos.telegram_notify.load_security_posture")
@patch("skopos.telegram_notify.send_telegram_message")
def test_maybe_send_skips_when_disabled(mock_send, mock_posture):
    cfg = AppConfig(
        db_path="./skopos.sqlite3",
        telegram_enabled=False,
        servers=[],
    )
    ok, detail = maybe_send_security_telegram(cfg, force=True)
    assert ok is False
    mock_send.assert_not_called()
    mock_posture.assert_not_called()


@patch("skopos.telegram_notify.load_security_posture")
@patch("skopos.telegram_notify.send_telegram_message")
def test_maybe_send_on_critical(mock_send, mock_posture):
    mock_posture.return_value = _sample_posture(
        alerts=[
            SecurityAlert(
                id="a1",
                severity="critical",
                category="auth",
                title="Root login",
                message="detail",
            )
        ]
    )
    mock_send.return_value = (True, "ok")

    cfg = AppConfig(
        db_path="./skopos.sqlite3",
        telegram_enabled=True,
        telegram_chat_id="-100123",
        telegram_notify_interval_minutes=60,
        servers=[],
    )

    with patch.dict("os.environ", {"TELEGRAM_BOT_TOKEN": "abc:token"}):
        ok, detail = maybe_send_security_telegram(cfg, force=True)

    assert ok is True
    mock_send.assert_called_once()


@patch("skopos.telegram_notify.send_telegram_message")
def test_password_expiry_alert_when_expired(mock_send):
    import skopos.telegram_notify as tn

    mock_send.return_value = (True, "ok")
    tn._last_password_notify_utc = None

    cfg = AppConfig(
        db_path="./skopos.sqlite3",
        telegram_enabled=True,
        telegram_chat_id="-100123",
        servers=[],
    )

    with patch("skopos.auth_store.password_expires_in_days", return_value=-3), patch(
        "skopos.auth_store.password_expired", return_value=True
    ), patch("skopos.auth_store.password_expiring_soon", return_value=False), patch.dict(
        "os.environ", {"TELEGRAM_BOT_TOKEN": "abc:token"}
    ):
        ok, detail = maybe_send_password_expiry_telegram(cfg)

    assert ok is True
    mock_send.assert_called_once()
    sent_text = mock_send.call_args[0][2]
    assert "expired" in sent_text.lower()


@patch("skopos.telegram_notify.send_telegram_message")
def test_password_expiry_alert_skipped_when_healthy(mock_send):
    import skopos.telegram_notify as tn

    tn._last_password_notify_utc = None
    cfg = AppConfig(
        db_path="./skopos.sqlite3",
        telegram_enabled=True,
        telegram_chat_id="-100123",
        servers=[],
    )
    with patch("skopos.auth_store.password_expires_in_days", return_value=42), patch(
        "skopos.auth_store.password_expired", return_value=False
    ), patch("skopos.auth_store.password_expiring_soon", return_value=False):
        ok, detail = maybe_send_password_expiry_telegram(cfg)

    assert ok is False
    mock_send.assert_not_called()


# ── the poison-body failure mode, and the two fixes for it ───────────────────────────────────


@patch("skopos.telegram_notify.urllib.request.urlopen")
def test_html_refusal_falls_back_to_plain_text(mock_urlopen):
    """Telegram answers an unparseable body with a 400.

    Before the fallback, the caller advanced the notify cooldown only on success, so one such body
    was rebuilt and re-refused every interval — forever, and logged at DEBUG as "skipped". The
    retry has no `parse_mode`, so it cannot be refused for markup.
    """
    import json as _json

    calls = []

    def _urlopen(req, timeout=None):
        calls.append(_json.loads(req.data))
        resp = MagicMock()
        if "parse_mode" in calls[-1]:
            resp.read.return_value = b'{"ok": false, "description": "can\'t parse entities"}'
        else:
            resp.read.return_value = b'{"ok": true}'
        ctx = MagicMock()
        ctx.__enter__.return_value = resp
        return ctx

    mock_urlopen.side_effect = _urlopen

    ok, detail = send_telegram_message("token123", "999", "<b>unbalanced")
    assert ok is True, detail
    assert "plain-text fallback" in detail
    assert len(calls) == 2
    assert "parse_mode" in calls[0] and "parse_mode" not in calls[1]


@patch("skopos.telegram_notify.urllib.request.urlopen")
def test_both_attempts_failing_reports_both_reasons(mock_urlopen):
    resp = MagicMock()
    resp.read.return_value = b'{"ok": false, "description": "chat not found"}'
    mock_urlopen.return_value.__enter__.return_value = resp

    ok, detail = send_telegram_message("token123", "999", "hello")
    assert ok is False
    assert "chat not found" in detail
    assert "plain-text retry also failed" in detail


@patch("skopos.telegram_notify.urllib.request.urlopen")
def test_a_working_body_is_sent_once(mock_urlopen):
    """The fallback must not double-send a message Telegram accepted."""
    resp = MagicMock()
    resp.read.return_value = b'{"ok": true}'
    mock_urlopen.return_value.__enter__.return_value = resp

    ok, _ = send_telegram_message("token123", "999", "hello")
    assert ok is True
    assert mock_urlopen.call_count == 1


def test_the_benign_skip_is_a_sentinel_not_prose():
    """`auto_scan` distinguishes "nothing to report" from "could not deliver" by this value.

    Both used to be `(False, <some text>)` logged at DEBUG as "skipped", which is how a dead
    security channel can look healthy.
    """
    from skopos.telegram_notify import SKIP_NO_ALERTS

    assert SKIP_NO_ALERTS == "No actionable alerts"
    source = (Path(__file__).resolve().parents[1] / "skopos" / "security" / "auto_scan.py").read_text()
    assert "SKIP_NO_ALERTS" in source
    assert "FAILED to send" in source
    assert source.index("_log.warning") > 0
