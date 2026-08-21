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
