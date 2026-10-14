"""The A2A wire observer — SKOPOS's view of agent↔agent traffic."""

from __future__ import annotations

import httpx
import pytest

from skopos.remediation.a2a_observer import A2AEvent, A2AObserver, scrub


def test_scrub_bounds_and_redacts():
    assert len(scrub("x" * 500)) <= 240
    assert "<redacted>" in scrub("Authorization: Bearer sk-abc123")
    assert "\x1b" not in scrub("bad\x1b[31mescape")          # terminal escape stripped
    assert "\x00" not in scrub("nul\x00byte")


def test_records_inbound_and_outbound(tmp_path):
    obs = A2AObserver(str(tmp_path))
    obs.record_inbound(
        {"skill": "remediate", "from_agent": "momus", "task_id": "t1",
         "input": {"ticket": {"finding_id": "mom-1", "component": "oracle-family"}},
         "message": "confirmed high finding"},
        state="working")
    obs.record_outbound(peer="momus", skill="retest", finding_id="mom-1", latency_ms=120,
                        summary="gate: fixed=True", artifacts=["fix-verdict"])
    rows = obs.recent(10)
    assert len(rows) == 2
    dirs = {r["direction"] for r in rows}
    assert dirs == {"in", "out"}
    out = next(r for r in rows if r["direction"] == "out")
    assert out["peer"] == "momus" and out["skill"] == "retest" and out["artifacts"] == ["fix-verdict"]


def test_rejected_inbound_marked_not_ok(tmp_path):
    obs = A2AObserver(str(tmp_path))
    obs.record_inbound({"skill": "deploy", "from_agent": "stranger"}, state="rejected",
                       note="unsupported skill")
    row = obs.recent(1)[0]
    assert row["ok"] is False and row["state"] == "rejected"


def test_stats_and_filters(tmp_path):
    obs = A2AObserver(str(tmp_path))
    obs.record(A2AEvent(direction="out", peer="momus", skill="retest", latency_ms=100))
    obs.record(A2AEvent(direction="out", peer="momus", skill="retest", latency_ms=300))
    obs.record(A2AEvent(direction="in", peer="momus", skill="remediate"))
    obs.record(A2AEvent(direction="in", peer="factory", skill="remediate", ok=False, state="failed"))
    s = obs.stats()
    assert s["total"] == 4
    assert s["by_skill"]["retest"] == 2 and s["by_peer"]["momus"] == 3
    assert s["by_direction"]["out"] == 2 and s["rejected"] == 1
    assert s["avg_latency_ms"] == 200.0
    assert len(obs.recent(10, skill="retest")) == 2
    assert len(obs.recent(10, peer="factory")) == 1


def test_survives_restart(tmp_path):
    A2AObserver(str(tmp_path)).record(A2AEvent(direction="in", peer="momus", skill="remediate"))
    assert A2AObserver(str(tmp_path)).stats()["total"] == 1


def test_ui_rows_are_display_ready(tmp_path):
    from skopos.ui_a2a import event_rows
    obs = A2AObserver(str(tmp_path))
    obs.record_outbound(peer="momus", skill="retest", finding_id="mom-abcdef1234567890",
                        latency_ms=42, summary="gate: fixed=True")
    rows = event_rows(obs)
    assert rows and rows[0]["direction"].startswith("⬆")
    assert rows[0]["finding_id"] == "mom-abcdef1234567"[:16]


# ── the ingress records what it accepts and refuses ──────────────────────────
@pytest.fixture
def ingress(tmp_path, monkeypatch):
    monkeypatch.setenv("SKOPOS_REMEDIATION_DIR", str(tmp_path / "rem"))
    monkeypatch.setenv("SKOPOS_CONDUCTOR_KEY_PATH", str(tmp_path / "rem" / "cond.key"))
    monkeypatch.setenv("SKOPOS_REMEDIATION_DRY_RUN", "1")
    from skopos.remediation.a2a_ingress import build_app
    from skopos.remediation.conductor import Conductor, RemediationConfig
    conductor = Conductor(RemediationConfig.from_env())
    app = build_app(conductor)
    return httpx.AsyncClient(transport=httpx.ASGITransport(app=app),
                             base_url="http://skopos.local"), conductor


@pytest.mark.asyncio
async def test_ingress_logs_rejected_skill(ingress):
    client, conductor = ingress
    async with client as c:
        r = await c.post("/a2a/tasks", json={"skill": "deploy", "from_agent": "momus"})
        assert r.json()["state"] == "rejected"
        events = (await c.get("/a2a/events")).json()
        assert events["stats"]["total"] >= 1
        assert events["events"][0]["ok"] is False


@pytest.mark.asyncio
async def test_ingress_exposes_agent_card_with_conductor_key(ingress):
    client, conductor = ingress
    async with client as c:
        card = (await c.get("/.well-known/agent-card.json")).json()
        assert card["name"] == "SKOPOS"
        assert any(s["id"] == "remediate" for s in card["skills"])
        assert card["conductorPublicKey"] == conductor.conductor_pubkey
