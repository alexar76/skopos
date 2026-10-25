"""SKOPOS remediation pushes with host keys unchecked only for a remote on this host.

The remote (SKOPOS_GIT_REPO_URL) is configurable, so `StrictHostKeyChecking=no` for every host
let anyone on the path to a remote Gitea take the deploy-key push (CWE-295, the class Vulnetix
found in skopos-fleet's SSH client).
"""

from __future__ import annotations

import pytest
from skopos.remediation.git_push import ssh_remote_is_local


@pytest.mark.parametrize("url", [
    "ssh://git@localhost:2222/alexar76/aicom.git",
    "ssh://git@127.0.0.1:22/a/b.git",
    "ssh://git@[::1]:22/a/b.git",
    "git@gitea:alexar76/aicom.git",
    "ssh://git@gitea:22/alexar76/aicom.git",
])
def test_local_remotes(url):
    assert ssh_remote_is_local(url)


@pytest.mark.parametrize("url", [
    "ssh://git@git.example.com:2222/alexar76/aicom.git",
    "git@github.com:alexar76/aicom.git",
    "ssh://git@203.0.113.7/a/b.git",
    "ssh://git@10.0.0.5/a/b.git",
    "",
])
def test_other_remotes_are_pinned(url):
    assert not ssh_remote_is_local(url)


def test_the_ssh_command_pins_a_remote_host(tmp_path, monkeypatch):
    from skopos.remediation import git_push

    monkeypatch.setenv("SKOPOS_KNOWN_HOSTS", str(tmp_path / "kh"))
    seen = {}
    pusher = git_push.GitPusher.__new__(git_push.GitPusher)
    pusher.cfg = git_push.GitPushConfig(repo_url="git@git.example.com:a/b.git", ssh_key_path="/k")
    monkeypatch.setattr(pusher, "_run", lambda argv, cwd, stdin: seen.setdefault("argv", argv) or (0, "", ""),
                        raising=False)
    pusher._git("status")
    cmd = next(a for a in seen["argv"] if a.startswith("core.sshCommand="))
    assert "StrictHostKeyChecking=accept-new" in cmd and str(tmp_path / "kh") in cmd
    assert "StrictHostKeyChecking=no" not in cmd
