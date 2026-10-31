from schema_registry import FieldDef, check_compatibility
from schema_registry.models import SchemaVersion

def schema(fields, subject="s"):
    return SchemaVersion(subject, 1, fields)

def F(n, t="string", **kw): return FieldDef(n, t, **kw)

def test_backward_add_optional_ok_add_required_fails():
    old = schema([F("a")])
    assert check_compatibility(old, schema([F("a"), F("b", required=False)]) , "BACKWARD").compatible
    r = check_compatibility(old, schema([F("a"), F("b")]), "BACKWARD")
    assert not r.compatible and any(v.kind == "added_required_field" for v in r.violations)

def test_backward_narrowing_fails_widening_passes():
    old = schema([F("n", "integer")])
    assert check_compatibility(old, schema([F("n", "number")]), "BACKWARD").compatible
    r = check_compatibility(old, schema([F("n", "string")]), "BACKWARD")
    assert not r.compatible

def test_forward_removing_required_fails_adding_ok():
    old = schema([F("a"), F("b")])
    assert check_compatibility(old, schema([F("a"), F("b"), F("c", required=False)]), "FORWARD").compatible
    r = check_compatibility(old, schema([F("a")]), "FORWARD")
    assert not r.compatible and any(v.kind == "removed_field" for v in r.violations)

def test_full_requires_both_and_none_allows_all():
    old = schema([F("a", "integer")])
    new = schema([F("a", "number"), F("b")])
    assert not check_compatibility(old, new, "FULL").compatible  # widening breaks FORWARD
    assert check_compatibility(old, new, "NONE").compatible
    assert check_compatibility(old, schema([F("a", "integer")]), "FULL").compatible

def test_requiredness_changes():
    old = schema([F("a", required=False)])
    assert not check_compatibility(old, schema([F("a", required=True)]), "BACKWARD").compatible
    old2 = schema([F("a", required=True)])
    assert not check_compatibility(old2, schema([F("a", required=False)]), "FORWARD").compatible
