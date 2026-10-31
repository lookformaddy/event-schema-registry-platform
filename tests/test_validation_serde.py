import pytest
from schema_registry import FieldDef, Registry, validate_record, encode_record, decode_record
from schema_registry.models import SchemaVersion
from schema_registry.serde import SerdeError

def schema():
    return SchemaVersion("order.created", 1, [
        FieldDef("order_id", "string"), FieldDef("amount", "number"),
        FieldDef("count", "integer", required=False, default=1)])

def test_valid_and_coerced_int_to_number():
    r = validate_record(schema(), {"order_id": "X", "amount": 5})
    assert r.valid and r.coerced == {"amount": 5.0, "count": 1}

def test_collects_all_errors_with_paths():
    r = validate_record(schema(), {"amount": "not-a-number", "extra": 1})
    assert not r.valid
    paths = {e.path for e in r.errors}
    assert {"order_id", "amount", "extra"} <= paths

def test_bool_is_not_integer_and_string_not_coerced():
    s = SchemaVersion("s", 1, [FieldDef("n", "integer"), FieldDef("m", "number")])
    assert not validate_record(s, {"n": True, "m": 1}).valid
    assert not validate_record(s, {"n": "3", "m": 1}).valid

def test_serde_round_trip_and_unknown_schema_rejected():
    reg = Registry()
    reg.register("order.created", [FieldDef("order_id", "string"), FieldDef("amount", "number")])
    wire = encode_record(reg, "order.created", 1, {"order_id": "O1", "amount": 10})
    s, rec = decode_record(reg, wire)
    assert s.schema_id == "order.created:v1" and rec["order_id"] == "O1"
    with pytest.raises(SerdeError):
        decode_record(reg, b"ESR1" + (15).to_bytes(4, "big") + b"nope.subject:v9" + b"{}")
    with pytest.raises(SerdeError):
        decode_record(reg, b"GARBAGE")
    with pytest.raises(SerdeError):
        encode_record(reg, "order.created", 1, {"order_id": 123, "amount": 1})
