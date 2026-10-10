"""Config defaults for security auto-scan."""

from __future__ import annotations

from pathlib import Path

import yaml

from skopos.config import DEFAULT_SECURITY_SCAN_INTERVAL_MINUTES, load_config


def test_security_scan_config_defaults(tmp_path):
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
    assert cfg.security_auto_scan is True
    assert cfg.security_scan_interval_minutes == DEFAULT_SECURITY_SCAN_INTERVAL_MINUTES
