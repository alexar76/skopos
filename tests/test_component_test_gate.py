"""A patch must survive the component's own tests, not just the probe that found the bug.

The loop's only gate was one MOMUS probe re-run. A probe asserts the single behaviour it was
written for — it is a regression test for one finding, and it was never a test suite. So a
patch could satisfy the probe, break everything else in the component, pass the gate, and
ship. Nothing in the loop ran the component's tests, on any host, ever.

These tests hold the new gate to both halves of its job: it must fail a build whose suite
fails, and it must not become a new way for repairs to stop for no reason.
"""

from __future__ import annotations

import pytest

from skopos.remediation.agent_executor import NodeDeployExecutor


class FakeDocker:
    """Records argv and replays scripted results, so the gate runs without Docker."""

    def __init__(self, results: dict[str, tuple[int, str, str]] | None = None):
        self.calls: list[list[str]] = []
        self.results = results or {}

    def __call__(self, argv: list[str], timeout: int) -> tuple[int, str, str]:
        self.calls.append(list(argv))
        for key, value in self.results.items():
            if key in " ".join(argv):
                return value
        return 0, "", ""

    def ran(self, fragment: str) -> bool:
        return any(fragment in " ".join(c) for c in self.calls)


def _executor(*, runner, require_tests=False) -> NodeDeployExecutor:
    return NodeDeployExecutor(
        conductor_pubkey="c", momus_pubkey="m", service_allowlist=["gaia"],
        dry_run=False, require_tests=require_tests, runner=runner, sleeper=lambda _s: None,
    )


_SPEC = {"test_target": "test", "test_paths": "/app/gaia/tests/test_a.py"}


# ── the suite fails ───────────────────────────────────────────────────────────────

def test_a_failing_suite_blocks_the_build_when_enforced():
    docker = FakeDocker({"pytest": (1, "1 failed, 40 passed", "")})
    ex = _executor(runner=docker, require_tests=True)

    record = ex._run_component_tests(_SPEC, "Dockerfile", ".", "gaia:momus-abc")

    assert record["ran"] is True
    assert record["passed"] is False
    assert record["blocked"] is True
    assert "own tests failed" in record["reason"]
    assert "1 failed" in record["summary"]


def test_a_failing_suite_is_reported_but_does_not_block_while_advisory():
    docker = FakeDocker({"pytest": (1, "1 failed, 40 passed", "")})
    ex = _executor(runner=docker, require_tests=False)

    record = ex._run_component_tests(_SPEC, "Dockerfile", ".", "gaia:momus-abc")

    assert record["passed"] is False
    assert record["blocked"] is False, "advisory mode must not stop repairs"
    assert record["enforced"] is False
    assert record["output"], "the failure must still be carried back to whoever reads it"


def test_the_failure_output_is_carried_back_for_the_next_attempt():
    docker = FakeDocker({"pytest": (1, "E   assert 3 == 4\n1 failed", "")})
    ex = _executor(runner=docker, require_tests=True)

    record = ex._run_component_tests(_SPEC, "Dockerfile", ".", "gaia:momus-abc")

    assert "assert 3 == 4" in record["output"]


# ── the suite passes ──────────────────────────────────────────────────────────────

def test_a_passing_suite_never_blocks():
    docker = FakeDocker({"pytest": (0, "41 passed", "")})
    for enforced in (True, False):
        ex = _executor(runner=docker, require_tests=enforced)
        record = ex._run_component_tests(_SPEC, "Dockerfile", ".", "gaia:momus-abc")
        assert record["passed"] is True
        assert record["blocked"] is False


# ── the suite is absent ───────────────────────────────────────────────────────────

def test_a_component_with_no_test_stage_says_so_instead_of_looking_green():
    # An absent gate that reports nothing is indistinguishable from a gate that passed.
    # The canary genuinely has no suite; that fact must be visible, not inferred.
    docker = FakeDocker()
    ex = _executor(runner=docker, require_tests=True)

    record = ex._run_component_tests({}, "Dockerfile", ".", "canary:momus-abc")

    assert record["ran"] is False
    assert "no test stage" in record["reason"]
    assert not docker.ran("pytest"), "nothing should have been run"


def test_a_missing_suite_does_not_block_a_component_that_never_had_one():
    docker = FakeDocker()
    ex = _executor(runner=docker, require_tests=True)
    record = ex._run_component_tests({}, "Dockerfile", ".", "canary:momus-abc")
    assert record["blocked"] is False


# ── the gate itself is broken ─────────────────────────────────────────────────────

def test_a_test_stage_that_will_not_build_is_reported_as_a_broken_gate():
    docker = FakeDocker({"--target test": (1, "", "unknown stage 'test'")})
    ex = _executor(runner=docker, require_tests=True)

    record = ex._run_component_tests(_SPEC, "Dockerfile", ".", "gaia:momus-abc")

    assert record["ran"] is False
    assert "failed to build" in record["reason"]
    assert "unknown stage" in record["stderr"]
    assert record["blocked"] is True, "an unbuildable gate must not be read as a pass"


# ── how it runs ───────────────────────────────────────────────────────────────────

def test_the_suite_runs_without_a_network():
    # A unit suite that needs the internet is not testing this patch, and a gate with
    # network access is a gate a patch can talk to.
    docker = FakeDocker({"pytest": (0, "ok", "")})
    ex = _executor(runner=docker, require_tests=True)
    ex._run_component_tests(_SPEC, "Dockerfile", ".", "gaia:momus-abc")

    run_call = next(c for c in docker.calls if "run" in c and "pytest" in " ".join(c))
    assert "--network" in run_call and "none" in run_call
    assert "--memory" in run_call


def test_only_the_declared_paths_are_run():
    spec = {"test_target": "test", "test_paths": "/app/gaia/tests/test_a.py /app/gaia/tests/test_b.py"}
    docker = FakeDocker({"pytest": (0, "ok", "")})
    ex = _executor(runner=docker, require_tests=True)
    ex._run_component_tests(spec, "Dockerfile", ".", "gaia:momus-abc")

    run_call = next(c for c in docker.calls if "pytest" in " ".join(c))
    assert run_call[-2:] == ["/app/gaia/tests/test_a.py", "/app/gaia/tests/test_b.py"]


def test_the_test_image_is_removed_afterwards():
    # These are built per commit; leaving them behind fills the host that runs the loop.
    docker = FakeDocker({"pytest": (0, "ok", "")})
    ex = _executor(runner=docker, require_tests=True)
    ex._run_component_tests(_SPEC, "Dockerfile", ".", "gaia:momus-abc")

    assert docker.ran("rmi -f gaia:momus-abc-tests") or docker.ran("rmi")


def test_the_test_image_never_takes_the_runtime_tag():
    docker = FakeDocker({"pytest": (0, "ok", "")})
    ex = _executor(runner=docker, require_tests=True)
    ex._run_component_tests(_SPEC, "Dockerfile", ".", "gaia:momus-abc")

    build = next(c for c in docker.calls if "build" in c)
    tag = build[build.index("-t") + 1]
    assert tag == "gaia:momus-abc-tests", "the gate must not overwrite the image being promoted"


# ── the recipe the loop actually ships with ───────────────────────────────────────

def test_gaia_declares_a_test_stage_and_avoids_the_live_suites():
    from skopos.remediation.recipes import DEFAULT_BUILD_RECIPES

    gaia = DEFAULT_BUILD_RECIPES["gaia"]
    assert gaia.get("test_target") == "test"
    paths = gaia.get("test_paths", "").split()
    assert paths, "gaia has 268 test files and must declare which ones gate a repair"
    assert not any("test_live_" in p for p in paths), (
        "the test container has no network; a live suite would fail for the wrong reason"
    )


def test_the_canary_declares_no_test_stage_because_it_has_no_tests():
    from skopos.remediation.recipes import DEFAULT_BUILD_RECIPES

    # Stating this in a test so that adding a canary suite later is a deliberate act,
    # and so nobody reads the absence as an oversight.
    assert "test_target" not in DEFAULT_BUILD_RECIPES["canary"]


# ── a verdict lowers the bar; it must not remove it ───────────────────────────────
#
# The dispatch policy's verdict branch was unreachable for as long as nothing wrote a
# verdict. The day one arrived it would silently have let a single model answer override
# the hub's three-sighting conservatism — a loosening nobody chose, arriving as a side
# effect of fixing something else.

from skopos.remediation.autopilot import (  # noqa: E402
    VERDICT_MIN_SCORE,
    VERDICT_SIGHTING_FLOOR,
    _independently_confirmed,
)


def _verdict(**over):
    v = {"verdict": "confirmed", "score": 0.9, "verifier_id": "metis",
         "verifier_pubkey": "pk-verifier"}
    v.update(over)
    return v


def test_a_confident_independent_verdict_counts():
    ok, note = _independently_confirmed({"scanner_pubkey": "pk-scanner",
                                         "verdicts": [_verdict()]})
    assert ok is True
    assert "metis" in note


def test_an_inconclusive_verdict_does_not_count():
    ok, _ = _independently_confirmed({"verdicts": [_verdict(verdict="inconclusive")]})
    assert ok is False


def test_a_low_confidence_confirmation_does_not_count():
    # The dangerous shape: it reads as evidence and is not. `inconclusive` at least admits it.
    ok, _ = _independently_confirmed({"verdicts": [_verdict(score=VERDICT_MIN_SCORE - 0.01)]})
    assert ok is False
    ok, _ = _independently_confirmed({"verdicts": [_verdict(score=VERDICT_MIN_SCORE)]})
    assert ok is True


def test_a_verdict_signed_by_the_scanner_is_not_independent():
    # MOMUS refuses to build such a verifier. This is the second place that cannot be
    # talked out of it, because the two run on different hosts and fail differently.
    ok, _ = _independently_confirmed({
        "scanner_pubkey": "pk-same",
        "verdicts": [_verdict(verifier_pubkey="pk-same")],
    })
    assert ok is False


def test_no_verdicts_at_all_is_simply_not_confirmed():
    assert _independently_confirmed({})[0] is False
    assert _independently_confirmed({"verdicts": []})[0] is False
    assert _independently_confirmed({"verdicts": [None, "nonsense"]})[0] is False


def test_a_malformed_score_is_ignored_rather_than_crashing_the_tick():
    assert _independently_confirmed({"verdicts": [_verdict(score="high")]})[0] is False
    assert _independently_confirmed({"verdicts": [_verdict(score=None)]})[0] is False


def test_the_floor_is_two_not_one():
    # One opinion is better evidence than one sighting. It is not better than three.
    assert VERDICT_SIGHTING_FLOOR == 2
