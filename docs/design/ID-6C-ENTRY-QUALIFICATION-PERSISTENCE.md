# ID-6C — Entry Qualification Persistence Design

**Status:** Implemented. Read for the exact contract before touching
`entry_qualifications` or `SqliteRepository`'s ID-6C methods.
**Depends on:** ID-6A (`EntryQualification` domain contract), ID-6B.2/ID-6B.2A
(the pure engine — owner-closed, methodology frozen, input-coherence
hardened).
**Does not:** change the v0 readiness methodology, wire production
workflow, add API/UI, or resolve Decision supersession.

## 1. Scope

ID-6C persists exactly what `EntryQualificationEngine.evaluate()` already
concluded. It stores; it never reinterprets. All ten frozen ID-6B.2/2A
decisions (formula, tri-state logic, state precedence, Option C, WATCH/TRADE
parity, confirmation, evidence-finality passthrough, point-in-time
semantics, input-coherence rules) are out of scope for this milestone and
were not touched.

## 2. Append-only observation model

`EntryQualification` is a point-in-time, non-sticky evaluation — ID-6B
measured ~40% checkpoint-level flicker on the underlying rule. Persistence
therefore models **observations**, never a mutable "current state" row.
Each `save_entry_qualification` call either inserts a new row or is a
no-op; it never overwrites an earlier observation's payload.

## 3. Logical identity / idempotency key

The table's composite primary key is:

```
(instrument_id, session_date, as_of, decision_id, methodology_version)
```

This is the natural identity of "one candidate, evaluated at one checkpoint,
against one canonical Decision, under one methodology version." A
deterministic engine re-evaluating the identical logical candidate — even
under a *different* `run_id`/`cycle_id` — must produce the identical
payload, so `run_id`/`cycle_id` are deliberately **excluded** from both the
identity key and the conflict comparison; they are stored as informational
provenance only (whichever write actually landed keeps its own values —
the first write's provenance wins on a no-op repeat).

## 4. Write semantics

`SqliteRepository.save_entry_qualification(eq, *, persisted_at)`:

1. Look up the existing row (if any) by the logical identity key, inside
   one write-locked transaction.
2. **No existing row** → insert; returns `True`.
3. **Existing row, identical methodology-relevant payload** (`decision_type`,
   `state`, `evidence_finality`, `confirmation`, `reason_codes`,
   `evidence_refs`, `config_snapshot_id`, `explanation`) → no-op; returns
   `False`.
4. **Existing row, genuinely different payload** → raises `RepositoryError`
   naming every conflicting field. This is an integrity problem (the
   engine is supposed to be deterministic), never a silent overwrite.

The read-then-write is not a check-then-insert race: both steps run inside
the same `self._lock` + `with self._conn:` transaction already used
elsewhere in `SqliteRepository` for multi-step operations (mirrors
`confirm_portfolio_import`), so it is atomic under this repository's
existing single-writer-connection architecture — no new locking
infrastructure was introduced.

## 5. Read API

| Method | Purpose |
|---|---|
| `get_entry_qualification(...)` | Exact logical-identity lookup (the same key `save` uses) — round-trip verification and audit. |
| `latest_entry_qualification_for_decision(decision_id)` | Most recent observation bound to one canonical Decision. Does **not** resolve whether that Decision is still current/non-superseded — see §7. |
| `latest_entry_qualification_for_instrument_session(instrument_id, session_date)` | Most recent observation for one instrument's session, across whichever Decision(s) were evaluated that day. |
| `list_entry_qualifications_for_instrument_session(instrument_id, session_date)` | Full append-only history, oldest first — the one audit query added beyond what a future workflow strictly needs. |

Ordering is always `as_of DESC` (or `ASC` for the history list) with
deterministic tie-breakers (`decision_id`, `methodology_version`) — never
insertion/`persisted_at` order, so a "latest" query always means latest
*market-time*, not latest *write-time*.

A **point-in-time** (`as_of <= requested_as_of`) query was deliberately
**not** added — no current ID-6D/replay need justifies it yet; it belongs
to whichever milestone (likely ID-6E replay) first needs it.

## 6. Schema

`SCHEMA_VERSION` 16 → 17. New table `entry_qualifications`
(`src/athena/data/store/schema.py`), FK-referencing `decisions(decision_id)`
— consistent with `decision_traces`/`decision_journal`/`trade_outcomes`.
One explicit index, `idx_entry_qualifications_decision (decision_id, as_of
DESC)`, supports `latest_entry_qualification_for_decision`; the primary
key's own implicit index already begins `(instrument_id, session_date,
as_of, ...)`, which is exactly the shape
`latest_entry_qualification_for_instrument_session` needs, so no second
explicit index was added.

Enums are stored as `.value` strings; `reason_codes`/`evidence_refs` as
JSON arrays (`json.dumps([...])` — order-preserving, since `sort_keys=True`
only sorts keys *within* each object, never array element order);
timestamps as ISO-8601 tz-aware text; `Decimal`s N/A here. All matches
existing `serialization.py` convention exactly (see `decision_to_row`/
`trace_to_row` for the precedent).

## 7. Decision supersession — explicitly deferred

ID-6B.2A froze: *"Current/non-superseded Decision selection is a
caller/workflow responsibility."* ID-6C preserves that boundary exactly.
`latest_entry_qualification_for_decision` retrieves what was persisted for
a *given* `decision_id` — it does not know or decide whether that Decision
is still the instrument's current one. Resolving that is ID-6D's job, using
real repository state this persistence layer does not attempt to interpret.

## 8. No knowledge-time claim

This table adds historical audit state **from the point a caller starts
persisting observations onward** — it does not retroactively reconstruct
live knowledge-time state that was never captured. The engine is not even
production-wired yet (ID-6D), so no observations exist until that wiring
(or a manual replay) starts calling `save_entry_qualification`. This is not
a solution to, or an extension of, ID-5's knowledge-time limitation.

## 9. No workflow wiring

Nothing in this milestone invokes `EntryQualificationEngine` from
production, schedules it, resolves a current Decision, resolves
`evidence_finality`, or fetches `SessionContext`/`IntradaySignalSet` at
runtime. `entry_qualifications` remains empty in the real `db/athena.db`
until ID-6D wires it in.
