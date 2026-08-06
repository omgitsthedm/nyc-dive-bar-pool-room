"""Standard-library-only identity contract for pool trajectory JSON.

This module is intentionally safe to import from both the isolated Pooltool
Python environment and Blender's bundled Python.  It has no solver, NumPy, or
Blender dependency.
"""
from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from typing import Any


# These are the only root-level export fields omitted from the trajectory
# identity.  Event/sample timestamps and every other payload value are
# authoritative and therefore remain covered by the digest.
TRAJECTORY_HASH_VOLATILE_FIELDS = frozenset({
    "generated_utc",
    "output_path",
    "source_path",
    "trajectory_sha256",
})
TRAJECTORY_HASH_REQUIRED_FIELDS = frozenset({
    "schema",
    "shot_id",
    "sample_rate_hz",
    "duration_s",
    "solver_duration_s",
    "profile_sha256",
    "geometry_contract_sha256",
    "ball_parameters",
    "cue",
    "rack",
    "events",
    "balls",
})


def trajectory_hash_payload(payload: Mapping[str, Any]) -> dict[str, Any]:
    """Return every hash-authoritative field from a trajectory payload."""
    missing = TRAJECTORY_HASH_REQUIRED_FIELDS - set(payload)
    if missing:
        raise ValueError(
            "trajectory payload is missing hash-authoritative fields: "
            + ", ".join(sorted(missing))
        )
    return {
        key: value
        for key, value in payload.items()
        if key not in TRAJECTORY_HASH_VOLATILE_FIELDS
    }


def canonical_trajectory_bytes(payload: Mapping[str, Any]) -> bytes:
    """Serialize the authoritative payload with a stable JSON encoding."""
    return json.dumps(
        trajectory_hash_payload(payload),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    ).encode("utf-8")


def recompute_trajectory_sha256(payload: Mapping[str, Any]) -> str:
    """Recompute a trajectory identity from all authoritative payload fields."""
    return hashlib.sha256(canonical_trajectory_bytes(payload)).hexdigest()


def verify_trajectory_sha256(payload: Mapping[str, Any]) -> str:
    """Validate and return the trajectory digest, raising on any mismatch."""
    expected = payload.get("trajectory_sha256")
    if not isinstance(expected, str) or len(expected) != 64:
        raise ValueError("trajectory_sha256 is missing or malformed")
    try:
        int(expected, 16)
    except ValueError as exc:
        raise ValueError("trajectory_sha256 is not hexadecimal") from exc
    actual = recompute_trajectory_sha256(payload)
    if actual != expected:
        raise ValueError(
            "trajectory_sha256 mismatch: expected %s, recomputed %s"
            % (expected, actual)
        )
    return actual
