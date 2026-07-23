"""GeoIP resolver — MMDB vs HTTP fallback policy."""

from __future__ import annotations

from pathlib import Path

from skopos.geoip import GeoIPResolver, resolve_api_fallback


def test_resolve_api_fallback_off_when_mmdb_exists(tmp_path, monkeypatch):
    mmdb = tmp_path / "GeoLite2-Country.mmdb"
    mmdb.write_bytes(b"x")
    monkeypatch.delenv("SKOPOS_GEOIP_API_FALLBACK", raising=False)
    assert resolve_api_fallback(str(mmdb)) is False


def test_resolve_api_fallback_on_without_mmdb(monkeypatch):
    monkeypatch.delenv("SKOPOS_GEOIP_API_FALLBACK", raising=False)
    assert resolve_api_fallback("./missing.mmdb") is True
    assert resolve_api_fallback(None) is True


def test_resolve_api_fallback_env_override(tmp_path, monkeypatch):
    mmdb = tmp_path / "GeoLite2-Country.mmdb"
    mmdb.write_bytes(b"x")
    monkeypatch.setenv("SKOPOS_GEOIP_API_FALLBACK", "1")
    assert resolve_api_fallback(str(mmdb)) is True
    monkeypatch.setenv("SKOPOS_GEOIP_API_FALLBACK", "0")
    assert resolve_api_fallback(str(mmdb)) is False
    assert resolve_api_fallback(None) is True
    assert resolve_api_fallback("./missing.mmdb") is True


def test_resolve_api_fallback_off_requires_mmdb_file(tmp_path, monkeypatch):
    monkeypatch.setenv("SKOPOS_GEOIP_API_FALLBACK", "0")
    missing = str(tmp_path / "missing.mmdb")
    assert resolve_api_fallback(missing) is True
    ready = tmp_path / "GeoLite2-Country.mmdb"
    ready.write_bytes(b"x")
    assert resolve_api_fallback(str(ready)) is False


def test_geoip_resolver_falls_back_to_http_without_mmdb(tmp_path, monkeypatch):
    monkeypatch.setenv("SKOPOS_GEOIP_API_FALLBACK", "0")
    geo = GeoIPResolver(str(tmp_path / "nope.mmdb"))
    assert geo.has_mmdb is False
    assert geo.uses_http_fallback is True
    info = geo.country_for_ip("8.8.8.8")
    assert info.iso_code == "US"
