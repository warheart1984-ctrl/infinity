"""WitnessProvider — Ring 6, external reality anchor.

    "The governor cannot secretly rewrite yesterday because
     somebody else remembers yesterday."

    "It remembers because we made sure someone always would."

Operator-ratified role name for the agent holding this ring: **Witness**.
Names persist so instances don't have to.

The checkpoint tuple is deliberately minimal: it proves WHICH history the
node claims, without revealing proposals, VT contents, or user data
(privacy by construction).

Provider-neutral interface so Rekor, another machine, or an offline
institutional witness can implement the same surface later.
"""

from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path
from typing import Any, Dict, List, Protocol

WITNESS_SCHEMA_VERSION = 1

WITNESS_CHECKPOINT_FIELDS = (
    "node_id",
    "security_epoch",
    "epoch_id",
    "ledger_position",
    "ledger_head_hash",
    "constitution_hash",
    "manifest_hash",
)


def _sha3(text: str) -> str:
    return "sha3-256:" + hashlib.sha3_256(text.encode("utf-8")).hexdigest()


def canonical_checkpoint(checkpoint: Dict[str, Any]) -> Dict[str, Any]:
    """Project a checkpoint onto its minimal, privacy-preserving tuple."""
    return {field: checkpoint.get(field) for field in WITNESS_CHECKPOINT_FIELDS}


def checkpoint_hash(checkpoint: Dict[str, Any]) -> str:
    material = json.dumps(canonical_checkpoint(checkpoint), sort_keys=True, separators=(",", ":"))
    return _sha3(material)


class WitnessProvider(Protocol):
    def publish(self, checkpoint: Dict[str, Any]) -> Dict[str, Any]:
        """Notarize one checkpoint; returns an inclusion proof."""
        ...

    def verify(self, checkpoint: Dict[str, Any], proof: Dict[str, Any]) -> bool:
        """Verify that a proof attests exactly this checkpoint."""
        ...

    def audit_rollback(self, claimed: Dict[str, Any]) -> Dict[str, Any]:
        """Compare a claimed ledger state against what was witnessed."""
        ...


class LocalFileWitnessProvider:
    """V1 witness: an append-only, hash-chained local notary log.

    Not a substitute for an EXTERNAL witness — but the same interface,
    so swapping in Rekor/remote providers changes nothing downstream.
    """

    def __init__(self, *, witness_dir: Path | str, node_id: str = "local"):
        self._dir = Path(witness_dir)
        self._path = self._dir / "witness_chain.jsonl"
        self._entries: List[Dict[str, Any]] = []
        self._loaded = False
        self.node_id = node_id

    def _load(self) -> None:
        if self._loaded:
            return
        if self._path.exists():
            with self._path.open("r", encoding="utf-8") as fh:
                for line in fh:
                    stripped = line.strip()
                    if stripped:
                        self._entries.append(json.loads(stripped))
        self._loaded = True

    def _append(self, entry: Dict[str, Any]) -> None:
        self._dir.mkdir(parents=True, exist_ok=True)
        with self._path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(entry, sort_keys=True, separators=(",", ":")) + "\n")
            fh.flush()
        self._entries.append(entry)

    def publish(self, checkpoint: Dict[str, Any]) -> Dict[str, Any]:
        self._load()
        cp_hash = checkpoint_hash(checkpoint)
        prev_witness = self._entries[-1]["witness_entry_hash"] if self._entries else None
        entry = {
            "position": len(self._entries),
            "prev_witness_hash": prev_witness,
            "checkpoint_hash": cp_hash,
            "checkpoint": canonical_checkpoint(checkpoint),
            "notarized_at": time.time(),
            "schema_version": WITNESS_SCHEMA_VERSION,
        }
        entry["witness_entry_hash"] = _sha3(
            json.dumps(
                {k: v for k, v in entry.items() if k != "witness_entry_hash"},
                sort_keys=True,
                separators=(",", ":"),
            )
        )
        self._append(entry)
        return {
            "checkpoint_hash": cp_hash,
            "position": entry["position"],
            "witness_entry_hash": entry["witness_entry_hash"],
            "prev_witness_hash": prev_witness,
        }

    def verify(self, checkpoint: Dict[str, Any], proof: Dict[str, Any]) -> bool:
        self._load()
        cp_hash = checkpoint_hash(checkpoint)
        if proof.get("checkpoint_hash") != cp_hash:
            return False
        position = proof.get("position")
        if not isinstance(position, int) or position < 0 or position >= len(self._entries):
            return False
        entry = self._entries[position]
        if entry["checkpoint_hash"] != cp_hash:
            return False
        if entry.get("witness_entry_hash") != proof.get("witness_entry_hash"):
            return False
        return True

    def audit_rollback(self, claimed: Dict[str, Any]) -> Dict[str, Any]:
        self._load()
        claimed_position = claimed.get("ledger_position")
        witnessed_position = max(
            (e["checkpoint"].get("ledger_position") or 0) for e in self._entries
        ) if self._entries else 0
        consistent = (
            isinstance(claimed_position, int)
            and claimed_position >= witnessed_position
        )
        return {
            "consistent": consistent,
            "claimed_position": claimed_position,
            "witnessed_position": witnessed_position,
            "witness_entries": len(self._entries),
        }

    # ---- convenience query surface ----

    def entries(self) -> List[Dict[str, Any]]:
        """All witness entries in publication order."""
        self._load()
        return list(self._entries)

    def latest(self) -> Dict[str, Any] | None:
        """The most recent inclusion proof, or None when nothing published."""
        self._load()
        if not self._entries:
            return None
        last = self._entries[-1]
        return {
            "checkpoint_hash": last["checkpoint_hash"],
            "position": last["position"],
            "witness_entry_hash": last["witness_entry_hash"],
            "checkpoint": last["checkpoint"],
        }

    def check_rollback(
        self, *, local_ledger_head: str, local_ledger_position: int
    ) -> Dict[str, Any]:
        """Core Ring-6 promise: detect a rewound node.

        A local head at a position EARLIER than what was witnessed — or a
        head hash that disagrees with the witnessed entry at the same
        position — means history moved backward or was rewritten.
        """
        self._load()
        witnessed_position = max(
            (e["checkpoint"].get("ledger_position") or 0) for e in self._entries
        ) if self._entries else -1
        rollback_by_position = (
            isinstance(local_ledger_position, int)
            and witnessed_position >= 0
            and local_ledger_position < witnessed_position
        )
        matching = [
            e for e in self._entries
            if e["checkpoint"].get("ledger_position") == local_ledger_position
        ]
        rollback_by_hash = bool(
            matching
            and local_ledger_head
            and all(
                e["checkpoint"].get("ledger_head_hash") != local_ledger_head
                for e in matching
            )
        )
        return {
            "rollback_suspected": bool(rollback_by_position or rollback_by_hash),
            "local_ledger_position": local_ledger_position,
            "witnessed_position": witnessed_position,
            "reason": (
                "position behind witness" if rollback_by_position
                else "head hash differs from witness record" if rollback_by_hash
                else ""
            ),
        }

    def entries(self) -> List[Dict[str, Any]]:
        """Full witness log (oldest first) — for external auditors."""
        self._load()
        return list(self._entries)

    def latest(self) -> Dict[str, Any] | None:
        """The most recent inclusion proof, or None on an empty log."""
        self._load()
        if not self._entries:
            return None
        entry = self._entries[-1]
        return {
            "checkpoint_hash": entry["checkpoint_hash"],
            "position": entry["position"],
            "checkpoint": entry["checkpoint"],
            "witness_entry_hash": entry["witness_entry_hash"],
            "prev_witness_hash": entry.get("prev_witness_hash"),
        }

    def check_rollback(
        self,
        *,
        local_ledger_head: str,
        local_ledger_position: int | None = None,
    ) -> Dict[str, Any]:
        """Core Ring-6 promise: detect a rewound node.

        A node whose claimed ledger position is behind the last witnessed
        position is presenting history the outside world never saw — either
        restored from an old snapshot or actively falsified.
        """
        self._load()
        witnessed_position = max(
            (e["checkpoint"].get("ledger_position") or 0) for e in self._entries
        ) if self._entries else 0
        rollback_suspected = (
            local_ledger_position is not None
            and local_ledger_position < witnessed_position
        )
        return {
            "rollback_suspected": rollback_suspected,
            "local_ledger_position": local_ledger_position,
            "witnessed_position": witnessed_position,
            "witnessed_head_hash": (
                self._entries[-1]["checkpoint"].get("ledger_head_hash")
                if self._entries
                else None
            ),
            "witness_entries": len(self._entries),
        }
