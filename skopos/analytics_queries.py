"""SQL-side analytics aggregates — full period accuracy, no row sampling.

Computes KPIs and chart series in the database so the dashboard does not
materialize every http_requests row into pandas.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pandas as pd

from .analytics_filters import AnalyticsFilterState
from .db import DbConnection, read_sql_query
from .traffic import SERVICE_PATH_PATTERN, SERVICE_UA_PATTERN

# Keep bot path filter aligned with dashboard.py BOT_SCAN_PATTERN (common cases).
_BOT_PATH_SQL_FRAGMENTS = (
    "%/wp-%",
    "%/wordpress%",
    "%/xmlrpc.php%",
    "%/wp-admin%",
    "%/wp-login.php%",
    "%/phpmyadmin%",
    "%/pma/%",
    "%/cgi-bin/%",
    "%/.env%",
    "%/.git/%",
    "%/vendor/phpunit%",
)


@dataclass(frozen=True)
class AnalyticsKpis:
    requests: int
    unique_ips: int
    countries: int
    pages: int
    hosts: int


def _server_placeholders(servers: tuple[str, ...]) -> str:
    return ",".join("?" * len(servers)) if servers else "''"


def period_where_sql(servers: tuple[str, ...]) -> str:
    """Index-friendly period filter on canonical ts_utc (file logs only)."""
    ph = _server_placeholders(servers)
    return f"""
      log_source LIKE 'file:%'
        AND server_name IN ({ph})
        AND ts_utc IS NOT NULL
        AND ts_utc >= ?
        AND ts_utc <= ?
    """


def period_params(servers: tuple[str, ...], since_utc_iso: str, until_utc_iso: str) -> list[Any]:
    return list(servers) + [since_utc_iso, until_utc_iso]


def _like_escape(value: str) -> str:
    return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def filters_sql(
    filters: AnalyticsFilterState,
    *,
    backend: str,
) -> tuple[str, list[Any]]:
    """Return extra AND … clauses + params mirroring dashboard `_apply_filters`."""
    clauses: list[str] = []
    params: list[Any] = []

    if filters.sel_servers:
        ph = ",".join("?" * len(filters.sel_servers))
        clauses.append(f"server_name IN ({ph})")
        params.extend(filters.sel_servers)
    if filters.sel_hosts:
        ph = ",".join("?" * len(filters.sel_hosts))
        clauses.append(f"host IN ({ph})")
        params.extend(filters.sel_hosts)
    if filters.sel_countries:
        ph = ",".join("?" * len(filters.sel_countries))
        clauses.append(f"country_code IN ({ph})")
        params.extend(filters.sel_countries)
    if filters.path_contains.strip():
        clauses.append("path LIKE ? ESCAPE '\\'")
        params.append(f"%{_like_escape(filters.path_contains.strip())}%")

    if filters.hide_bots:
        clauses.append("(ua_is_bot IS NULL OR ua_is_bot != 1)")
        for frag in _BOT_PATH_SQL_FRAGMENTS:
            clauses.append("path NOT LIKE ? ESCAPE '\\'")
            params.append(frag)
        clauses.append("(path IS NULL OR path NOT LIKE '%.php')")

    if filters.hide_service:
        # Approximate SERVICE_UA_PATTERN / SERVICE_PATH_PATTERN with LIKE prefixes.
        ua_prefixes = (
            "alien-monitor%",
            "AlienMonitor%",
            "node%",
            "dioscuri%",
            "python-httpx%",
            "TLM-Audit%",
            "Go-http-client%",
            "curl%",
            "wget%",
            "okhttp%",
        )
        ua_parts = " OR ".join(["LOWER(COALESCE(user_agent, '')) LIKE ?"] * len(ua_prefixes))
        path_parts = " OR ".join(
            [
                "path LIKE ?",
                "path LIKE ?",
                "path LIKE ?",
                "path LIKE ?",
                "path LIKE ?",
            ]
        )
        clauses.append(f"NOT (({ua_parts}) OR ({path_parts}))")
        params.extend(p.lower() for p in ua_prefixes)
        params.extend(
            [
                "%/api/health",
                "%/monitor/api/state%",
                "%/monitor/api/argus/run%",
                "%/monitor/api/chain/status%",
                "%/monitor/api/health",
            ]
        )
        _ = (SERVICE_UA_PATTERN, SERVICE_PATH_PATTERN, backend)  # documented parity

    if filters.visitors_only:
        # Exclude common private / loopback ranges (same intent as is_private_ip).
        for prefix in (
            "10.%",
            "127.%",
            "192.168.%",
            "169.254.%",
            "0.%",
            "::1%",
            "fc%",
            "fd%",
            "fe80%",
        ):
            clauses.append("remote_addr NOT LIKE ?")
            params.append(prefix)
        for i in range(16, 32):
            clauses.append("remote_addr NOT LIKE ?")
            params.append(f"172.{i}.%")

    if not clauses:
        return "", []
    return " AND " + " AND ".join(clauses), params


def _base(
    con: DbConnection,
    servers: tuple[str, ...],
    since: str,
    until: str,
    filters: AnalyticsFilterState,
) -> tuple[str, list[Any]]:
    where = period_where_sql(servers)
    params = period_params(servers, since, until)
    extra, extra_params = filters_sql(filters, backend=con.backend)
    return where + extra, params + extra_params


def fetch_filter_options(
    con: DbConnection,
    servers: tuple[str, ...],
    since: str,
    until: str,
) -> tuple[list[str], list[str]]:
    where = period_where_sql(servers)
    params = period_params(servers, since, until)
    hosts = read_sql_query(
        f"SELECT DISTINCT host AS v FROM http_requests WHERE {where} AND host IS NOT NULL AND host != ''",
        con,
        params=params,
    )
    countries = read_sql_query(
        f"""
        SELECT DISTINCT country_code AS v FROM http_requests
        WHERE {where} AND country_code IS NOT NULL AND country_code != '' AND country_code != 'INT'
        """,
        con,
        params=params,
    )
    host_opts = sorted({str(v) for v in hosts["v"].tolist() if v}) if not hosts.empty else []
    country_opts = sorted({str(v) for v in countries["v"].tolist() if v}) if not countries.empty else []
    return host_opts, country_opts


def fetch_kpis(
    con: DbConnection,
    servers: tuple[str, ...],
    since: str,
    until: str,
    filters: AnalyticsFilterState,
) -> AnalyticsKpis:
    where, params = _base(con, servers, since, until, filters)
    df = read_sql_query(
        f"""
        SELECT
          COUNT(*) AS requests,
          COUNT(DISTINCT remote_addr) AS unique_ips,
          COUNT(DISTINCT CASE
            WHEN country_code IS NOT NULL AND country_code != 'INT' THEN country_code END
          ) AS countries,
          COUNT(DISTINCT path) AS pages,
          COUNT(DISTINCT host) AS hosts
        FROM http_requests
        WHERE {where}
        """,
        con,
        params=params,
    )
    if df.empty:
        return AnalyticsKpis(0, 0, 0, 0, 0)
    row = df.iloc[0]
    return AnalyticsKpis(
        requests=int(row["requests"] or 0),
        unique_ips=int(row["unique_ips"] or 0),
        countries=int(row["countries"] or 0),
        pages=int(row["pages"] or 0),
        hosts=int(row["hosts"] or 0),
    )


def fetch_country_stats(
    con: DbConnection,
    servers: tuple[str, ...],
    since: str,
    until: str,
    filters: AnalyticsFilterState,
) -> pd.DataFrame:
    where, params = _base(con, servers, since, until, filters)
    return read_sql_query(
        f"""
        SELECT
          country_code,
          MAX(country_name) AS country_name,
          COUNT(*) AS requests,
          COUNT(DISTINCT remote_addr) AS visitors
        FROM http_requests
        WHERE {where}
          AND country_code IS NOT NULL
          AND country_code != 'INT'
        GROUP BY country_code
        ORDER BY requests DESC
        """,
        con,
        params=params,
    )


def fetch_timeline(
    con: DbConnection,
    servers: tuple[str, ...],
    since: str,
    until: str,
    filters: AnalyticsFilterState,
    *,
    granularity: str = "hour",
) -> pd.DataFrame:
    where, params = _base(con, servers, since, until, filters)
    if con.backend == "postgresql":
        trunc = "hour" if granularity == "hour" else "day"
        bucket = f"date_trunc('{trunc}', ts_utc::timestamptz)"
    else:
        fmt = "%Y-%m-%d %H:00:00" if granularity == "hour" else "%Y-%m-%d"
        bucket = f"strftime('{fmt}', ts_utc)"
    df = read_sql_query(
        f"""
        SELECT {bucket} AS bucket,
               COUNT(*) AS requests,
               COUNT(DISTINCT remote_addr) AS visitors
        FROM http_requests
        WHERE {where}
        GROUP BY 1
        ORDER BY 1
        """,
        con,
        params=params,
    )
    if not df.empty:
        df["bucket"] = pd.to_datetime(df["bucket"], errors="coerce", utc=True)
    return df


def fetch_heatmap(
    con: DbConnection,
    servers: tuple[str, ...],
    since: str,
    until: str,
    filters: AnalyticsFilterState,
) -> pd.DataFrame:
    where, params = _base(con, servers, since, until, filters)
    if con.backend == "postgresql":
        dow = "EXTRACT(ISODOW FROM ts_utc::timestamptz)::int"  # 1=Mon … 7=Sun
        hour = "EXTRACT(HOUR FROM ts_utc::timestamptz)::int"
    else:
        # SQLite: strftime %w is 0=Sun … 6=Sat → map to ISO (1=Mon … 7=Sun)
        dow = "((CAST(strftime('%w', ts_utc) AS INTEGER) + 6) % 7) + 1"
        hour = "CAST(strftime('%H', ts_utc) AS INTEGER)"
    return read_sql_query(
        f"""
        SELECT {dow} AS dow, {hour} AS hour, COUNT(*) AS requests
        FROM http_requests
        WHERE {where}
        GROUP BY 1, 2
        """,
        con,
        params=params,
    )


def fetch_status_classes(
    con: DbConnection,
    servers: tuple[str, ...],
    since: str,
    until: str,
    filters: AnalyticsFilterState,
) -> pd.DataFrame:
    where, params = _base(con, servers, since, until, filters)
    if con.backend == "postgresql":
        klass = "(status / 100)::int || 'xx'"
    else:
        klass = "(status / 100) || 'xx'"
    return read_sql_query(
        f"""
        SELECT {klass} AS class, COUNT(*) AS requests
        FROM http_requests
        WHERE {where} AND status IS NOT NULL
        GROUP BY 1
        ORDER BY 1
        """,
        con,
        params=params,
    )


def fetch_top_dimension(
    con: DbConnection,
    servers: tuple[str, ...],
    since: str,
    until: str,
    filters: AnalyticsFilterState,
    column: str,
    *,
    top_n: int = 15,
) -> pd.DataFrame:
    allowed = {
        "path",
        "host",
        "referer_domain",
        "remote_addr",
        "ua_browser",
        "ua_os",
        "ua_device",
        "ecosystem_segment",
    }
    if column not in allowed:
        raise ValueError(f"unsupported dimension: {column}")
    where, params = _base(con, servers, since, until, filters)
    return read_sql_query(
        f"""
        SELECT {column} AS {column}, COUNT(*) AS requests
        FROM http_requests
        WHERE {where}
          AND {column} IS NOT NULL
          AND CAST({column} AS TEXT) != ''
        GROUP BY {column}
        ORDER BY requests DESC
        LIMIT ?
        """,
        con,
        params=params + [top_n],
    )


def fetch_country_hourly(
    con: DbConnection,
    servers: tuple[str, ...],
    since: str,
    until: str,
    filters: AnalyticsFilterState,
    *,
    metric: str = "requests",
    top_n: int = 6,
) -> pd.DataFrame:
    """Hourly series for top countries (requests or unique visitors)."""
    countries = fetch_country_stats(con, servers, since, until, filters)
    if countries.empty:
        return countries
    sort_col = "requests" if metric == "requests" else "visitors"
    top_codes = countries.sort_values(sort_col, ascending=False).head(top_n)["country_code"].tolist()
    if not top_codes:
        return pd.DataFrame(columns=["hour", "country", "value"])

    where, params = _base(con, servers, since, until, filters)
    ph = ",".join("?" * len(top_codes))
    if con.backend == "postgresql":
        hour = "date_trunc('hour', ts_utc::timestamptz)"
    else:
        hour = "strftime('%Y-%m-%d %H:00:00', ts_utc)"
    value_expr = "COUNT(*)" if metric == "requests" else "COUNT(DISTINCT remote_addr)"
    df = read_sql_query(
        f"""
        SELECT {hour} AS hour,
               COALESCE(NULLIF(country_name, ''), country_code) AS country,
               {value_expr} AS value
        FROM http_requests
        WHERE {where} AND country_code IN ({ph})
        GROUP BY 1, 2
        ORDER BY 1
        """,
        con,
        params=params + top_codes,
    )
    if not df.empty:
        df["hour"] = pd.to_datetime(df["hour"], errors="coerce", utc=True)
    return df


def fetch_countries_by_host(
    con: DbConnection,
    servers: tuple[str, ...],
    since: str,
    until: str,
    filters: AnalyticsFilterState,
    *,
    metric: str = "requests",
    top_countries: int = 8,
) -> pd.DataFrame:
    countries = fetch_country_stats(con, servers, since, until, filters)
    if countries.empty:
        return countries
    sort_col = "requests" if metric == "requests" else "visitors"
    top_codes = countries.sort_values(sort_col, ascending=False).head(top_countries)["country_code"].tolist()
    where, params = _base(con, servers, since, until, filters)
    ph = ",".join("?" * len(top_codes))
    value_expr = "COUNT(*)" if metric == "requests" else "COUNT(DISTINCT remote_addr)"
    return read_sql_query(
        f"""
        SELECT host,
               COALESCE(NULLIF(country_name, ''), country_code) AS country,
               {value_expr} AS value
        FROM http_requests
        WHERE {where}
          AND host IS NOT NULL AND host != ''
          AND country_code IN ({ph})
        GROUP BY host, country_code, country_name
        ORDER BY value DESC
        """,
        con,
        params=params + top_codes,
    )


def fetch_treemap(
    con: DbConnection,
    servers: tuple[str, ...],
    since: str,
    until: str,
    filters: AnalyticsFilterState,
    *,
    limit: int = 40,
) -> pd.DataFrame:
    where, params = _base(con, servers, since, until, filters)
    return read_sql_query(
        f"""
        SELECT host, path, COUNT(*) AS requests
        FROM http_requests
        WHERE {where} AND host IS NOT NULL AND path IS NOT NULL
        GROUP BY host, path
        ORDER BY requests DESC
        LIMIT ?
        """,
        con,
        params=params + [limit],
    )


def fetch_source_stats(
    con: DbConnection,
    servers: tuple[str, ...],
    since: str,
    until: str,
    filters: AnalyticsFilterState,
) -> tuple[int, int]:
    where, params = _base(con, servers, since, until, filters)
    df = read_sql_query(
        f"""
        SELECT
          COUNT(*) AS total,
          COUNT(referer_domain) AS with_referer
        FROM http_requests
        WHERE {where}
        """,
        con,
        params=params,
    )
    if df.empty:
        return 0, 0
    total = int(df.iloc[0]["total"] or 0)
    with_ref = int(df.iloc[0]["with_referer"] or 0)
    return total - with_ref, with_ref


def fetch_journal(
    con: DbConnection,
    servers: tuple[str, ...],
    since: str,
    until: str,
    filters: AnalyticsFilterState,
    *,
    limit: int = 1000,
) -> pd.DataFrame:
    """Ordered row sample for the visit log only (not used for KPIs/charts)."""
    where, params = _base(con, servers, since, until, filters)
    df = read_sql_query(
        f"""
        SELECT
          ts_utc, server_name, host, server_ip, remote_addr,
          country_code, country_name,
          ua_browser, ua_os, ua_device, user_agent,
          method, path, status, referer_domain
        FROM http_requests
        WHERE {where}
        ORDER BY ts_utc DESC
        LIMIT ?
        """,
        con,
        params=params + [limit],
    )
    if "ts_utc" in df.columns:
        df["ts_utc"] = pd.to_datetime(df["ts_utc"], errors="coerce", utc=True)
    return df


def fetch_has_traffic(
    con: DbConnection,
    servers: tuple[str, ...],
    since: str,
    until: str,
) -> bool:
    where = period_where_sql(servers)
    params = period_params(servers, since, until)
    df = read_sql_query(
        f"SELECT 1 AS ok FROM http_requests WHERE {where} LIMIT 1",
        con,
        params=params,
    )
    return not df.empty


def fetch_traffic_snapshot(
    con: DbConnection,
    servers: tuple[str, ...],
    since: str,
    until: str,
    filters: AnalyticsFilterState,
) -> dict[str, Any]:
    """Compact traffic stats for the ecosystem briefing card."""
    where, params = _base(con, servers, since, until, filters)
    df = read_sql_query(
        f"""
        SELECT
          COUNT(*) AS requests,
          COUNT(DISTINCT remote_addr) AS unique_ips,
          COUNT(DISTINCT host) AS active_hosts,
          SUM(CASE WHEN status >= 500 THEN 1 ELSE 0 END) AS errors
        FROM http_requests
        WHERE {where}
        """,
        con,
        params=params,
    )
    seg = read_sql_query(
        f"""
        SELECT COALESCE(ecosystem_segment, 'other') AS seg, COUNT(*) AS n
        FROM http_requests
        WHERE {where}
        GROUP BY 1
        ORDER BY n DESC
        LIMIT 1
        """,
        con,
        params=params,
    )
    if df.empty:
        return {
            "requests": 0,
            "unique_ips": 0,
            "active_hosts": 0,
            "error_rate_pct": 0.0,
            "top_segment": None,
            "top_segment_share_pct": 0.0,
        }
    row = df.iloc[0]
    requests = int(row["requests"] or 0)
    errors = int(row["errors"] or 0)
    top_segment = None
    top_share = 0.0
    if not seg.empty and requests:
        top_segment = str(seg.iloc[0]["seg"])
        top_share = round(int(seg.iloc[0]["n"]) / requests * 100, 1)
    return {
        "requests": requests,
        "unique_ips": int(row["unique_ips"] or 0),
        "active_hosts": int(row["active_hosts"] or 0),
        "error_rate_pct": round(errors / requests * 100, 1) if requests else 0.0,
        "top_segment": top_segment,
        "top_segment_share_pct": top_share,
    }
