"""Countries × server and countries × site aggregates stay split per entity."""

from __future__ import annotations

from datetime import datetime, timezone

from skopos.analytics_filters import AnalyticsFilterState
from skopos.analytics_queries import fetch_countries_by_dimension, fetch_countries_by_host
from skopos.charts import chart_countries_by_category, chart_countries_by_host
from skopos.db import ParsedRequest, connect, init_db, insert_requests
from skopos.i18n import t


def _req(*, ts: datetime, ip: str, country: str, host: str) -> ParsedRequest:
    iso = ts.isoformat()
    return ParsedRequest(
        log_source="file:/var/log/nginx/access.log",
        ecosystem_segment="web",
        server_ip="10.0.0.1",
        ts_utc=iso,
        remote_addr=ip,
        host=host,
        country_code=country,
        country_name=country,
        ua_browser="Chrome",
        ua_os="Linux",
        ua_device="desktop",
        ua_is_bot=0,
        referer_domain=None,
        method="GET",
        path="/",
        status=200,
        bytes_sent=100,
        referer=None,
        user_agent="Mozilla/5.0",
        request_raw="GET / HTTP/1.1",
        line_raw=f'{ip} - - [{iso}] "GET / HTTP/1.1" 200 100',
    )


def _filters() -> AnalyticsFilterState:
    return AnalyticsFilterState(
        hide_bots=False,
        hide_service=False,
        visitors_only=False,
        sel_servers=[],
        sel_hosts=[],
        sel_countries=[],
        path_contains="",
        hide_datacenter=False,
    )


def test_countries_split_by_server_and_site(tmp_path):
    db = str(tmp_path / "geo.sqlite3")
    con = connect(db)
    init_db(con)
    ts = datetime(2026, 9, 13, 12, 0, tzinfo=timezone.utc)
    insert_requests(
        con,
        "edge",
        [
            _req(ts=ts, ip="203.0.113.1", country="US", host="site-a.example"),
            _req(ts=ts, ip="203.0.113.2", country="US", host="site-a.example"),
            _req(ts=ts, ip="203.0.113.3", country="NL", host="site-b.example"),
        ],
    )
    insert_requests(
        con,
        "factory",
        [
            _req(ts=ts, ip="198.51.100.1", country="DE", host="modeldev.modelmarket.dev"),
        ],
    )
    since = "2026-09-13T00:00:00+00:00"
    until = "2026-09-13T23:59:59+00:00"
    servers = ("edge", "factory")
    filters = _filters()

    by_site = fetch_countries_by_dimension(
        con, servers, since, until, filters, dimension="host", metric="requests"
    )
    by_server = fetch_countries_by_dimension(
        con, servers, since, until, filters, dimension="server", metric="requests"
    )
    legacy = fetch_countries_by_host(con, servers, since, until, filters)
    con.close()

    site_req = {
        (row.entity, row.country_code): int(row.requests) for row in by_site.itertuples()
    }
    assert site_req[("site-a.example", "US")] == 2
    assert site_req[("site-b.example", "NL")] == 1
    assert site_req[("modeldev.modelmarket.dev", "DE")] == 1

    server_req = {
        (row.entity, row.country_code): int(row.requests) for row in by_server.itertuples()
    }
    assert server_req[("edge", "US")] == 2
    assert server_req[("edge", "NL")] == 1
    assert server_req[("factory", "DE")] == 1

    assert set(legacy["host"]) >= {"site-a.example", "site-b.example"}

    fig_site = chart_countries_by_category(by_site, metric="requests", title_key="countries_by_site")
    fig_host = chart_countries_by_host(legacy, metric="requests")
    assert fig_site.data
    assert fig_host.data


def test_geo_view_labels():
    assert t("analytics.geo_view_overall", "ru") == "Общая"
    assert t("analytics.geo_view_servers", "ru") == "По серверам"
    assert t("analytics.geo_view_sites", "ru") == "По сайтам"
    assert t("analytics.geo_view_overall", "en") == "Overall"
