"""Documentation page must stay readable without dashboard password."""

from __future__ import annotations

import skopos.app_auth as app_auth


def test_require_dashboard_auth_skips_on_documentation_page(monkeypatch):
    monkeypatch.setenv("SKOPOS_DASHBOARD_PASSWORD", "MySecurePass42")
    monkeypatch.setattr(app_auth, "is_documentation_page", lambda: True)

    assert app_auth.require_dashboard_auth("en") is True
