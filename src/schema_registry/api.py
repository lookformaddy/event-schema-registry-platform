"""FastAPI service (import-guarded: ``app`` is None without FastAPI).

Run with: ``uvicorn schema_registry.api:app --port 8000``
(or ``make serve``). The core library never depends on FastAPI,
so tests pass with stdlib only.
"""
from __future__ import annotations

try:
    from fastapi import FastAPI, HTTPException
    from pydantic import BaseModel
except ImportError:  # pragma: no cover - exercised when FastAPI is absent
    FastAPI = None  # type: ignore
    HTTPException = Exception  # type: ignore
    BaseModel = object  # type: ignore

from .models import FieldDef
from .registry import BreakingChangeError, Registry

registry = Registry()

if FastAPI is not None:
    app = FastAPI(title="Event Schema Registry")

    class FieldIn(BaseModel):
        name: str
        type: str
        required: bool = True
        default: object = None
        description: str = ""

    class RegisterIn(BaseModel):
        subject: str
        fields: list[FieldIn]
        compatibility: str = "BACKWARD"
        actor: str = "api"

    @app.get("/subjects")
    def list_subjects():
        return {"subjects": registry.list_subjects()}

    @app.post("/subjects/{subject}/versions", status_code=201)
    def register_version(subject: str, body: RegisterIn):
        try:
            schema = registry.register(
                subject, [FieldDef(f.name, f.type, f.required, f.default, f.description)
                          for f in body.fields],
                compatibility=body.compatibility, actor=body.actor)
        except BreakingChangeError as exc:
            raise HTTPException(status_code=409, detail=str(exc))
        return schema.to_dict()

    @app.get("/subjects/{subject}/versions/{version}")
    def get_version(subject: str, version: int):
        try:
            return registry.get(subject, version).to_dict()
        except Exception as exc:
            raise HTTPException(status_code=404, detail=str(exc))

    @app.post("/subjects/{subject}/versions/{version}/deprecate")
    def deprecate_version(subject: str, version: int):
        try:
            return registry.deprecate(subject, version, actor="api").to_dict()
        except Exception as exc:
            raise HTTPException(status_code=404, detail=str(exc))

    @app.get("/audit")
    def audit():
        return {"entries": [e.to_dict() for e in registry.audit.entries],
                "chain_valid": registry.audit.verify()}
else:
    app = None
