from __future__ import annotations

import pytest

from skopos.agent.redact import llm_include_auth_logs, sanitize_snapshot_dict
from skopos.config_paths import resolve_config_path
from skopos.shell_safe import (
    assert_safe_shell_word,
    custom_ssh_commands_allowed,
    validate_custom_ssh_command,
    validate_docker_name,
    validate_log_path,
)


def test_validate_log_path_rejects_injection():
    with pytest.raises(ValueError):
        validate_log_path("/var/log/nginx/access.log; rm -rf /")
    assert validate_log_path("/var/log/nginx/access.log") == "/var/log/nginx/access.log"


def test_validate_docker_name_rejects_shell_chars():
    with pytest.raises(ValueError):
        validate_docker_name("nginx;id")
    assert validate_docker_name("metis-nginx") == "metis-nginx"


def test_custom_ssh_commands_disabled_by_default(monkeypatch):
    monkeypatch.delenv("SKOPOS_ALLOW_CUSTOM_SSH_COMMANDS", raising=False)
    assert custom_ssh_commands_allowed() is False


def test_validate_custom_ssh_command_blocks_chaining():
    with pytest.raises(ValueError):
        validate_custom_ssh_command("tail -n 5 /var/log/nginx/access.log && id")


def test_resolve_config_path_blocks_traversal(tmp_path):
    root = tmp_path / "project"
    root.mkdir()
    allowed = root / "servers.yaml"
    allowed.write_text("db_path: ./skopos.sqlite3\nservers: []\n", encoding="utf-8")
    resolved = resolve_config_path("servers.yaml", root=root)
    assert resolved == allowed.resolve()
    with pytest.raises(ValueError):
        resolve_config_path("../../etc/passwd", root=root)


def test_sanitize_snapshot_dict_redacts_auth_logs(monkeypatch):
    monkeypatch.delenv("SKOPOS_LLM_INCLUDE_AUTH_LOGS", raising=False)
    data = {
        "server_name": "web-1",
        "failed_logins": ["Failed password for root"],
        "recent_logins": ["Accepted publickey"],
        "cpu_pct": 12.0,
    }
    cleaned = sanitize_snapshot_dict(data)
    assert "failed_logins" not in cleaned
    assert "recent_logins" not in cleaned
    assert cleaned["cpu_pct"] == 12.0


def test_sanitize_snapshot_dict_can_include_auth_logs(monkeypatch):
    monkeypatch.setenv("SKOPOS_LLM_INCLUDE_AUTH_LOGS", "1")
    assert llm_include_auth_logs() is True
    data = {"failed_logins": ["x"], "cpu_pct": 1.0}
    cleaned = sanitize_snapshot_dict(data)
    assert cleaned["failed_logins"] == ["x"]


def test_assert_safe_shell_word_rejects_newlines():
    with pytest.raises(ValueError):
        assert_safe_shell_word("foo\nbar", label="value")
