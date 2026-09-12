from __future__ import annotations

import tempfile
from pathlib import Path

from skopos.config import load_config
from skopos.config_io import load_config_with_commands, save_config
from skopos.config_io import draft_server_from_form
from skopos.ssh_setup import build_ssh_copy_id_cmd, build_keygen_ed25519_cmd, resolve_key_path


def test_build_ssh_copy_id_cmd():
    cmd = build_ssh_copy_id_cmd(user="root", host="1.2.3.4", port=8443, public_key_path="~/.ssh/id_ed25519.pub")
    assert "ssh-copy-id" in cmd
    assert "-p 8443" in cmd
    assert "root@1.2.3.4" in cmd


def test_keygen_command():
    cmd = build_keygen_ed25519_cmd()
    assert "ssh-keygen" in cmd
    assert "ed25519" in cmd


def test_resolve_key_path_missing(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    info = resolve_key_path("~/.ssh/id_ed25519")
    assert info.exists is False


def test_save_and_load_roundtrip():
    with tempfile.TemporaryDirectory() as td:
        path = Path(td) / "servers.yaml"
        path.write_text(
            "db_path: ./skopos.sqlite3\nservers:\n  - name: test\n    source: ssh_nginx_access_log\n"
            "    ssh: {host: 10.0.0.1, port: 22, user: root, key_path: ~/.ssh/id_ed25519}\n"
            "    nginx: {access_log_path: /var/log/nginx/access.log}\n",
            encoding="utf-8",
        )
        cfg, cmds = load_config_with_commands(str(path))
        assert len(cfg.servers) == 1
        new_server = draft_server_from_form(
            name="metis",
            host="203.0.113.50",
            port=22,
            user="root",
            key_path="~/.ssh/id_ed25519",
            key_passphrase_env="SKOPOS_SSH_KEY_PASSPHRASE",
            access_log_path="",
            auto_discover_logs=False,
            auto_discover_docker_logs=True,
            docker_log_containers="metis-nginx",
        )
        from skopos.config import AppConfig

        new_cfg = AppConfig(
            db_path=cfg.db_path,
            geoip_mmdb_path=cfg.geoip_mmdb_path,
            poll_interval_seconds=cfg.poll_interval_seconds,
            batch_lines_per_server=cfg.batch_lines_per_server,
            servers=[cfg.servers[0], new_server],
        )
        save_config(
            str(path),
            new_cfg,
            ssh_commands={"test": [{"name": "Tail", "command": "tail -n 20 /var/log/nginx/access.log"}]},
        )
        reloaded, commands = load_config_with_commands(str(path))
        assert len(reloaded.servers) == 2
        assert commands["test"][0]["name"] == "Tail"
