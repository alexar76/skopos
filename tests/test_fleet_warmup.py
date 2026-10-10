"""Fleet warmup after servers.yaml save."""

from __future__ import annotations

from skopos.config import AppConfig, NginxConfig, SSHConfig, ServerConfig
from skopos.fleet_warmup import new_or_changed_server_names, warm_fleet_after_save


def _srv(name: str, host: str = "10.0.0.1") -> ServerConfig:
    return ServerConfig(
        name=name,
        source="nginx",
        ssh=SSHConfig(host=host, port=22, user="root", key_path="~/.ssh/id_ed25519"),
        nginx=NginxConfig(access_log_path="/var/log/nginx/access.log"),
    )


def test_new_or_changed_detects_add_and_host_change():
    before = [_srv("a"), _srv("b", host="1.1.1.1")]
    after = [_srv("a"), _srv("b", host="2.2.2.2"), _srv("c")]
    names = new_or_changed_server_names(before, after)
    assert names == ["b", "c"]


def test_warm_fleet_after_save_targets_new_only(monkeypatch):
    calls: list[set[str] | None] = []

    def fake_warm(cfg, *, server_names=None):
        calls.append(set(server_names) if server_names is not None else None)
        from skopos.fleet_warmup import FleetWarmupResult

        return FleetWarmupResult(
            server_names=tuple(server_names or ()),
            collect=(),
            scans=(),
        )

    monkeypatch.setattr("skopos.fleet_warmup.warm_fleet", fake_warm)
    before = [_srv("a")]
    after = AppConfig(db_path=":memory:", servers=[_srv("a"), _srv("b")])
    warm_fleet_after_save(after, previous_servers=before)
    assert calls and calls[0] == {"b"}
