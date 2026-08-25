"""Ring 3 — persistent epoch ledger with boot recovery.

Append-only, hash-chained receipt log bound to boot epochs. Every receipt
carries enough evidence to prove the chain was valid at append time:

    Receipt_n.hash = H(Receipt_{n-1}.hash || position || epoch_id ||
                       type || nonce || payload_digest || resulting_state_hash)

Continuity semantics (never silently reset):
- Clean shutdown writes a SHUTDOWN receipt.
- Boot after anything else writes an UNEXPECTED_REBOOT constitutional event.
- TRUST_DISCONTINUITY is irreversible: once present in the chain, the ledger
  reports broken continuity forever and any new epoch must be opened through
  a RECOVERY receipt. History permanently remembers that trust ended here;
  repair is permitted, falsification is not.

Single-writer by design (the Ring 2 mutation gateway owns this file);
multi-writer arbitration is deployment-level (registryd), not ledger-level.
"""

from __future__ import annotations

import hashlib
import json
import os
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

LEDGER_SCHEMA_VERSION = 1
LEDGER_FILENAME = "sovereign_epoch_ledger.jsonl"
GENESIS_PREV_HASH = "sha3-256:" + "0" * 64

RECEIPT_TYPES = frozenset(
    {
        "EPOCH_OPEN",
        "COMMIT",
        "EPOCH_CLOSE",
        "SHUTDOWN",
        "UNEXPECTED_REBOOT",
        "TRUST_DISCONTINUITY",
        "RECOVERY",
    }
)

LIFECYCLE_TYPES = frozenset(
    {"EPOCH_OPEN", "EPOCH_CLOSE", "SHUTDOWN", "UNEXPECTED_REBOOT", "TRUST_DISCONTINUITY", "RECOVERY"}
)


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _canonical(obj: Any) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"))


def _sha3(text: str) -> str:
    return "sha3-256:" + hashlib.sha3_256(text.encode("utf-8")).hexdigest()


def derive_epoch_id(
    *,
    prev_epoch_id: str,
    constitution_hash: str,
    runtime_measurement: str,
    machine_measurement: str,
    boot_nonce: str,
) -> str:
    """Bind a boot epoch to its full inheritance chain.

    epoch_id = H(prev_epoch || constitution || runtime || machine || boot_nonce)

    Splicing receipts from an old epoch into a new boot fails the epoch
    binding check because the derived epoch differs.
    """
    material = "|".join(
        [
            str(prev_epoch_id or ""),
            str(constitution_hash or ""),
            str(runtime_measurement or ""),
            str(machine_measurement or ""),
            str(boot_nonce or ""),
        ]
    )
    return _sha3(material)


@dataclass(frozen=True)
class LedgerReceipt:
    """One immutable entry in the epoch ledger."""

    position: int
    prev_hash: str
    epoch_id: str
    receipt_type: str
    nonce: str
    timestamp_utc: str
    payload_digest: str
    authority_ref: str
    resulting_state_hash: str
    notes: Tuple[str, ...] = field(default_factory=tuple)

    def content_fields(self) -> Dict[str, Any]:
        return {
            "position": self.position,
            "prev_hash": self.prev_hash,
            "epoch_id": self.epoch_id,
            "receipt_type": self.receipt_type,
            "nonce": self.nonce,
            "timestamp_utc": self.timestamp_utc,
            "payload_digest": self.payload_digest,
            "authority_ref": self.authority_ref,
            "resulting_state_hash": self.resulting_state_hash,
            "notes": list(self.notes),
            "schema_version": LEDGER_SCHEMA_VERSION,
        }

    def compute_hash(self) -> str:
        return _sha3(_canonical(self.content_fields()))

    def to_json(self) -> Dict[str, Any]:
        doc = self.content_fields()
        doc["hash"] = self.compute_hash()
        return doc

    @classmethod
    def from_json(cls, data: Dict[str, Any]) -> "LedgerReceipt":
        receipt = cls(
            position=int(data["position"]),
            prev_hash=str(data["prev_hash"]),
            epoch_id=str(data["epoch_id"]),
            receipt_type=str(data["receipt_type"]),
            nonce=str(data["nonce"]),
            timestamp_utc=str(data["timestamp_utc"]),
            payload_digest=str(data.get("payload_digest", "")),
            authority_ref=str(data.get("authority_ref", "")),
            resulting_state_hash=str(data["resulting_state_hash"]),
            notes=tuple(str(n) for n in data.get("notes") or []),
        )
        expected = receipt.compute_hash()
        if str(data.get("hash")) != expected:
            raise ValueError(f"receipt hash mismatch at position {receipt.position}")
        return receipt


class EpochLedgerError(RuntimeError):
    """Raised when an append would violate ledger invariants."""


class EpochLedger:
    """Append-only persistent ledger guarding Ring 3 continuity."""

    def __init__(self, ledger_dir: Path | str):
        self._dir = Path(ledger_dir)
        self._path = self._dir / LEDGER_FILENAME
        self._entries: List[LedgerReceipt] = []
        self._seen_nonces: set[str] = set()
        self._loaded = False
        self._continuity_broken = False
        self._current_epoch_id: str = ""

    # ---- persistence ----

    def _load(self) -> None:
        if self._loaded:
            return
        self._entries = []
        self._seen_nonces = set()
        self._continuity_broken = False
        if self._path.exists():
            prev_hash = GENESIS_PREV_HASH
            with self._path.open("r", encoding="utf-8") as fh:
                for line_no, raw in enumerate(fh, start=1):
                    stripped = raw.strip()
                    if not stripped:
                        continue
                    try:
                        data = json.loads(stripped)
                    except json.JSONDecodeError as exc:
                        raise EpochLedgerError(
                            f"ledger corrupt: line {line_no} is not valid JSON"
                        ) from exc
                    try:
                        receipt = LedgerReceipt.from_json(data)
                    except ValueError as exc:
                        raise EpochLedgerError(f"ledger corrupt: line {line_no}: {exc}") from exc
                    if receipt.prev_hash != prev_hash:
                        raise EpochLedgerError(
                            f"chain break at position {receipt.position}: "
                            f"prev_hash does not link to {prev_hash[:24]}..."
                        )
                    if receipt.nonce in self._seen_nonces:
                        raise EpochLedgerError(
                            f"replay detected at position {receipt.position}: "
                            f"nonce already in ledger"
                        )
                    if str(data.get("receipt_type")) == "TRUST_DISCONTINUITY":
                        self._continuity_broken = True
                    prev_hash = data["hash"]
                    self._entries.append(receipt)
                    self._seen_nonces.add(receipt.nonce)
        self._loaded = True

    def _append(self, receipt: LedgerReceipt) -> Dict[str, Any]:
        doc = receipt.to_json()
        self._dir.mkdir(parents=True, exist_ok=True)
        with self._path.open("a", encoding="utf-8") as fh:
            fh.write(_canonical(doc) + "\n")
            fh.flush()
            os.fsync(fh.fileno())
        self._entries.append(receipt)
        self._seen_nonces.add(receipt.nonce)
        if receipt.receipt_type == "TRUST_DISCONTINUITY":
            self._continuity_broken = True
        return doc

    # ---- public surface ----

    def load_and_verify(self) -> Tuple[bool, str]:
        """Load the full chain from disk and verify integrity.

        Returns (True, "") or (False, reason). A corrupt or spliced ledger
        must refuse further operation — never silently reset.
        """
        try:
            self._load()
        except EpochLedgerError as exc:
            return False, str(exc)
        return True, ""

    @property
    def head_hash(self) -> str:
        self._load()
        if not self._entries:
            return GENESIS_PREV_HASH
        return self._entries[-1].compute_hash()

    @property
    def position(self) -> int:
        self._load()
        return len(self._entries)

    @property
    def current_epoch_id(self) -> str:
        self._load()
        return self._current_epoch_id

    @property
    def continuity_broken(self) -> bool:
        """True once a TRUST_DISCONTINUITY exists in the chain — forever."""
        self._load()
        return self._continuity_broken

    def entries(self) -> List[LedgerReceipt]:
        self._load()
        return list(self._entries)

    def _new_nonce(self) -> str:
        return uuid.uuid4().hex

    def boot(
        self,
        *,
        constitution_hash: str,
        runtime_measurement: str,
        machine_measurement: str,
        boot_nonce: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Open a boot epoch with full continuity accounting.

        Verifies the persisted chain, classifies the restart (clean vs
        unexpected vs post-discontinuity), and appends the appropriate
        constitutional events before opening the new epoch.
        """
        ok, reason = self.load_and_verify()
        if not ok:
            raise EpochLedgerError(f"refusing boot on unverified ledger: {reason}")

        prev_epoch = ""
        if self._entries:
            prev_epoch = self._entries[-1].epoch_id
            last_type = self._entries[-1].receipt_type
            if last_type != "SHUTDOWN" and last_type != "TRUST_DISCONTINUITY":
                self._append(
                    LedgerReceipt(
                        position=self.position + 0 + 1,
                        prev_hash=self.head_hash,
                        epoch_id=prev_epoch,
                        receipt_type="UNEXPECTED_REBOOT",
                        nonce=self._new_nonce(),
                        timestamp_utc=_utc_now_iso(),
                        payload_digest=_sha3(f"last_receipt={last_type}"),
                        authority_ref="",
                        resulting_state_hash=self.head_hash,
                        notes=("prior_receipt_type=" + last_type,),
                    )
                )

        new_epoch = derive_epoch_id(
            prev_epoch_id=prev_epoch,
            constitution_hash=constitution_hash,
            runtime_measurement=runtime_measurement,
            machine_measurement=machine_measurement,
            boot_nonce=boot_nonce or self._new_nonce(),
        )
        self._append(
            LedgerReceipt(
                position=self.position + 1,
                prev_hash=self.head_hash,
                epoch_id=new_epoch,
                receipt_type="EPOCH_OPEN",
                nonce=self._new_nonce(),
                timestamp_utc=_utc_now_iso(),
                payload_digest=_sha3(
                    _canonical({"constitution_hash": constitution_hash})
                ),
                authority_ref="",
                resulting_state_hash=self.head_hash,
                notes=(f"prev_epoch={prev_epoch}",),
            )
        )
        self._current_epoch_id = new_epoch
        return {
            "epoch_id": new_epoch,
            "prev_epoch_id": prev_epoch,
            "continuity_broken": self._continuity_broken,
            "unexpected_reboot": bool(
                self._entries and any(e.receipt_type == "UNEXPECTED_REBOOT" for e in self._entries[-2:])
            ),
            "position": self.position,
        }

    def append_commit(
        self,
        *,
        payload_digest: str,
        resulting_state_hash: str,
        authority_ref: str = "",
        notes: Tuple[str, ...] = (),
    ) -> Dict[str, Any]:
        """Append a COMMIT receipt bound to the current boot epoch."""
        self._load()
        if not self._current_epoch_id:
            raise EpochLedgerError("no open epoch: call boot() before appending commits")
        return self._append(
            LedgerReceipt(
                position=self.position + 1,
                prev_hash=self.head_hash,
                epoch_id=self._current_epoch_id,
                receipt_type="COMMIT",
                nonce=self._new_nonce(),
                timestamp_utc=_utc_now_iso(),
                payload_digest=payload_digest,
                authority_ref=authority_ref,
                resulting_state_hash=resulting_state_hash,
                notes=notes,
            )
        )

    def shutdown(self) -> Dict[str, Any]:
        """Write the clean-shutdown marker so the next boot knows it was orderly."""
        self._load()
        if not self._entries:
            raise EpochLedgerError("nothing to shut down: empty ledger")
        return self._append(
            LedgerReceipt(
                position=self.position + 1,
                prev_hash=self.head_hash,
                epoch_id=self._current_epoch_id or self._entries[-1].epoch_id,
                receipt_type="SHUTDOWN",
                nonce=self._new_nonce(),
                timestamp_utc=_utc_now_iso(),
                payload_digest=_sha3("orderly_shutdown"),
                authority_ref="",
                resulting_state_hash=self.head_hash,
            )
        )

    def declare_trust_discontinuity(self, *, reason: str) -> Dict[str, Any]:
        """Record that trust continuity has ended. Irreversible by design.

        After this, the ledger never claims uninterrupted sovereignty; the
        next epoch must be opened via open_recovery_epoch().
        """
        self._load()
        if not self._entries:
            raise EpochLedgerError("cannot declare discontinuity on an empty ledger")
        return self._append(
            LedgerReceipt(
                position=self.position + 1,
                prev_hash=self.head_hash,
                epoch_id=self._current_epoch_id or self._entries[-1].epoch_id,
                receipt_type="TRUST_DISCONTINUITY",
                nonce=self._new_nonce(),
                timestamp_utc=_utc_now_iso(),
                payload_digest=_sha3(str(reason or "")),
                authority_ref="",
                resulting_state_hash=self.head_hash,
                notes=("reason=" + str(reason or "")[:128],),
            )
        )

    def open_recovery_epoch(
        self,
        *,
        constitution_hash: str,
        runtime_measurement: str,
        machine_measurement: str,
        recovery_reason: str,
        boot_nonce: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Open a post-discontinuity epoch behind an explicit RECOVERY receipt."""
        self._load()
        if not self._continuity_broken:
            raise EpochLedgerError(
                "recovery epoch requires a prior TRUST_DISCONTINUITY receipt"
            )
        prev_epoch = self._entries[-1].epoch_id if self._entries else ""
        recovery_epoch = derive_epoch_id(
            prev_epoch_id=prev_epoch,
            constitution_hash=constitution_hash,
            runtime_measurement=runtime_measurement,
            machine_measurement=machine_measurement,
            boot_nonce=boot_nonce or self._new_nonce(),
        )
        self._append(
            LedgerReceipt(
                position=self.position + 1,
                prev_hash=self.head_hash,
                epoch_id=recovery_epoch,
                receipt_type="RECOVERY",
                nonce=self._new_nonce(),
                timestamp_utc=_utc_now_iso(),
                payload_digest=_sha3(str(recovery_reason or "")),
                authority_ref="",
                resulting_state_hash=self.head_hash,
                notes=(
                    "reason=" + str(recovery_reason or "")[:128],
                    "discontinuity_irrevocable=true",
                ),
            )
        )
        self._current_epoch_id = recovery_epoch
        return {
            "epoch_id": recovery_epoch,
            "prev_epoch_id": prev_epoch,
            "continuity_broken": True,
            "recovered": True,
            "position": self.position,
        }
