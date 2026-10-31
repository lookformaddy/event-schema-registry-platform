"""Hash-chained, append-only audit log.

Each entry commits to the previous entry's hash, so deleting or
rewriting a middle entry breaks every later hash. This is an audit
trail, not a cryptographic ledger: it detects tampering by anyone
without the ability to rewrite the whole chain, which is exactly
the bar for an internal registry log. ``verify()`` replays the chain.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

GENESIS_HASH = "0" * 64


def _canonical(payload: dict[str, Any]) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)


def _hash(prev_hash: str, payload: dict[str, Any]) -> str:
    return hashlib.sha256(f"{prev_hash}:{_canonical(payload)}".encode()).hexdigest()


@dataclass
class AuditEntry:
    index: int
    timestamp: str
    action: str  # register | deprecate | compatibility_override
    actor: str
    details: dict[str, Any]
    prev_hash: str
    hash: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "index": self.index, "timestamp": self.timestamp, "action": self.action,
            "actor": self.actor, "details": self.details,
            "prev_hash": self.prev_hash, "hash": self.hash,
        }


@dataclass
class AuditLog:
    entries: list[AuditEntry] = field(default_factory=list)

    def append(self, action: str, actor: str, details: dict[str, Any]) -> AuditEntry:
        prev = self.entries[-1].hash if self.entries else GENESIS_HASH
        payload = {
            "index": len(self.entries),
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "action": action, "actor": actor, "details": details,
        }
        entry = AuditEntry(
            index=payload["index"], timestamp=payload["timestamp"],
            action=action, actor=actor, details=details,
            prev_hash=prev, hash=_hash(prev, payload))
        self.entries.append(entry)
        return entry

    def verify(self) -> bool:
        prev = GENESIS_HASH
        for entry in self.entries:
            payload = {
                "index": entry.index, "timestamp": entry.timestamp,
                "action": entry.action, "actor": entry.actor, "details": entry.details,
            }
            if entry.prev_hash != prev or entry.hash != _hash(prev, payload):
                return False
            prev = entry.hash
        return True
