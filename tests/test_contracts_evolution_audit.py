from schema_registry import FieldDef, Registry, Consumer, ContractStore, plan_migration, is_breaking
from schema_registry.audit import AuditLog

def F(n, t="string", **kw): return FieldDef(n, t, **kw)

def test_migration_plan_names_breaking_steps():
    reg = Registry(strict=False)
    v1 = reg.register("s", [F("a"), F("b")])
    v2 = reg.register("s", [F("a")])
    # Removing a required field is BACKWARD-ok (new readers ignore extras)
    # but breaks FULL/FORWARD: old readers still expect it.
    plan = plan_migration(v1, v2, mode="FULL")
    assert not plan["compatible"] and any("deprecate" in s for s in plan["steps"])
    assert is_breaking(v1, v2, mode="FULL")
    assert not is_breaking(v1, v2, mode="BACKWARD")

def test_consumer_pin_ranges():
    assert Consumer("c", "s", ">=1,<3").allows(2)
    assert not Consumer("c", "s", ">=1,<3").allows(3)
    assert Consumer("c", "s", "==2").allows(2)
    assert Consumer("c", "s", "latest").allows(99)

def test_upgrade_impact_lists_pinned_out_and_incompatible():
    reg = Registry(strict=False)
    reg.register("s", [F("a")])
    reg.register("s", [F("a"), F("b", required=False)])
    store = ContractStore()
    store.add_consumer(Consumer("old-only", "s", "==1"))
    store.add_consumer(Consumer("flexible", "s", ">=1,<3"))
    impact = store.upgrade_impact(reg, "s", 2)
    names = [a["consumer"] for a in impact["affected"]]
    assert "old-only" in names and "flexible" not in names

def test_check_publish_reports_violations():
    reg = Registry(strict=False)
    reg.register("s", [F("a")])
    from schema_registry.models import SchemaVersion
    cand = SchemaVersion("s", 99, [F("a"), F("b")])
    store = ContractStore()
    assert not store.check_publish(reg, "s", cand)["compatible"]

def test_audit_chain_verifies_and_tamper_breaks_it():
    log = AuditLog()
    log.append("register", "alice", {"subject": "s", "version": 1})
    log.append("deprecate", "bob", {"subject": "s", "version": 1})
    assert log.verify()
    log.entries[0].details["version"] = 99
    assert not log.verify()
