"""SQL analytics aggregates match full-period accuracy without row materialization."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from skopos.analytics_filters import AnalyticsFilterState
from skopos.analytics_queries import fetch_country_stats, fetch_kpis, fetch_timeline
from skopos.db import ParsedRequest, connect, init_db, insert_requests
from skopos.period_data import fetch_period_requests


def _req(*, ts: datetime, ip: str, country: str, path: str = "/") -> ParsedRequest:
    iso = ts.isoformat()
    return ParsedRequest(
        log_source="file:/var/log/nginx/access.log",
        ecosystem_segment="web",
        server_ip="10.0.0.1",
        ts_utc=iso,
        remote_addr=ip,
        host="example.com",
        country_code=country,
        country_name=country,
        ua_browser="Chrome",
        ua_os="Linux",
        ua_device="desktop",
        ua_is_bot=0,
        referer_domain=None,
        method="GET",
        path=path,
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
    )


def test_sql_kpis_match_full_row_load(tmp_path):
    db = str(tmp_path / "agg.sqlite3")
    con = connect(db)
    init_db(con)
    now = datetime(2026, 7, 20, 12, 0, tzinfo=timezone.utc)
    rows = []
    for hour in range(48):
        ts = now - timedelta(hours=hour)
        for i in range(5):
            rows.append(
                _req(
                    ts=ts,
                    ip=f"203.0.113.{(hour + i) % 50}",
                    country="US" if hour < 24 else "NL",
                )
            )
    insert_requests(con, "web-1", rows)

    until = now.isoformat()
    since = (now - timedelta(hours=24) + timedelta(seconds=1)).isoformat()
    servers = ("web-1",)
    filters = _filters()

    kpis = fetch_kpis(con, servers, since, until, filters)
    df, meta = fetch_period_requests(con, servers, since, until)
    countries = fetch_country_stats(con, servers, since, until, filters)
    timeline = fetch_timeline(con, servers, since, until, filters, granularity="hour")
    con.close()

    assert meta.returned_rows == 24 * 5
    assert kpis.requests == meta.returned_rows == len(df)
    assert kpis.unique_ips == int(df["remote_addr"].nunique())
    assert set(countries["country_code"]) == {"US"}
    assert int(countries.loc[countries["country_code"] == "US", "visitors"].iloc[0]) == int(
        df[df["country_code"] == "US"]["remote_addr"].nunique()
    )
    assert not timeline.empty
    assert int(timeline["requests"].sum()) == kpis.requests


def test_fetch_period_no_order_full_window(tmp_path):
    db = str(tmp_path / "period.sqlite3")
    con = connect(db)
    init_db(con)
    now = datetime(2026, 7, 20, 12, 0, tzinfo=timezone.utc)
    rows = []
    for hour in range(24 * 7):
        ts = now - timedelta(hours=hour)
        for i in range(10):
            rows.append(
                _req(
                    ts=ts,
                    ip=f"203.0.113.{(hour + i) % 200}",
                    country="US" if hour < 24 else "NL",
                )
            )
    insert_requests(con, "web-1", rows)

    until = now.isoformat()
    since_24h = (now - timedelta(hours=24) + timedelta(seconds=1)).isoformat()
    since_7d = (now - timedelta(days=7)).isoformat()
    servers = ("web-1",)

    df_24, meta_24 = fetch_period_requests(con, servers, since_24h, until)
    df_7d, meta_7d = fetch_period_requests(con, servers, since_7d, until)
    con.close()

    assert meta_24.returned_rows == meta_24.total_in_period == 24 * 10
    assert meta_7d.returned_rows == meta_7d.total_in_period == 24 * 7 * 10
    assert set(df_24["country_code"].dropna()) == {"US"}
    assert "NL" in set(df_7d["country_code"].dropna())
