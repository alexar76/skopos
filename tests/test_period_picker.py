from __future__ import annotations

from datetime import datetime, timezone

import pytest

from skopos.period_picker import (
    PeriodRange,
    _cache_aligned_now,
    resolve_absolute_period,
    resolve_preset,
    resolve_relative_period,
)


def test_cache_period_is_stable_within_a_minute():
    first = datetime(2026, 7, 14, 12, 30, 1, 123456, tzinfo=timezone.utc)
    later = datetime(2026, 7, 14, 12, 30, 59, 999999, tzinfo=timezone.utc)
    assert _cache_aligned_now(first) == _cache_aligned_now(later)
    assert _cache_aligned_now(first).second == 0
    assert _cache_aligned_now(first).microsecond == 0


def test_cache_period_advances_on_the_next_minute():
    first = datetime(2026, 7, 14, 12, 30, 59, tzinfo=timezone.utc)
    next_minute = datetime(2026, 7, 14, 12, 31, 0, tzinfo=timezone.utc)
    assert _cache_aligned_now(next_minute) > _cache_aligned_now(first)


def test_relative_hours():
    now = datetime(2026, 7, 14, 12, 0, tzinfo=timezone.utc)
    p = resolve_relative_period(24, "hours", now=now)
    assert p.until == now
    assert p.since == datetime(2026, 7, 13, 12, 0, tzinfo=timezone.utc)


def test_relative_minutes():
    now = datetime(2026, 7, 14, 12, 30, tzinfo=timezone.utc)
    p = resolve_relative_period(90, "minutes", now=now)
    assert p.duration.total_seconds() == 90 * 60


def test_relative_months_approx():
    now = datetime(2026, 7, 14, 0, 0, tzinfo=timezone.utc)
    p = resolve_relative_period(2, "months", now=now)
    assert p.duration.days == 60


def test_absolute_swaps_if_reversed():
    start = datetime(2026, 7, 14, 18, 0, tzinfo=timezone.utc)
    end = datetime(2026, 7, 14, 6, 0, tzinfo=timezone.utc)
    p = resolve_absolute_period(start, end)
    assert isinstance(p, PeriodRange)
    assert p.since == end
    assert p.until == start


def test_relative_rejects_zero():
    with pytest.raises(ValueError):
        resolve_relative_period(0, "hours")


def test_preset_day():
    now = datetime(2026, 7, 14, 12, 0, tzinfo=timezone.utc)
    p = resolve_preset("1d", now=now)
    assert p.duration.days == 1


def test_preset_year():
    now = datetime(2026, 7, 14, 12, 0, tzinfo=timezone.utc)
    p = resolve_preset("365d", now=now)
    assert p.duration.days == 365


def test_resolve_custom_period_uses_stored_prefix(monkeypatch):
    from skopos.period_picker import SESSION_CUSTOM_PREFIX_KEY, _resolve_custom_period

    class FakeSession(dict):
        def get(self, key, default=None):
            return super().get(key, default)

    fake = FakeSession(
        {
            SESSION_CUSTOM_PREFIX_KEY: "analytics_period_sb",
            "analytics_period_sb_mode": "relative",
            "analytics_period_sb_amount": 2,
            "analytics_period_sb_unit": "days",
        }
    )
    monkeypatch.setattr("skopos.period_picker.st.session_state", fake)
    now = datetime(2026, 7, 14, 12, 0, tzinfo=timezone.utc)
    p = _resolve_custom_period(now=now)
    assert p.duration.days == 2
