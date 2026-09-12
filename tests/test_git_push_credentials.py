"""The push credential must not be readable by every user on the host.

`GitPusher._git`'s own docstring says a credential must not reach "the process list of anything
that can read /proc" — and the next branch put it there, as
`-c http.extraHeader=Authorization: token <token>` in **argv**. `/proc/<pid>/cmdline` is
world-readable, so any local account could read the token off a running `git push` with `ps`.

The same host's alerter unit states the rule plainly: "Credentials only, never argv: `ps` is
world-readable on this host."

git reads config from `GIT_CONFIG_COUNT` / `GIT_CONFIG_KEY_<n>` / `GIT_CONFIG_VALUE_<n>`
(git >= 2.31), so the token now travels in the environment. That is not secret from root — it is
`/proc/<pid>/environ`, readable by the same UID and root only — but it is no longer readable by
every user on the box, which is the whole difference.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from skopos.remediation.git_push import GitPusher, GitPushConfig  # noqa: E402

TOKEN = "s3cr3t-push-token-do-not-leak"


class _Recorder:
    """Stands in for the subprocess runner and records argv AND the env git would inherit."""

    def __init__(self) -> None:
        self.calls: list[tuple[list[str], dict[str, str]]] = []

    def __call__(self, argv, cwd=None, stdin=None):
        seen = {k: v for k, v in os.environ.items() if k.startswith("GIT_CONFIG")}
        self.calls.append((list(argv), seen))
        return 0, "", ""


def _pusher(**over) -> tuple[GitPusher, _Recorder]:
    cfg = GitPushConfig(**{"token": TOKEN, "ssh_key_path": "", **over}) \
        if _accepts(GitPushConfig, "token") else GitPushConfig()
    if not _accepts(GitPushConfig, "token"):          # pragma: no cover - config shape changed
        pytest.skip("GitPushConfig no longer carries a token field")
    rec = _Recorder()
    return GitPusher(cfg, runner=rec), rec


def _accepts(cls, field: str) -> bool:
    import dataclasses

    return any(f.name == field for f in dataclasses.fields(cls)) \
        if dataclasses.is_dataclass(cls) else False


def test_the_token_never_appears_in_argv():
    pusher, rec = _pusher()
    pusher._git("push", "origin", "HEAD")
    assert rec.calls, "the runner was not called"
    argv, _env = rec.calls[0]
    joined = " ".join(argv)
    assert TOKEN not in joined, f"token is readable via ps: {joined}"
    assert "extraHeader" not in joined, "the credential header is back in argv"


def test_the_token_reaches_git_through_the_environment():
    pusher, rec = _pusher()
    pusher._git("push", "origin", "HEAD")
    _argv, env = rec.calls[0]
    assert env.get("GIT_CONFIG_COUNT") == "1"
    assert env.get("GIT_CONFIG_KEY_0") == "http.extraHeader"
    assert env.get("GIT_CONFIG_VALUE_0") == f"Authorization: token {TOKEN}"


def test_the_environment_is_restored_after_the_call():
    """A leaked GIT_CONFIG_* would apply to every later subprocess in this process."""
    before = {k: v for k, v in os.environ.items() if k.startswith("GIT_CONFIG")}
    pusher, _rec = _pusher()
    pusher._git("status")
    after = {k: v for k, v in os.environ.items() if k.startswith("GIT_CONFIG")}
    assert after == before


def test_a_pre_existing_git_config_env_is_put_back_not_dropped():
    os.environ["GIT_CONFIG_COUNT"] = "7"
    try:
        pusher, _rec = _pusher()
        pusher._git("status")
        assert os.environ["GIT_CONFIG_COUNT"] == "7"
    finally:
        os.environ.pop("GIT_CONFIG_COUNT", None)


def test_ssh_key_path_still_wins_and_sets_no_token_env():
    """With an SSH key configured the HTTP token is irrelevant and must not be exported."""
    if not _accepts(GitPushConfig, "ssh_key_path"):    # pragma: no cover
        pytest.skip("GitPushConfig no longer carries ssh_key_path")
    cfg = GitPushConfig(token=TOKEN, ssh_key_path="/tmp/id_ed25519")
    rec = _Recorder()
    GitPusher(cfg, runner=rec)._git("push")
    argv, env = rec.calls[0]
    assert "core.sshCommand=" in " ".join(argv)
    assert not env, f"token env leaked on the SSH path: {sorted(env)}"
    assert TOKEN not in " ".join(argv)


def test_the_source_still_states_the_rule_it_now_obeys():
    source = (ROOT / "skopos" / "remediation" / "git_push.py").read_text(encoding="utf-8")
    assert "GIT_CONFIG_VALUE_0" in source
    # The old shape must not come back.
    assert 'f"http.extraHeader=Authorization: token {self.cfg.token}"' not in source
