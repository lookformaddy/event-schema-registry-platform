"""Core data models for the event schema registry.

Clean-room, generic domain: subjects are event names such as
``order.created``; no employer data, names, or internal designs appear here.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

FIELD_TYPES = frozenset({"string", "integer", "number", "boolean"})

# Widening is the only type change that preserves every old value:
# an integer is a valid number, nothing else widens safely.
WIDENING: dict[str, set[str]] = {"integer": {"number"}}


def is_widening(old: str, new: str) -> bool:
    return old == new or new in WIDENING.get(old, set())


def is_narrowing(old: str, new: str) -> bool:
    return old != new and not is_widening(old, new)


@dataclass(frozen=True)
class FieldDef:
    """One field of a schema version.

    ``default`` must be supplied for a newly added required field to be
    BACKWARD compatible: old writers omit it, new readers fill it in.
    """

    name: str
    type: str
    required: bool = True
    default: Any = None
    description: str = ""

    def __post_init__(self) -> None:
        if self.type not in FIELD_TYPES:
            raise ValueError(f"unsupported field type: {self.type!r} (field {self.name!r})")
        if not self.name or "." in self.name:
            raise ValueError(f"field name must be a non-empty dotted-path-free name: {self.name!r}")
        if not self.required and self.default is None:
            # Optional fields may simply be absent; no default needed.
            pass

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "type": self.type,
            "required": self.required,
            "default": self.default,
            "description": self.description,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "FieldDef":
        return cls(
            name=data["name"],
            type=data["type"],
            required=data.get("required", True),
            default=data.get("default"),
            description=data.get("description", ""),
        )


@dataclass
class SchemaVersion:
    """One immutable version of a subject's schema."""

    subject: str
    version: int
    fields: list[FieldDef]
    compatibility: str = "BACKWARD"
    deprecated: bool = False
    description: str = ""

    def __post_init__(self) -> None:
        names = [f.name for f in self.fields]
        if len(names) != len(set(names)):
            raise ValueError(f"duplicate field names in {self.subject} v{self.version}")
        if self.compatibility not in {"BACKWARD", "FORWARD", "FULL", "NONE"}:
            raise ValueError(f"unknown compatibility mode: {self.compatibility!r}")

    @property
    def schema_id(self) -> str:
        return f"{self.subject}:v{self.version}"

    def field_map(self) -> dict[str, FieldDef]:
        return {f.name: f for f in self.fields}

    def to_dict(self) -> dict[str, Any]:
        return {
            "subject": self.subject,
            "version": self.version,
            "compatibility": self.compatibility,
            "deprecated": self.deprecated,
            "description": self.description,
            "fields": [f.to_dict() for f in self.fields],
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "SchemaVersion":
        return cls(
            subject=data["subject"],
            version=data["version"],
            fields=[FieldDef.from_dict(f) for f in data["fields"]],
            compatibility=data.get("compatibility", "BACKWARD"),
            deprecated=data.get("deprecated", False),
            description=data.get("description", ""),
        )
