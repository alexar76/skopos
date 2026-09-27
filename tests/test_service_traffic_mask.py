"""Vectorized service-traffic mask."""

from skopos.traffic import is_service_traffic, service_traffic_mask


def test_service_traffic_mask_matches_scalar():
    uas = ["curl/8.0", "Mozilla/5.0", "python-httpx/0.27", "Chrome"]
    paths = ["/", "/api/health", "/page", "/monitor/api/state"]
    mask = service_traffic_mask(uas, paths)
    for i, (ua, path) in enumerate(zip(uas, paths)):
        assert bool(mask.iloc[i]) == is_service_traffic(user_agent=ua, path=path)
