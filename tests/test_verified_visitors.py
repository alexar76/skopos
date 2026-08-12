"""ASN enrichment + datacenter filter + GA-comparable verified-visitors KPI."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from skopos.analytics_filters import AnalyticsFilterState
from skopos.analytics_queries import (
    fetch_first_ts,
    fetch_kpis,
    fetch_verified_visitors,
    filters_sql,
)
from skopos.asn_db import AsnResolver
from skopos.db import ParsedRequest, connect, init_db, insert_requests
from skopos.traffic import (
    is_datacenter_org,
    looks_like_asset_path,
    looks_like_page_path,
)

NOW = datetime(2026, 7, 20, 12, 0, tzinfo=timezone.utc)
SINCE = (NOW - timedelta(days=30)).isoformat()
UNTIL = NOW.isoformat()


def _filters(**kwargs) -> AnalyticsFilterState:
    base = dict(
        hide_bots=False,
        hide_service=False,
        visitors_only=False,
        hide_datacenter=False,
        sel_servers=[],
        sel_hosts=[],
        sel_countries=[],
        path_contains="",
    )
    base.update(kwargs)
    return AnalyticsFilterState(**base)


# ── ASN resolver ─────────────────────────────────────────────────────────────


def _tsv(tmp_path, body: str) -> str:
    p = tmp_path / "ip2asn-combined.tsv"
    p.write_text(body, encoding="utf-8")
    return str(p)


def test_asn_resolver_range_lookup(tmp_path):
    path = _tsv(
        tmp_path,
        "1.0.0.0\t1.0.0.255\t13335\tUS\tCLOUDFLARENET\n"
        "9.9.9.0\t9.9.9.255\t0\tNone\tNot routed\n"
        "23.226.212.0\t23.226.212.255\t398781\tUS\tOSL-188 OCULUS NETWORKS\n"
        "2606:4700::\t2606:4700::ffff\t64512\tUS\tEXAMPLE-V6\n",
    )
    r = AsnResolver(path)
    assert r.has_data
    assert r.lookup("1.0.0.10").asn == 13335
    assert r.lookup("1.0.0.10").org == "CLOUDFLARENET"
    assert r.lookup("1.0.1.0").asn is None  # outside range
    assert r.lookup("9.9.9.9").asn is None  # AS 0 dropped
    assert r.lookup("23.226.212.139").asn == 398781
    assert r.lookup("2606:4700::5").asn == 64512
    assert r.lookup("::ffff:1.0.0.10").asn == 13335  # IPv4-mapped IPv6
    assert r.lookup("192.168.1.1").asn is None  # private
    assert r.lookup("not-an-ip").asn is None


def test_asn_resolver_drops_out_of_range_asn(tmp_path):
    # postgres asn column is BIGINT but bogus >32-bit ASNs are dropped at parse
    path = _tsv(tmp_path, "59.101.13.0\t59.101.13.255\t9294901909999\tAU\tBOGUS\n")
    r = AsnResolver(path)
    assert r.lookup("59.101.13.5").asn is None


def test_asn_resolver_missing_file_is_noop():
    r = AsnResolver("/nonexistent/ip2asn.tsv")
    assert not r.has_data
    assert r.lookup("8.8.8.8").asn is None


def test_is_datacenter_org_positives_negatives():
    assert is_datacenter_org("TENCENT-NET-AP Shenzhen Tencent Computer Systems")
    assert is_datacenter_org("DIGITALOCEAN-ASN")
    assert is_datacenter_org("OVH SAS")
    assert is_datacenter_org("AMAZON-02")
    assert is_datacenter_org("Aeza International Ltd")
    # Residential eyeball ISPs must never match — they carry real visitors.
    assert not is_datacenter_org("COMCAST-7922")
    assert not is_datacenter_org("ASN-CXA-ALL-CCI-22773-RDC Cox Communications")
    assert not is_datacenter_org("ATT-INTERNET4")
    assert not is_datacenter_org("CHINA169-Backbone CHINA UNICOM")
    assert not is_datacenter_org(None)
    assert not is_datacenter_org("")


# ── page/asset path classification ───────────────────────────────────────────


def test_page_vs_asset_paths():
    assert looks_like_page_path("/")
    assert looks_like_page_path("/pricing")
    assert looks_like_page_path("/docs/quickstart")
    # anchored excludes must not swallow real documents
    assert looks_like_page_path("/docs/api/overview")
    assert looks_like_page_path("/feedback")
    # replay-fleet favourites are NOT page documents
    assert not looks_like_page_path("/api/products")
    assert not looks_like_page_path("/monitor/api/v1/state")
    assert not looks_like_page_path("/?_rsc=yIp22O3xgPPxC28X")
    assert not looks_like_page_path("/_next/image?url=%2Fgallery.webp&w=384")
    assert not looks_like_page_path("/index.json")
    assert not looks_like_page_path("/robots.txt")
    assert not looks_like_page_path("/blog/feed")
    assert looks_like_asset_path("/themes.css")
    assert looks_like_asset_path("/_next/static/chunks/main.js")
    assert looks_like_asset_path("/favicon.ico")
    assert not looks_like_asset_path("/pricing")


def test_hide_datacenter_sql_parity():
    sql, params = filters_sql(_filters(hide_datacenter=True), backend="postgresql")
    assert "asn_org" in sql
    assert sql.count("?") == len(params)
    assert "%tencent%" in params


# ── verified visitors on a real (sqlite) DB ──────────────────────────────────


def _row(ip, path, *, status=200, method="GET", ua="Mozilla/5.0 Chrome/149", asn=None, asn_org=None, minute=0):
    ts = (NOW - timedelta(hours=1, minutes=minute)).isoformat()
    return ParsedRequest(
        log_source="file:/var/log/nginx/access.log",
        ecosystem_segment=None,
        server_ip="10.0.0.1",
        ts_utc=ts,
        remote_addr=ip,
        host="example.com",
        country_code="US",
        country_name="United States",
        ua_browser="Chrome",
        ua_os="Linux",
        ua_device="Desktop",
        ua_is_bot=0,
        referer_domain=None,
        method=method,
        path=path,
        status=status,
        bytes_sent=100,
        referer=None,
        user_agent=ua,
        request_raw=f"{method} {path} HTTP/1.1",
        line_raw=f'{ip} [{ts}] "{method} {path}" {status}',
        asn=asn,
        asn_org=asn_org,
    )


def _seed(tmp_path):
    db = str(tmp_path / "vv.sqlite3")
    con = connect(db)
    init_db(con)
    rows = [
        # human: page + assets, residential ASN
        _row("100.64.1.1", "/", asn=7922, asn_org="COMCAST-7922", minute=1),
        _row("100.64.1.1", "/themes.css", asn=7922, asn_org="COMCAST-7922", minute=2),
        _row("100.64.1.1", "/app.js", asn=7922, asn_org="COMCAST-7922", minute=3),
        # replay fleet: APIs + RSC + assets, but never a page document
        _row("100.64.2.2", "/api/products", asn=22773, asn_org="Cox Communications", minute=1),
        _row("100.64.2.2", "/?_rsc=abc123", asn=22773, asn_org="Cox Communications", minute=2),
        _row("100.64.2.2", "/themes.css", asn=22773, asn_org="Cox Communications", minute=3),
        # scanner: page document but zero assets
        _row("100.64.3.3", "/", asn=4134, asn_org="CHINANET-BACKBONE", minute=1),
        # datacenter browser: page + assets from Tencent cloud
        _row("100.64.4.4", "/", asn=45090, asn_org="TENCENT-NET-AP", minute=1),
        _row("100.64.4.4", "/themes.css", asn=45090, asn_org="TENCENT-NET-AP", minute=2),
        # pre-enrichment human: page + assets, NULL asn (must still count)
        _row("100.64.5.5", "/pricing", minute=1),
        _row("100.64.5.5", "/favicon.ico", minute=2),
        # mixed-enrichment datacenter IP: NULL-asn page+asset rows PLUS a
        # tagged AWS row — must never count, whatever the checkbox state
        _row("100.64.6.6", "/", minute=1),
        _row("100.64.6.6", "/app.js", minute=2),
        _row("100.64.6.6", "/pricing", asn=16509, asn_org="AMAZON-02", minute=3),
        # returning visitor: 304 document + 304 asset (cache revalidation)
        _row("100.64.7.7", "/", status=304, asn=7018, asn_org="ATT-INTERNET4", minute=1),
        _row("100.64.7.7", "/themes.css", status=304, asn=7018, asn_org="ATT-INTERNET4", minute=2),
        # UA bot with page+assets: never a person, even with Hide bots off
        _row("100.64.8.8", "/", ua="Mozilla/5.0 (compatible; GPTBot/1.4)", minute=1),
        _row("100.64.8.8", "/app.js", ua="Mozilla/5.0 (compatible; GPTBot/1.4)", minute=2),
        # iCloud Private Relay human: Cloudflare ASN but page+assets pass
        _row("100.64.9.9", "/", asn=13335, asn_org="CLOUDFLARENET", minute=1),
        _row("100.64.9.9", "/app.js", asn=13335, asn_org="CLOUDFLARENET", minute=2),
        # self-traffic: remote_addr equals a monitored server's own IP
        _row("10.0.0.1", "/", asn=7922, asn_org="COMCAST-7922", minute=1),
        _row("10.0.0.1", "/app.js", asn=7922, asn_org="COMCAST-7922", minute=2),
    ]
    inserted = insert_requests(con, "web-1", rows)
    assert inserted == len(rows)
    return con


def test_verified_visitors_excludes_fleet_scanner_datacenter(tmp_path):
    con = _seed(tmp_path)
    n = fetch_verified_visitors(con, ("web-1",), SINCE, UNTIL, _filters())
    # people: Comcast human, NULL-asn human, 304 returning visitor, relay human
    assert n == 4


def test_verified_visitors_stable_across_checkboxes(tmp_path):
    """Mixed NULL/DC-tagged IPs and UA bots stay excluded whatever the filters."""
    con = _seed(tmp_path)
    for f in (
        _filters(),
        _filters(hide_datacenter=True),
        _filters(hide_bots=True, hide_service=True, hide_datacenter=True),
    ):
        assert fetch_verified_visitors(con, ("web-1",), SINCE, UNTIL, f) == 4


def test_hide_datacenter_row_filter_drops_tencent(tmp_path):
    con = _seed(tmp_path)
    kpis_all = fetch_kpis(con, ("web-1",), SINCE, UNTIL, _filters())
    kpis_dc = fetch_kpis(con, ("web-1",), SINCE, UNTIL, _filters(hide_datacenter=True))
    assert kpis_all.unique_ips == 10
    # hidden: tencent rows + the Cloudflare rows (%cloud% hides them at row
    # level; the relay exemption applies only to the People KPI); the mixed
    # IP survives via its NULL-asn rows
    assert kpis_dc.unique_ips == 8


def test_fetch_first_ts_reports_actual_coverage(tmp_path):
    con = _seed(tmp_path)
    first = fetch_first_ts(con, ("web-1",), SINCE, UNTIL, _filters())
    assert first is not None
    assert first.startswith((NOW - timedelta(hours=1, minutes=3)).isoformat()[:13])
