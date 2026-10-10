from __future__ import annotations

from skopos.charts import prevent_label_overlap, short_path_label
from skopos.security.charts import chart_disk_usage, chart_resource_gauge, chart_resource_gauges, chart_threat_3d
from skopos.themes import apply_chart_theme


def test_short_path_label_truncates_docker_overlay():
    path = "/var/lib/docker/overlay2/fe05ded714f7fdf937dbd39884fc5efc2201ec08282/merged"
    label = short_path_label(path)
    assert len(label) <= 34
    assert "docker" in label
    assert "fe05" in label


def test_prevent_label_overlap_expands_margins_for_long_y_labels():
    import plotly.graph_objects as go

    fig = go.Figure(
        data=[
            go.Bar(
                x=[10, 20],
                y=[
                    "/var/lib/docker/overlay2/abc1234567890/merged",
                    "/var/lib/docker/overlay2/def0987654321/merged",
                ],
                orientation="h",
            )
        ]
    )
    prevent_label_overlap(fig)
    assert fig.layout.margin.l >= 120


def test_chart_disk_usage_uses_horizontal_bars():
    disks = [
        {"mount": "/", "use_pct": 55.0},
        {
            "mount": "/var/lib/docker/rootfs/overlayfs/4ede72a3f1ab2c8d9e0a1234567890ab",
            "use_pct": 88.0,
        },
        {"mount": "/var/lib/docker/rootfs/overlayfs/4d35b36bf1ab2c8d9e0a1234567890cd", "use_pct": 40.0},
    ]
    fig = chart_disk_usage(disks)
    assert fig.data[0].orientation == "h"
    assert fig.layout.yaxis.title.text in ("", None)
    assert fig.layout.xaxis.title.text == "Used %"
    assert len(fig.data[0].y) == 3
    assert all(str(y).startswith("docker") or y == "/" for y in fig.data[0].y)


def test_chart_resource_gauge_single_indicator():
    fig = chart_resource_gauge(42.0, "Memory %", "#4285F4")
    assert len(fig.data) == 1
    assert fig.data[0].type == "indicator"
    assert fig.data[0].domain.x == (0, 1)
    assert fig.data[0].value == 42.0


def test_resource_gauge_metrics_from_snapshot():
    from skopos.security.charts import resource_gauge_metrics

    metrics = resource_gauge_metrics(
        {"mem_used_pct": 50, "cpu_idle_pct": 84, "load_1": 2.0, "cpu_cores": 4}
    )
    assert len(metrics) == 3
    assert metrics[0][0] == 16.0
    assert metrics[1][0] == 50.0


def test_chart_resource_gauges_places_indicators_in_separate_columns():
    snap = {
        "mem_used_pct": 42.5,
        "cpu_idle_pct": 80,
        "load_1": 1.2,
        "cpu_cores": 4,
    }
    fig = chart_resource_gauges(snap)
    assert len(fig.data) == 3
    domains = [trace.domain for trace in fig.data]
    x_starts = sorted(d.x[0] for d in domains)
    assert x_starts[0] < x_starts[1] < x_starts[2]
    assert all(d.x[1] - d.x[0] < 0.5 for d in domains)


def test_chart_threat_3d_uses_typed_glyphs():
    snap = {
        "server_name": "factory",
        "host": "203.0.113.10",
        "ports": [
            {"port": 443, "proto": "tcp", "bind_scope": "public", "process": "nginx"},
            {"port": 22, "proto": "tcp", "bind_scope": "public"},
            {"port": 8080, "proto": "tcp", "bind_scope": "localhost"},
        ],
    }
    findings = [
        {"title": "HTTP port publicly exposed", "severity": "medium", "category": "ports"},
        {"title": "SSH open to world", "severity": "critical", "category": "ports"},
    ]
    fig = chart_threat_3d(snap, findings, title="3D topology")
    assert fig.layout.meta["stats_chart"] == "threat_universe"
    assert fig.layout.scene.bgcolor == "rgb(6,8,24)"
    assert fig.layout.paper_bgcolor == "rgb(4,6,18)"
    names = {t.name for t in fig.data if t.name}
    assert "Server" in names
    assert "Internet" in names
    assert "Public port" in names
    assert "Critical finding" in names


def test_chart_threat_3d_aggregates_disk_findings():
    snap = {"server_name": "factory", "host": "1.2.3.4", "ports": []}
    findings = [
        {
            "title": f"Disk usage high (/var/lib/docker/overlay2/abc{i}/merged)",
            "severity": "medium",
            "category": "resources",
            "detail": f"{92}% used",
        }
        for i in range(8)
    ]
    fig = chart_threat_3d(snap, findings, title="3D")
    medium = [t for t in fig.data if t.name == "Medium finding"]
    assert medium
    assert len(medium[0].x) == 1


def test_aggregate_findings_for_map():
    from skopos.security.charts import _aggregate_findings_for_map

    rows = [
        {"title": "Disk usage high (/var/lib/docker/overlay2/a/merged)", "severity": "medium", "category": "resources", "detail": "90%"},
        {"title": "Disk usage high (/var/lib/docker/overlay2/b/merged)", "severity": "medium", "category": "resources", "detail": "91%"},
    ]
    out = _aggregate_findings_for_map(rows)
    assert len(out) == 1
    assert "Storage" in out[0]["title"]
    assert "(2)" in out[0]["title"]
