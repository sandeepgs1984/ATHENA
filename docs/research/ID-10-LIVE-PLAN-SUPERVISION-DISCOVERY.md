# ID-10 — Live Plan Supervision Discovery + V0 Contract

Status: **VWAP COMPOSITION CONTRACT — READY FOR OWNER / CHIEF ARCHITECT
FREEZE.** Read-only discovery/design only. Zero code changes, zero
production impact, zero schema change. See §0 for the first correction
round's record (path-dependence of invalidation/target progress); §9/§12
for this third round's fix (VWAP is session-cumulative from canonical
session start, never from the supervised `EntryActionability`'s own
`evidence_as_of` — the VWAP *source* window and the supervision *event*
window are two different things and must never be merged); §1 for what
survived Owner source review unchanged from the original pass.

## 0. Correction round (2026-09-08) — summary

The Owner/Chief Architect reviewed the original discovery pass against
the authoritative frozen sources (`entry_actionability_engine.py`,
`docs/research/ID-8-FULL-HISTORICAL-ENTRY-RISK-OUTCOME-VALIDATION.md`)
and found three corrections required before V0 could be considered
ready to freeze:

1. **Hard invalidation was wrong.** The original pass proposed comparing
   the latest completed M5 close against `EntryActionability.operative_
   invalidation.level` as the forward invalidation line. A direct source
   read (§7 below) confirms `operative_invalidation.level` is a **frozen
   VWAP snapshot from the synchronous entry checkpoint**, not a forward-
   updating reference — reusing it as a moving invalidation line would
   silently check against a stale number. The frozen ID-7B/ID-8
   "VWAP-loss" methodology is defined against the **evolving,
   session-cumulative VWAP recomputed at every subsequent completed M5
   checkpoint** — corrected in §7/§8/§10.
2. **WEAKENING had no source-grounded basis of its own.** Once hard
   invalidation is correctly the evolving-VWAP-loss event, none of the
   candidate soft signals (RS delta, RVOL delta, session-time, M5/M15
   structure) survive as a genuinely separate, deterministic, evidence-
   backed rule. WEAKENING is deferred (§8/§10) rather than kept merely
   for a richer-looking state model.
3. **Target-progress composition was under-specified.** A single
   `latest_completed_m5` candle cannot answer "was T1/T2 already touched
   earlier, before this checkpoint" — target reachability is path-
   dependent across every completed M5 bar between the supervised
   `EntryActionability`'s own checkpoint and now. Corrected in §9/§10.

Additionally corrected: superseded ID-8 figures (T1 23.88%/T2 14.81%,
the pre-correction-round denominator of 783) were replaced with the
report's own final, corrected figures (denominator 756) — §6.

Everything in §11's list was reviewed and confirmed to survive
unchanged — nothing there was reopened.

## 1. Existing architecture inventory

*(Unchanged from the original discovery pass — preserved verbatim, per
§11 of this round's authorization.)*

| Area | Key finding |
|---|---|
| Notifications/alerts | `BriefingDispatcher` is a batch, once-per-run digest (day summary, journal prompts, near-misses at build time). No re-check/notify-on-change mechanism exists anywhere. The project's own UX roadmap confirms this explicitly: "every alert today is an ops-failure notice, never a trading condition the owner defines" (`docs/design/ATHENA-DARVAX-UX-ROADMAP.md:101`). |
| `plan-freshness` API | The closest-named existing artifact (`GET /decisions/{id}/plan-freshness`) is a **pure time-decay clock** over `TradePlan.valid_from/valid_until` (`decisions_service.py:793-826`). It never reads current price, VWAP, or any technical condition. `FRESH/AGING/STALE/EXPIRED` vocabulary and DTO shape are reusable; the computation is not. |
| Dashboard | Client-side JS (`05-utils.js:101-197`) duplicates the same time-decay formula and renders badges; a separate, unrelated "stale" vocabulary exists for market-data ingestion staleness (don't conflate). |
| Dormant P5 order-lifecycle | `OrderLifecycleEngine`'s state machine (`config/models.py:1442-1459`) is pure order-fill mechanics. Its own module docstring states it does "NO market analysis." Zero thesis-revalidation concept anywhere in `orders/`/`execution/`/`brokers/`. |
| Portfolio Structural/Daily Review | The **closest real precedent** for "does this thing I already recommended still hold." `PortfolioDailyReviewStatus` and `PortfolioStructuralReviewResult` are both **recomputed fresh every call from current evidence — no stored FSM**, each paired with a closed reason-code enum, an `as_of`/`evidence_as_of`/`methodology_version` provenance triple, and a template-composed guidance string. This shape — not the D1/portfolio content — is the strongest transferable design pattern in the codebase. |
| EMR live-scanner state machine | `ScannerState` (8 states, `state_machine.py:24-32`) is a genuine **stateful** precedent (pure `determine_next_state` + caller-replayed session memory). Rejected for V0 — see §11/§13 (persistence). |
| DarvaX `action_for_held` | A **stateless**, position-aware reclassification re-evaluated fresh from current structural state every call. Twin technical/plain-English reason fields are a good explainability pattern to reuse. |
| ID-9 currentness dependency | `PositionSizing` already consumes `entry_actionability_currentness.is_currently_usable(...)` as a mandatory caller-supplied input — "is the evidence still fresh enough to size" is already solved upstream. ID-10 answers a different, later question. |
| ID-8 historical module | `forward_candles` and `_vwap_at` (`id8_entry_risk_outcome_validation.py:409,441`) are reusable point-in-time/forward-window *research* primitives. RS/RVOL were only ever measured at entry, never tracked forward. |
| Workflow DAG | 13 stages, `position_sizing` declared last, zero persistence. `WorkflowContext.get()` is a flat namespace; the real `Decision`/`ScanCapture` object lives in a closure-local `box["cap"]` var only reachable inside the same `builder()` closure in `owner_validation.py`. |
| FAST-tier | Runs the exact same 13-stage DAG via the same `OwnerValidationPipeline`; no `trigger` threading exists, so a new stage automatically runs on both REFRESH and FAST ticks. |
| Cadence | REFRESH = 15 min (`base.json:refresh_interval_minutes`). FAST = 10 min, 5m-only, `include_daily=False`, 150-symbol cap. Currentness freshness bound = 600s. |

## 2. Reusable vs. legacy components

*(Unchanged — preserved per §11.)*

- **REUSE (as-is, never modify):** `entry_actionability_currentness.is_currently_usable(...)`; `session.latest_completed_candle`/`is_candle_completed`/`completed_candles`/`classify_session_phase`; `indicators.calculations.vwap(...)`; the persisted, immutable `EntryActionability` artifact and its exact field set; `RelativeStrengthContext`/`RelativeVolumeContext` (fresh, current-cycle reads only).
- **REUSE_WITH_ADAPTER:** `plan-freshness`'s status vocabulary and dashboard badge pattern; ID-8's `_vwap_at`/forward-walk *semantics* (not its private `ReadOnlyStore` implementation — see §7 correction); DarvaX's twin reason-field pattern; the Portfolio Review provenance-triple + closed-reason-code-enum + template-guidance shape.
- **LEGACY_COMPATIBILITY_ONLY:** the entire dormant P5 order/execution/broker pipeline.
- **RESEARCH_ONLY (pattern, not code):** EMR's `ScannerState`/`determine_next_state` shape; Portfolio Structural/Daily Review's exact D1 content.
- **NOT_APPLICABLE:** `notifications/`'s existing alert/briefing machinery for the core supervision computation.

## 3. Canonical upstream input

*(Unchanged — preserved per §11.)* A single, specific, already-persisted `EntryActionability` row, identified by its own full composite key — not "whatever is currently latest," and not `PositionSizing`, which cannot serve as an identity anchor since it is never persisted. Supervision of one specific such row is well-posed: is it still the reigning one (currentness), and has live evidence since its own `entry_actionability_as_of` broken the frozen invalidation rule this correction round redefines in §7-§8.

- Is `EntryActionability` alone sufficient? **Yes.**
- Is `PositionSizing` required? **No** — decorative context only, same-cycle, never an identity anchor.
- Does supervision require `SIZED`? **No.**
- Supersession handling: already free, via `is_currently_usable` → `SUPERSEDED` (§7 keeps this orthogonal to market invalidation).

## 4. Direction scope

*(Unchanged.)* LONG only. A SHORT (or `NONE`) `EntryActionability` is refused with a dedicated `UNVALIDATED_DIRECTION` reason code (mirroring `PositionSizingReasonCode.UNVALIDATED_DIRECTION` verbatim), before any supervision evidence is composed. Empirically reinforced: ID-8 found 100% of real SHORT `TRADE`+`QUALIFIED` rows fail at the `EntryActionability` layer itself (`INVALIDATION_UNAVAILABLE`).

## 5. Candidate supervision dimensions (superseded by §8's corrected table — retained here only as the pre-correction record)

*(See §8 for the corrected, authoritative classification. The original table incorrectly split "evolving VWAP loss" as soft and "frozen operative_invalidation.level breach" as hard — exactly backwards per §7's finding.)*

## 6. Corrected ID-8 figures (authoritative, replaces superseded 783-denominator numbers)

Source: `docs/research/ID-8-FULL-HISTORICAL-ENTRY-RISK-OUTCOME-VALIDATION.md`, corrected-denominator section (lines 115-259). LONG population: **783 total observations, 756 forward-data-bearing** (27 excluded for insufficient forward data, population identity unchanged from ID-7B.1's own published count).

| Metric | Corrected value | Source line |
|---|---|---|
| T1 intrabar hit rate | **248/756 = 32.80%** (median time-to-hit 55.0 min) | `:184` |
| T2 intrabar hit rate | **147/756 = 19.44%** (median time-to-hit 75.0 min) | `:189` |
| VWAP-loss event rate | **505/756 = 66.80%** | `:243` |
| Median time-to-VWAP-loss | **40.0 minutes** (p90 173.0 min) | `:247` |
| Terminal ordering — `INVALIDATION_FIRST` | **417/756 = 55.16%** | `:257` |
| Terminal ordering — `TARGET_SIDE_NO_LATER_THAN_INVALIDATION` | **194/756 = 25.66%** | `:258` |
| Terminal ordering — `SESSION_END_NO_RESOLUTION` | **145/756 = 19.18%** | `:259` |

These three terminal-ordering categories sum to exactly 100% of the 756 denominator (report's own note, `:261`) — no observation double-counted. All figures cited going forward (§14 of the original pass, and any future ID-10 report) must use this table, not the pre-correction 783-denominator numbers.

## 7. Confirmed `EntryActionabilityEngine` construction of `operative_invalidation.level` (confirmatory read, ID-7 methodology NOT reopened)

Direct source read, `src/athena/intraday/entry_actionability_engine.py:376-429`:

```python
entry_price = candle.close
evidence_as_of = candle.ts_open + _M5_BAR_DURATION
...
deviation_pct = (entry_price - vwap) / vwap * Decimal(100)
entry_location_context = EntryLocationContext(vwap=vwap, vwap_deviation_pct=deviation_pct)

if not _geometry_valid(decision.direction, entry_price, vwap):
    ...  # UNKNOWN / INVALIDATION_UNAVAILABLE

operative_invalidation = OperativeInvalidation(level=vwap, basis=InvalidationBasis.VWAP_LOSS)
```

- `vwap` here is `market_evidence.session_vwap` — the session-cumulative VWAP value **as supplied by the same synchronous checkpoint** that produced the completed M5 entry candle (`session_vwap_as_of == candle.ts_open + 5min`, an invariant `EntryActionabilityMarketEvidence.__post_init__` already proves, per ID-7C.1).
- `operative_invalidation.level` is therefore **literally the VWAP number at one single instant** — the moment `EntryActionabilityEngine.evaluate` ran — assigned once and frozen forever into the immutable, persisted `EntryActionability` row. Nothing re-reads or updates it after construction.
- Session-cumulative VWAP is, by its own definition (`indicators/calculations.py`'s `vwap()` — cumulative typical-price × volume from session open through `as_of`), **evolving through the session and recomputed at each completed-M5 checkpoint** — its value at 09:30 and its value at 11:00 for the same instrument are different numbers by construction, not the same reference re-observed. (Correction, this round: this is *not* claimed to be monotonic — a cumulative VWAP can move up or down as new bars are incorporated; the only claim is that it changes and must be recomputed, never that it moves in one direction.)
- **Why it represents synchronous checkpoint risk geometry, and must not be reused as the evolving future VWAP value:** this snapshot exists to give `PositionSizingV0Engine.per_share_risk = entry_reference_price - operative_invalidation_level` a **fixed** number to size a position against — sizing math structurally requires a static risk distance, not a moving target. Reusing that same frozen number as a *forward* invalidation test would mean checking a live price at 11:00 against what VWAP was at 09:30 — a stale, methodologically meaningless comparison the frozen ID-7B/ID-8 "VWAP-loss" concept never intended and ID-8 never validated that way.
- **Confirmed correction:** the forward hard-invalidation test must recompute the SAME `vwap()` function fresh at each future completed-M5 checkpoint (exactly ID-8's own `_vwap_at` pattern) and compare the current completed M5 close against *that* evolving value — never against the frozen `operative_invalidation.level`.

No ID-7 methodology was reopened, reinterpreted, or changed by this read — this is a confirmation of existing, unmodified behavior.

## 8. Revised V0 dimension classification (corrected, authoritative — replaces §5)

| Dimension | Classification | Reasoning |
|---|---|---|
| **Evolving session VWAP close-loss** (current completed M5 close vs. VWAP recomputed at that same checkpoint) | **V0_BINDING — HARD INVALIDATION** | This *is* the frozen ID-7B/ID-8 "VWAP-loss" methodology, applied forward instead of once at entry. Reuses `vwap()` unmodified; zero new methodology. |
| **Frozen `operative_invalidation.level`** | **CONTEXT / ORIGINAL RISK GEOMETRY ONLY — NOT forward invalidation** | Retained and echoed for provenance (original risk geometry, `EntryActionability`'s own record, ID-9 sizing geometry) — never compared against a future checkpoint (§7). |
| **Target progress** (T1/T2 intrabar touch, path-dependent) | **V0_INFORMATIONAL, path-dependent** | Reuses ID-8's own validated intrabar-touch convention and corrected hit-rate evidence (§6); requires the bounded candle-path composition in §9/§10, not a single candle. Never gates; never becomes execution language. |
| **Relative strength delta vs. entry** | **DEFERRED** (or context-only, current-cycle reading) | No confirmed, cleanly-sourceable persisted entry-time RS baseline to diff against (open evidence gap, unchanged from original pass). |
| **Relative volume delta vs. entry** | **DEFERRED** (or context-only) | Same reasoning. |
| **Session/time budget** | **CONTEXT_ONLY, no gate** | ID-8's own finding is explicitly correlational and mechanism-unresolved ("no gate is proposed from either framing" — ID-8-FULL-HISTORICAL...:426). Raw remaining-session-time fact only. |
| **M5/M15 structural weakening** (beyond VWAP) | **DEFERRED** | No already-frozen deterministic source rule exists beyond OR15/session VWAP; inventing one would be new methodology. |
| **Upstream currentness/supersession** | **V0_BINDING, mandatory gate, orthogonal** | Reuse `is_currently_usable(...)` exactly as-is (§10/§11). |
| **WEAKENING as its own verdict** | **DEFERRED** | No dimension above survives as a genuinely separate, deterministic, evidence-backed *soft* signal once hard invalidation is correctly the evolving-VWAP-loss event (§0 item 2) — see §10. |

## 9. Corrected target-progress evidence composition — and the same defect class in invalidation

**The defect (target progress):** a single `latest_completed_m5` candle cannot answer "was T1/T2 already touched earlier, before this checkpoint" — the worked example in the authorization (T1 touched at 10:15, retraces, evaluated at 11:00) shows a single-candle read would falsely report `NONE_REACHED`.

**A second, load-bearing instance of the identical defect class was found this round: hard invalidation.** The corrected §7/§8 rule ("current completed M5 close vs. evolving VWAP at that checkpoint") is *directionally* correct but, read literally as two current-checkpoint scalars, has exactly the same path-dependence bug as target progress: if VWAP-loss triggered at 10:40 and price later recovers back above the evolving VWAP by 11:00, a **current-checkpoint-only** comparison would incorrectly report `VALID` at 11:00. Invalidation is an event that happened somewhere in the supervised plan's path, not merely a fact about the current instant — once true, it stays true for that plan, regardless of later recovery. **Both target progress and invalidation are therefore path-dependent facts over the identical bounded candle window, and both are corrected together here.**

**A third correction, this round: the supervision-event window and the VWAP-source window are not the same thing, and conflating them would silently redefine the frozen methodology.** `vwap()` is *session*-cumulative — its value at any checkpoint T is defined over candles from the canonical session start through T (`indicators/calculations.py`'s own definition, reused unmodified by `EntryActionabilityEngine` itself). Fetching candles only from `EntryActionability.evidence_as_of` onward and calling `vwap()` over that narrower window would compute a **different, unvalidated "post-entry-window VWAP"** — not the session-cumulative VWAP ID-7B/ID-8's own frozen methodology means by "VWAP-loss." Two windows must therefore be kept explicit and never merged:

- **VWAP source window** — canonical session start through the current evaluation checkpoint. Used *only* to calculate the correct session-cumulative VWAP value at each checkpoint being tested. Every checkpoint's VWAP is computed from the *same* session-start origin, exactly matching how `EntryActionabilityEngine` itself computes it at entry.
- **Supervision event window** — strictly after the supervised `EntryActionability`'s own `evidence_as_of`, up to (inclusive of) the current evaluation checkpoint, bounded by the canonical session close, never a candle after "now." Used only to decide *which checkpoints* are eligible to register a VWAP-loss or target-touch event for *this specific plan* — evidence from before the plan existed is irrelevant to "did this plan's price action violate VWAP-loss," even though that same pre-entry evidence is mandatory input to computing what VWAP itself equals.

This mirrors ID-8's own `forward_candles`/`_vwap_at` *semantics* exactly (same "never future" boundary rule; same separation, in the research module, between the full historical candle read and the specific forward window under test) — but **not** its private implementation, which reads directly off a raw research-only SQLite connection (`ReadOnlyStore`) never meant to cross into production (§12 addresses the production-safe replacement).

**a) `TargetProgressEvidence`** — needs **only the supervision event window** (target reachability is intentionally scoped to "after this plan began," and touching a goal band requires no session-history context to evaluate). For each candle in that window, direction-aware intrabar touch against `reward.t1_price`/`t2_price` (LONG: `candle.high >= t1_price`), taking the first such touch chronologically; `NONE_REACHED` if none touch either level. (Unchanged from the prior correction round.)

**b) `VwapLossEvidence`** (new last round, composition corrected this round) — needs **both windows**: for each candle in the *supervision event window*, in chronological order, recompute `vwap()` using the *VWAP source window* (session start through that candle's own completion instant) — never the frozen `operative_invalidation.level`, and never a window starting at `evidence_as_of` — then check the direction-aware close-confirmed relation (LONG: `candle.close < evolving_vwap_at_that_checkpoint`). Record the **first** candle in the event window (chronologically) where this is true, if any. Proposed minimal fields, named/typed to match this repository's own value-object conventions (frozen dataclass, `Decimal` prices, tz-aware `datetime`):

```python
@dataclass(frozen=True, slots=True)
class VwapLossEvidence:
    triggered: bool
    first_triggered_as_of: datetime | None   # the triggering candle's own completion instant
    trigger_close: Decimal | None            # that candle's close
    trigger_vwap: Decimal | None              # the evolving VWAP at that same instant
    # Current-checkpoint relation, kept separate from the historical fact
    # above for presentation only — never a substitute for `triggered`:
    current_close: Decimal | None
    current_vwap: Decimal | None
    currently_above_vwap: bool | None
```

`triggered`/`first_triggered_as_of`/`trigger_close`/`trigger_vwap` are all `None`/`False` only when the currentness gate itself failed (§10) — for every genuinely evaluated LONG/CURRENT case, `triggered` is a definite `True`/`False` fact about the whole bounded path, never re-derived from `current_close`/`current_vwap` alone. **The key invariant, proven by construction, not merely asserted:** once `triggered == True` for a given bounded path, no later evaluation of that same, still-identified `EntryActionability` can ever recompute `triggered == False` — every future evaluation re-walks the *same* historical candles (plus any new ones appended at the end) and the *same* trigger candle, once found chronologically first, is still the chronologically-first trigger in any longer path that includes it. Recovery above VWAP at a later candle cannot erase an earlier `True` — it can only ever add candles *after* the trigger, which the "first chronologically" rule already ignores. No persisted state machine is required for this guarantee — it falls directly out of recomputing a deterministic function over a monotonically-growing (in time, not in VWAP value) bounded window every time.

This composition happens entirely in the **workflow stage** (I/O, repository-bound), producing two immutable, already-computed evidence objects that are *passed into* the pure engine — the engine itself never reads a candle series, recomputes VWAP, or does its own repository work (§10's invariant). The two composers are symmetric in *what kind of window* they evaluate events over (the same supervision event window) but not in *what raw candle data* they require — `VwapLossEvidence` additionally needs the session-history prefix that `TargetProgressEvidence` never touches (§12).

## 10. Revised state model and pure-engine contract

### State model

Three orthogonal dimensions (unchanged shape from the original pass, now evidence-consistent):

1. **Currentness** — reused verbatim: `CURRENT / STALE / SUPERSEDED / SESSION_CLOSED / METHODOLOGY_NOT_ACTIONABLE`. Never itself a market verdict.
2. **Supervision state** — meaningful only when (1) is `CURRENT` and direction is `LONG`:
   - `NOT_APPLICABLE` — non-`CURRENT` currentness, or SHORT/`NONE` direction, or upstream not `ACTIONABLE`. Reason codes: `UPSTREAM_NOT_CURRENT` (mirroring `PositionSizingReasonCode`'s own name for this exact situation), `UNVALIDATED_DIRECTION`, `UPSTREAM_NOT_ACTIONABLE`.
   - `VALID` — currentness `CURRENT`, direction `LONG`, `vwap_loss_evidence.triggered is False` (§9 — evaluated over the *entire* bounded path since the supervised checkpoint, not just the current instant).
   - `INVALIDATED` — `vwap_loss_evidence.triggered is True` — an event fact about the path, permanent for this specific `EntryActionability` once true (§9's invariant), never reverted by a later candle's own current-checkpoint relation recovering above VWAP. Reason code: `VWAP_LOSS`.
   - **`WEAKENING` is DEFERRED** — no dimension in §8 survives as a distinct, deterministic, evidence-backed soft signal separate from `INVALIDATED`. If the Owner wants it reinstated, it needs its own explicitly source-proven rule first, not reintroduction "for state-model richness."
3. **Target progress** — orthogonal, informational: `NONE_REACHED | T1_REACHED | T2_REACHED`, computed per §9, never gating, never execution language.

### Pure-engine contract (revised this round — replaces raw current-checkpoint scalars with the path-derived evidence object from §9)

```python
def evaluate(
    self,
    *,
    entry_actionability: EntryActionability,
    currentness: CurrentnessResult,
    vwap_loss_evidence: VwapLossEvidence,         # precomputed by the workflow stage, per §9
    target_progress_evidence: TargetProgressEvidence,  # precomputed by the workflow stage, per §9
    evaluated_at: datetime,
) -> LivePlanSupervision:
```

Corrected this round: the previous sketch supplied `evolving_vwap_at_checkpoint`/`current_completed_m5_close` as two bare current-instant scalars — insufficient, since (§9) invalidation is path-dependent and a current-instant-only comparison cannot represent "triggered earlier, still true now." Both bounded-path facts the engine needs are now pre-composed, immutable evidence objects:

- `vwap_loss_evidence`/`target_progress_evidence` are **both computed over the identical supervision event window** (§9 — strictly after `evidence_as_of`, up to now), composed once by the workflow stage (which calls `session.completed_candles` + `indicators.calculations.vwap(...)` — both already-reused, already-frozen utilities, per §12) — the engine itself performs zero I/O, zero clock reads, zero repository/provider access, zero candle walking, mirroring `PositionSizingV0Engine`/`EntryActionabilityEngine` exactly. They are **not** derived from identical raw candle inputs: `VwapLossEvidence` additionally consumes the session-history prefix (session start onward) solely to compute session-cumulative VWAP correctly at each event-window checkpoint (§12); `TargetProgressEvidence` needs only the event window itself. Both composers are nonetheless consumed identically by the pure engine, each as one already-decided, immutable fact.
- The engine only interprets `vwap_loss_evidence.triggered` (a already-decided path-wide fact, §9) and `target_progress_evidence`'s own already-decided touch fact — it never re-derives either from a raw candle or a current-instant scalar.
- Gate order inside the engine, mirroring the established "upstream gates before evidence" discipline (ID-7C.2's own precedent): direction check → currentness check → (only if both pass) `vwap_loss_evidence.triggered` check → assemble `LivePlanSupervision` with target progress always attached (informational, independent of the other two gates).

## 11. Confirmation: findings preserved unchanged, per this round's explicit list

All of the following were reviewed and confirmed to survive this correction round unchanged — none reopened:

- `EntryActionability` is the canonical durable anchor (§3).
- `PositionSizing` is not required for supervision identity (§3).
- `SIZED` is not a supervision prerequisite (§3).
- `LONG_VALIDATED_SHORT_UNVALIDATED` remains (§4).
- Derived-only / no persistence is preferred for V0 (unchanged reasoning: `EntryActionability` is already the durable, identity-stable record; supervision is a pure recompute, not a stored FSM).
- `OrderLifecycleEngine` is legacy execution mechanics only (§1/§2).
- EMR's state machine is research-pattern-only, not adopted (§1).
- No owner-configurable trading-condition alerting exists today; delivery stays out of V0 scope (§1/§2).
- No schema bump.
- No broker/order/execution integration.
- REFRESH/FAST cadence unchanged during V0; FAST-tier participation remains automatic-by-default with no new exclusion plumbing proposed.
- The exact upstream currentness helper (`is_currently_usable`) is reused, never duplicated (§10).
- No RS/RVOL numeric thresholds invented (§8: DEFERRED).
- No late-session gate invented (§8: CONTEXT_ONLY, no gate).

## 12. Target-path production composition — corrected fetch strategy and helper contract

**Do not reuse `id8_entry_risk_outcome_validation.ReadOnlyStore`** (or its private `forward_candles`) directly in production — that class opens a raw SQLite connection via a hand-rolled `mode=ro` URI, deliberately isolated for offline research and never intended to cross into the canonical repository abstraction (ADR-002 provider/repository independence).

**Corrected this round: one repository fetch, spanning the session-start-to-now window, is sufficient for both purposes — a second, narrower fetch bounded at `evidence_as_of` is neither necessary nor correct** (it would silently redefine session-cumulative VWAP into a post-entry-window VWAP, per §9's third correction). Proposed production-safe composition, reusing only the *semantics* of ID-8's research module, entirely inside the same workflow-stage pattern `ind_stage`/`entry_actionability_stage` already establish:

- **One fetch, from canonical session start**: `session_candles = self._repo.get_candles(instrument_id, Timeframe.M5, session_day_start, ctx.as_of)` — the exact same shape and origin `ind_stage` already uses for `vwap_raw` (`owner_validation.py:1015`, which *already* starts at session day start, not at any per-instrument evidence checkpoint). No new repository capability, and no second, evidence_as_of-bounded fetch — one read supplies both the VWAP source window and (after slicing) the supervision event window.
- Filter to completed bars via the existing `session.completed_candles(session_candles, Timeframe.M5, as_of=ctx.as_of)` helper (already imported and used at `owner_validation.py:1019`) → `session_completed_m5`. This is the **VWAP source window** (§9): session start through now, used only to compute `vwap()` correctly at any checkpoint within it.
- Derive the **supervision event window** as a plain slice of the same list: `supervised_path = [c for c in session_completed_m5 if c.ts_open >= entry_actionability.evidence_as_of]` (strictly after, per §9) — no second repository call.
- Two independent pure folds, both taking the already-fetched data as plain arguments (no repository/provider/clock access inside either):
  - `compose_target_progress_evidence(supervised_path, reward, direction) -> TargetProgressEvidence` — needs only `supervised_path` (unchanged from the prior round).
  - `compose_vwap_loss_evidence(session_completed_m5, supervised_path, direction) -> VwapLossEvidence` — walks `supervised_path` chronologically for event eligibility, but for each candle recomputes `vwap()` over the *prefix of `session_completed_m5` from session start through that candle's own completion instant* — never over `supervised_path` alone. This signature makes the session-history dependency impossible to omit by construction, rather than relying on a docstring to explain it.
- The explicit, non-negotiable invariant this corrects: **`vwap()` at any checkpoint T is always computed from `session_completed_m5` (session-start origin); event eligibility (which checkpoints may register a trigger/touch) is always restricted to `supervised_path` (post-`evidence_as_of` origin).** These are never the same list passed to the same purpose.
- New pure helper functions (not a new repository method, not a new provider call) belong beside the new engine — e.g. `src/athena/intraday/live_plan_supervision_engine.py` — mirroring how `_vwap_at`/target-touch logic are pure functions of an already-fetched list in the ID-8 research module, just relocated to production-owned, repository-sourced input, with the two-window distinction made explicit in the function signatures themselves.

This is source-design only — no file was created for the engine/helper itself; only this discovery document was written.

## 13. Recommendation: is ID-10 V0 now ready to freeze?

**Yes, the contract itself is now internally consistent and ready for freeze**, pending only the Owner's own explicit sign-off (this document cannot self-approve). This round closed the final load-bearing composition defect: `vwap()` at any supervised checkpoint must be computed from the canonical session start, never from the supervised `EntryActionability`'s own `evidence_as_of` — the supervision *event* window (post-`evidence_as_of`) and the VWAP *source* window (session start) are now kept explicit and never merged (§9/§12), while the path-permanence semantics from the prior round (invalidation is a fact about the whole event window, not the current instant; recovery above VWAP cannot revert a prior `INVALIDATED` verdict) are unchanged. Combined with the earlier round's corrections (§7's confirmed source read, §8's dimension table, §6's corrected figures), there is no remaining known internal inconsistency in the V0 contract.

The still-open evidence gap from the original pass (entry-time RS/RVOL baseline sourceability) remains genuinely unresolved but does not block this freeze — it only matters if/when RS/RVOL are ever un-deferred from §8's `DEFERRED` classification, which itself is not being revisited here.

No independent correctness blocker requiring a sub-milestone was found — this stays the same single discovery → Owner review → V0 implementation path.

## 14. Production safety

Zero files edited other than this discovery document. Zero DB writes, zero restarts, zero code changes. No ID-6/7/8/9 methodology touched (§7 was a read, not a modification). EMR/DarvaX untouched.

---

**ID-10 LIVE PLAN SUPERVISION VWAP COMPOSITION CONTRACT READY FOR OWNER / CHIEF ARCHITECT FREEZE**
