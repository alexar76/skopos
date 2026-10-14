from __future__ import annotations

import sqlite3

import pandas as pd
import pytest

from skopos.charts import chart_countries_map, chart_countries_map_2d


@pytest.fixture
def sample_geo_df() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "remote_addr": ["1.1.1.1"] * 100 + ["2.2.2.2"] * 50 + ["3.3.3.3"] * 10,
            "country_code": ["NL"] * 100 + ["US"] * 50 + ["DE"] * 10,
            "country_name": ["Netherlands"] * 100 + ["United States"] * 50 + ["Germany"] * 10,
        }
    )


def test_globe_chart_has_3d_traces(sample_geo_df: pd.DataFrame):
    fig = chart_countries_map(sample_geo_df, metric="requests")
    assert fig.layout.scene is not None
    types = {type(tr).__name__ for tr in fig.data}
    assert "Mesh3d" in types
    assert "Scatter3d" in types
    assert len(fig.data) >= 4  # earth + borders + atmosphere + pillars/markers per country


def test_globe_chart_empty_df():
    fig = chart_countries_map(pd.DataFrame(columns=["remote_addr", "country_code"]), metric="requests")
    assert len(fig.layout.annotations) >= 1


def test_map_2d_chart_has_choropleth(sample_geo_df: pd.DataFrame):
    fig = chart_countries_map_2d(sample_geo_df, metric="requests")
    assert fig.layout.geo is not None
    assert fig.data[0].type == "choropleth"
    assert "3D Globe" not in str(fig.layout.title.text)


def test_map_2d_chart_empty_df():
    fig = chart_countries_map_2d(pd.DataFrame(columns=["remote_addr", "country_code"]), metric="requests")
    assert len(fig.layout.annotations) >= 1
