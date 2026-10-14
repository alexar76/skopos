from __future__ import annotations

from skopos.security.docker_insights import format_docker_section, infer_container_role, parse_docker_section


SAMPLE_DOCKER = """
__PS__
metis-nginx|nginx:1.25-alpine|Up 3 days|running|0.0.0.0:80->80/tcp, 0.0.0.0:443->443/tcp
metis-api|metis/api:latest|Up 3 days|running|127.0.0.1:8080->8080/tcp
old-worker|metis/worker:old|Exited (1) 2 days ago|exited|
__SKOPOS__
metis-nginx|0.42%|24MiB / 2GiB|1.17%|12MB / 8MB|0B / 0B|5
metis-api|3.10%|512MiB / 2GiB|25.00%|200MB / 150MB|1MB / 0B|18
__META__
/metis-nginx|nginx|metis|metis-nginx
/metis-api|api|metis|metis-api
"""


def test_parse_docker_section_enriched():
    rows = parse_docker_section(SAMPLE_DOCKER)
    assert len(rows) == 3
    nginx = next(r for r in rows if r["name"] == "metis-nginx")
    assert nginx["state"] == "running"
    assert nginx["cpu_percent"] == "0.42%"
    assert "24MiB" in nginx["mem_usage"]
    assert nginx["compose_project"] == "metis"
    assert "Reverse proxy" in nginx["role"]
    assert nginx["ports"].startswith("0.0.0.0:80")


def test_parse_docker_legacy_format():
    legacy = "metis-nginx|nginx:alpine|0.0.0.0:80->80/tcp"
    rows = parse_docker_section(legacy)
    assert len(rows) == 1
    assert rows[0]["name"] == "metis-nginx"
    assert rows[0]["role"]


def test_infer_metis_role():
    role = infer_container_role(name="metis-worker", image="python:3.12", compose_service="worker")
    assert "Metis" in role or "Python" in role


def test_format_docker_section_markdown():
    rows = parse_docker_section(SAMPLE_DOCKER)
    md = format_docker_section(rows, server_name="metis")
    assert "Docker workloads" in md
    assert "metis-nginx" in md
    assert "CPU 0.42%" in md
    assert "Running: 2" in md
