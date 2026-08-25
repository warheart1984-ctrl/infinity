"""AMUL Epistemic Ledger — timestamped evidence without truth collapse.

This module is deliberately separate from durable memory and the canonical
URG epistemic standing layer.  It preserves timestamped claims and explicit
relationships, then derives temporal freshness for a requested point in time.
It does not infer contradictions, rank sources, or decide semantic truth.
"""

from __future__ import annotations

import json
import os
import threading
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
from typing import Any
from uuid import uuid4

from src.temporal_replay.paths import default_runtime_dir
from src.ugr.discovery.standing import EpistemicState

MODULE_ID = "AAIS-AEL-01"
SCHEMA_VERSION = "amul_epistemic_ledger.v1"
EVENT_VERSION = "amul_epistemic_claim_event.v1"

CLAIM_KINDS = frozenset({"reported", "observed", "inferred", "predicted"})
TEMPORAL_STATES = frozenset(
    {
        "bounded_current",
        "unbounded_current",
        "stale",
        "future",
        "superseded",
        "contested",
    }
)
CURRENT_TEMPORAL_STATES = frozenset(
    {"bounded_current", "unbounded_current", "contested"}
)
DEFAULT_LIST_LIMIT = 200
EPISTEMIC_LAW_TEXT = (
    "Epistemic law: Treat memory as timestamped evidence, not current truth. Distinguish reported, observed, "
    "inferred, and predicted claims. Check scope and validity; reverify stale or changeable claims. Preserve "
    "contradictions and uncertainty; never erase history or choose truth by confidence."
)


class EpistemicLedgerIntegrityError(RuntimeError):
    """Raised when an append-only ledger cannot be trusted as read."""


def build_epistemic_law_prompt_block() -> dict[str, Any]:
    """Return model-neutral, required prompt law for every Jarvis turn."""
    return {
        "identity": "epistemic_law",
        "role": "system",
        "content": EPISTEMIC_LAW_TEXT,
        "channel": "instruction",
        "source": MODULE_ID,
        "priority": 12,
        "required": True,
        "singleton": True,
    }


def _utc_now() -> datetime:
    return datetime.now(timezone.utc).replace(microsecond=0)


def _iso_utc(value: datetime) -> str:
    return value.astimezone(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _parse_timestamp(value: Any, *, field: str, default_now: bool = False) -> tuple[datetime, str]:
    if value in (None, ""):
        if not default_now:
            raise ValueError(f"{field} is required")
        parsed = _utc_now()
        return parsed, _iso_utc(parsed)
    if isinstance(value, datetime):
        parsed = value
    else:
        text = str(value).strip()
        if text.endswith("Z"):
            text = text[:-1] + "+00:00"
        try:
            parsed = datetime.fromisoformat(text)
        except ValueError as exc:
            raise ValueError(f"{field} must be an ISO-8601 timestamp") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError(f"{field} must include a timezone")
    parsed = parsed.astimezone(timezone.utc).replace(microsecond=0)
    return parsed, _iso_utc(parsed)


def _stable_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _bounded_text(value: Any, *, field: str, limit: int, required: bool = True) -> str:
    text = str(value or "").strip()
    if required and not text:
        raise ValueError(f"{field} is required")
    if len(text) > limit:
        raise ValueError(f"{field} exceeds {limit} characters")
    return text


def _unique_text_list(value: Any, *, field: str, limit: int = 64) -> list[str]:
    if value in (None, ""):
        return []
    if not isinstance(value, (list, tuple, set)):
        raise ValueError(f"{field} must be a list")
    result: list[str] = []
    for raw in list(value)[:limit]:
        item = _bounded_text(raw, field=field, limit=500)
        if item not in result:
            result.append(item)
    if len(value) > limit:
        raise ValueError(f"{field} exceeds {limit} entries")
    return result


def _normalize_source(value: Any) -> dict[str, str]:
    if isinstance(value, str):
        return {
            "kind": "unspecified",
            "ref": _bounded_text(value, field="source", limit=500),
        }
    if not isinstance(value, dict):
        raise ValueError("source must be a string or object")
    kind = _bounded_text(value.get("kind") or "unspecified", field="source.kind", limit=64)
    ref = _bounded_text(value.get("ref"), field="source.ref", limit=500)
    source = {"kind": kind, "ref": ref}
    note = _bounded_text(value.get("note"), field="source.note", limit=500, required=False)
    if note:
        source["note"] = note
    return source


def _claim_id() -> str:
    return f"ael_{uuid4().hex}"


class AMULEpistemicLedgerStore:
    """Thread-safe, append-only temporal claim ledger with a hash chain."""

    def __init__(self, *, runtime_dir: Path | None = None):
        self._runtime_dir_override = Path(runtime_dir) if runtime_dir else None
        self._lock = threading.RLock()

    @property
    def runtime_dir(self) -> Path:
        return self._runtime_dir_override or default_runtime_dir()

    @property
    def path(self) -> Path:
        return self.runtime_dir / "amul_epistemic_ledger" / "claims.jsonl"

    def configure_runtime_dir(self, runtime_dir: Path | str | None) -> None:
        with self._lock:
            self._runtime_dir_override = Path(runtime_dir) if runtime_dir else None

    def _read_rows_unchecked(self) -> list[dict[str, Any]]:
        if not self.path.exists():
            return []
        rows: list[dict[str, Any]] = []
        with self.path.open(encoding="utf-8") as handle:
            for line_number, line in enumerate(handle, start=1):
                line = line.strip()
                if not line:
                    continue
                try:
                    row = json.loads(line)
                except json.JSONDecodeError as exc:
                    raise EpistemicLedgerIntegrityError(
                        f"epistemic ledger row {line_number} is not valid JSON"
                    ) from exc
                if not isinstance(row, dict):
                    raise EpistemicLedgerIntegrityError(
                        f"epistemic ledger row {line_number} is not an object"
                    )
                rows.append(row)
        return rows

    @staticmethod
    def _row_hash(row_without_hash: dict[str, Any]) -> str:
        return sha256(_stable_json(row_without_hash).encode("utf-8")).hexdigest()

    @classmethod
    def _verify_rows(cls, rows: list[dict[str, Any]]) -> dict[str, Any]:
        previous = ""
        errors: list[str] = []
        for index, row in enumerate(rows):
            material = {key: value for key, value in row.items() if key != "row_hash"}
            actual = str(row.get("row_hash") or "")
            expected = cls._row_hash(material)
            if str(row.get("prev_row_hash") or "") != previous:
                errors.append(f"row {index}: prev_row_hash mismatch")
            if actual != expected:
                errors.append(f"row {index}: hash mismatch")
            previous = actual
        return {
            "valid": not errors,
            "entry_count": len(rows),
            "chain_tip": previous,
            "errors": errors[:12],
        }

    def verify_chain(self) -> dict[str, Any]:
        with self._lock:
            try:
                rows = self._read_rows_unchecked()
            except EpistemicLedgerIntegrityError as exc:
                return {
                    "valid": False,
                    "entry_count": 0,
                    "chain_tip": "",
                    "errors": [str(exc)],
                }
            return self._verify_rows(rows)

    def _trusted_rows(self) -> list[dict[str, Any]]:
        rows = self._read_rows_unchecked()
        verification = self._verify_rows(rows)
        if not verification["valid"]:
            raise EpistemicLedgerIntegrityError(
                "epistemic ledger hash chain is invalid: " + "; ".join(verification["errors"])
            )
        return rows

    def _normalize_claim(
        self,
        claim: dict[str, Any],
        *,
        existing_rows: list[dict[str, Any]],
    ) -> dict[str, Any]:
        if not isinstance(claim, dict):
            raise ValueError("claim must be an object")
        claim_kind = str(claim.get("kind") or "").strip().lower()
        if claim_kind not in CLAIM_KINDS:
            raise ValueError(f"kind must be one of: {', '.join(sorted(CLAIM_KINDS))}")

        observed_dt, observed_at = _parse_timestamp(
            claim.get("observed_at"), field="observed_at", default_now=True
        )
        valid_until = None
        if claim.get("valid_until") not in (None, ""):
            valid_dt, valid_until = _parse_timestamp(claim.get("valid_until"), field="valid_until")
            if valid_dt <= observed_dt:
                raise ValueError("valid_until must be later than observed_at")

        claim_id = _bounded_text(
            claim.get("claim_id") or _claim_id(), field="claim_id", limit=128
        )
        existing_by_id = {
            str(row.get("claim_id")): row for row in existing_rows if row.get("claim_id")
        }
        if claim_id in existing_by_id:
            raise ValueError(f"claim_id already exists: {claim_id}")

        scope = _bounded_text(claim.get("scope") or "global", field="scope", limit=240)
        subject = _bounded_text(claim.get("subject"), field="subject", limit=240)
        evidence_refs = _unique_text_list(claim.get("evidence_refs"), field="evidence_refs")
        verification_method = _bounded_text(
            claim.get("verification_method"),
            field="verification_method",
            limit=500,
            required=False,
        )
        if claim_kind == "observed" and (not evidence_refs or not verification_method):
            raise ValueError(
                "observed claims require verification_method and at least one evidence_ref"
            )

        epistemic_state = str(
            claim.get("epistemic_state") or EpistemicState.PENDING.value
        ).strip().lower()
        try:
            epistemic_state = EpistemicState(epistemic_state).value
        except ValueError as exc:
            allowed = ", ".join(state.value for state in EpistemicState)
            raise ValueError(f"epistemic_state must be one of: {allowed}") from exc

        try:
            confidence = float(claim.get("confidence", 0.5))
        except (TypeError, ValueError) as exc:
            raise ValueError("confidence must be a number from 0 to 1") from exc
        if not 0.0 <= confidence <= 1.0:
            raise ValueError("confidence must be a number from 0 to 1")

        supersedes = _unique_text_list(claim.get("supersedes"), field="supersedes")
        contradicts = _unique_text_list(claim.get("contradicts"), field="contradicts")
        for relation, targets in (("supersedes", supersedes), ("contradicts", contradicts)):
            if claim_id in targets:
                raise ValueError(f"{relation} cannot reference the claim itself")
            for target_id in targets:
                target = existing_by_id.get(target_id)
                if target is None:
                    raise ValueError(f"{relation} references unknown claim_id: {target_id}")
                if str(target.get("subject")) != subject or str(target.get("scope")) != scope:
                    raise ValueError(
                        f"{relation} target {target_id} must share subject and scope"
                    )

        _, recorded_at = _parse_timestamp(None, field="recorded_at", default_now=True)
        row: dict[str, Any] = {
            "event_version": EVENT_VERSION,
            "schema_version": SCHEMA_VERSION,
            "module_id": MODULE_ID,
            "claim_id": claim_id,
            "subject": subject,
            "proposition": _bounded_text(
                claim.get("proposition"), field="proposition", limit=4000
            ),
            "kind": claim_kind,
            "source": _normalize_source(claim.get("source")),
            "scope": scope,
            "observed_at": observed_at,
            "valid_until": valid_until,
            "recorded_at": recorded_at,
            "confidence": confidence,
            "epistemic_state": epistemic_state,
            "evidence_refs": evidence_refs,
            "verification_method": verification_method or None,
            "supersedes": supersedes,
            "contradicts": contradicts,
        }
        return row

    def append_claim(self, claim: dict[str, Any]) -> dict[str, Any]:
        with self._lock:
            rows = self._trusted_rows()
            row = self._normalize_claim(claim, existing_rows=rows)
            row["prev_row_hash"] = str(rows[-1].get("row_hash") or "") if rows else ""
            row["row_hash"] = self._row_hash(row)
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with self.path.open("a", encoding="utf-8") as handle:
                handle.write(_stable_json(row) + "\n")
                handle.flush()
                os.fsync(handle.fileno())
            return dict(row)

    def list_claims(
        self,
        *,
        subject: str | None = None,
        scope: str | None = None,
        limit: int = DEFAULT_LIST_LIMIT,
    ) -> list[dict[str, Any]]:
        with self._lock:
            rows = self._trusted_rows()
        if subject:
            rows = [row for row in rows if str(row.get("subject")) == str(subject)]
        if scope:
            rows = [row for row in rows if str(row.get("scope")) == str(scope)]
        cap = max(1, min(int(limit or DEFAULT_LIST_LIMIT), 500))
        return [dict(row) for row in rows[-cap:]]

    @staticmethod
    def _relation_pairs(rows: list[dict[str, Any]], relation: str) -> set[tuple[str, str]]:
        pairs: set[tuple[str, str]] = set()
        known = {str(row.get("claim_id")) for row in rows}
        for row in rows:
            source_id = str(row.get("claim_id") or "")
            for target_id in list(row.get(relation) or []):
                target = str(target_id)
                if source_id and target in known:
                    pairs.add(tuple(sorted((source_id, target))))
        return pairs

    def reconcile(
        self,
        *,
        subject: str,
        scope: str = "global",
        as_of: Any = None,
    ) -> dict[str, Any]:
        subject_text = _bounded_text(subject, field="subject", limit=240)
        scope_text = _bounded_text(scope or "global", field="scope", limit=240)
        as_of_dt, as_of_iso = _parse_timestamp(as_of, field="as_of", default_now=True)
        with self._lock:
            trusted_rows = self._trusted_rows()
        rows = [
            dict(row)
            for row in trusted_rows
            if str(row.get("subject")) == subject_text and str(row.get("scope")) == scope_text
        ]
        by_id = {str(row["claim_id"]): row for row in rows}
        superseded_ids = {
            target
            for row in rows
            if _parse_timestamp(row.get("observed_at"), field="observed_at")[0] <= as_of_dt
            for target in list(row.get("supersedes") or [])
        }

        temporal_by_id: dict[str, str] = {}
        trail: list[dict[str, Any]] = []
        for row in rows:
            claim_id = str(row["claim_id"])
            observed_dt = _parse_timestamp(row.get("observed_at"), field="observed_at")[0]
            valid_dt = None
            if row.get("valid_until"):
                valid_dt = _parse_timestamp(row.get("valid_until"), field="valid_until")[0]
            if observed_dt > as_of_dt:
                temporal_state = "future"
                rule = "observed_after_as_of"
            elif claim_id in superseded_ids:
                temporal_state = "superseded"
                rule = "explicit_supersession"
            elif valid_dt is not None and valid_dt <= as_of_dt:
                temporal_state = "stale"
                rule = "validity_window_expired"
            elif valid_dt is not None:
                temporal_state = "bounded_current"
                rule = "inside_explicit_validity_window"
            else:
                temporal_state = "unbounded_current"
                rule = "no_explicit_validity_end"
            temporal_by_id[claim_id] = temporal_state
            trail.append({"claim_id": claim_id, "rule": rule, "result": temporal_state})

        contradiction_pairs = self._relation_pairs(rows, "contradicts")
        open_conflicts: list[dict[str, Any]] = []
        historical_conflicts: list[dict[str, Any]] = []
        for left_id, right_id in sorted(contradiction_pairs):
            left_current = (
                temporal_by_id.get(left_id) in CURRENT_TEMPORAL_STATES
                and by_id[left_id].get("epistemic_state") != EpistemicState.REJECTED.value
            )
            right_current = (
                temporal_by_id.get(right_id) in CURRENT_TEMPORAL_STATES
                and by_id[right_id].get("epistemic_state") != EpistemicState.REJECTED.value
            )
            conflict = {
                "claim_ids": [left_id, right_id],
                "relation": "explicit_contradiction",
            }
            if left_current and right_current:
                temporal_by_id[left_id] = "contested"
                temporal_by_id[right_id] = "contested"
                open_conflicts.append(conflict)
                trail.append(
                    {
                        "claim_ids": [left_id, right_id],
                        "rule": "explicit_current_contradiction",
                        "result": "contested",
                    }
                )
            else:
                historical_conflicts.append(conflict)

        evaluated_claims: list[dict[str, Any]] = []
        for row in rows:
            evaluated = dict(row)
            evaluated["temporal_state"] = temporal_by_id[str(row["claim_id"])]
            evaluated_claims.append(evaluated)

        active_claims = [
            row
            for row in evaluated_claims
            if row["temporal_state"] in CURRENT_TEMPORAL_STATES
            and row.get("epistemic_state") != EpistemicState.REJECTED.value
        ]
        if open_conflicts:
            overall_state = "contested"
            recommended_action = "Run a scoped live verification for every open conflict; do not choose by confidence."
        elif len(active_claims) > 1:
            overall_state = "multiple_current"
            recommended_action = "Evaluate whether the current claims are compatible; no semantic merge was attempted."
        elif len(active_claims) == 1:
            overall_state = str(active_claims[0]["temporal_state"])
            if overall_state == "unbounded_current":
                recommended_action = "Establish a validity window when the subject can change."
            else:
                recommended_action = "Use only within the recorded scope and validity window."
        elif rows and all(state == "future" for state in temporal_by_id.values()):
            overall_state = "not_yet_observed"
            recommended_action = "Wait for the observation time or gather present evidence."
        elif rows and any(state == "stale" for state in temporal_by_id.values()):
            overall_state = "stale"
            recommended_action = "Reverify the subject in the same scope before relying on it."
        else:
            overall_state = "unknown"
            recommended_action = "Gather scoped, timestamped evidence."

        return {
            "schema_version": SCHEMA_VERSION,
            "module_id": MODULE_ID,
            "subject": subject_text,
            "scope": scope_text,
            "as_of": as_of_iso,
            "overall_state": overall_state,
            "claims": evaluated_claims,
            "current_claims": active_claims,
            "open_conflicts": open_conflicts,
            "historical_conflicts": historical_conflicts,
            "evaluation_trail": trail,
            "recommended_action": recommended_action,
            "truth_adjudicated": False,
        }

    def status(self) -> dict[str, Any]:
        chain = self.verify_chain()
        return {
            "schema_version": SCHEMA_VERSION,
            "module_id": MODULE_ID,
            "status": "ready" if chain["valid"] else "integrity_error",
            "path": str(self.path),
            "entry_count": chain["entry_count"],
            "chain": chain,
            "claim_kinds": sorted(CLAIM_KINDS),
            "temporal_states": sorted(TEMPORAL_STATES),
            "canonical_epistemic_states": [state.value for state in EpistemicState],
            "truth_adjudicated": False,
            "limitations": [
                "contradictions must be declared explicitly",
                "confidence is recorded but never used to choose a winner",
                "live verification probes are external to this ledger",
            ],
        }


amul_epistemic_ledger = AMULEpistemicLedgerStore()
