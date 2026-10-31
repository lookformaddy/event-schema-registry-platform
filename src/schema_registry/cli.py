"""CLI demo: register, evolve, validate, encode, and audit.

Usage: ``python -m schema_registry.cli demo`` (from ``src/`` on PYTHONPATH,
or ``make demo``). Uses only synthetic example data.
"""
from __future__ import annotations

import argparse
import json

from .contracts import Consumer, ContractStore
from .evolution import plan_migration
from .models import FieldDef
from .registry import Registry
from .serde import decode_record, encode_record
from .validation import validate_record


def demo() -> None:
    reg = Registry()
    v1 = reg.register("order.created", [
        FieldDef("order_id", "string"), FieldDef("amount", "number"),
        FieldDef("currency", "string"),
    ], actor="demo")
    print(f"registered {v1.schema_id}")

    v2 = reg.register("order.created", [
        FieldDef("order_id", "string"), FieldDef("amount", "number"),
        FieldDef("currency", "string"),
        FieldDef("discount_code", "string", required=False, default=""),
    ], actor="demo")
    print(f"registered {v2.schema_id} (optional field added: BACKWARD compatible)")

    print("migration plan v1 -> v2:", json.dumps(plan_migration(v1, v2), indent=2))
    try:
        reg.register("order.created", [FieldDef("order_id", "string")], actor="demo")
    except Exception as exc:  # BreakingChangeError in strict mode
        print(f"strict mode blocked breaking change: {exc}")

    record = {"order_id": "ORD-1", "amount": 42, "currency": "USD"}
    print("validation:", validate_record(v2, record))
    wire = encode_record(reg, "order.created", 2, record)
    schema, decoded = decode_record(reg, wire)
    print(f"serde round-trip via {schema.schema_id}: {decoded}")

    contracts = ContractStore()
    contracts.add_consumer(Consumer("billing-service", "order.created", ">=1,<3"))
    print("upgrade impact:", json.dumps(
        contracts.upgrade_impact(reg, "order.created", 2), indent=2))
    print("audit chain valid:", reg.audit.verify(),
          f"({len(reg.audit.entries)} entries)")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="schema-registry")
    parser.add_subparsers(dest="cmd", required=True).add_parser("demo")
    args = parser.parse_args(argv)
    if args.cmd == "demo":
        demo()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
