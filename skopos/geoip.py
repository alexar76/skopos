from __future__ import annotations

import time
from dataclasses import dataclass
from functools import lru_cache
from ipaddress import ip_address
from pathlib import Path
from typing import Iterable

import maxminddb
import requests


@dataclass(frozen=True)
class CountryInfo:
    iso_code: str | None
    name: str | None


def is_private_ip(ip: str) -> bool:
    try:
        addr = ip_address(ip.strip())
    except Exception:
        return True
    return bool(
        addr.is_private
        or addr.is_loopback
        or addr.is_link_local
        or addr.is_reserved
        or addr.is_multicast
    )


class GeoIPResolver:
    """Country lookup: MaxMind MMDB if present, else ip-api.com (cached, rate-limited)."""

    def __init__(self, mmdb_path: str | None = None, *, api_fallback: bool = True):
        self._reader = None
        self._api_fallback = api_fallback
        self._last_api_at = 0.0

        if mmdb_path:
            p = Path(mmdb_path).expanduser()
            if p.is_file():
                self._reader = maxminddb.open_database(str(p))

    @property
    def has_mmdb(self) -> bool:
        return self._reader is not None

    def close(self) -> None:
        if self._reader:
            try:
                self._reader.close()
            except Exception:
                pass

    @lru_cache(maxsize=50000)
    def country_for_ip(self, ip: str) -> CountryInfo:
        ip = (ip or "").strip()
        if not ip:
            return CountryInfo(iso_code=None, name=None)
        if is_private_ip(ip):
            return CountryInfo(iso_code="INT", name="Internal")

        if self._reader:
            info = self._lookup_mmdb(ip)
            if info.iso_code or info.name:
                return info

        if self._api_fallback:
            return self._lookup_api(ip)
        return CountryInfo(iso_code=None, name=None)

    def _lookup_mmdb(self, ip: str) -> CountryInfo:
        try:
            rec = self._reader.get(ip)
        except Exception:
            return CountryInfo(iso_code=None, name=None)
        if not isinstance(rec, dict):
            return CountryInfo(iso_code=None, name=None)
        country = rec.get("country") or rec.get("registered_country") or {}
        if not isinstance(country, dict):
            return CountryInfo(iso_code=None, name=None)
        iso = country.get("iso_code")
        names = country.get("names") or {}
        name = names.get("en") if isinstance(names, dict) else None
        return CountryInfo(iso_code=str(iso) if iso else None, name=str(name) if name else None)

    def _lookup_geojs(self, ip: str) -> CountryInfo:
        try:
            r = requests.get(f"https://get.geojs.io/v1/ip/geo/{ip}.json", timeout=8)
            r.raise_for_status()
            data = r.json()
            if not isinstance(data, dict):
                return CountryInfo(iso_code=None, name=None)
            cc = data.get("country_code") or data.get("country_code3")
            return CountryInfo(
                iso_code=str(cc) if cc else None,
                name=str(data.get("country") or "") or None,
            )
        except Exception:
            return CountryInfo(iso_code=None, name=None)

    def _lookup_api(self, ip: str) -> CountryInfo:
        # geojs.io works from datacenters; ip-api.com often returns 403 on server IPs.
        now = time.monotonic()
        wait = 0.12 - (now - self._last_api_at)
        if wait > 0:
            time.sleep(wait)
        self._last_api_at = time.monotonic()
        info = self._lookup_geojs(ip)
        if info.iso_code or info.name:
            return info
        try:
            r = requests.get(
                f"https://ipwho.is/{ip}",
                timeout=8,
            )
            r.raise_for_status()
            data = r.json()
            if not isinstance(data, dict) or not data.get("success", True):
                return CountryInfo(iso_code=None, name=None)
            return CountryInfo(
                iso_code=str(data.get("country_code") or "") or None,
                name=str(data.get("country") or "") or None,
            )
        except Exception:
            return CountryInfo(iso_code=None, name=None)

    def batch_lookup(self, ips: list[str]) -> dict[str, CountryInfo]:
        """Resolve many public IPs via geojs (ip-api batch blocked on many hosts)."""
        out: dict[str, CountryInfo] = {}
        todo = [ip.strip() for ip in ips if ip and not is_private_ip(ip.strip())]
        for ip in ips:
            if is_private_ip((ip or "").strip()):
                out[ip.strip()] = CountryInfo(iso_code="INT", name="Internal")

        for ip in todo:
            if ip in out:
                continue
            out[ip] = self._lookup_api(ip)
        return out

    def prefetch_map(self, ips: Iterable[str]) -> dict[str, CountryInfo]:
        """Resolve many IPs efficiently: MMDB when present, else ip-api batch."""
        unique = list(dict.fromkeys(ip.strip() for ip in ips if ip and ip.strip()))
        out: dict[str, CountryInfo] = {}
        api_todo: list[str] = []
        for ip in unique:
            if is_private_ip(ip):
                out[ip] = CountryInfo(iso_code="INT", name="Internal")
            elif self._reader:
                out[ip] = self.country_for_ip(ip)
            else:
                api_todo.append(ip)
        if api_todo:
            out.update(self.batch_lookup(api_todo))
        return out
