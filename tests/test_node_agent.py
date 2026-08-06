"""The host agent, driven directly with hostile input.

These tests never go through SKOPOS's own validation. That is the point: the
agent is the only thing standing between a stolen collector key and the host, so
it has to hold on its own, against a caller who has already replaced whatever
SKOPOS would have checked.
"""

from __future__ import annotations

import ast
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from skopos.node_agent import AGENT_SOURCE_PATH, agent_sha256, agent_version
from skopos.wrapper_gen import AGENT_COMMAND, authorized_keys_line, sshd_dropin

EXIT_REJECT = 92
EXIT_UNSAFE = 93


@pytest.fixture
def host(tmp_path):
    """A fake monitored host: a log root, a decoy outside it, and a config."""
    logs = tmp_path / "var" / "log" / "nginx"
    logs.mkdir(parents=True)
    (logs / "access.log").write_text(
        '203.0.113.9 - - [31/Jul/2026:10:00:00 +0000] "GET /a HTTP/1.1" 200 12 "-" "curl/8"\n'
    )
    secret = tmp_path / "secret.txt"
    secret.write_text("root-only-content\n")

    cfg = tmp_path / "config.json"
    cfg.write_text(json.dumps({
        "base_url": "https://skopos.example",
        "log_roots": [str(logs)],
        "privileged": False,
        "interval_s": 60,
    }))

    env = {
        **os.environ,
        "SKOPOS_NODE_CONFIG": str(cfg),
        "SKOPOS_NODE_STATE": str(tmp_path / "state.json"),
        "SKOPOS_NODE_RUN_DIR": str(tmp_path / "run"),
        # The harness cannot chown files to a different user; the agent reports
        # this as a problem in selftest so it can never pass unnoticed in prod.
        "SKOPOS_NODE_UNSAFE_SKIP_OWNERSHIP_CHECK": "1",
    }
    return type("Host", (), {
        "logs": logs, "secret": secret, "cfg": cfg, "env": env, "tmp": tmp_path,
    })


def run(host, *args, ssh_command=None):
    env = dict(host.env)
    if ssh_command is not None:
        env["SSH_ORIGINAL_COMMAND"] = ssh_command
    return subprocess.run(
        [sys.executable, str(AGENT_SOURCE_PATH), *args],
        env=env, capture_output=True, text=True, timeout=120,
    )


# --- Shipping constraints ---------------------------------------------------

def test_the_agent_never_imports_skopos():
    # It runs on someone else's server; importing the dashboard package there
    # would be both broken and a leak of what SKOPOS is.
    tree = ast.parse(AGENT_SOURCE_PATH.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                assert not alias.name.startswith("skopos"), alias.name
        elif isinstance(node, ast.ImportFrom):
            assert not (node.module or "").startswith("skopos"), node.module


def test_the_agent_uses_only_the_standard_library():
    third_party = {"requests", "yaml", "paramiko", "streamlit", "cryptography", "pydantic"}
    tree = ast.parse(AGENT_SOURCE_PATH.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        names = []
        if isinstance(node, ast.Import):
            names = [a.name.split(".")[0] for a in node.names]
        elif isinstance(node, ast.ImportFrom):
            names = [(node.module or "").split(".")[0]]
        for n in names:
            assert n not in third_party, f"{n} is not available on a monitored host"


def test_the_agent_hash_is_derivable():
    assert len(agent_sha256()) == 64
    assert agent_version().count(".") == 2


# --- The ssh-op vocabulary --------------------------------------------------

def test_ping_answers_with_its_capabilities(host):
    r = run(host, "ssh-op", ssh_command="v1 ping")
    assert r.returncode == 0, r.stderr
    payload = json.loads(r.stdout)
    assert payload["capabilities"] == ["ping", "collect"]
    assert payload["protocol"] == 1


def test_collect_returns_a_document(host):
    r = run(host, "ssh-op", ssh_command="v1 collect")
    assert r.returncode == 0, r.stderr
    doc = json.loads(r.stdout)
    assert doc["sources"][0]["lines"][0].startswith("203.0.113.9")


@pytest.mark.parametrize("request_str", [
    "",
    "collect",
    "ping",
    "v1",
    "v2 collect",
    "v1 collect extra",
    "v1 unknown",
    "v1 collect; id",
    "v1 collect && id",
    "v1 collect | id",
    "v1 $(id)",
    "v1 `id`",
    "v1 tail /etc/passwd 100",
    "v1 tail /var/log/nginx/access.log 100",
    "v1 docker-logs web 100",
    "v1 collect\nv1 ping",
    "V1 COLLECT",
    "v1  collect ",
])
def test_everything_outside_the_vocabulary_is_refused(host, request_str):
    r = run(host, "ssh-op", ssh_command=request_str)
    if request_str == "v1  collect ":
        # Extra whitespace is not an attack; splitting handles it.
        assert r.returncode == 0
        return
    assert r.returncode == EXIT_REJECT, f"{request_str!r} -> {r.returncode}: {r.stdout[:120]}"
    assert "SKOPOS_NODE_REJECT" in r.stderr
    assert "uid=" not in r.stdout, "a shell interpreted the request"


def test_an_overlong_request_is_refused(host):
    r = run(host, "ssh-op", ssh_command="v1 " + "a" * 5000)
    assert r.returncode == EXIT_REJECT
    assert "too long" in r.stderr


# --- What it will and will not read -----------------------------------------

def test_a_symlink_out_of_the_log_root_is_not_followed(host):
    os.symlink(host.secret, host.logs / "evil.access.log")
    r = run(host, "collect")
    assert r.returncode == 0
    assert "root-only-content" not in r.stdout
    doc = json.loads(r.stdout)
    assert any("evil.access.log" in e for e in doc["facts"]["collect_errors"])


def test_a_fifo_does_not_hang_the_collection(host):
    os.mkfifo(host.logs / "pipe.access.log")
    r = run(host, "collect")  # would block forever without O_NONBLOCK + S_ISREG
    assert r.returncode == 0
    assert "pipe.access.log" not in r.stdout or "lines" in r.stdout


def test_a_hard_link_into_the_log_root_is_refused(host):
    target = host.logs / "linked.access.log"
    try:
        os.link(host.secret, target)
    except OSError:
        pytest.skip("filesystem does not support hard links here")
    r = run(host, "collect")
    assert "root-only-content" not in r.stdout


def test_a_file_outside_the_roots_is_never_reachable(host):
    # There is no way to *ask* for one — the vocabulary has no path — so the
    # only route in would be config, which is root-owned on a real host.
    r = run(host, "collect")
    doc = json.loads(r.stdout)
    for source in doc["sources"]:
        assert source["id"].startswith("file:%s" % host.logs)


def test_it_refuses_to_run_as_root_without_an_explicit_override(host, monkeypatch):
    # Simulated: the real check is os.geteuid() == 0.
    src = AGENT_SOURCE_PATH.read_text(encoding="utf-8")
    assert 'os.geteuid() == 0' in src
    assert "SKOPOS_NODE_ALLOW_ROOT" in src
    assert "privileged collection belongs to" in src


# --- Documents it produces are ones SKOPOS accepts ---------------------------

def test_the_document_passes_the_servers_own_validator(host):
    from skopos.node_report import parse_report

    doc = json.loads(run(host, "collect").stdout)
    report = parse_report(doc)
    assert report.total_lines == 1


def test_the_document_carries_no_identity(host):
    doc = json.loads(run(host, "collect").stdout)
    assert "server_name" not in doc
    assert "server_ip" not in doc


def test_the_document_carries_no_parsed_fields(host):
    doc = json.loads(run(host, "collect").stdout)
    for source in doc["sources"]:
        assert set(source) <= {"id", "kind", "parser", "lines", "truncated"}


def test_selftest_reports_the_ownership_override(host):
    r = run(host, "selftest")
    payload = json.loads(r.stdout)
    assert any("OWNERSHIP_CHECK" in p for p in payload["problems"])


# --- The authorized_keys line -----------------------------------------------

def test_the_key_line_pins_the_agent_and_restricts():
    line = authorized_keys_line("ssh-ed25519 AAAAC3Nz comment")
    assert line.startswith(f'command="{AGENT_COMMAND}",restrict ')
    assert line.endswith("ssh-ed25519 AAAAC3Nz comment")


def test_the_key_line_can_pin_a_source_address():
    line = authorized_keys_line("ssh-ed25519 AAAA x", from_addresses=("10.8.0.2",))
    assert 'from="10.8.0.2"' in line


@pytest.mark.parametrize("key, addrs", [
    ("", ()),
    ("ssh-ed25519 AAAA x\nssh-ed25519 BBBB y", ()),          # a smuggled second key
    ("ssh-ed25519 AAAA x", ('1.2.3.4" command="/bin/sh',)),  # option injection
    ("ssh-ed25519 AAAA x", ("1.2.3.4 5.6.7.8",)),            # whitespace splits the line
    ("ssh-ed25519 AAAA x", ("0.0.0.0/0",)),                  # a restriction that restricts nothing
])
def test_the_key_line_refuses_to_build_something_dangerous(key, addrs):
    with pytest.raises(ValueError):
        authorized_keys_line(key, from_addresses=addrs)


def test_the_sshd_dropin_forces_the_command_and_nothing_else():
    text = sshd_dropin("skopos-node")
    assert "ForceCommand /usr/local/bin/skopos-node ssh-op" in text
    assert "AuthorizedKeysFile /etc/ssh/authorized_keys.d/%u" in text
    for off in ("PermitTTY no", "AllowTcpForwarding no", "AllowAgentForwarding no"):
        assert off in text


# --- The generated installer ------------------------------------------------

@pytest.mark.skipif(shutil.which("bash") is None, reason="bash is not available")
@pytest.mark.parametrize("push,key", [(True, ""), (False, "ssh-ed25519 AAAA c")])
def test_the_installer_is_a_valid_shell_script(tmp_path, push, key):
    from skopos.node_installer import render_installer

    script = tmp_path / "install.sh"
    script.write_text(render_installer(
        base_url="https://skopos.example",
        server_name="web-1",
        push=push,
        collector_public_key=key,
        containers=("metis-nginx",),
    ))
    r = subprocess.run(["bash", "-n", str(script)], capture_output=True, text=True)
    assert r.returncode == 0, r.stderr


@pytest.mark.skipif(shutil.which("bash") is None, reason="bash is not available")
def test_the_privileged_dumper_is_a_valid_shell_script(tmp_path):
    from skopos.node_installer import render_privdump

    script = tmp_path / "privdump.sh"
    script.write_text(render_privdump(containers=("a", "b")))
    assert subprocess.run(["bash", "-n", str(script)], capture_output=True).returncode == 0


def test_the_installer_never_embeds_a_long_lived_secret():
    from skopos.node_installer import render_installer

    text = render_installer(base_url="https://skopos.example", server_name="web-1")
    # The ticket goes in on stdin; the credential is minted server-side and
    # written straight to a 0600 file. Neither should be renderable into a file
    # the operator might leave on disk or paste into a chat.
    assert "secret_b64" in text, "the installer should receive one, not carry one"
    assert "$(cat)" in text or "TICKET=\"$(cat)\"" in text
    assert "--ticket" not in text


def test_the_installer_verifies_root_ownership_after_writing():
    from skopos.node_installer import render_installer

    text = render_installer(base_url="https://skopos.example", server_name="web-1")
    assert "is owned by $owner, not root" in text


def test_the_installer_never_grants_docker_or_sudo():
    from skopos.node_installer import render_installer

    text = render_installer(base_url="https://skopos.example", server_name="web-1")
    assert "usermod -aG docker" not in text
    assert "/etc/sudoers" not in text
    assert "NOPASSWD" not in text


# --- The two ends must agree on what the secret is --------------------------

def _load_agent_module():
    import importlib.util

    spec = importlib.util.spec_from_file_location("skopos_node_under_test", AGENT_SOURCE_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_the_agent_signs_with_the_bytes_the_server_verifies_against():
    """The credential file carries base64; HMAC needs the bytes it stands for.

    Signing with the encoded text produces a well-formed signature the server
    will never accept, and the only symptom is a 401 — indistinguishable from a
    wrong key, a revoked node, or a clock problem. This pins the decode.
    """
    import base64
    import hashlib
    import hmac as _hmac

    from skopos.node_protocol import verify

    agent = _load_agent_module()
    raw_secret = b"\x01\x02\x03" * 10 + b"\x04\x05"
    assert len(raw_secret) == 32

    # Exactly what the installer writes.
    credential = {"key_id": "nk_test", "secret_b64": base64.b64encode(raw_secret).decode()}
    assert agent.credential_secret(credential) == raw_secret

    body = b'{"protocol":1}'
    ts, seq = 1785485760, 7
    material = "\n".join(
        ("nk_test", str(ts), str(seq), hashlib.sha256(body).hexdigest())
    ).encode()
    signature = _hmac.new(agent.credential_secret(credential), material, hashlib.sha256).hexdigest()

    assert verify(raw_secret, signature, key_id="nk_test", timestamp=ts, seq=seq, body=body)


def test_a_credential_holding_raw_bytes_still_works():
    agent = _load_agent_module()
    assert agent.credential_secret({"secret_b64": b"\x00" * 32}) == b"\x00" * 32


def test_the_agent_advances_its_sequence_even_when_the_send_fails(tmp_path):
    """Mirror of the server-side contract: a number is spent per attempt.

    Without this the agent retries a seq the server already consumed and stays
    stuck on it — a permanently silent host whose only symptom is a 401.
    """
    agent = _load_agent_module()
    state_path = tmp_path / "state.json"
    agent.STATE_PATH = str(state_path)

    cfg = {"base_url": "https://skopos.invalid"}
    credential = {"key_id": "nk_x", "secret_b64": "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA="}

    for expected in (1, 2, 3):
        with pytest.raises(Exception):
            agent.send_report(cfg, credential, {"protocol": 1})
        assert json.loads(state_path.read_text())["seq"] == expected


# --- Fixes from the security audit ------------------------------------------

def test_one_oddly_named_file_does_not_silence_the_whole_host(host):
    """The server rejects a whole document over one bad source id.

    Anything that can write to a log directory — the web application itself, on
    most hosts — could otherwise create "a;b.log" and stop the host reporting at
    all. The agent drops what it cannot express instead of shipping it.
    """
    from skopos.node_report import parse_report

    (host.logs / "a;b-access.log").write_text("x\n")
    (host.logs / "ok-access.log").write_text(
        '198.51.100.1 - - [31/Jul/2026:10:00:00 +0000] "GET /z HTTP/1.1" 200 1 "-" "x"\n'
    )
    doc = json.loads(run(host, "collect").stdout)

    ids = [s["id"] for s in doc["sources"]]
    assert not any(";" in i for i in ids)
    assert any(i.endswith("ok-access.log") for i in ids)
    parse_report(doc)  # the server accepts it


def test_the_canonical_log_is_not_evicted_by_junk(host, monkeypatch):
    """A flood of matching filenames must not push access.log past the cap."""
    agent = _load_agent_module()
    for i in range(agent.MAX_SOURCES + 20):
        (host.logs / ("zzz%03d-access.log" % i)).write_text("x\n")

    cfg = {"log_roots": [str(host.logs)], "log_globs": ["*access*.log"]}
    found = agent.discover_logs(cfg)
    assert len(found) <= agent.MAX_SOURCES
    assert str(host.logs / "access.log") in found, "the real log was evicted"


@pytest.mark.parametrize("proposed, adopted", [
    (9, 9),        # a real catch-up
    (5, None),     # not forward
    (1, None),     # backwards
    (10**9, None), # absurd
])
def test_the_agent_only_adopts_a_sane_server_proposed_sequence(tmp_path, proposed, adopted):
    """next_seq is the one value the server gets to influence on the host.

    Adopting it blindly would let a hostile or broken server push the counter
    somewhere the node can never come back from.
    """
    import urllib.error

    agent = _load_agent_module()
    state = tmp_path / "state.json"
    agent.STATE_PATH = str(state)
    state.write_text(json.dumps({"seq": 5}))

    class FakeResponse:
        def read(self, n=None):
            return json.dumps({"next_seq": proposed}).encode()

        def close(self):
            pass

    def explode(request, timeout=None):
        raise urllib.error.HTTPError(
            "https://x", 409, "conflict", {}, FakeResponse()
        )

    class FakeOpener:
        open = staticmethod(explode)

    agent.urllib.request.build_opener = lambda *a, **k: FakeOpener()

    credential = {"key_id": "nk_x", "secret_b64": "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA="}
    with pytest.raises(Exception) as exc:
        agent.send_report({"base_url": "https://x"}, credential, {"protocol": 1})

    final = json.loads(state.read_text())["seq"]
    if adopted is None:
        assert "not a sane step" in str(exc.value)
        assert final == 6, "the burnt attempt still counts, but the hint was ignored"
    else:
        assert final == adopted


def test_the_sshd_dropin_closes_its_match_block():
    """sshd applies drop-ins in order; a file ending mid-Match captures the next."""
    text = sshd_dropin("skopos-node")
    body = text.strip().splitlines()
    assert body[-1].strip() == "Match all", body[-3:]


@pytest.mark.parametrize("bad", ["a b", "a;id", "", "a$b", "../x", "a'b"])
def test_the_installer_refuses_an_unsafe_server_name(bad):
    from skopos.node_installer import render_installer

    with pytest.raises(ValueError):
        render_installer(base_url="https://x.example", server_name=bad)


def test_the_acl_grant_keeps_directories_traversable():
    """`-m u:X:r` applied recursively strips +x and breaks nested log dirs."""
    from skopos.node_installer import render_installer

    text = render_installer(base_url="https://x.example", server_name="web-1")
    assert "setfacl -R -m u:skopos-node:rX" in text
    assert "setfacl -R -m u:skopos-node:r " not in text


def test_the_installer_reasserts_the_login_shell_on_an_existing_account():
    from skopos.node_installer import render_installer

    text = render_installer(
        base_url="https://x.example", server_name="web-1", push=False,
        collector_public_key="ssh-ed25519 AAAA c",
    )
    # A host converted from push keeps nologin otherwise, and ForceCommand needs
    # a shell to run the command with.
    assert "usermod --shell" in text


def test_an_agent_ssh_installer_does_not_try_to_enroll():
    from skopos.node_installer import render_installer

    text = render_installer(
        base_url="https://x.example", server_name="web-2", push=False,
        collector_public_key="ssh-ed25519 AAAA c",
    )
    assert "/node/v1/enroll" not in text
    assert "authorized_keys.d" in text
    assert "ForceCommand" in text


def test_ssh_op_collect_keeps_no_offsets(host):
    """Over SSH the agent never learns whether its output arrived.

    Advancing a read offset on the strength of having written to stdout makes
    every dropped connection a permanent hole in the fleet's logs — and
    deferring the commit by one call only moves the hole. So this path returns a
    bounded window every time and lets the server deduplicate: repeated, not
    lost.
    """
    state_path = Path(host.env["SKOPOS_NODE_STATE"])

    first = json.loads(run(host, "ssh-op", ssh_command="v1 collect").stdout)
    assert first["sources"], "nothing was collected to begin with"
    assert not state_path.exists() or "pending" not in json.loads(state_path.read_text())

    # A dropped connection must not cost us the lines.
    second = json.loads(run(host, "ssh-op", ssh_command="v1 collect").stdout)
    assert second["sources"], "the lines were consumed despite never being acknowledged"
    assert second["sources"][0]["lines"] == first["sources"][0]["lines"]


def test_the_push_path_does_track_offsets(host):
    """Push gets an acknowledgement, so it can honestly advance."""
    agent = _load_agent_module()
    agent.STATE_PATH = host.env["SKOPOS_NODE_STATE"]
    agent.CONFIG_PATH = host.env["SKOPOS_NODE_CONFIG"]
    agent.RUN_DIR = host.env["SKOPOS_NODE_RUN_DIR"]
    cfg = agent.load_config()

    state = {}
    first = agent.collect(cfg, state)
    assert first["sources"], "nothing collected"
    # The same state carried forward reports nothing new.
    second = agent.collect(cfg, state)
    assert not second["sources"]


def test_selftest_can_report_an_unsafe_install(host):
    """It exists to report exactly this, so it must survive reaching it."""
    r = run(host, "selftest")
    assert r.returncode in (0, 1)
    payload = json.loads(r.stdout)
    assert "problems" in payload
