"""Event schema registry platform: versioned schemas, compatibility, serde."""

from .audit import AuditLog
from .compatibility import check_compatibility
from .contracts import Consumer, ContractStore
from .evolution import is_breaking, plan_migration
from .models import FieldDef, SchemaVersion
from .registry import BreakingChangeError, Registry
from .serde import decode_record, encode_record
from .validation import validate_record

__all__ = [
    "AuditLog", "BreakingChangeError", "Consumer", "ContractStore",
    "FieldDef", "Registry", "SchemaVersion", "check_compatibility",
    "decode_record", "encode_record", "is_breaking", "plan_migration",
    "validate_record",
]
