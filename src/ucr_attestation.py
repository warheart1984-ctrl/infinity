"""UCR attestation — Python port of @aaes-os/ucr-attestation.

Mythic: only a measured instance may hold the law's keys.
Engineering: attestation tokens bound to the sealed trust root, corridors
and law-spine hashes, with deterministic refusal ordering and a
domain-separated sha3-256 signature. Mirrors
packages/ucr-attestation/src/index.ts byte-for-byte. The registered UCR
handle is what downstream consumers (e.g. CEN authority-token validation)
check before trusting an execution instance.
"""

from __future__ import annotations

import hashlib
import re
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any

from src.trust_root import (
    as_measurement,
    get_trust_root,
    is_trust_root_sealed,
    to_ucr_context,
)

ERR_LAW_KEY_INVALID = 1001
ERR_TRUST_ROOT_MISMATCH = 1006
ERR_BOOT_NOT_SEALED = 1007
ERR_TOKEN_EXPIRED = 1008
ERR_CORRIDORS_HASH_MISMATCH = 1009
ERR_LAW_SPINE_HASH_MISMATCH = 1010
ERR_SIGNATURE_INVALID = 1011

ATTEST_DOMAIN = b"AAES-UCR-ATTEST-v1\x00"
DEFAULT_LAW_KEY = "00000000000000000000000000000001"
LAW_KEY_RE = re.compile(r"^[0-9a-f]{32}$")

_registered_ucr_handle: str | None = None


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _parse_ts(value: str) -> float:
    text = str(value).strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        return datetime.fromisoformat(text).timestamp()
    except ValueError:
        return 0.0


def validate_law_key(law_key: str) -> bool:
    return bool(LAW_KEY_RE.match(str(law_key))) and str(law_key) != "0" * 32


def placeholder_signature(token: dict[str, Any]) -> str:
    # TS: [ATTEST_DOMAIN, f0, f1, ...].join('|') hashes the raw NUL byte of
    # the domain buffer followed by '|'. Reproduce those exact bytes.
    fields = "|".join(
        [
            str(token.get("tokenId") or ""),
            str(token.get("ucrInstanceId") or ""),
            str(token.get("buildFingerprint") or ""),
            str(token.get("lawKey") or ""),
            str(token.get("trustRoot") or ""),
            str(token.get("corridorsHash") or ""),
            str(token.get("lawSpineHash") or ""),
            str(token.get("issuedAt") or ""),
            str(token.get("expiresAt") or ""),
            str(token.get("nonce") or ""),
        ]
    )
    material = ATTEST_DOMAIN + b"|" + fields.encode("utf-8")
    return hashlib.sha3_256(material).hexdigest()


def issue_attestation_token(
    *,
    ucr_instance_id: str,
    build_fingerprint: str,
    trust_root: str,
    corridors_hash: str,
    law_spine_hash: str,
    expires_at: str,
    token_id: str | None = None,
    law_key: str | None = None,
    issued_at: str | None = None,
    nonce: str | None = None,
) -> dict[str, Any]:
    if not str(ucr_instance_id).strip():
        raise ValueError("ucrInstanceId is required")
    if not str(build_fingerprint).strip():
        raise ValueError("buildFingerprint is required")
    token: dict[str, Any] = {
        "tokenId": token_id or secrets.token_hex(16),
        "ucrInstanceId": ucr_instance_id,
        "buildFingerprint": build_fingerprint,
        "lawKey": law_key or DEFAULT_LAW_KEY,
        "trustRoot": as_measurement(trust_root),
        "corridorsHash": as_measurement(corridors_hash),
        "lawSpineHash": as_measurement(law_spine_hash),
        "issuedAt": issued_at or _utc_now().isoformat(timespec="milliseconds").replace("+00:00", "Z"),
        "expiresAt": expires_at,
        "nonce": nonce or secrets.token_hex(16),
        "signature": "",
    }
    token["signature"] = placeholder_signature(token)
    return token


def issue_attestation_from_sealed_trust(
    *,
    ucr_instance_id: str,
    build_fingerprint: str,
    expires_at: str | None = None,
    law_key: str | None = None,
) -> dict[str, Any]:
    sealed = get_trust_root()
    return issue_attestation_token(
        ucr_instance_id=ucr_instance_id,
        build_fingerprint=build_fingerprint,
        law_key=law_key,
        trust_root=sealed["hTrustRoot"],
        corridors_hash=sealed["hCorridors"],
        law_spine_hash=sealed["hLawSpine"],
        expires_at=expires_at
        or (_utc_now() + timedelta(minutes=5)).isoformat(timespec="milliseconds").replace("+00:00", "Z"),
    )


def _refused(reason_code: int, reason_detail: str) -> dict[str, Any]:
    return {"outcome": "REFUSED", "reasonCode": reason_code, "reasonDetail": reason_detail}


def ucr_register(token: dict[str, Any]) -> dict[str, Any]:
    global _registered_ucr_handle
    if not is_trust_root_sealed():
        return _refused(ERR_BOOT_NOT_SEALED, "trust root is not sealed")
    if _parse_ts(token.get("expiresAt") or "") <= _utc_now().timestamp():
        return _refused(ERR_TOKEN_EXPIRED, "attestation token expired")
    if not validate_law_key(str(token.get("lawKey") or "")):
        return _refused(ERR_LAW_KEY_INVALID, "law key is invalid")
    signature = token.get("signature")
    if not signature or signature != placeholder_signature(token):
        return _refused(ERR_SIGNATURE_INVALID, "signature is invalid")

    sealed = get_trust_root()
    context = to_ucr_context(sealed)
    if token.get("trustRoot") != sealed["hTrustRoot"] or context["hTrustRoot"] != token.get("trustRoot"):
        return _refused(ERR_TRUST_ROOT_MISMATCH, "trust root mismatch")
    if token.get("corridorsHash") != sealed["hCorridors"]:
        return _refused(ERR_CORRIDORS_HASH_MISMATCH, "corridors hash mismatch")
    if token.get("lawSpineHash") != sealed["hLawSpine"]:
        return _refused(ERR_LAW_SPINE_HASH_MISMATCH, "law spine hash mismatch")

    _registered_ucr_handle = secrets.token_hex(16)
    return {
        "outcome": "OK",
        "ucrHandle": _registered_ucr_handle,
        "metadata": {
            "tokenId": token["tokenId"],
            "ucrInstanceId": token["ucrInstanceId"],
            "trustRoot": token["trustRoot"],
        },
    }


def get_registered_ucr_handle() -> str | None:
    return _registered_ucr_handle


def reset_ucr_registration_for_tests() -> None:
    global _registered_ucr_handle
    _registered_ucr_handle = None
