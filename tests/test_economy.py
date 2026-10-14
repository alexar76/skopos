"""Tests for optional AIMarket economy integration."""

from __future__ import annotations

import json
import os
from unittest.mock import patch

import pytest

from skopos.economy.capabilities import CAPABILITY_BY_ID
from skopos.economy.config import EconomyConfig, load_economy_config
from skopos.economy.invoke import InvokeError, dispatch_invoke
from skopos.economy.manifest import build_supply_manifest, build_v2_manifest, build_well_known


@pytest.fixture
def eco_cfg(tmp_path, monkeypatch):
    cfg_file = tmp_path / "servers.yaml"
    cfg_file.write_text("servers: []\ndb_path: ./test.sqlite3\n", encoding="utf-8")
    monkeypatch.setenv("SKOPOS_AIMARKET_ENABLED", "1")
    monkeypatch.setenv("SKOPOS_AIMARKET_PUBLIC_URL", "https://skopos.test")
    monkeypatch.setenv("SKOPOS_CONFIG_PATH", str(cfg_file))
    monkeypatch.setenv("SKOPOS_SIGNING_KEY_PATH", str(tmp_path / "aimarket_signing_key"))
    from skopos.economy import signing

    signing._signer = None
    yield load_economy_config()
    signing._signer = None


def test_load_economy_disabled_by_default(monkeypatch):
    monkeypatch.delenv("SKOPOS_AIMARKET_ENABLED", raising=False)
    cfg = load_economy_config()
    assert cfg.enabled is False


def test_well_known_manifest(eco_cfg: EconomyConfig):
    wk = build_well_known(eco_cfg)
    assert wk["manifest_url"].endswith("/ai-market/v2/manifest")
    assert "v2" in wk["protocol_versions"]
    assert wk["capabilities_count"] == len(CAPABILITY_BY_ID)
    assert wk["signer_public_key"]
    assert wk["hub_url"] == "https://skopos.test"


def test_v2_manifest_lists_capabilities(eco_cfg: EconomyConfig):
    import base64

    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

    from skopos.economy.signing import get_signer

    manifest = build_v2_manifest(eco_cfg)
    assert manifest["capabilities_count"] == len(CAPABILITY_BY_ID)
    assert manifest["local_capabilities"] == len(CAPABILITY_BY_ID)
    assert manifest["tools"][0]["invoke_url"] == "https://skopos.test/aimarket/invoke"
    assert manifest["tools"][0]["source_hub"] == "https://skopos.test"
    sig = manifest["signature"]
    assert sig["algorithm"] == "ed25519"
    assert sig["public_key"] == build_well_known(eco_cfg)["signer_public_key"]
    canonical = get_signer().manifest_canonical(manifest)
    Ed25519PublicKey.from_public_bytes(base64.b64decode(sig["public_key"])).verify(
        base64.b64decode(sig["value"]), canonical.encode()
    )


def test_supply_manifest_one_per_capability(eco_cfg: EconomyConfig):
    items = build_supply_manifest(eco_cfg)
    assert len(items) == len(CAPABILITY_BY_ID)
    assert items[0]["publisher_id"] == eco_cfg.publisher_id


def test_dispatch_fleet_status(eco_cfg: EconomyConfig):
    # The handler calls build_fleet_status, not build_status — patching the latter replaced a
    # function nobody invokes, so the test exercised the real (empty) path and asserted 42 against 0.
    # A patch that silently misses its target is worse than no patch: it reports a failure in code
    # that is correct, and it would have kept passing if the handler had actually broken.
    with patch(
        "skopos.public_status.build_fleet_status",
        return_value={"ok": True, "requests_total": 42},
    ):
        out = dispatch_invoke(
            {"capability_id": "skopos.fleet.status@v1", "input": {}},
            cfg=eco_cfg,
        )
    assert out["result"]["requests_total"] == 42


def test_dispatch_unknown_capability(eco_cfg: EconomyConfig):
    with pytest.raises(InvokeError) as exc:
        dispatch_invoke({"capability_id": "unknown@v1", "input": {}}, cfg=eco_cfg)
    assert exc.value.status == 404


def test_dispatch_disabled():
    cfg = EconomyConfig(
        enabled=False,
        public_base_url="http://localhost",
        product_id="prod-skopos",
        publisher_id="skopos",
        invoke_path="/aimarket/invoke",
        api_key=None,
        hub_url=None,
        auto_register=False,
        publish_token=None,
        agent_yaml_path="./agent.yaml",
        config_path="./servers.yaml",
    )
    with pytest.raises(InvokeError) as exc:
        dispatch_invoke({"capability_id": "skopos.fleet.status@v1"}, cfg=cfg)
    assert exc.value.status == 503


# ── The unpaid door ─────────────────────────────────────────────────────────────
# An unpaid caller used to get 401 "unauthorized", which says the wrong thing: it is not
# that we do not know them, it is that this capability is sold. A federation hub reads an
# unpaid invoke's answer as evidence the door is real, and 401 is not that evidence — which
# is why SKOPOS sat pending at modelmarket.dev while its own catalogue said it was for sale.


def test_an_unpaid_caller_is_quoted_a_price(eco_cfg: EconomyConfig):
    from skopos.economy.payments import payment_required_body

    body = payment_required_body("skopos.fleet.status@v1", eco_cfg)
    assert body["error"] == "payment_required"
    assert body["needed"] == CAPABILITY_BY_ID["skopos.fleet.status@v1"].price_per_call_usd
    assert body["capability_id"] == "skopos.fleet.status@v1"
    rails = {way["rail"] for way in body["payment_ways"]}
    assert "api-key" in rails


def test_the_quote_never_promises_a_settlement_we_cannot_check(eco_cfg: EconomyConfig):
    """No x402 `accepts`: SKOPOS verifies no chain, and an unverifiable quote invites a
    buyer to pay into silence."""
    from skopos.economy.payments import payment_required_body

    body = payment_required_body("skopos.fleet.status@v1", eco_cfg)
    assert "accepts" not in body
    assert all("payTo" not in way for way in body["payment_ways"])


def test_an_unknown_capability_is_quoted_no_amount(eco_cfg: EconomyConfig):
    from skopos.economy.payments import payment_required_body

    body = payment_required_body("nope@v1", eco_cfg)
    assert "needed" not in body
    assert body["payment_ways"]


def test_a_hub_url_is_offered_as_a_rail(tmp_path, monkeypatch):
    monkeypatch.setenv("SKOPOS_AIMARKET_ENABLED", "1")
    monkeypatch.setenv("SKOPOS_HUB_URL", "https://modelmarket.dev/")
    from skopos.economy.config import load_economy_config
    from skopos.economy.payments import payment_required_body

    body = payment_required_body("skopos.fleet.status@v1", load_economy_config())
    hub = next(w for w in body["payment_ways"] if w["rail"] == "hub-channel")
    assert hub["open"] == "https://modelmarket.dev/ai-market/v2/channel/open"


def test_a_wrong_key_is_still_a_rejection_not_an_invitation():
    """401 and 402 answer different questions; the handler must keep them apart."""
    import inspect

    import api_server

    src = inspect.getsource(api_server.Handler.do_POST)
    assert "_credential_presented" in src
    assert src.index("_credential_presented") < src.index("payment_required_body")
    assert callable(api_server._credential_presented)
