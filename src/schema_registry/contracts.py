"""Producer/consumer contracts: pinning and upgrade impact.

A consumer pins a version range such as ``>=1,<3`` or an exact
version (``==2``), or follows ``latest``. At publish time the
registry checks the new version against the latest under the
subject's mode; the upgrade-impact report then lists every consumer
whose pin excludes the new version or whose pinned version is
incompatible with it — the list a producer must notify before
deploying.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from .compatibility import check_compatibility
from .models import SchemaVersion
from .registry import Registry

_RANGE_RE = re.compile(r"^(>=|<=|>|<|==)?\s*(\d+)$")


@dataclass
class Consumer:
    name: str
    subject: str
    pin: str = "latest"  # e.g. "latest", "==2", ">=1,<3"

    def allows(self, version: int) -> bool:
        if self.pin.strip() == "latest":
            return True
        for clause in self.pin.split(","):
            clause = clause.strip()
            match = _RANGE_RE.match(clause)
            if not match:
                raise ValueError(f"invalid pin clause: {clause!r} (consumer {self.name!r})")
            op, num = match.group(1) or "==", int(match.group(2))
            ok = {"==": version == num, ">=": version >= num, "<=": version <= num,
                  ">": version > num, "<": version < num}[op]
            if not ok:
                return False
        return True


@dataclass
class ContractStore:
    consumers: list[Consumer] = field(default_factory=list)

    def add_consumer(self, consumer: Consumer) -> Consumer:
        self.consumers.append(consumer)
        return consumer

    def consumers_for(self, subject: str) -> list[Consumer]:
        return [c for c in self.consumers if c.subject == subject]

    def check_publish(self, registry: Registry, subject: str,
                      candidate: SchemaVersion) -> dict[str, object]:
        """Compatibility of a candidate version at publish time."""
        latest = registry.get(subject)
        result = check_compatibility(latest, candidate, candidate.compatibility)
        return {"compatible": result.compatible,
                "violations": [str(v) for v in result.violations],
                "against_version": latest.version}

    def upgrade_impact(self, registry: Registry, subject: str,
                       new_version: int) -> dict[str, object]:
        """Consumers affected by upgrading ``subject`` to ``new_version``."""
        new_schema = registry.get(subject, new_version)
        affected: list[dict[str, str]] = []
        for consumer in self.consumers_for(subject):
            reasons: list[str] = []
            if not consumer.allows(new_version):
                reasons.append(f"pin {consumer.pin!r} excludes v{new_version}")
            # If the consumer pins an older version, check that version
            # against the new one under the new schema's mode.
            pinned = [v for v in registry.list_versions(subject)
                      if consumer.allows(v.version)]
            if pinned and pinned[-1].version != new_version:
                result = check_compatibility(pinned[-1], new_schema, new_schema.compatibility)
                if not result.compatible:
                    reasons.append("pinned version incompatible: "
                                   + "; ".join(str(v) for v in result.violations))
            if reasons:
                affected.append({"consumer": consumer.name, "reasons": "; ".join(reasons)})
        return {"subject": subject, "new_version": new_version, "affected": affected}
