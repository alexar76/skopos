"""A shared guessing budget delays submitted attempts without denying the operator."""

from __future__ import annotations

from contextlib import nullcontext
from types import SimpleNamespace

import pytest

from skopos import app_auth, auth_store, themes


class Stop(Exception):
    pass


class Rerun(Exception):
    pass


class SessionState(dict):
    def __getattr__(self, key):
        return self[key]

    def __setattr__(self, key, value):
        self[key] = value


class LoginUI:
    def __init__(self):
        self.session_state = SessionState()
        self.password = "CorrectOperator9"
        self.submitted = True
        self.form_rendered = False
        self.messages = []

    def markdown(self, *args, **kwargs):
        pass

    caption = markdown

    def info(self, message):
        self.messages.append(message)

    error = info
    warning = info

    def expander(self, *args, **kwargs):
        return nullcontext()

    def form(self, *args, **kwargs):
        self.form_rendered = True
        return nullcontext()

    def text_input(self, *args, **kwargs):
        return self.password

    def form_submit_button(self, *args, **kwargs):
        return self.submitted

    def stop(self):
        raise Stop()

    def rerun(self):
        raise Rerun()


class Clock:
    def __init__(self):
        self.wall = 1_000_000.0
        self.monotonic = 100.0
        self.sleeps = []
        self.during_wait = lambda: None

    def sleep(self, seconds):
        # Short/interrupted waits and a failure each second must not extend the
        # admitted attempt. No real sleep or network service is used in these tests.
        step = min(seconds, 1)
        self.sleeps.append(step)
        self.monotonic += step
        self.wall += step
        self.during_wait()


@pytest.fixture
def login(tmp_path, monkeypatch):
    db = str(tmp_path / "auth.sqlite")
    clock, ui = Clock(), LoginUI()
    ip = "192.0.2.200"
    monkeypatch.setattr(auth_store, "time", SimpleNamespace(
        time=lambda: clock.wall, monotonic=lambda: clock.monotonic))
    monkeypatch.setattr(app_auth, "time", SimpleNamespace(
        time=lambda: clock.wall, monotonic=lambda: clock.monotonic, sleep=clock.sleep))
    monkeypatch.setenv("SKOPOS_LOGIN_GLOBAL_MAX_ATTEMPTS", "30")
    monkeypatch.setenv("SKOPOS_LOGIN_MAX_ATTEMPTS", "5")
    monkeypatch.setenv("SKOPOS_LOGIN_LOCKOUT_SECONDS", "300")
    monkeypatch.setenv("SKOPOS_LOGIN_KNOWN_DAYS", "30")
    auth_store.set_dashboard_password(ui.password, db_target=db)
    monkeypatch.setattr(app_auth, "st", ui)
    monkeypatch.setattr(app_auth, "_client_ip", lambda: ip)
    monkeypatch.setattr(app_auth, "is_documentation_page", lambda: False)
    monkeypatch.setattr(app_auth, "dashboard_password_configured", lambda: True)
    monkeypatch.setattr(app_auth, "_restore_session_from_cookie", lambda: None)
    monkeypatch.setattr(app_auth, "configured_password_meets_policy", lambda: (True, []))
    monkeypatch.setattr(themes, "get_active_theme", lambda: None)
    monkeypatch.setattr(themes, "build_login_gate_css", lambda theme: "")
    monkeypatch.setattr(app_auth, "login_pace_seconds",
                        lambda addr: auth_store.login_pace_seconds(addr, db_target=db))
    monkeypatch.setattr(app_auth, "login_lockout_remaining_seconds",
                        lambda addr: auth_store.login_lockout_remaining_seconds(addr, db_target=db))
    monkeypatch.setattr(app_auth, "clear_login_lockout",
                        lambda addr: auth_store.clear_login_lockout(addr, db_target=db))
    monkeypatch.setattr(app_auth, "register_failed_login",
                        lambda addr: auth_store.register_failed_login(addr, db_target=db))
    verified = []

    def verify(password):
        verified.append(clock.monotonic)
        return auth_store.verify_dashboard_password(password, db_target=db)

    monkeypatch.setattr(app_auth, "verify_dashboard_password", verify)

    def flood(count=37):
        for n in range(count):
            auth_store.register_failed_login(f"198.51.100.{n}", db_target=db)

    return SimpleNamespace(db=db, clock=clock, ui=ui, ip=ip, flood=flood, verified=verified)


def test_new_operator_can_submit_and_log_in_despite_continuing_other_failures(login):
    login.flood()
    assert auth_store.login_pace_seconds(login.ip, db_target=login.db) == 60
    login.clock.during_wait = lambda: auth_store.register_failed_login(
        "198.51.100.99", db_target=login.db)

    with pytest.raises(Rerun):
        app_auth.require_dashboard_auth("en")

    assert login.ui.form_rendered
    assert sum(login.clock.sleeps) == 60
    assert login.verified == [160]
    assert login.ui.session_state["_skopos_auth_ok"] is True
    assert login.ui.session_state["_skopos_persist_cookie"] is True
    # The attack is still active: an unrelated new address faces a fresh delay.
    # It did not postpone the operator's admitted password check.
    assert auth_store.login_pace_seconds("192.0.2.201", db_target=login.db) == 60


def test_shared_failures_leave_form_visible_without_waiting_on_page_load(login):
    login.flood()
    login.ui.submitted = False
    with pytest.raises(Stop):
        app_auth.require_dashboard_auth("en")
    assert login.ui.form_rendered
    assert login.clock.sleeps == []
    assert login.verified == []


def test_wrong_password_is_delayed_and_still_counts_against_own_budget(login):
    login.flood()
    login.ui.password = "wrong"
    for attempt in range(5):
        with pytest.raises(Stop):
            app_auth.require_dashboard_auth("en")
        assert len(login.verified) == attempt + 1
    assert auth_store.login_lockout_remaining_seconds(login.ip, db_target=login.db) > 0
    assert login.ui.session_state.get("_skopos_auth_ok") is not True
    previous_checks = list(login.verified)
    with pytest.raises(Stop):
        app_auth.require_dashboard_auth("en")
    assert login.verified == previous_checks
    assert login.clock.sleeps  # Guessing beyond the shared budget incurs real delay.


def test_same_address_lockout_is_rechecked_after_delay(login):
    login.flood()
    triggered = False

    def exhaust_own_address():
        nonlocal triggered
        if not triggered:
            triggered = True
            for _ in range(5):
                auth_store.register_failed_login(login.ip, db_target=login.db)

    login.clock.during_wait = exhaust_own_address
    with pytest.raises(Stop):
        app_auth.require_dashboard_auth("en")
    assert login.ui.form_rendered
    assert login.verified == []
    assert auth_store.login_lockout_remaining_seconds(login.ip, db_target=login.db) > 0


def test_recent_successful_address_keeps_pacing_exemption(login):
    auth_store.clear_login_lockout(login.ip, db_target=login.db)
    login.flood()
    with pytest.raises(Rerun):
        app_auth.require_dashboard_auth("en")
    assert login.clock.sleeps == []
    assert login.verified == [100]
