"""AIMarket discovery manifests for SKOPOS supply side."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from .capabilities import CAPABILITIES, CapabilitySpec
from .config import EconomyConfig


def _tool_entry(cfg: EconomyConfig, spec: CapabilitySpec) -> dict[str, Any]:
    return {
        "name": f"{cfg.product_id}.{spec.capability_id}",
        "description": spec.description,
        "input_schema": spec.input_schema,
        "output_schema": spec.output_schema,
        "price_per_call_usd": spec.price_per_call_usd,
        "p50_latency_ms": spec.p50_latency_ms,
        "success_rate_30d": 0.99,
        "product_id": cfg.product_id,
        "capability_id": spec.capability_id,
        "invoke_url": cfg.invoke_url,
    }


def build_well_known(cfg: EconomyConfig) -> dict[str, Any]:
    base = cfg.public_base_url.rstrip("/")
    return {
        "name": "SKOPOS Fleet Intelligence",
        "description": "Self-hosted nginx analytics & security posture — billable fleet telemetry for AI agents.",
        "protocol_versions": ["v2"],
        "manifest_url": f"{base}/ai-market/v2/manifest",
        "prices_url": f"{base}/ai-market/v2/prices",
        "base_url": base,
        "service": "skopos",
        "chain": "base",
        "token": "USDC",
        "mcp_servers": [],
        "federation": {"role": "provider"},
        "peers": [],
    }


def build_v2_manifest(cfg: EconomyConfig) -> dict[str, Any]:
    tools = [_tool_entry(cfg, spec) for spec in CAPABILITIES]
    return {
        "protocol_version": "v2",
        "generated_at": datetime.now(tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "base_url": cfg.public_base_url.rstrip("/"),
        "products_count": 1,
        "capabilities_count": len(tools),
        "tools": tools,
        "local_capabilities": tools,
        "federated_capabilities": [],
        "total_capabilities": len(tools),
    }


def build_prices(cfg: EconomyConfig) -> dict[str, Any]:
    prices = [
        {
            "product_id": cfg.product_id,
            "capability_id": spec.capability_id,
            "price_per_call_usd": spec.price_per_call_usd,
            "currency": "USD",
        }
        for spec in CAPABILITIES
    ]
    return {
        "protocol_version": "v2",
        "currency": "USD",
        "count": len(prices),
        "prices": prices,
    }


def build_supply_manifest(cfg: EconomyConfig) -> list[dict[str, Any]]:
    """One registration payload per capability (Hub supply/register)."""
    out: list[dict[str, Any]] = []
    for spec in CAPABILITIES:
        out.append(
            {
                "product_id": cfg.product_id,
                "capability_id": spec.capability_id,
                "name": spec.name,
                "description": spec.description,
                "invoke_url": cfg.invoke_url,
                "price_per_call_usd": spec.price_per_call_usd,
                "publisher_id": cfg.publisher_id,
                "input_schema": spec.input_schema,
                "output_schema": spec.output_schema,
            }
        )
    return out
