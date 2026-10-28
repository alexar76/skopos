"""SKOPOS remediation pins every SSH remote's host key; only a loopback Gitea may skip the check,
and only when the operator says so.

The remote (SKOPOS_GIT_REPO_URL) is configurable, so `StrictHostKeyChecking=no` for every host let
anyone on the path to a remote Gitea take the deploy-key push (CWE-295, the class Vulnetix found in
skopos-fleet's SSH client). A single-label container name stayed unchecked after that fix, and it
resolves on a shared docker network (Vulnetix GCVE-110-VULN-PYPI-2026-000639).
"""

from __future__ import annotations

import pytest
from skopos.remediation.git_push import skip_host_key_check, ssh_remote_is_loopback


@pytest.mark.parametrize("url", [
    "ssh://git@localhost:2222/alexar76/aicom.git",
    "ssh://git@127.0.0.1:22/a/b.git",
    "ssh://git@[::1]:22/a/b.git",
])
def test_loopback_remotes(url):
    assert ssh_remote_is_loopback(url)


@pytest.mark.parametrize("url", [
    "git@gitea:alexar76/aicom.git",
    "ssh://git@gitea:22/alexar76/aicom.git",
    "ssh://git@git.example.com:2222/alexar76/aicom.git",
    "git@github.com:alexar76/aicom.git",
    "ssh://git@203.0.113.7/a/b.git",
    "ssh://git@10.0.0.5/a/b.git",
    "",
])
def test_every_other_remote_is_not_loopback(url):
    assert not ssh_remote_is_loopback(url)


def test_skipping_needs_the_setting_and_a_loopback_remote(monkeypatch):
    monkeypatch.delenv("SKOPOS_GIT_SKIP_HOST_KEY_LOOPBACK", raising=False)
    assert not skip_host_key_check("ssh://git@127.0.0.1:22/a/b.git")
    monkeypatch.setenv("SKOPOS_GIT_SKIP_HOST_KEY_LOOPBACK", "1")
    assert skip_host_key_check("ssh://git@127.0.0.1:22/a/b.git")
    assert not skip_host_key_check("git@gitea:alexar76/aicom.git")
    assert not skip_host_key_check("git@git.example.com:a/b.git")


def _ssh_command(monkeypatch, tmp_path, url):
    from skopos.remediation import git_push

    monkeypatch.setenv("SKOPOS_KNOWN_HOSTS", str(tmp_path / "kh"))
    seen = {}
    pusher = git_push.GitPusher.__new__(git_push.GitPusher)
    pusher.cfg = git_push.GitPushConfig(repo_url=url, ssh_key_path="/k")
    monkeypatch.setattr(pusher, "_run", lambda argv, cwd, stdin: seen.setdefault("argv", argv) or (0, "", ""),
                        raising=False)
    pusher._git("status")
    return next(a for a in seen["argv"] if a.startswith("core.sshCommand="))


@pytest.mark.parametrize("url", ["git@git.example.com:a/b.git", "git@gitea:alexar76/aicom.git",
                                 "ssh://git@127.0.0.1:22/a/b.git"])
def test_the_ssh_command_pins_every_remote_by_default(tmp_path, monkeypatch, url):
    monkeypatch.delenv("SKOPOS_GIT_SKIP_HOST_KEY_LOOPBACK", raising=False)
    cmd = _ssh_command(monkeypatch, tmp_path, url)
    assert "StrictHostKeyChecking=accept-new" in cmd and str(tmp_path / "kh") in cmd
    assert "StrictHostKeyChecking=no" not in cmd


def test_the_setting_unchecks_only_a_loopback_gitea(tmp_path, monkeypatch):
    monkeypatch.setenv("SKOPOS_GIT_SKIP_HOST_KEY_LOOPBACK", "1")
    assert "StrictHostKeyChecking=no" in _ssh_command(monkeypatch, tmp_path, "ssh://git@127.0.0.1:22/a/b.git")
    assert "StrictHostKeyChecking=no" not in _ssh_command(monkeypatch, tmp_path, "git@gitea:alexar76/aicom.git")
