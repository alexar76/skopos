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
    import skopos.geoip as geoip
    from types import SimpleNamespace

    requested = []

    def fake_get(url, **kwargs):
        requested.append((url, kwargs["timeout"]))
        return SimpleNamespace(raise_for_status=lambda: None,
                               json=lambda: {"country_code": "US", "country": "United States"})

    monkeypatch.setattr(geoip.requests, "get", fake_get)
    monkeypatch.setenv("SKOPOS_GEOIP_API_FALLBACK", "0")
    geo = GeoIPResolver(str(tmp_path / "nope.mmdb"))
    assert geo.has_mmdb is False
    assert geo.uses_http_fallback is True
    info = geo.country_for_ip("8.8.8.8")
    assert info.iso_code == "US"
    assert requested == [("https://get.geojs.io/v1/ip/geo/8.8.8.8.json", 8)]


def test_no_http_lookup_is_sent_past_the_deadline(monkeypatch):
    import skopos.geoip as geoip

    sent = []

    def fake_get(url, **_kw):
        sent.append(url)
        raise ConnectionError("offline in tests")

    monkeypatch.setattr(geoip.requests, "get", fake_get)

    geo = GeoIPResolver(None, api_fallback=True)
    geo.prefetch_map(["8.8.8.8"])
    assert sent, "control: without a deadline the lookup goes out"

    sent.clear()
    geo = GeoIPResolver(None, api_fallback=True)
    geo.limit_http_to(0)
    out = geo.prefetch_map(["1.1.1.1", "9.9.9.9"])
    assert sent == []
    assert {info.iso_code for info in out.values()} == {None}
