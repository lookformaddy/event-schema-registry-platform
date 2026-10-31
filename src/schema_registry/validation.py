"""Record validation against a schema version, with coercion.

Validation collects *all* errors (with dotted field paths) instead of
failing fast, so producers get a complete report in one pass.
Coercion is deliberately conservative: only integer -> number is
coerced. Strings are never parsed into numbers, booleans are never
treated as integers, and unknown fields are reported (strict mode)
rather than silently dropped.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .models import SchemaVersion

_PYTHON_TYPES = {"string": str, "integer": int, "number": (int, float), "boolean": bool}


@dataclass
class ValidationError:
    path: str
    message: str

    def __str__(self) -> str:
        return f"{self.path}: {self.message}"


@dataclass
class ValidationResult:
    valid: bool
    errors: list[ValidationError] = field(default_factory=list)
    coerced: dict[str, Any] = field(default_factory=dict)

    def __bool__(self) -> bool:
        return self.valid


def _type_ok(value: Any, field_type: str) -> bool:
    if field_type == "integer":
        # bool is a subclass of int in Python; it is not an integer here.
        return isinstance(value, int) and not isinstance(value, bool)
    if field_type == "boolean":
        return isinstance(value, bool)
    return isinstance(value, _PYTHON_TYPES[field_type])


def validate_record(schema: SchemaVersion, record: dict[str, Any],
                     *, allow_unknown_fields: bool = False,
                     coerce: bool = True) -> ValidationResult:
    if not isinstance(record, dict):
        return ValidationResult(False, [ValidationError("$", "record must be an object")])
    errors: list[ValidationError] = []
    coerced: dict[str, Any] = {}
    field_map = schema.field_map()

    for name, field_def in field_map.items():
        if name not in record:
            if field_def.required:
                errors.append(ValidationError(name, "missing required field"))
            elif field_def.default is not None:
                coerced[name] = field_def.default
            continue
        value = record[name]
        # Canonicalize integer values for number fields to float.
        if field_def.type == "number" and isinstance(value, int) and not isinstance(value, bool):
            coerced[name] = float(value)
            continue
        if _type_ok(value, field_def.type):
            continue
        # Safe coercion only: integer value for a number field.
        if coerce and field_def.type == "number" and _type_ok(value, "integer"):
            coerced[name] = float(value)
            continue
        errors.append(ValidationError(
            name, f"expected {field_def.type}, got {type(value).__name__}"))

    if not allow_unknown_fields:
        for name in record:
            if name not in field_map:
                errors.append(ValidationError(name, "unknown field"))
    return ValidationResult(not errors, errors, coerced)


def apply_coercion(record: dict[str, Any], coerced: dict[str, Any]) -> dict[str, Any]:
    out = dict(record)
    out.update(coerced)
    return out
