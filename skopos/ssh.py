from __future__ import annotations

import os
from dataclasses import dataclass

import paramiko


@dataclass(frozen=True)
class SSHConnInfo:
    host: str
    port: int
    user: str
    key_path: str | None = None
    key_passphrase_env: str | None = None


def _load_pkey(key_path: str, passphrase: str | None) -> paramiko.PKey:
    path = os.path.expanduser(key_path)
    if not os.path.isfile(path):
        raise FileNotFoundError(f"SSH key not found: {path}")
    last_err: Exception | None = None
    for cls in (paramiko.Ed25519Key, paramiko.RSAKey, paramiko.ECDSAKey):
        try:
            return cls.from_private_key_file(path, password=passphrase)
        except PermissionError as e:
            raise PermissionError(
                f"SSH key not readable (check permissions, should be 600): {path}"
            ) from e
        except Exception as e:  # noqa: BLE001 - try next key type
            last_err = e
    assert last_err is not None
    raise last_err


def run_command(info: SSHConnInfo, command: str, timeout_s: int = 20) -> str:
    passphrase = None
    if info.key_passphrase_env:
        passphrase = os.environ.get(info.key_passphrase_env)

    client = paramiko.SSHClient()
    strict = os.environ.get("SKOPOS_SSH_STRICT_HOST_KEYS", "").lower() in ("1", "true", "yes")
    if strict:
        try:
            client.load_system_host_keys()
        except Exception:
            pass
        client.set_missing_host_key_policy(paramiko.RejectPolicy())
    else:
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

    pkey = None
    if info.key_path:
        pkey = _load_pkey(info.key_path, passphrase)

    client.connect(
        hostname=info.host,
        port=info.port,
        username=info.user,
        pkey=pkey,
        timeout=timeout_s,
        banner_timeout=timeout_s,
        auth_timeout=timeout_s,
    )
    try:
        stdin, stdout, stderr = client.exec_command(command, timeout=timeout_s)
        _ = stdin  # unused
        out = stdout.read().decode("utf-8", errors="replace")
        err = stderr.read().decode("utf-8", errors="replace")
        if err.strip():
            # Don't fail hard — nginx logs can produce benign warnings depending on shell.
            out = out + ("\n" if out and not out.endswith("\n") else "") + f"# STDERR:\n{err}"
        return out
    finally:
        client.close()

