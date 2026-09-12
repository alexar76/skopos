from __future__ import annotations

import json
from pathlib import Path

import pytest

from skopos.setup_state import (
    SetupStatus,
    dismiss_wizard,
    evaluate_setup,
    is_wizard_dismissed,
    reset_wizard_dismissed,
    suggest_wizard_step,
)


def test_suggest_wizard_step_no_server():
    status = SetupStatus(
        config_exists=False,
        config_valid=False,
        server_count=0,
        ssh_key_exists=False,
        password_set=False,
        ai_key_set=False,
        has_traffic=False,
        has_scan=False,
        wizard_dismissed=False,
    )
    assert suggest_wizard_step(status) == 1


def test_suggest_wizard_step_complete():
    status = SetupStatus(
        config_exists=True,
        config_valid=True,
        server_count=1,
        ssh_key_exists=True,
        password_set=True,
        ai_key_set=True,
        has_traffic=True,
        has_scan=True,
        wizard_dismissed=False,
    )
    assert suggest_wizard_step(status) == 6


def test_wizard_dismissed_file(tmp_path, monkeypatch):
    state_file = tmp_path / ".skopos_wizard.json"
    monkeypatch.setattr("skopos.setup_state._WIZARD_STATE_FILE", state_file)
    assert is_wizard_dismissed() is False
    dismiss_wizard()
    assert is_wizard_dismissed() is True
    data = json.loads(state_file.read_text(encoding="utf-8"))
    assert data["dismissed"] is True
    reset_wizard_dismissed()
    assert is_wizard_dismissed() is False


def test_evaluate_setup_with_valid_config(tmp_path, monkeypatch):
    cfg_path = tmp_path / "servers.yaml"
    cfg_path.write_text(
        "db_path: ./skopos.sqlite3\nservers:\n"
        "  - name: web-1\n    source: ssh_nginx_access_log\n"
        "    ssh: {host: 203.0.113.1, port: 22, user: stats, key_path: ~/.ssh/id_ed25519}\n"
        "    nginx: {access_log_path: /var/log/nginx/access.log}\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("HOME", str(tmp_path))
    status = evaluate_setup(str(cfg_path), agent_path="./agent.example.yaml")
    assert status.config_valid is True
    assert status.server_count == 1
