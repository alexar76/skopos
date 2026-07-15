from __future__ import annotations

import plotly.express as px
import plotly.graph_objects as go

from skopos.charts import prevent_label_overlap, short_path_label


def test_short_path_label_keeps_short_paths():
    assert short_path_label("/") == "/"
    assert short_path_label("/var/log") == "/var/log"


def test_short_path_label_docker_rootfs():
    path = "/var/lib/docker/rootfs/overlayfs/4ede72a3f1ab2c8d9e0a1234567890ab"
    label = short_path_label(path)
    assert len(label) <= 34
    assert label.startswith("docker …/")
    assert "4ede72a3" in label


def test_prevent_label_overlap_angles_long_x_labels():
    fig = px.bar(
        x=["very-long-category-name-one", "very-long-category-name-two"],
        y=[1, 2],
        title="demo",
    )
    prevent_label_overlap(fig)
    assert fig.layout.xaxis.tickangle != 0
    assert fig.layout.margin.b >= 48
