"""The op catalogue is the security boundary for a restricted collector key.

If a value can reach ``op.token``, it can reach the far end of an SSH key that is
pinned to ``skopos-collect``. These tests pin down what is expressible.
"""

from __future__ import annotations

import pytest

from skopos import remote_ops, remote_scripts
from skopos.remote_ops import (
    FIXED_OPS,
    OP_NAMES,
    PARAM_OPS,
    OpError,
    RemoteOp,
    op_docker_logs,
    op_tail,
    run_op,
    ssh_info,
)
from skopos.ssh import SSHConnInfo


class _Server:
    """Stand-in for ServerConfig — only ``.ssh`` is read by ssh_info()."""

    def __init__(self, **ssh):
        self.ssh = type("SSH", (), {
            "host": "203.0.113.10",
            "port": 22,
            "user": "skopos",
            "key_path": "/root/.ssh/id_ed25519",
            "key_passphrase_env": None,
            "mode": "direct",
            "known_hosts_path": None,
            **ssh,
        })()


# --- The catalogue itself ---------------------------------------------------

def test_every_script_is_present_and_banner_shaped():
    for name in ("PROBE", "PORT_KNOCKS", "DISCOVER_DOCKER", "DISCOVER_NGINX_LOGS",
                 "DISCOVER_APACHE_LOGS"):
        script = getattr(remote_scripts, name)
        assert script.strip(), f"{name} is empty"

    # The parsers split on these banners; losing one silently empties a section.
    assert "===META===" in remote_scripts.PROBE
    assert "===DOCKER===" in remote_scripts.PROBE
    assert "===FAIL2BAN===" in remote_scripts.PROBE
    assert "===AUTH===" in remote_scripts.PORT_KNOCKS
    assert "===UFW===" in remote_scripts.PORT_KNOCKS


def test_fixed_ops_carry_no_arguments_and_are_all_named():
    for name, op in FIXED_OPS.items():
        assert op.args == ()
        assert op.token == name
        assert op.script.strip()
    assert set(OP_NAMES) == set(FIXED_OPS) | set(PARAM_OPS)


def test_protocol_version_is_an_int():
    # The wrapper compares against this; a string would compare unequal forever.
    assert isinstance(remote_ops.PROTOCOL_VERSION, int)


# --- Token grammar ----------------------------------------------------------

def test_tail_token_and_script_agree():
    op = op_tail("/var/log/nginx/access.log", 4000)
    assert op.token == "tail /var/log/nginx/access.log 4000"
    assert "tail -n 4000 /var/log/nginx/access.log" in op.script


def test_docker_logs_token_and_script_agree():
    op = op_docker_logs("metis-skopos", 500)
    assert op.token == "docker-logs metis-skopos 500"
    assert "docker logs --tail 500 metis-skopos" in op.script


@pytest.mark.parametrize(
    "path",
    [
        "/var/log/x;rm -rf /",          # command chaining
        "/var/log/$(id).log",           # command substitution
        "/var/log/`id`.log",            # backtick substitution
        "/var/log/a|b.log",             # pipe
        "/var/log/a&b.log",             # background
        "relative/path.log",            # not absolute
        "/var/log/../../etc/shadow",    # traversal out of the log tree
        "/var/log/with space.log",      # breaks the whitespace-delimited token
        "-/var/log/access.log",         # option injection
        "/var/log/nl\nline.log",        # embedded newline
        "",                             # empty
    ],
)
def test_tail_rejects_anything_it_cannot_express_safely(path):
    with pytest.raises((OpError, ValueError)):
        op_tail(path, 100)


@pytest.mark.parametrize(
    "name",
    ["a b", "a;b", "a$(id)", "-rm", "", "a\nb", "../etc", "a|b"],
)
def test_docker_logs_rejects_bad_container_names(name):
    with pytest.raises((OpError, ValueError)):
        op_docker_logs(name, 100)


def test_no_token_can_contain_whitespace_in_an_argument():
    # The wrapper splits the token on whitespace, so an argument that contains
    # any would silently become two arguments — or a smuggled second parameter.
    for op in (op_tail("/var/log/nginx/access.log", 100),
               op_docker_logs("web-1", 100)):
        assert len(op.token.split()) == 1 + len(op.args)


def test_line_counts_are_clamped_both_ways():
    assert op_tail("/var/log/a.log", 1).token.endswith(" 100")
    assert op_tail("/var/log/a.log", 10**9).token.endswith(" 100000")
    # A float or numeric string must not smuggle anything into the token.
    assert op_tail("/var/log/a.log", 250.7).token.endswith(" 250")


# --- Transport selection ----------------------------------------------------

def test_ssh_info_maps_wrapper_mode_to_forced_command():
    assert ssh_info(_Server(mode="direct")).forced_command is False
    assert ssh_info(_Server(mode="wrapper")).forced_command is True


def test_ssh_info_carries_the_known_hosts_override():
    assert ssh_info(_Server(known_hosts_path="/etc/skopos/kh")).known_hosts_path == "/etc/skopos/kh"


def test_run_op_sends_the_script_in_direct_mode(monkeypatch):
    sent = {}

    def fake(info, command, timeout_s=20):
        sent["command"] = command
        return "out"

    monkeypatch.setattr(remote_ops, "run_command", fake)
    op = op_tail("/var/log/nginx/access.log", 4000)
    run_op(SSHConnInfo(host="h", port=22, user="u", forced_command=False), op)
    assert sent["command"] == op.script


def test_run_op_sends_only_the_token_in_wrapper_mode(monkeypatch):
    sent = {}

    def fake(info, command, timeout_s=20):
        sent["command"] = command
        return "out"

    monkeypatch.setattr(remote_ops, "run_command", fake)
    op = op_tail("/var/log/nginx/access.log", 4000)
    run_op(SSHConnInfo(host="h", port=22, user="u", forced_command=True), op)
    assert sent["command"] == "tail /var/log/nginx/access.log 4000"
    # Crucially, no shell fragment crosses the wire in this mode.
    assert "tail -n" not in sent["command"]
    assert "||" not in sent["command"]


def test_run_op_uses_the_ops_own_timeout(monkeypatch):
    seen = {}

    def fake(info, command, timeout_s=20):
        seen["timeout"] = timeout_s
        return ""

    monkeypatch.setattr(remote_ops, "run_command", fake)
    run_op(SSHConnInfo(host="h", port=22, user="u"), RemoteOp("probe", (), "x", 90))
    assert seen["timeout"] == 90
