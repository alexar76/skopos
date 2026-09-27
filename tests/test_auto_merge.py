"""Merging a machine-authored fix into the default branch — the one exception, and its guards.

Every other path in `git_push` refuses `main` on principle, and that refusal is what keeps a
stolen conductor credential a nuisance rather than an incident: the worst it can do is create a
branch nobody merges. Turning this on changes that sentence, so the switch is off by default
and the path around it is written to be hard to reach by accident.

These tests hold the guards, not the happy path. The happy path is one `git merge --no-ff`; the
value is entirely in what it refuses.
"""

from __future__ import annotations

import pytest

from skopos.remediation.git_push import GitPushConfig, GitPusher


class FakeGit:
    """Records argv and replays scripted results, so no repository is touched."""

    def __init__(self, results: dict[str, tuple[int, str, str]] | None = None):
        self.calls: list[list[str]] = []
        self.results = results or {}

    def __call__(self, argv, cwd=None, stdin=None):
        self.calls.append(list(argv))
        for key, value in self.results.items():
            if key in " ".join(argv):
                return value
        return 0, "", ""

    def ran(self, fragment: str) -> bool:
        return any(fragment in " ".join(c) for c in self.calls)


def _pusher(*, auto_merge: bool, results=None, tmp_path=None) -> GitPusher:
    cfg = GitPushConfig(
        repo_url="ssh://git@localhost:2222/o/r.git",
        work_root=str(tmp_path) if tmp_path else "/tmp/skopos-test",
        auto_merge=auto_merge,
    )
    return GitPusher(cfg, runner=FakeGit(results or {}))


# ── off by default ────────────────────────────────────────────────────────────────

def test_it_is_off_unless_explicitly_enabled(tmp_path):
    p = _pusher(auto_merge=False, tmp_path=tmp_path)
    r = p.merge_to_main(finding_id="mom-1", branch="momus/fix-mom-1", component="praxis")

    assert r.ok is False
    assert "auto-merge is off" in r.error
    assert not p._run.ran("merge"), "nothing may touch git while the switch is off"


def test_the_default_config_has_it_off():
    # Read from the dataclass rather than the environment: a default that depends on what
    # happens to be exported is not a default.
    assert GitPushConfig().auto_merge is False


def test_the_environment_switch_is_explicit(monkeypatch):
    monkeypatch.delenv("SKOPOS_EXPERIMENTAL_AUTO_MERGE", raising=False)
    assert GitPushConfig.from_env().auto_merge is False

    for truthy in ("1", "true", "yes", "on", "ON"):
        monkeypatch.setenv("SKOPOS_EXPERIMENTAL_AUTO_MERGE", truthy)
        assert GitPushConfig.from_env().auto_merge is True

    for falsy in ("0", "false", "no", "off", ""):
        monkeypatch.setenv("SKOPOS_EXPERIMENTAL_AUTO_MERGE", falsy)
        assert GitPushConfig.from_env().auto_merge is False


# ── what it refuses even when on ──────────────────────────────────────────────────

def test_it_refuses_a_branch_that_is_not_a_fix_branch(tmp_path):
    # So a wrong branch name computed anywhere upstream cannot aim this at a person's work.
    p = _pusher(auto_merge=True, tmp_path=tmp_path)
    for branch in ("main", "master", "feature/mine", "", "momus-fix-mom-1"):
        r = p.merge_to_main(finding_id="mom-1", branch=branch, component="praxis")
        assert r.ok is False
        assert "not a fix branch" in r.error or "auto-merge is off" in r.error
    assert not p._run.ran("merge")


def test_it_refuses_an_unsafe_finding_id(tmp_path):
    p = _pusher(auto_merge=True, tmp_path=tmp_path)
    r = p.merge_to_main(finding_id="../../etc", branch="momus/fix-x", component="praxis")
    assert r.ok is False
    assert "unsafe" in r.error


def test_it_refuses_when_no_repository_is_configured(tmp_path):
    cfg = GitPushConfig(repo_url="", work_root=str(tmp_path), auto_merge=True)
    p = GitPusher(cfg, runner=FakeGit())
    r = p.merge_to_main(finding_id="mom-1", branch="momus/fix-mom-1", component="praxis")
    assert r.ok is False and "REPO_URL" in r.error


# ── how it merges ─────────────────────────────────────────────────────────────────

def test_it_merges_without_fast_forward_so_the_result_is_revertible(tmp_path):
    p = _pusher(auto_merge=True, tmp_path=tmp_path,
                results={"rev-parse HEAD": (0, "abc123\n", "")})
    r = p.merge_to_main(finding_id="mom-1", branch="momus/fix-mom-1", component="praxis",
                        summary="import the canonical form")

    assert r.ok is True
    merge = next(c for c in p._run.calls if "merge" in c)
    assert "--no-ff" in merge, "a fast-forward leaves nothing to revert"
    assert r.details.get("revert", "").startswith("git revert -m 1")


def test_the_merge_message_names_the_finding_and_the_way_back(tmp_path):
    p = _pusher(auto_merge=True, tmp_path=tmp_path,
                results={"rev-parse HEAD": (0, "abc123\n", "")})
    p.merge_to_main(finding_id="mom-1", branch="momus/fix-mom-1", component="praxis")

    merge = next(c for c in p._run.calls if "merge" in c)
    message = merge[merge.index("-m") + 1]
    assert "mom-1" in message
    assert "git revert -m 1" in message
    assert "SKOPOS_EXPERIMENTAL_AUTO_MERGE" in message, "the record should say what enabled it"


def test_it_never_force_pushes(tmp_path):
    """Narrowly about PUSHES.

    A first pass at this test forbade `+refs` anywhere and failed on the mirror clone's own
    `+refs/heads/*:refs/remotes/origin/*` — which is the standard refspec for a local
    remote-tracking ref and forces nothing on the server. Asserting against every git call
    catches the wrong thing and teaches the next reader to loosen the guard rather than the
    test.
    """
    p = _pusher(auto_merge=True, tmp_path=tmp_path,
                results={"rev-parse HEAD": (0, "abc123\n", "")})
    p.merge_to_main(finding_id="mom-1", branch="momus/fix-mom-1", component="praxis")

    pushes = [c for c in p._run.calls if "push" in c]
    assert pushes, "precondition: it pushed something"
    for call in pushes:
        joined = " ".join(call)
        assert "--force" not in joined
        assert "-f" not in call
        assert "+refs" not in joined, "a leading + on a push refspec IS a force"


# ── when it cannot ────────────────────────────────────────────────────────────────

def test_a_conflict_aborts_and_leaves_the_default_branch_untouched(tmp_path):
    # main moved under the fix. A machine picking a side there is the thing nobody asked for.
    p = _pusher(auto_merge=True, tmp_path=tmp_path,
                results={"merge --no-ff": (1, "", "CONFLICT (content): praxis/praxis.py")})
    r = p.merge_to_main(finding_id="mom-1", branch="momus/fix-mom-1", component="praxis")

    assert r.ok is False
    assert "conflicted" in r.error and "left untouched" in r.error
    assert p._run.ran("merge --abort")
    assert not p._run.ran("push origin HEAD:refs/heads/main")


def test_a_server_refusal_is_reported_not_worked_around(tmp_path):
    """The expected outcome on this deployment.

    The conductor pushes with a deploy key and the repository's `main` protection excludes
    deploy keys, so the server says no. That is a second, independent policy — the right
    response is to report it, never to reach for another credential.
    """
    p = _pusher(auto_merge=True, tmp_path=tmp_path,
                results={"rev-parse HEAD": (0, "abc123\n", ""),
                         "push origin HEAD:refs/heads/main":
                             (1, "", "remote: deploy key not allowed on protected branch")})
    r = p.merge_to_main(finding_id="mom-1", branch="momus/fix-mom-1", component="praxis")

    assert r.ok is False
    assert "refused" in r.error and "deploy key" in r.error
    assert r.commit_sha == "abc123", "the merge happened locally; only the push was refused"


def test_a_failed_fetch_does_not_merge_anything(tmp_path):
    p = _pusher(auto_merge=True, tmp_path=tmp_path,
                results={"fetch origin": (1, "", "could not read from remote")})
    r = p.merge_to_main(finding_id="mom-1", branch="momus/fix-mom-1", component="praxis")

    assert r.ok is False
    assert not p._run.ran("merge --no-ff")


# ── the ordinary paths must be unaffected ─────────────────────────────────────────

def test_the_branch_push_still_refuses_the_default_branch(tmp_path):
    # The exception is the merge path and only the merge path.
    p = _pusher(auto_merge=True, tmp_path=tmp_path)
    ok, err = p._push("/tmp/wt", "main")
    assert ok is False and "refusing to push" in err
