"""Analytics filter helpers."""

from __future__ import annotations

from streamlit.testing.v1 import AppTest

from skopos.i18n import t
from skopos.analytics_filters import parse_filter_flag


def test_all_countries_placeholder_ru():
    assert t("common.all_countries", "ru") == "Все страны"


def test_all_servers_placeholder_ru():
    assert t("common.all_servers", "ru") == "Все серверы"


def test_filter_flag_query_parameter_parser():
    assert parse_filter_flag("1", False) is True
    assert parse_filter_flag("false", True) is False
    assert parse_filter_flag(["0", "1"], False) is True
    assert parse_filter_flag("broken", True) is True


def test_filter_checkboxes_survive_a_new_browser_session():
    script = """
import streamlit as st
from skopos.analytics_filters import render_analytics_filters

render_analytics_filters(
    st,
    "ru",
    key_suffix="_test",
    server_opts=[],
    host_opts=[],
    country_opts=[],
    server_labels={},
)
"""
    first_session = AppTest.from_string(script).run()
    first_session.checkbox[0].set_value(False).run()
    assert first_session.query_params["fb"] == ["0"]

    reloaded_session = AppTest.from_string(script)
    reloaded_session.query_params = dict(first_session.query_params)
    reloaded_session.run()

    assert not reloaded_session.exception
    assert reloaded_session.checkbox[0].value is False
    assert [checkbox.value for checkbox in reloaded_session.checkbox[1:]] == [
        True,
        True,
        True,
    ]
