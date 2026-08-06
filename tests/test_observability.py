"""Unit tests for Skopos Observability PromQL parsing and 3D graph."""

from __future__ import annotations

from skopos.observability.charts import chart_kpi_gauges, chart_timeseries_matrix, targets_table_rows
from skopos.observability.graph3d import chart_service_graph_3d
from skopos.observability.prom import demo_kpis, parse_instant_vector, parse_range_matrix


def test_parse_instant_vector_success():
    payload = {
        "status": "success",
        "data": {
            "resultType": "vector",
            "result": [
                {"metric": {"job": "aicom"}, "value": [1710000000, "1"]},
                {"metric": {"job": "hub"}, "value": [1710000000, "0.5"]},
            ],
        },
    }
    rows = parse_instant_vector(payload)
    assert len(rows) == 2
    assert rows[0]["value"] == 1.0
    assert rows[1]["metric"]["job"] == "hub"


def test_parse_instant_vector_error():
    assert parse_instant_vector({"status": "error", "error": "boom"}) == []


def test_parse_range_matrix():
    payload = {
        "status": "success",
        "data": {
            "resultType": "matrix",
            "result": [
                {
                    "metric": {"capability": "x@v1"},
                    "values": [[100.0, "0.1"], [130.0, "0.2"]],
                }
            ],
        },
    }
    rows = parse_range_matrix(payload)
    assert len(rows) == 1
    assert rows[0]["timestamps"] == [100.0, 130.0]
    assert rows[0]["values"] == [0.1, 0.2]


def test_chart_service_graph_3d_builds_without_network():
    fig = chart_service_graph_3d(demo_kpis())
    assert fig.data
    assert len(fig.data) == 2  # edges + nodes
    assert fig.layout.title.text


def test_chart_kpi_and_timeseries():
    fig = chart_kpi_gauges(demo_kpis())
    assert fig.data
    series = [
        {
            "metric": {"capability": "demo"},
            "timestamps": [1.0, 2.0, 3.0],
            "values": [0.1, 0.2, 0.15],
        }
    ]
    ts = chart_timeseries_matrix(series, "demo")
    assert len(ts.data) == 1


def test_chart_heatmap_merges_margin_without_typeerror():
    from skopos.observability.charts import chart_heatmap_by_capability

    rows = [
        {"metric": {"capability": "platon.oracle@v1", "result": "payment_required"}, "value": 0.12},
        {"metric": {"capability": "sandbox.demo@v1", "result": "ok"}, "value": 0.4},
    ]
    fig = chart_heatmap_by_capability(rows, "heat")
    assert fig.data
    assert fig.layout.margin.l >= 160


def test_targets_table_rows_demo():
    rows = targets_table_rows(False, demo_kpis())
    assert len(rows) == 3
    assert all(r["source"] == "demo" for r in rows)
    assert rows[0]["status"] == "up"
