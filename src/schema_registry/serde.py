"""Serde: schema-id framing for wire records.

Wire format (all synthetic, documented here so any consumer can
implement it without this library):

    b"ESR1" + uint32_be(len(schema_id)) + schema_id_utf8 + payload_json_utf8

Decoding rejects unknown schema ids and payloads that fail
validation, instead of guessing — an unknown schema is a fail-closed
error, never a silent pass-through. Payloads are validated against
the resolved version, with safe coercion applied.
"""
from __future__ import annotations

import json
import struct
from typing import Any

from .models import SchemaVersion
from .registry import Registry
from .validation import ValidationError, apply_coercion, validate_record

MAGIC = b"ESR1"
_HEADER = struct.Struct(">4sI")


class SerdeError(Exception):
    pass


def encode_record(registry: Registry, subject: str, version: int | None,
                  record: dict[str, Any]) -> bytes:
    schema = registry.get(subject, version)
    if schema.deprecated:
        raise SerdeError(f"refusing to encode with deprecated schema {schema.schema_id}")
    result = validate_record(schema, record)
    if not result.valid:
        raise SerdeError("record failed validation: "
                         + "; ".join(str(e) for e in result.errors))
    payload = apply_coercion(record, result.coerced)
    schema_id = schema.schema_id.encode()
    body = json.dumps(payload, sort_keys=True).encode()
    return _HEADER.pack(MAGIC, len(schema_id)) + schema_id + body


def decode_record(registry: Registry, data: bytes) -> tuple[SchemaVersion, dict[str, Any]]:
    if len(data) < _HEADER.size or data[:4] != MAGIC:
        raise SerdeError("bad framing: missing ESR1 magic header")
    _, id_len = _HEADER.unpack(data[:_HEADER.size])
    rest = data[_HEADER.size:]
    if len(rest) < id_len:
        raise SerdeError("truncated schema id")
    schema_id = rest[:id_len].decode()
    try:
        schema = registry.get_by_schema_id(schema_id)
    except Exception as exc:
        raise SerdeError(f"unknown schema id: {schema_id!r}") from exc
    try:
        payload = json.loads(rest[id_len:].decode())
    except (ValueError, UnicodeDecodeError) as exc:
        raise SerdeError("payload is not valid JSON") from exc
    result = validate_record(schema, payload)
    if not result.valid:
        raise SerdeError("payload failed validation: "
                         + "; ".join(str(e) for e in result.errors))
    return schema, apply_coercion(payload, result.coerced)
