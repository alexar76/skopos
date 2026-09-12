"""SKOPOS signs hybrid Ed25519 + ML-DSA-65, and the ecosystem's verifier accepts it.

SKOPOS was one of three signers still emitting classical-only signatures, so phase 3
of the PQC migration — `AIMARKET_PQC_REQUIRE=1` on the hubs, which refuses a document
carrying no `pq_value` — would have rejected its manifest. It cannot use
`oracle_core.Signer` (its canonical form is the HUB's, with `by_hub`), so the PQ half
is imported rather than reimplemented, and what has to be pinned is that the imported
half produces something the REAL verifier accepts. A signature only this file can
check is not a signature.

Run:  ../oracles/.venv/bin/python -m pytest tests/test_economy_pqc.py -q   (from skopos/)
"""

from __future__ import annotations

import inspect

import pytest

from skopos.economy.signing import Signer

oracle_signing = pytest.importorskip("oracle_core.signing")

MANIFEST = {
    "capabilities_count": 3,
    "generated_at": "2026-09-09T00:00:00Z",
    "protocol_version": "v1",
    "tools": [{"name": "skopos.fleet.status@v1"}],
    "by_hub": {"skopos": 3},
}


def _verify(canonical, signature, public_key_b64, *, require_pq: bool) -> bool:
    """Call the ecosystem verifier; emulate ``require_pq`` on PyPI ≤0.3.0."""
    fn = oracle_signing.Signer.verify_signature_object
    if "require_pq" in inspect.signature(fn).parameters:
        return fn(canonical, signature, public_key_b64, require_pq=require_pq)
    # Older wheels accept classical-only always; phase-3 downgrade guard is local.
    if require_pq and not signature.get("pq_value"):
        return False
    return fn(canonical, signature, public_key_b64)


@pytest.fixture
def key(tmp_path, monkeypatch):
    monkeypatch.setenv("ORACLE_PQC", "1")
    monkeypatch.delenv("SKOPOS_SIGNING_SEED_B64", raising=False)
    return tmp_path / "aimarket_signing_key"


def test_the_real_verifier_accepts_the_manifest_under_phase_3(key):
    signer = Signer(key_path=str(key))
    signature = signer.sign_manifest(MANIFEST)
    canonical = signer.manifest_canonical(MANIFEST)

    assert _verify(canonical, signature, signer.public_key_b64, require_pq=True)


def test_the_pq_key_lands_beside_the_classical_one(key):
    """`<key>_mldsa` — the convention every phase-2 signer uses, so it persists on the
    same volume the Ed25519 key already does (`skopos_ui_data:/app/.skopos`)."""
    Signer(key_path=str(key))
    assert key.exists() and key.with_name(key.name + "_mldsa").exists()


def test_enabling_pq_does_not_change_the_identity_a_peer_pinned(key):
    """The whole point of hybrid: the Ed25519 key is untouched, so no peer re-pins."""
    classical = Signer(key_path=str(key)).public_key_b64
    import os

    os.environ["ORACLE_PQC"] = "0"
    assert Signer(key_path=str(key)).public_key_b64 == classical
    os.environ["ORACLE_PQC"] = "1"
    hybrid = Signer(key_path=str(key))
    assert hybrid.public_key_b64 == classical
    assert hybrid.sign_manifest(MANIFEST)["pq_value"]


def test_pq_off_still_signs_classical(key, monkeypatch):
    """Phase 2 is opt-in per host; a node that has not flipped it must still publish."""
    monkeypatch.setenv("ORACLE_PQC", "0")
    signature = Signer(key_path=str(key)).sign_manifest(MANIFEST)
    assert signature["algorithm"] == "ed25519" and "pq_value" not in signature
    # And the same verifier accepts it while phase 3 is off, which is what makes the
    # rollout ordered rather than a flag day.
    signer = Signer(key_path=str(key))
    assert _verify(
        signer.manifest_canonical(MANIFEST), signature, signer.public_key_b64, require_pq=False
    )


def test_a_stripped_pq_signature_is_refused_under_phase_3(key):
    """The downgrade guard is the reason to emit pq_* at all."""
    signer = Signer(key_path=str(key))
    signature = signer.sign_manifest(MANIFEST)
    stripped = {k: v for k, v in signature.items() if not k.startswith("pq_")}
    canonical = signer.manifest_canonical(MANIFEST)

    assert not _verify(canonical, stripped, signer.public_key_b64, require_pq=True)
    assert _verify(canonical, stripped, signer.public_key_b64, require_pq=False)


def test_a_tampered_manifest_fails_both_halves(key):
    signer = Signer(key_path=str(key))
    signature = signer.sign_manifest(MANIFEST)
    tampered = signer.manifest_canonical({**MANIFEST, "capabilities_count": 4})

    assert not _verify(tampered, signature, signer.public_key_b64, require_pq=True)
