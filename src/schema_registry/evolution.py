"""Safe-migration planner and breaking-change detection.

The planner turns a compatibility result into actionable steps:
add a field with a default first, deprecate (don't delete) a field,
widen instead of narrowing, and only remove a field once no consumer
reads it. Breaking changes are never "fixed" by the planner — they
are named, so a human can choose the multi-step migration.
"""
from __future__ import annotations

from .compatibility import CompatibilityResult, check_compatibility
from .models import SchemaVersion


def plan_migration(old: SchemaVersion, new: SchemaVersion,
                   mode: str = "BACKWARD") -> dict[str, object]:
    """Return steps to evolve ``old`` into ``new`` safely, if possible."""
    result: CompatibilityResult = check_compatibility(old, new, mode)
    old_map, new_map = old.field_map(), new.field_map()
    steps: list[str] = []
    for name, new_field in new_map.items():
        if name not in old_map:
            if new_field.required and new_field.default is None:
                steps.append(
                    f"Add field '{name}' as OPTIONAL with a default first, "
                    "deploy readers, then tighten to required in a later version.")
            else:
                steps.append(f"Add field '{name}' ({new_field.type}); "
                             "old readers ignore it.")
    for name in old_map:
        if name not in new_map:
            steps.append(
                f"Do NOT delete '{name}' yet: deprecate it, confirm no consumer "
                "reads it, then remove it in a later version.")
    for name in old_map:
        if name in new_map and old_map[name].type != new_map[name].type:
            steps.append(
                f"Change '{name}' from {old_map[name].type} to {new_map[name].type} "
                "via a widening step or a new field; in-place type changes break readers.")
    if result.compatible:
        steps.append("Migration is compatible under "
                     f"{mode}: deploy readers first, then writers.")
    return {
        "compatible": result.compatible,
        "mode": mode,
        "violations": [str(v) for v in result.violations],
        "steps": steps,
    }


def is_breaking(old: SchemaVersion, new: SchemaVersion, mode: str = "BACKWARD") -> bool:
    return not check_compatibility(old, new, mode).compatible
