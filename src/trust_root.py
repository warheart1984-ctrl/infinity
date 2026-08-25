"""Trust root — Python port of @aaes-os/trust-root.

Mythic: the body measures itself before it may move.
Engineering: canonical sha3-256 measurement strings, deterministic
hTrustRoot over the fixed kernel/law-spine/corridors/boot-manifest
order, one-shot sealing, and UCR context projection. Mirrors
packages/trust-root/src/index.ts byte-for-byte (domain-separated
sha3-256 over raw measurement bytes).
"""

from __future__ import annotations

import hashlib
import re
from typing import Any

HASH_ALG = "sha3-256"
MEASUREMENT_RE = re.compile(r"^sha3-256:[0-9a-f]{64}$")
TRUST_ROOT_DOMAIN = b"AAES-TRUST-ROOT-v1\x00"

TRUST_ROOT_FIELDS = ("hKernelImage", "hLawSpine", "hCorridors", "hBootManifest")

_sealed_trust_root: dict[str, Any] | None = None


def is_measurement(value: Any) -> bool:
    return isinstance(value, str) and bool(MEASUREMENT_RE.match(value))


def as_measurement(value: str) -> str:
    if not is_measurement(value):
        raise ValueError(f"invalid measurement: {value}")
    return value


def compute_measurement(value: str | bytes) -> str:
    data = value.encode("utf-8") if isinstance(value, str) else value
    return f"sha3-256:{hashlib.sha3_256(data).hexdigest()}"


def compute_h_trust_root(
    *,
    h_kernel_image: str,
    h_law_spine: str,
    h_corridors: str,
    h_boot_manifest: str,
    hash_alg: str = HASH_ALG,
) -> str:
    """Domain-separated sha3-256 over raw measurement bytes in fixed order."""
    if hash_alg != HASH_ALG:
        raise ValueError(f"unsupported hash algorithm: {hash_alg}")
    measurements = [
        as_measurement(h_kernel_image),
        as_measurement(h_law_spine),
        as_measurement(h_corridors),
        as_measurement(h_boot_manifest),
    ]
    digest = hashlib.sha3_256()
    digest.update(TRUST_ROOT_DOMAIN)
    for measurement in measurements:
        digest.update(bytes.fromhex(measurement[len("sha3-256:"):]))
    return f"sha3-256:{digest.hexdigest()}"


def build_trust_root(
    *,
    h_kernel_image: str,
    h_law_spine: str,
    h_corridors: str,
    h_boot_manifest: str,
    hash_alg: str = HASH_ALG,
) -> dict[str, Any]:
    return {
        "hashAlg": hash_alg,
        "hKernelImage": as_measurement(h_kernel_image),
        "hLawSpine": as_measurement(h_law_spine),
        "hCorridors": as_measurement(h_corridors),
        "hBootManifest": as_measurement(h_boot_manifest),
        "hTrustRoot": compute_h_trust_root(
            h_kernel_image=h_kernel_image,
            h_law_spine=h_law_spine,
            h_corridors=h_corridors,
            h_boot_manifest=h_boot_manifest,
            hash_alg=hash_alg,
        ),
    }


def seal_trust_root(trust_root: dict[str, Any]) -> None:
    global _sealed_trust_root
    if _sealed_trust_root is not None:
        raise RuntimeError("trust root already sealed")
    _sealed_trust_root = trust_root


def get_trust_root() -> dict[str, Any]:
    if _sealed_trust_root is None:
        raise RuntimeError("trust root is not sealed")
    return _sealed_trust_root


def is_trust_root_sealed() -> bool:
    return _sealed_trust_root is not None


def reset_trust_root_for_tests() -> None:
    global _sealed_trust_root
    _sealed_trust_root = None


def to_ucr_context(trust_root: dict[str, Any]) -> dict[str, Any]:
    return {
        "hashAlg": trust_root["hashAlg"],
        "hLawSpine": trust_root["hLawSpine"],
        "hCorridors": trust_root["hCorridors"],
        "hTrustRoot": trust_root["hTrustRoot"],
    }


def run_early_boot(
    *,
    h_kernel_image: str,
    h_law_spine: str,
    h_corridors: str,
    h_boot_manifest: str,
    hash_alg: str = HASH_ALG,
) -> dict[str, Any]:
    trust_root = build_trust_root(
        h_kernel_image=h_kernel_image,
        h_law_spine=h_law_spine,
        h_corridors=h_corridors,
        h_boot_manifest=h_boot_manifest,
        hash_alg=hash_alg,
    )
    seal_trust_root(trust_root)
    return {"bootResult": "OK", "trustRoot": trust_root}
