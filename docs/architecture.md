# Architecture

## Diagram (description)

```
Producer ──register──▶ Registry (subjects → immutable versions)
                              │ strict-mode compatibility check
                              │ (BACKWARD/FORWARD/FULL/NONE)
                              ▼
                       Audit log (hash-chained)
Producer ──encode──▶ Serde (ESR1 framing + schema id) ──wire──▶ Consumer
Consumer ──decode──▶ schema-id resolution → validation → record
Consumer pins ──▶ ContractStore ──upgrade impact report──▶ Producer
```

## Compatibility semantics

| Change | BACKWARD (new reads old) | FORWARD (old reads new) |
|---|---|---|
| Add required field, no default | ❌ break | ✅ ok (old ignores it) |
| Add optional / defaulted field | ✅ ok | ✅ ok |
| Remove required field | ✅ ok (extra ignored) | ❌ break |
| Remove optional field | ✅ ok | ✅ ok |
| Widen integer → number | ✅ ok | ❌ break |
| Narrow any type | ❌ break | ❌ break |
| Optional → required | ❌ break | ✅ ok |
| Required → optional | ✅ ok | ❌ break |

FULL is the union of both columns; NONE accepts everything.

## Wire format (serde)

```
b"ESR1" | uint32 big-endian len(schema_id) | schema_id utf-8 | payload JSON utf-8
```

Example schema id: `order.created:v2`. Decoding resolves the id in
the registry, rejects unknown ids, validates the payload against
that exact version, and applies only safe (integer → number)
coercion.

## Evolution strategy

Never delete-then-add in one version. The planner's safe sequence is:
(1) add a field as optional/with a default, (2) deploy readers,
(3) tighten to required, (4) deprecate the old field, (5) remove it
only after the upgrade-impact report shows no consumer reads it.
Breaking changes require an audited override (approver + reason).

## Audit log

Entries: `{index, timestamp, action, actor, details, prev_hash, hash}`
with `hash = sha256(prev_hash + canonical_json(payload))`.
`verify()` replays the chain; editing any entry breaks all later
hashes. Actions recorded: `register`, `deprecate`,
`compatibility_override`.

## Trade-offs and limits

- In-memory registry: persistence (e.g. a database-backed store) is
  the natural next step; the `Registry` API is deliberately
  storage-agnostic so it can be swapped without touching callers.
- Flat fields only (no nested objects/arrays in this version):
  nested schemas would reuse the same compatibility rules recursively.
- No schema-id numeric registry (unlike Confluent's integer ids):
  human-readable `subject:vN` ids keep debugging trivial at this scale.
