import pytest
from schema_registry import FieldDef, Registry, BreakingChangeError

def f(name, type="string", **kw):
    return FieldDef(name, type, **kw)

def test_register_versions_increment_and_latest():
    reg = Registry()
    v1 = reg.register("order.created", [f("order_id")])
    v2 = reg.register("order.created", [f("order_id"), f("note", required=False)])
    assert (v1.version, v2.version) == (1, 2)
    assert reg.get("order.created") is v2
    assert reg.get_by_schema_id("order.created:v1") is v1
    assert reg.list_subjects() == ["order.created"]

def test_strict_mode_blocks_breaking_change():
    reg = Registry(strict=True)
    reg.register("s", [f("a"), f("b")])
    with pytest.raises(BreakingChangeError):
        reg.register("s", [f("a"), f("b", required=False, default=None), f("c")])
    # added required field without default is the breaking change
    with pytest.raises(BreakingChangeError):
        reg.register("s", [f("a"), f("b"), f("c")])

def test_override_requires_approver_and_reason_and_is_audited():
    reg = Registry(strict=True)
    reg.register("s", [f("a")])
    with pytest.raises(BreakingChangeError):
        reg.register("s", [f("a"), f("b")], override_approver="lead")
    v2 = reg.register("s", [f("a"), f("b")], override_approver="lead", override_reason="planned cutover")
    assert v2.version == 2
    assert any(e.action == "compatibility_override" for e in reg.audit.entries)

def test_non_strict_allows_breaking():
    reg = Registry(strict=False)
    reg.register("s", [f("a")])
    assert reg.register("s", [f("a"), f("b")]).version == 2

def test_deprecate_and_unknown_subject():
    reg = Registry()
    reg.register("s", [f("a")])
    assert reg.deprecate("s", 1).deprecated is True
    with pytest.raises(Exception):
        reg.get("nope")
