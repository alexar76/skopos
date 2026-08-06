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
    return load_economy_config()


def test_load_economy_disabled_by_default(monkeypatch):
    monkeypatch.delenv("SKOPOS_AIMARKET_ENABLED", raising=False)
    cfg = load_economy_config()
    assert cfg.enabled is False


def test_well_known_manifest(eco_cfg: EconomyConfig):
    wk = build_well_known(eco_cfg)
    assert wk["manifest_url"].endswith("/ai-market/v2/manifest")
    assert "v2" in wk["protocol_versions"]


def test_v2_manifest_lists_capabilities(eco_cfg: EconomyConfig):
    manifest = build_v2_manifest(eco_cfg)
    assert manifest["capabilities_count"] == len(CAPABILITY_BY_ID)
    assert manifest["tools"][0]["invoke_url"] == "https://skopos.test/aimarket/invoke"


def test_supply_manifest_one_per_capability(eco_cfg: EconomyConfig):
    items = build_supply_manifest(eco_cfg)
    assert len(items) == len(CAPABILITY_BY_ID)
    assert items[0]["publisher_id"] == eco_cfg.publisher_id


def test_dispatch_fleet_status(eco_cfg: EconomyConfig):
    with patch("skopos.public_status.build_status", return_value={"ok": True, "requests_total": 42}):
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
