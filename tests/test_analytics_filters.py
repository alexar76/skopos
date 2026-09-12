"""Analytics filter helpers."""

from __future__ import annotations

from skopos.i18n import t


def test_all_countries_placeholder_ru():
    assert t("common.all_countries", "ru") == "Все страны"


def test_all_servers_placeholder_ru():
    assert t("common.all_servers", "ru") == "Все серверы"
