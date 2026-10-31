# Event Schema Registry Platform

## The enterprise problem

In an event-driven company, dozens of producers and consumers share
event schemas, and nobody owns the contract between them. A producer
adds a required field, renames a type, or deletes a field, and a
consumer that was working yesterday starts failing — or worse,
silently misreading data — today. The failure is discovered in
production, not at publish time, because there was no single place
where schemas were versioned, checked, and pinned.

This platform is that place: a versioned schema registry with a
compatibility engine, producer/consumer contracts, schema-id framed
serde, and a tamper-evident audit log. All code is original and all
example data is synthetic; the domain is deliberately generic
(`order.created` with `order_id`/`amount`/`currency`).

## Architecture overview

```
src/schema_registry/
  models.py         FieldDef / SchemaVersion (immutable versions)
  registry.py       Registry: registration, strict mode, deprecation
  compatibility.py  BACKWARD / FORWARD / FULL / NONE engine
  evolution.py      Safe-migration planner, breaking-change detection
  validation.py     Record validation, all-errors reporting, safe coercion
  contracts.py      Consumer pinning (>=1,<3 / ==2 / latest), upgrade impact
  serde.py          ESR1 framing: magic + schema-id length + id + JSON payload
  audit.py          Hash-chained append-only log (sha256, verify())
  api.py            FastAPI service (import-guarded; app is None without it)
  cli.py            CLI demo
```

See [docs/architecture.md](docs/architecture.md) for the compatibility
semantics, wire format, and design decisions in full.

## How to run

```bash
pip install -r requirements.txt   # core needs stdlib only; FastAPI optional
make test                          # pytest, stdlib-only
make demo                          # register -> evolve -> validate -> serde -> audit
make serve                         # FastAPI on :8000 (needs fastapi + uvicorn)
```

API (when serving): `GET /subjects`, `POST /subjects/{subject}/versions`,
`GET /subjects/{subject}/versions/{version}`,
`POST /subjects/{subject}/versions/{version}/deprecate`, `GET /audit`.

Docker: `docker build -t event-schema-registry . && docker run -p 8000:8000 event-schema-registry`

## Key design decisions and trade-offs

- **Strict mode fail-closes.** A breaking registration raises instead
  of landing, unless an approver + reason override is supplied — and
  that override is itself audited. Convenience never silently wins
  over consumer safety.
- **Validation reports all errors, not the first.** Producers fix a
  record in one pass instead of iterating error-by-error.
- **Coercion is conservative: integer → number only.** Strings are
  never parsed into numbers and booleans are never integers. Silent
  reinterpretation is how data corruption starts.
- **Serde fail-closes on unknown schema ids.** An undecodable record
  is an error, never a guess — guessing is how poisoned data enters
  a warehouse.
- **Audit log is hash-chained, not a blockchain.** It detects
  tampering by anyone who cannot rewrite the whole chain, which is
  the right bar (and cost) for an internal registry log.
- **Stdlib-first core, guarded FastAPI.** The registry logic has no
  web-framework dependency, so it can be embedded in producers,
  consumers, and tests alike.
- **CI ships as `docs/github-actions-ci.yml`.** The push integration
  rejects `.github/workflows/`; moving the file there activates it
  unchanged.

## What it demonstrates

Versioned schema governance, compatibility reasoning in both
directions, contract-based impact analysis before deployment,
fail-closed serialization, and auditable change control — the
building blocks of a data platform that can evolve without breaking
its consumers.
