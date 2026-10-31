"""Compatibility engine: BACKWARD / FORWARD / FULL / NONE.

Semantics (documented here and in docs/architecture.md, and tested):

- BACKWARD — a new reader can read data written by the old schema:
  adding a required field without a default breaks it, narrowing a
  type breaks it, and tightening optional -> required breaks it.
  Removing a field is fine (the new reader ignores the extra field).
- FORWARD — an old reader can read data written by the new schema:
  removing a required field breaks it, widening a type breaks it
  (old reader may receive a float where it expected an int), and
  loosening required -> optional breaks it (the field may be absent).
  Adding a field is fine (the old reader ignores it).
- FULL — both directions must hold.
- NONE — any change is accepted; the caller owns the risk.

Every violation is reported, not just the first, so callers can show
producers exactly what to fix.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from .models import SchemaVersion, is_narrowing, is_widening

MODES = ("BACKWARD", "FORWARD", "FULL", "NONE")


@dataclass
class Violation:
    field: str
    kind: str  # e.g. "added_required_field", "removed_field", "type_narrowed"
    message: str

    def __str__(self) -> str:
        return f"{self.field}: {self.message}"


@dataclass
class CompatibilityResult:
    compatible: bool
    mode: str
    violations: list[Violation] = field(default_factory=list)

    def __bool__(self) -> bool:
        return self.compatible


def _backward_violations(old: SchemaVersion, new: SchemaVersion) -> list[Violation]:
    violations: list[Violation] = []
    old_map, new_map = old.field_map(), new.field_map()
    for name, new_field in new_map.items():
        if name not in old_map:
            if new_field.required and new_field.default is None:
                violations.append(Violation(name, "added_required_field",
                    "new required field has no default; old writers will omit it"))
            continue
        old_field = old_map[name]
        if is_narrowing(old_field.type, new_field.type):
            violations.append(Violation(name, "type_narrowed",
                f"type narrowed from {old_field.type} to {new_field.type}"))
        if not old_field.required and new_field.required:
            violations.append(Violation(name, "requiredness_tightened",
                "field changed from optional to required"))
    # Removed fields: new reader ignores extra old fields -> no violation.
    return violations


def _forward_violations(old: SchemaVersion, new: SchemaVersion) -> list[Violation]:
    violations: list[Violation] = []
    old_map, new_map = old.field_map(), new.field_map()
    for name, old_field in old_map.items():
        if name not in new_map:
            if old_field.required:
                violations.append(Violation(name, "removed_field",
                    "required field removed; old readers expect it"))
            continue
        new_field = new_map[name]
        if is_widening(old_field.type, new_field.type) and old_field.type != new_field.type:
            violations.append(Violation(name, "type_widened",
                f"type widened from {old_field.type} to {new_field.type}; "
                "old readers may receive values they cannot handle"))
        elif is_narrowing(old_field.type, new_field.type):
            # Narrowing also breaks forward readers when new writers
            # emit the new (incompatible) type, e.g. string vs integer.
            violations.append(Violation(name, "type_changed",
                f"type changed from {old_field.type} to {new_field.type}"))
        if old_field.required and not new_field.required:
            violations.append(Violation(name, "requiredness_loosened",
                "field changed from required to optional; it may be absent for old readers"))
    return violations


def check_compatibility(old: SchemaVersion, new: SchemaVersion, mode: str) -> CompatibilityResult:
    """Check ``new`` against ``old`` under ``mode``."""
    if mode not in MODES:
        raise ValueError(f"unknown compatibility mode: {mode!r}")
    if mode == "NONE":
        return CompatibilityResult(True, mode, [])
    violations: list[Violation] = []
    if mode in ("BACKWARD", "FULL"):
        violations.extend(_backward_violations(old, new))
    if mode in ("FORWARD", "FULL"):
        violations.extend(_forward_violations(old, new))
    return CompatibilityResult(not violations, mode, violations)
