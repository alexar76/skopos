"""Host-key verification and credential scoping for the SSH transport.

Two failure modes are guarded here. Unverified first contact hands the whole log
stream to whoever answers on the address; and paramiko's defaults will happily
authenticate with any key lying in the invoking user's ~/.ssh, which would undo
the point of giving each host its own least-privilege key.
"""

from __future__ import annotations

import paramiko
import pytest

from skopos import ssh as ssh_mod
from skopos.ssh import (
    DEFAULT_KNOWN_HOSTS,
    HostKeyUnknown,
    SSHConnInfo,
    known_hosts_file,
    strict_host_keys_enabled,
)


@pytest.fixture(autouse=True)
def _clear_env(monkeypatch):
    monkeypatch.delenv("SKOPOS_SSH_STRICT_HOST_KEYS", raising=False)
    monkeypatch.delenv("SKOPOS_KNOWN_HOSTS", raising=False)


def test_strict_host_keys_default_on():
    # The whole point of the change: forgetting the variable must not silently
    # downgrade to trust-anything.
    assert strict_host_keys_enabled() is True


@pytest.mark.parametrize("raw", ["0", "false", "FALSE", "no", "off", " off "])
def test_strict_host_keys_can_be_turned_off_explicitly(monkeypatch, raw):
    monkeypatch.setenv("SKOPOS_SSH_STRICT_HOST_KEYS", raw)
    assert strict_host_keys_enabled() is False


@pytest.mark.parametrize("raw", ["1", "true", "yes", "on", "", "anything-else"])
def test_anything_not_a_recognised_off_value_stays_strict(monkeypatch, raw):
    monkeypatch.setenv("SKOPOS_SSH_STRICT_HOST_KEYS", raw)
    assert strict_host_keys_enabled() is True


def test_known_hosts_precedence(monkeypatch, tmp_path):
    import os

    assert known_hosts_file() == os.path.expanduser(DEFAULT_KNOWN_HOSTS)

    monkeypatch.setenv("SKOPOS_KNOWN_HOSTS", str(tmp_path / "env"))
    assert known_hosts_file() == str(tmp_path / "env")

    per_server = SSHConnInfo(host="h", port=22, user="u", known_hosts_path=str(tmp_path / "srv"))
    assert known_hosts_file(per_server) == str(tmp_path / "srv")


def test_strict_mode_installs_reject_policy(monkeypatch, tmp_path):
    monkeypatch.setenv("SKOPOS_KNOWN_HOSTS", str(tmp_path / "kh"))
    client = ssh_mod._build_client(SSHConnInfo(host="h", port=22, user="u"))
    assert isinstance(client._policy, paramiko.RejectPolicy)


def test_relaxed_mode_installs_autoadd_policy(monkeypatch):
    monkeypatch.setenv("SKOPOS_SSH_STRICT_HOST_KEYS", "0")
    client = ssh_mod._build_client(SSHConnInfo(host="h", port=22, user="u"))
    assert isinstance(client._policy, paramiko.AutoAddPolicy)


def test_a_corrupt_trust_store_is_not_treated_as_trusting_nothing(monkeypatch, tmp_path):
    store = tmp_path / "kh"
    store.write_bytes(b"\xff\xfe not a known_hosts file\n")
    monkeypatch.setenv("SKOPOS_KNOWN_HOSTS", str(store))

    def explode(self, path):
        raise OSError("boom")

    monkeypatch.setattr(paramiko.SSHClient, "load_host_keys", explode)
    with pytest.raises(HostKeyUnknown):
        ssh_mod._build_client(SSHConnInfo(host="h", port=22, user="u"))


class _FakeClient:
    """Records what connect() was asked to do."""

    last_kwargs: dict = {}

    def __init__(self):
        self._policy = None

    def load_host_keys(self, path):
        pass

    def load_system_host_keys(self):
        pass

    def set_missing_host_key_policy(self, policy):
        self._policy = policy

    def connect(self, **kwargs):
        _FakeClient.last_kwargs = kwargs

    def close(self):
        pass


def test_connect_refuses_to_fall_back_to_other_credentials(monkeypatch):
    monkeypatch.setattr(paramiko, "SSHClient", _FakeClient)
    monkeypatch.setattr(ssh_mod, "_load_pkey", lambda path, passphrase: "PKEY")

    ssh_mod.connect(SSHConnInfo(host="h", port=2222, user="skopos", key_path="/k"))

    kwargs = _FakeClient.last_kwargs
    assert kwargs["allow_agent"] is False, "an agent socket would widen the key set"
    assert kwargs["look_for_keys"] is False, "~/.ssh scanning would widen the key set"
    assert kwargs["pkey"] == "PKEY"
    assert kwargs["username"] == "skopos"
    assert kwargs["port"] == 2222


def test_unknown_host_error_tells_the_operator_what_to_run(monkeypatch):
    class Rejecting(_FakeClient):
        def connect(self, **kwargs):
            raise paramiko.SSHException("Server 'h' not found in known_hosts")

    monkeypatch.setattr(paramiko, "SSHClient", Rejecting)
    monkeypatch.setattr(ssh_mod, "_load_pkey", lambda path, passphrase: "PKEY")

    with pytest.raises(HostKeyUnknown) as exc:
        ssh_mod.connect(SSHConnInfo(host="h", port=22, user="u", key_path="/k"))
    assert "trust-host" in str(exc.value)


def test_remember_host_key_round_trips(tmp_path):
    key = paramiko.RSAKey.generate(2048)
    target = tmp_path / "nested" / "known_hosts"

    written = ssh_mod.remember_host_key("203.0.113.10", 22, key, path=str(target))
    assert written == str(target)

    hostkeys = paramiko.HostKeys()
    hostkeys.load(written)
    assert hostkeys.lookup("203.0.113.10") is not None

    # A non-default port is stored in the bracketed form OpenSSH uses.
    ssh_mod.remember_host_key("203.0.113.11", 2222, key, path=str(target))
    hostkeys = paramiko.HostKeys()
    hostkeys.load(written)
    assert hostkeys.lookup("[203.0.113.11]:2222") is not None


def test_trust_store_is_not_world_readable(tmp_path):
    import stat

    key = paramiko.RSAKey.generate(2048)
    target = tmp_path / "known_hosts"
    ssh_mod.remember_host_key("h", 22, key, path=str(target))
    mode = stat.S_IMODE(target.stat().st_mode)
    assert mode == 0o600
