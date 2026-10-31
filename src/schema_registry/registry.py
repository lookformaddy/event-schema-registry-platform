"""The registry itself: subjects, immutable versions, strict mode.

Strict mode is fail-closed: registering a version that violates the
subject's compatibility mode against the latest version raises
:class:`BreakingChangeError` unless the caller supplies an explicit
override (approver + reason), which is recorded in the audit log.
That is the whole point of a registry in production: breaking
changes must be a deliberate, attributed decision, never an accident.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from .audit import AuditLog
from .compatibility import CompatibilityResult, check_compatibility
from .models import FieldDef, SchemaVersion


class RegistryError(Exception):
    pass


class BreakingChangeError(RegistryError):
    def __init__(self, result: CompatibilityResult) -> None:
        self.result = result
        super().__init__("breaking change: " + "; ".join(str(v) for v in result.violations))


class UnknownSubjectError(RegistryError):
    pass


class UnknownVersionError(RegistryError):
    pass


@dataclass
class Registry:
    strict: bool = True
    subjects: dict[str, list[SchemaVersion]] = field(default_factory=dict)
    audit: AuditLog = field(default_factory=AuditLog)

    def register(self, subject: str, fields: list[FieldDef],
                 *, compatibility: str = "BACKWARD", actor: str = "system",
                 description: str = "",
                 override_approver: str | None = None,
                 override_reason: str | None = None) -> SchemaVersion:
        versions = self.subjects.setdefault(subject, [])
        new_version = SchemaVersion(
            subject=subject, version=len(versions) + 1, fields=list(fields),
            compatibility=compatibility, description=description)
        if versions:
            latest = versions[-1]
            result = check_compatibility(latest, new_version, compatibility)
            if not result.compatible:
                if self.strict and not (override_approver and override_reason):
                    raise BreakingChangeError(result)
                if override_approver and override_reason:
                    self.audit.append("compatibility_override", override_approver, {
                        "subject": subject, "from_version": latest.version,
                        "to_version": new_version.version, "mode": compatibility,
                        "reason": override_reason,
                        "violations": [str(v) for v in result.violations]})
        versions.append(new_version)
        self.audit.append("register", actor, {
            "subject": subject, "version": new_version.version,
            "schema_id": new_version.schema_id, "compatibility": compatibility})
        return new_version

    def get(self, subject: str, version: int | None = None) -> SchemaVersion:
        versions = self.subjects.get(subject)
        if not versions:
            raise UnknownSubjectError(f"unknown subject: {subject!r}")
        if version is None:
            return versions[-1]
        for v in versions:
            if v.version == version:
                return v
        raise UnknownVersionError(f"{subject} has no version {version}")

    def get_by_schema_id(self, schema_id: str) -> SchemaVersion:
        try:
            subject, _, version = schema_id.rpartition(":v")
            return self.get(subject, int(version))
        except (ValueError, RegistryError):
            raise UnknownVersionError(f"unknown schema id: {schema_id!r}")

    def list_subjects(self) -> list[str]:
        return sorted(self.subjects)

    def list_versions(self, subject: str) -> list[SchemaVersion]:
        if subject not in self.subjects:
            raise UnknownSubjectError(f"unknown subject: {subject!r}")
        return list(self.subjects[subject])

    def deprecate(self, subject: str, version: int, *, actor: str = "system") -> SchemaVersion:
        schema = self.get(subject, version)
        schema.deprecated = True
        self.audit.append("deprecate", actor, {"subject": subject, "version": version})
        return schema
