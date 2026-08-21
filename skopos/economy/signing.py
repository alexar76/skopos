"""Ed25519 signing for SKOPOS Hub federation (manifest + well-known pubkey).

Canonical form matches ``aimarket_hub.signing.Signer.manifest_canonical`` so a
crawler can verify. Persist the key under the SKOPOS data dir (compose volume
``/app/.skopos``) so a rebuild does not mint a new identity.
"""

from __future__ import annotations

import base64
import hashlib
import json
import os
from pathlib import Path
from typing import Any


def _ensure_keypair(path: Path) -> tuple[bytes, bytes]:
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

    if path.exists():
        raw = path.read_bytes()
        if len(raw) == 64:
            return raw[:32], raw[32:]
        raise RuntimeError(f"Ed25519 key file {path} is corrupted (size={len(raw)})")
    path.parent.mkdir(parents=True, exist_ok=True)
    priv = Ed25519PrivateKey.generate()
    seed = priv.private_bytes_raw()
    pub = priv.public_key().public_bytes_raw()
    try:
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except FileExistsError:
        raw = path.read_bytes()
        if len(raw) == 64:
            return raw[:32], raw[32:]
        raise RuntimeError(f"Ed25519 key file {path} is corrupted (size={len(raw)})")
    try:
        os.write(fd, seed + pub)
    finally:
        os.close(fd)
    return seed, pub


def _seed_from_env() -> bytes | None:
    raw = os.environ.get("SKOPOS_SIGNING_SEED_B64", "").strip()
    if not raw:
        return None
    seed = base64.b64decode(raw)
    if len(seed) != 32:
        raise RuntimeError("SKOPOS_SIGNING_SEED_B64 must decode to a 32-byte seed")
    return seed


class Signer:
    def __init__(self, key_path: str | Path | None = None) -> None:
        path = Path(
            key_path
            or os.environ.get("SKOPOS_SIGNING_KEY_PATH")
            or ".skopos/aimarket_signing_key"
        )
        self.key_path = path
        env_seed = _seed_from_env()
        if env_seed is not None:
            from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

            self._seed = env_seed
            self._pub_bytes = (
                Ed25519PrivateKey.from_private_bytes(env_seed).public_key().public_bytes_raw()
            )
        else:
            self._seed, self._pub_bytes = _ensure_keypair(self.key_path)
        self._public_key_b64 = base64.b64encode(self._pub_bytes).decode()

    @property
    def public_key_b64(self) -> str:
        return self._public_key_b64

    def sign_canonical(self, canonical: str) -> str:
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

        sig = Ed25519PrivateKey.from_private_bytes(self._seed).sign(canonical.encode())
        return base64.b64encode(sig).decode()

    def manifest_canonical(self, manifest: dict[str, Any]) -> str:
        tools = manifest.get("tools", [])
        tools_hash = hashlib.sha256(
            json.dumps(tools, sort_keys=True, ensure_ascii=False).encode()
        ).hexdigest()
        by_hub_hash = hashlib.sha256(
            json.dumps(manifest.get("by_hub", {}), sort_keys=True, ensure_ascii=False).encode()
        ).hexdigest()
        return (
            f"capabilities_count:{manifest.get('capabilities_count', 0)}"
            f"|generated_at:{manifest.get('generated_at', '')}"
            f"|protocol_version:{manifest.get('protocol_version', 'v1')}"
            f"|tools_hash:{tools_hash}"
            f"|by_hub_hash:{by_hub_hash}"
        )

    def sign_manifest(self, manifest: dict[str, Any]) -> dict[str, str]:
        return {
            "algorithm": "ed25519",
            "public_key": self.public_key_b64,
            "value": self.sign_canonical(self.manifest_canonical(manifest)),
        }


_signer: Signer | None = None


def get_signer(key_path: str | Path | None = None) -> Signer:
    global _signer
    if key_path is not None:
        return Signer(key_path=key_path)
    if _signer is None:
        _signer = Signer()
    return _signer


__all__ = ["Signer", "get_signer"]
