from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass

from .config import AppConfig, load_config

_HTTP_LOG_SOURCES = frozenset({"ssh_nginx_access_log", "ssh_http_access_log"})
from .db import ParsedRequest, connect_for_config, init_db, insert_requests, upsert_collector_status
from .ecosystem import ecosystem_segment
from .enrich import parse_user_agent, referer_domain
from .geoip import GeoIPResolver, is_private_ip
from .host_infer import infer_host
from .log_sources import LogSource, fetch_lines, host_hint, parse_line, resolve_log_sources


@dataclass(frozen=True)
class CollectResult:
    server_name: str
    fetched_lines: int
    inserted_rows: int
    log_paths: tuple[str, ...]


def _enrich_request(
    pr: ParsedRequest,
    *,
    log_source: str,
    server_name: str,
    server_ip: str,
    host_fallback: str | None,
    geo: GeoIPResolver | None,
    geo_map: dict | None = None,
) -> ParsedRequest | None:
    # Skip docker internal noise — nginx already has the same public traffic.
    if log_source.startswith("docker:"):
        if not pr.remote_addr or is_private_ip(pr.remote_addr):
            return None

    host = pr.host or host_fallback
    seg = ecosystem_segment(pr.path, host=host, log_source=log_source)
    if not host:
        host = infer_host(
            pr.path,
            server_name=server_name,
            ecosystem_segment=seg,
            referer=pr.referer,
        )

    country_code = pr.country_code
    country_name = pr.country_name
    if geo and pr.remote_addr:
        if is_private_ip(pr.remote_addr):
            country_code = "INT"
            country_name = "Internal"
        elif geo_map is not None:
            info = geo_map.get(pr.remote_addr) or geo.country_for_ip(pr.remote_addr)
            country_code = info.iso_code
            country_name = info.name
        else:
            c = geo.country_for_ip(pr.remote_addr)
            country_code = c.iso_code
            country_name = c.name

    ua = parse_user_agent(pr.user_agent)
    return ParsedRequest(
        **{
            **pr.__dict__,
            "log_source": log_source,
            "ecosystem_segment": seg,
            "server_ip": server_ip,
            "host": host,
            "country_code": country_code,
            "country_name": country_name,
            "ua_browser": ua.browser,
            "ua_os": ua.os,
            "ua_device": ua.device,
            "ua_is_bot": (1 if ua.is_bot else 0) if ua.is_bot is not None else None,
            "referer_domain": referer_domain(pr.referer),
        }
    )


def _parse_source_line(source: LogSource, line: str) -> ParsedRequest | None:
    pr = parse_line(source, line)
    if not pr or not isinstance(pr, ParsedRequest):
        return None
    if not pr.method and not pr.remote_addr:
        return None
    return pr


def _make_geo(cfg: AppConfig) -> GeoIPResolver:
    path = getattr(cfg, "geoip_mmdb_path", None)
    return GeoIPResolver(path, api_fallback=True)


def collect_once(cfg: AppConfig) -> list[CollectResult]:
    con = connect_for_config(cfg)
    init_db(con)
    results: list[CollectResult] = []

    geo = _make_geo(cfg)
    per_source_batch = max(500, int(cfg.batch_lines_per_server))

    for s in cfg.servers:
        if s.source not in _HTTP_LOG_SOURCES:
            continue
        try:
            sources = resolve_log_sources(s)
            all_lines: list[tuple[LogSource, str]] = []
            source_ids: list[str] = []

            for src in sources:
                source_ids.append(src.id)
                for ln in fetch_lines(s, src, per_source_batch):
                    all_lines.append((src, ln))

            parsed: list[ParsedRequest] = []
            staged: list[tuple[LogSource, ParsedRequest]] = []
            for src, ln in all_lines:
                pr = _parse_source_line(src, ln)
                if not pr:
                    continue
                staged.append((src, pr))

            public_ips = [
                pr.remote_addr
                for _, pr in staged
                if pr.remote_addr and not is_private_ip(pr.remote_addr)
            ]
            geo_map = geo.prefetch_map(public_ips) if geo else {}

            for src, pr in staged:
                enriched = _enrich_request(
                    pr,
                    log_source=src.id,
                    server_name=s.name,
                    server_ip=s.ssh.host,
                    host_fallback=host_hint(src) if src.kind == "file" else None,
                    geo=geo,
                    geo_map=geo_map,
                )
                if enriched:
                    parsed.append(enriched)

            inserted = insert_requests(con, s.name, parsed)
            upsert_collector_status(
                con,
                server_name=s.name,
                ok=True,
                fetched_lines=len(all_lines),
                inserted_rows=inserted,
                log_paths=json.dumps(source_ids),
            )
            results.append(
                CollectResult(
                    server_name=s.name,
                    fetched_lines=len(all_lines),
                    inserted_rows=inserted,
                    log_paths=tuple(source_ids),
                )
            )
        except Exception as e:
            upsert_collector_status(con, server_name=s.name, ok=False, error=repr(e))
            results.append(
                CollectResult(server_name=s.name, fetched_lines=0, inserted_rows=0, log_paths=())
            )

    geo.close()
    con.close()
    return results


def run_forever(cfg: AppConfig | str) -> None:
    log = logging.getLogger(__name__)
    while True:
        live = load_config(cfg) if isinstance(cfg, str) else cfg
        try:
            _ = collect_once(live)
        except Exception:
            log.exception("Collector cycle failed")
        time.sleep(max(1, int(live.poll_interval_seconds)))
