"""Read/write project .env for secrets configured from the Settings UI."""

from __future__ import annotations

import re
from pathlib import Path


def project_env_path() -> Path:
    return Path(__file__).resolve().parents[1] / ".env"


def _format_env_value(value: str) -> str:
    if value == "":
        return ""
    if re.fullmatch(r"[\w.@+-]+", value):
        return value
    escaped = value.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")
    return f'"{escaped}"'


def upsert_env_var(name: str, value: str, *, env_path: Path | None = None) -> None:
    """Set or replace a single KEY=value line in .env."""
    key = name.strip()
    if not key or not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", key):
        raise ValueError(f"Invalid env var name: {name!r}")

    path = env_path or project_env_path()
    lines: list[str] = []
    if path.is_file():
        lines = path.read_text(encoding="utf-8").splitlines()

    pattern = re.compile(rf"^\s*{re.escape(key)}\s*=")
    new_line = f"{key}={_format_env_value(value)}"
    replaced = False
    out: list[str] = []
    for line in lines:
        if pattern.match(line):
            out.append(new_line)
            replaced = True
        else:
            out.append(line)
    if not replaced:
        if out and out[-1].strip():
            out.append("")
        out.append(new_line)

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(out).rstrip() + "\n", encoding="utf-8")


def remove_env_var(name: str, *, env_path: Path | None = None) -> None:
    """Remove KEY=value line from .env if present."""
    key = name.strip()
    if not key:
        return
    path = env_path or project_env_path()
    if not path.is_file():
        return
    pattern = re.compile(rf"^\s*{re.escape(key)}\s*=")
    out = [line for line in path.read_text(encoding="utf-8").splitlines() if not pattern.match(line)]
    path.write_text("\n".join(out).rstrip() + ("\n" if out else ""), encoding="utf-8")
    import os

    os.environ.pop(key, None)
