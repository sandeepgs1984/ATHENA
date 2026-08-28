# EM-5 Live Scanner Contract Proposal

| Field | Value |
|---|---|
| Status | **Proposed — awaiting Owner/Chief Architect approval** |
| Date | 2026-08-28 |
| Governing | ADR-012 (Explosive Move Radar Research Boundary), EM-4 Modeling Contract (frozen artifacts), ADR-010 (DarvaX satellite pattern — architectural precedent reused directly) |
| Scope | EM-5 only: live scanner engineering/replay. No UI (EM-6), no shadow validation (EM-7), no canonical integration (EM-8) |

This document is the required pre-implementation deliverable per the
Owner's EM-4 GO decision (2026-08-28): "Before implementation, first
return: EM-5 Live Scanner Contract Proposal... Do not write production
scanner code until that contract is approved." No scanner code has
been written. Every design decision below was checked against the
actual current codebase (cited by file path) rather than invented —
see the grounding notes inline.

---

## 0. What EM-5 is and is not

EM-5 applies the frozen EM-4 model stack (EM-4A deterministic rules +
EM-4B logistic coefficients + EM-4D Platt calibration) to **current**
market evidence, at the 9 already-approved checkpoints, producing a
ranked, explainable, replayable candidate list per checkpoint. It is
an engineering/replay milestone: it must not refit, retune,
recalibrate, or redesign anything EM-4 already froze.

It does **not**: place orders, touch canonical ATHENA `Decision`/
`TradePlan`/scoring/confidence/risk/portfolio, run inside ATHENA's
scheduling cycle, call a market-data provider per symbol, or expose
any UI.

---

## 1. Frozen Model Contract — promotion/hash semantics (revised per Blocker 3)

EM-5 consumes exactly:

- **EM-2 feature contract**: `evidence_contract.EVIDENCE_CONTRACT_VERSION`
  (`em2-evidence-v1`), the 22 `CANDIDATE_FEATURE` fields, unchanged.
- **EM-4B artifacts**: the 18 `artifacts/research/em4b/{FAMILY}_{THRESHOLD}.json`
  files — `feature_names`, `coefficients`, `intercept`, full
  `preprocessing` block, each already carrying its own content-hash
  `run_id`.
- **EM-4D artifacts**: the 18 `artifacts/research/em4d/{FAMILY}_{THRESHOLD}.json`
  files — per-checkpoint `level` (`CHECKPOINT_SPECIFIC` /
  `POOLED_FAMILY_THRESHOLD` / `UNCALIBRATED_INSUFFICIENT_SUPPORT`),
  `platt_a`/`platt_b`.
- **EM-3 register**: `artifacts/research/em3/F_exploratory_candidate_register.json`
  + `manifest.json`'s `bin_edges`, for EM-4A's deterministic vote rules.

**Correction (Blocker 3): the earlier proposal to add a `run_id` field
*inside* the EM-4D source JSON files is withdrawn.** That would have
mutated an already-frozen, already-approved research artifact — not
approved, and unnecessary. The identity/versioning problem is solved
entirely at **promotion time**, without touching a single byte of any
EM-4B/EM-4D/EM-3 source file:

1. **Read** each source artifact's bytes exactly as they sit in
   `artifacts/research/{em4b,em4d,em3}/` — no re-serialization, no
   re-formatting, no key reordering.
2. **Hash** those exact original bytes with SHA256. This is the
   artifact's identity — computed from what's already there, nothing
   recalculated, nothing re-derived.
3. **Derive** a promoted ID from that hash alone, e.g.
   `promoted-em4b-touch-10-{sha256[:16]}` / `promoted-em4d-touch-10-{sha256[:16]}`
   — a label for the promotion record, not a value written back into
   the source file.
4. **Copy** the file byte-identically into
   `config/emr/frozen_models/v1/{em4b,em4d,em3}/...` (same relative
   layout, unmodified content — a `shutil.copyfile`-equivalent, not a
   read-parse-rewrite).
5. **Verify**: `sha256(source_bytes) == sha256(promoted_copy_bytes)`.
   This is a real, automated check (part of the promotion script and
   covered by a test) — not an assumption.
6. **Record** every file's relative path, source path, and SHA256 in
   one top-level `FROZEN_MODEL_MANIFEST.json` under
   `config/emr/frozen_models/v1/` — this manifest is the only *new*
   content; the 18+18+2 promoted files themselves are byte-for-byte
   copies of already-approved, already-frozen research output.

So: **promotion = approved. Content hashing = approved. Mutating any
EM-4B/EM-4D/EM-3 source artifact = not approved, and this design no
longer does it.** EM-5's loader reads only from
`config/emr/frozen_models/`, never from `artifacts/research/`. A
future re-promotion (a new EM-4 cycle, an accepted new model) is a new
versioned directory (`v2/`) with its own manifest — never an in-place
overwrite; old live runs stay replayable against the exact version
they used. This step requires no FINAL_TEST access and recalculates
nothing — it only reads and hashes bytes that already exist.

No fitting library is imported anywhere in the live path — confirmed
achievable: `em4c_scoring.score_logit` (dot product) and
`em4d_calibration.apply_platt_scaling` (2-parameter affine + sigmoid)
are both pure Python already, no numpy/scikit-learn. EM-5's own
architecture test (§16) asserts no `sklearn`/`numpy` import anywhere
under the new live module.

---

## 2. Live Prediction Granularity — checkpoint-price semantic parity: RESOLVED via live diagnostic (was Final Blocker A)

Reuses `explosive_move.contracts.CANDIDATE_CHECKPOINTS_IST` verbatim
(`09:20, 09:30, 09:45, 10:00, 10:30, 11:00, 12:00, 13:00, 14:00` IST) —
no new checkpoint invented, no subset dropped.

**Historical note, kept for the audit trail (see the RESOLVED subsection
below for the outcome).** An earlier draft of this section proposed
`live_price_at_checkpoint` = close of the last candle with
`ts_open < C`, and asserted this was "the same rule, just applied
consistently." That claim was checked, not assumed, and **it is
false**: the frozen model was trained and evaluated on `price_at_checkpoint(C)`
= **open of the candle whose `ts_open == C` exactly** — a different,
specific value — and the audit below shows it materially disagrees
with "prior candle's close" often enough that substituting one for
the other would silently score a different feature than the one
FINAL_TEST actually validated. That prior proposal is **withdrawn**,
not retained.

### Audit method and result

Traced the exact code path: `checkpoint_dynamic_evidence.py:76` calls
`price = price_at_checkpoint(checkpoint_instant, session_candles)`
**once**, and every price-dependent field below reads that same
`price` variable. `price_at_checkpoint` (`event_labels.py:144`)
matches the candle with `candle.ts_open == checkpoint_instant` and
returns `candle.open` — confirmed by reading the function, not
assumed from its docstring.

Then measured, on real EM-1r3 candle data (TRAIN-era instruments, no
labels/outcomes read) whether `candle[i-1].close == candle[i].open`
for consecutive same-session 5-minute candles — i.e., whether "prior
candle's close" would have been a faithful stand-in for "this
candle's open" if it had been used instead:

| Sample | Consecutive candle pairs checked | Exact match (`prev.close == cur.open`) | Mismatch rate | Max abs diff | Median abs diff (mismatches only) | Mismatches > 0.5% |
|---|---|---|---|---|---|---|
| 20 instruments (first pass) | 758,722 | 70.40% | 29.60% | 1.84% | 0.039% | — |
| 60 instruments (random sample, larger) | 3,142,558 | 64.81% | 35.19% | 3.92% | 0.033% | 2,545 |

**Result: Outcome C.** The historical/frozen model used the `ts_open == C`
candle's **open**. In live operation, that exact candle has not closed
yet at the real-time instant checkpoint C occurs (it starts at C), so
its row does not exist in ingested OHLC storage at scan time — using
it would require future information. Substituting the prior candle's
close is not a faithful reproduction: roughly a third of consecutive
candle transitions in real data differ, with mismatches up to ~3.9%
and a non-trivial number (2,545 in the 60-instrument sample alone)
exceeding 0.5% — large enough to flip a 5% threshold decision in a
meaningful fraction of cases. **Per the Owner's explicit instruction
for Outcome C, this is not silently resolved by substitution.**

### Two realistic paths forward (not chosen — returned for Owner decision)

1. **Live LTP/quote snapshot instead of a completed candle.**
   `price_at_checkpoint`'s own docstring describes its *intent* as "the
   first real trade price known at/after the checkpoint instant" — in
   historical replay, a completed candle's `open` is the only way to
   reconstruct that after the fact. In genuine live operation, ATHENA's
   `MarketDataProvider.quotes(instrument_ids)` (`domain/interfaces.py:90`,
   implemented in `kite_provider.py:195`) is an **already-existing,
   already-batched** (not per-symbol) capability, and a canonical
   `quotes` table already exists in `db/athena.db` (confirmed: real
   record counts include `"quotes": 243820`) — so querying the current
   LTP at/immediately after instant C would not be "a new external-data
   source," and would arguably be a *more* faithful live reproduction of
   the same stated intent than either a completed candle's open or the
   prior candle's close. It has not been proven numerically identical
   to `price_at_checkpoint`'s historical value, though — only that it
   targets the same underlying concept via an existing capability. This
   would need its own real-data audit (comparing live LTP to what the
   equivalent completed candle later recorded as its open) before
   trusting it.
2. **Accept the close-of-last-completed-candle substitution
   explicitly**, with the measured discrepancy above documented as a
   known, bounded, live-vs-research definitional difference — i.e.,
   deliberately choose to operationalize a *slightly different* feature
   than the one FINAL_TEST validated, accepting that risk consciously
   rather than by accident. Not recommended without your explicit sign-off,
   given the magnitude measured above.

Neither path above was chosen speculatively — the Owner instead
authorized a real, narrow live diagnostic to test option 1 (the live
LTP/quote path) empirically before committing to it. See the RESOLVED
subsection below for the real, measured result.

### Checkpoint-price-dependent frozen features (exact list)

Traced directly from `checkpoint_dynamic_evidence.py`'s use of the
`price` variable — exactly 7 of the 22 `CANDIDATE_FEATURE` fields (all
`CHECKPOINT_DYNAMIC`, none `SESSION_INVARIANT`):

| Feature | Formula (uses `price`) |
|---|---|
| `DIST_FROM_20D_HIGH_C` | `price / high_20d - 1` |
| `DIST_FROM_20D_LOW_C` | `price / low_20d - 1` |
| `RANGE_POSITION_20D_C` | `(price - low_20d) / (high_20d - low_20d)` |
| `RETURN_FROM_OPEN_C` | `price / session_open - 1` |
| `RETURN_FROM_PREV_CLOSE_C` | `price / prev_close - 1` |
| `DIST_FROM_HIGH_SO_FAR_C` | `price / high_so_far - 1` |
| `VWAP_REL_C` | `price / vwap_value - 1` |

Not price-dependent, confirmed by reading the same function: `REL_VOLUME_C`
(uses cumulative volume only), `RANGE_SO_FAR_C` (uses `high_so_far`/
`low_so_far`/`session_open` only — no `price` reference at all). No
`SESSION_INVARIANT` field touches checkpoint price at all (confirmed:
`session_invariant_evidence.py` has zero references to
`price_at_checkpoint` or `checkpoint_instant`).

All other checkpoint-dynamic evidence fields (`REL_VOLUME_C`,
`HIGH_SO_FAR_C`, etc.) already use the `ts_open < C` boundary
correctly and need no change — this section is exclusively about the
`price_at_checkpoint`/"current price" concept and the 7 features
above.

### RESOLVED (2026-08-28): live parity diagnostic — PARITY ACCEPTABLE, my recommendation

Per the Owner's authorization, ran a narrow, read-only, diagnostic-only
capture (never touching the shared `Quote` type or any production
consumer) against a real, live, interactively-authorized Kite session
during real market hours on 2026-08-28. Full evidence and methodology
in `artifacts/research/em5_diagnostic/` (git-ignored; manifest
`em5-checkpoint-price-diagnostic-6ca8b3854421a7b55e0766d9c28643c1681cc59ef9accf11fe03ed44db21e28a`).

**Schema inspection** (before assuming anything): Kite's real `/quote`
response carries two distinct timestamps — `timestamp` (quote-snapshot
time) and `last_trade_time` (authoritative last-executed-trade time).
The existing `KiteProvider.quotes()` and `kite_ltp.py` both silently
prefer `timestamp` over `last_trade_time` when both are present
(`row.get("timestamp") or row.get("last_trade_time")`) — meaning
neither existing consumer can currently answer "when did a real trade
last occur," only "when did Kite generate this response." A new,
fully isolated module, `em5_checkpoint_price_diagnostic.py`, parses
and persists both fields explicitly and separately; it does not modify
`Quote`, `quotes()`, or `kite_ltp.py`.

**Semantic canary** (90s, 3 instruments, before trusting the semantic
for real capture): **passed**. `last_trade_time` stayed exactly frozen
for a zero-trade instrument (NSE:MRF) across 43 consecutive polls; a
moderate-liquidity instrument (NSE:CHOLAFIN) advanced only on genuine
price-relevant events with zero anomalies. One bounded, understood
limitation found and documented: for an extremely high-frequency name
(NSE:YESBANK), `last_trade_time`'s 1-second resolution occasionally
can't distinguish multiple real trades within the same second (price
ticks while the displayed second stays fixed) — irrelevant at the
checkpoint boundary's minutes-apart granularity, confirmed by the
capture results below showing no degradation for that instrument.

**Live capture**: market was already open when the diagnostic became
ready (11:54 IST) — checkpoints `09:20`–`11:00` are `NOT_OBSERVED_LIVE`
today (not fabricated, not reconstructed). Captured all of `12:00`,
`13:00`, `14:00` against the representative sample (2 high/2 medium/2
low liquidity by real historical TRAIN volume, not future/label data:
`NSE:IDEA`, `NSE:YESBANK` / `NSE:MFSL`, `NSE:CHOLAFIN` / `NSE:MRF`,
`NSE:HONAUT`). **All 18 (instrument x checkpoint) observations
qualified** — zero `NO_CHECKPOINT_PRICE`. Observed first-post-C-trade
latency ranged 0–188s (median liquidity-dependent: near-instant for
the two most liquid names, up to ~2-3 minutes for the least liquid).

**Historical parity** (live first-qualifying-trade price vs. the real,
already-closed M5 candle's `open` where `ts_open == C`, fetched via
`KiteProvider.intraday_candles` after each candle closed):

| Metric | Value |
|---|---|
| Comparable observations | 18 |
| Exact match | 8/18 (44.4%) |
| Median relative difference | 0.0075% |
| Max relative difference | 0.0685% |
| % differing > 0.1% | 0% |
| % differing > 0.25% | 0% |
| % differing > 0.5% | 0% |
| Live qualifying-price coverage | 18/18 (100%) |
| No-post-C-trade count | 0 |

Compare this to the *rejected* prior-candle-close substitution's real
measured mismatch (29.6–35.2% of pairs differing, max 3.92%) — the
live-quote-based checkpoint price is two to three orders of magnitude
closer to the historical value than the substitution the Owner
correctly rejected.

**Seven-feature and frozen-model impact** (real EM-2 session-invariant
evidence computed from real daily bars fetched for these 6 instruments;
the 7 price-dependent checkpoint-dynamic fields computed twice — once
per price variant — through the exact frozen `TOUCH_10` EM-4B
coefficients + EM-4D calibration, no fitting): raw logit differences
ranged `0.0` to `+/-0.046` (small against the model's own real decision-
relevant scale — recall TOUCH_10's own checkpoint-intercept
coefficients alone span `+1.03` to `-1.33`); calibrated-probability
differences ranged `~1e-8` to `~1.3e-5` — negligible next to TOUCH_10's
own real base rate (~0.3-1%). Within this small 6-instrument sample,
relative rank order was **identical** between the two price variants
at all 3 checkpoints (not a substitute for a real top-20/10/5 overlap
test at full-universe scale, which this deliberately small, rate-
limit-safe diagnostic sample cannot support — flagged honestly, not
overclaimed).

**My recommendation: PARITY ACCEPTABLE.** The live quote path — "the
first observed trade whose authoritative `last_trade_time >= C`,"
sourced via `last_price` — is a faithful operational reproduction of
the historical `price_at_checkpoint` concept, well within any
reasonable tolerance for a rare-event model with 5-20% thresholds.
**This is my assessment, not an acceptance decision** — per the
Owner's explicit instruction, EM-5 contract `ACCEPTED` status remains
the Owner/Chief Architect's call.

If accepted: the live semantic target for EM-5's own
`checkpoint_reference_price(C)` becomes "the `last_price` of the first
qualifying `/quote` observation with `last_trade_time >= C`," with
`NO_CHECKPOINT_PRICE` (hard ineligible, §4) for any instrument that
never qualifies within EM-5's own production observation window — a
number still undecided (per the Owner's explicit instruction not to
freeze it from a diagnostic-only bound). This diagnostic's own
window (300s per checkpoint) was itself diagnostic-only, chosen
because today's remaining checkpoints were >=60 minutes apart, not a
proposal for EM-5's production timeout — the real latency distribution
measured above (0-188s across 18 observations, all under a 5-minute
diagnostic bound) is the evidence the Owner should use to set that
number, not this diagnostic's own generous collection window.

---

## 3. Scanner State Machine

Following `execution/engine.py`'s existing, proven pattern
(`LEGAL_TRANSITIONS: dict[State, set[State]]` + explicit validator +
custom error naming the illegal `from → to` pair + immutable event
history) rather than inventing a new style.

**States** (exactly the 8 ADR-012 §9 already names — none added, none
removed): `INACTIVE`, `WATCH`, `DEVELOPING`, `CONFIRMED`,
`HIGH_CONVICTION` (progression), `FADING`, `INVALIDATED`,
`TARGET_REACHED` (terminal/degradation).

**Inputs to a transition decision** (per symbol, per target
family/threshold, evaluated fresh at each checkpoint C from that
checkpoint's own evidence — never carrying hidden state beyond the
persisted prior state itself):
- `rank` among eligible candidates at C (the sole quantitative driver
  of progression/regression — see Blocker 1 correction below)
- `eligibility`/`feasibility` at C (§4) — the sole driver of
  `INVALIDATED`
- whether `TARGET_REACHED` fired (ALREADY_OCCURRED, §5)
- the candidate's own state as of the immediately preceding checkpoint
  (or `INACTIVE` if this is the symbol's first eligible checkpoint
  today)
- `calibrated_probability`/`raw_estimate` is still computed, displayed,
  and persisted on every row (§7) — it is simply not used as a state-
  transition threshold (see below)

**Correction (Blocker 1, approved): every probability-multiple-of-base-rate
threshold in the original proposal (`3x`/`10x`/`25x` FINAL_TEST base
rate, and FINAL_TEST-median-time-to-target-based invalidation) is
withdrawn**, replaced with the approved pre-declared ordinal shortlist
cutoffs: rank `<= 20` → `WATCH`-tier, rank `<= 10` → `CONFIRMED`-tier,
rank `<= 5` → `HIGH_CONVICTION`-tier.

**FADING recovery, completed (this revision)**: the concern was that
`FADING` could become an accidental dead end. It is not, and needs no
special-case "instant recovery" rule — the *same* rank-tier evaluation
that governs forward progression is applied fresh at every checkpoint
regardless of the candidate's current state, so recovery is simply
"the natural result of re-running the one rule every checkpoint,"
never a second recovery-specific rule:

1. Every checkpoint, first check `TARGET_REACHED` (ALREADY_OCCURRED,
   §5) — always takes priority, terminal.
2. Then check `INVALIDATED` — a **hard** eligibility/feasibility
   failure only (§4's `INELIGIBLE` outcomes), never a probability or
   rank condition — terminal.
3. Otherwise, compute the candidate's **rank tier** at C purely from
   its current rank: `HIGH_CONVICTION_TIER` (rank `<=5`),
   `CONFIRMED_TIER` (`5 < rank <= 10`), `WATCH_TIER` (`10 < rank <= 20`),
   or `BELOW_SHORTLIST` (rank `> 20`, or ineligible-this-checkpoint-
   but-not-hard-invalidated, e.g. `FEASIBILITY_UNKNOWN` candidates
   still get a tier from their rank normally).
4. Let `ever_reached` = the highest progression tier this candidate
   has held at any earlier checkpoint this session (`INACTIVE < WATCH
   < DEVELOPING < CONFIRMED < HIGH_CONVICTION`) — a plain, deterministic
   fact read back from this candidate's own persisted transition
   history (§3's event log), not a new hidden variable.
5. Apply the **same** sustained-progression rule in both directions:

| Rank tier at C | New state |
|---|---|
| `HIGH_CONVICTION_TIER` | `HIGH_CONVICTION` if `ever_reached >= CONFIRMED` (already proven once this session, including via an earlier FADING excursion) **or** prior-checkpoint state was `CONFIRMED`; otherwise capped at `CONFIRMED` this checkpoint (must hold `CONFIRMED` for one checkpoint before advancing — no single-step jump) |
| `CONFIRMED_TIER` | `CONFIRMED` if `ever_reached >= WATCH` (i.e. was at least `WATCH`/`DEVELOPING` at some earlier checkpoint) **or** prior-checkpoint state was `WATCH`/`DEVELOPING`; otherwise capped at `WATCH` this checkpoint |
| `WATCH_TIER` | `DEVELOPING` if prior-checkpoint state was `WATCH`/`DEVELOPING`/`FADING` **and** rank is sustained (>=2 consecutive checkpoints in this tier or better) or improved vs. the prior checkpoint; otherwise `WATCH` |
| `BELOW_SHORTLIST` | `FADING` if `ever_reached >= WATCH` (has been in the funnel before); otherwise `INACTIVE` (never yet qualified) |

This is exactly the forward-entry table from the earlier revision,
applied **symmetrically** — a `FADING` candidate whose rank recovers
to `<=20` next checkpoint lands back on `WATCH`/`DEVELOPING` through
the identical rule that would apply to any `WATCH_TIER` rank, and a
candidate that had already proven `CONFIRMED` earlier in the session
does not have to re-earn it checkpoint-by-checkpoint after a
`FADING` dip — it re-enters at the tier its rank justifies, capped
only by whether *this exact session* has already demonstrated that
level of standing (`ever_reached`), never by a probability threshold.
`FADING` is therefore never terminal by construction; only
`INVALIDATED` and `TARGET_REACHED` are.

The rank cutoffs (20/10/5) are still a *configuration* value (in
`config/emr/scanner_thresholds.json`, not hardcoded), but they are
**ordinal shortlist sizes**, not a statistic measured from any
partition — the same kind of "top-N" cutoff already used throughout
EM-4C/EM-4E's own Precision@5/10/20 reporting convention, just applied
operationally here instead of as an evaluation metric.

Every transition is persisted with: `from_state`, `to_state`,
`checkpoint`, the evidence that justified it (rank, eligibility/
feasibility flags, target-reached evidence where relevant), and a
monotonic sequence number — mirroring `execution/engine.py`'s
immutable `ExecutionEvent` log. Config strictness flag
(`enforce_strict_transitions`) reused from that same module's own
precedent: an illegal transition raises loudly rather than silently
coercing state.

**State semantics, restated explicitly per the Owner's brief**: a
state is an experimental research observation only. No state may
authorize a trade, modify ATHENA `Decision`/confidence/risk, affect
portfolio/order/execution, or feed back into model coefficients or
calibration (§12, §16). The reason for every transition is always
persisted (never just the new state in isolation).

---

## 4. Candidate Eligibility — hard vs. contextual, corrected per Blocker 4

The original proposal treated every gate as fail-closed, which would
have let an unrelated, merely-*unavailable* canonical source (e.g. no
authoritative price-band feed for a symbol) silently drop that symbol
from ranking, or even collapse the whole universe if a contextual
source went dark. **Corrected: eligibility is split into two
explicitly different categories.** `UNKNOWN` on a hard input excludes
a candidate; `UNKNOWN` on a contextual input never does — it is
persisted honestly and the candidate is still scored and ranked.

### HARD ELIGIBILITY INPUTS
(missing/failing → candidate excluded from ranking entirely at this
checkpoint, exact reason persisted, never a fabricated default)

1. **Canonical universe membership** — resolved via the existing
   ADR-011 symbol-master/named-universe resolver (`symbols/catalog.py`),
   not re-derived. Missing → `NOT_IN_UNIVERSE`.
2. **Data freshness** — the instrument's most recent ingested candle
   for today must be no older than one checkpoint interval. Stale →
   `STALE_DATA`.
3. **A resolvable live checkpoint reference price** — whichever function
   §2's Final Blocker A resolves to must resolve; without it, the
   feature vector's own reference price is undefined and inference
   cannot run at all. Missing → `NO_OBSERVABLE_PRICE_AT_CHECKPOINT`.
   (This gate's *existence* is settled; its exact source function is
   not, pending §2.)
4. **Known unsupported/special session** — `CalendarEngine.context_for(d)`
   checked once per scan cycle; Muhurat/truncated sessions excluded
   from scanning entirely for the whole session, matching EM-1a's
   existing exclusion semantics.
5. **Price-band feasibility, only when the authoritative source is
   actually known and shows the target is impossible** — see the
   3-way rule below; this is the one case where a *contextual* input
   can still produce a hard `INELIGIBLE` outcome, precisely because
   the evidence is known and conclusive, not because it's missing.

### OPTIONAL / CONTEXTUAL FEASIBILITY INPUTS
(never auto-excludes merely for being unavailable — persisted
honestly, candidate remains scored/ranked)

- **Price-band feasibility** (three-way, not binary):
  - authoritative band known **and** target price is impossible to
    reach within it → `INELIGIBLE` / reason `PRICE_BAND_IMPOSSIBLE`
    (this is the one contextual input allowed to hard-exclude, and
    only because the evidence is *known and conclusive*)
  - authoritative band known **and** target is possible → `FEASIBLE`
  - authoritative band **unavailable** → `FEASIBILITY_UNKNOWN` — the
    candidate is **still scored and ranked**; the uncertainty is
    displayed/persisted, not treated as a failure.
- **Remaining target distance** — informational only (persisted,
  shown), never a gate.
- **Remaining session time** (`remaining_session_minutes`, see gap
  below) — **informational only in EM-5 v1**, per Blocker 1: it is
  persisted alongside each candidate for context, but it does **not**
  invalidate or suppress a candidate, and it is never compared against
  any FINAL_TEST-derived historical time-to-target statistic to make
  an operational decision.
- **Historical excursion context** (EM-4E's real MFE/MAE/time-to-target
  findings) — informational display only (e.g. "historically, this
  target's median time-to-target was ~140 minutes on VALIDATION"),
  never used to gate, invalidate, or reorder a live candidate.
- **Any UNKNOWN evidence field the frozen preprocessing already
  handles via imputation/missing-indicator** (e.g. a continuous
  feature with no known value) — passed through exactly as the frozen
  EM-4B preprocessing spec already handles it in research; this was
  never a gate, only a modeling input, and stays that way.

**Already-occurred target status** is handled by §5 (routes to
`TARGET_REACHED`, not an eligibility exclusion).

**Gap found while grounding this proposal**: no `remaining_session_minutes`
helper exists yet as a reusable function — today it's computed ad hoc,
inline, only inside the historical `em1b_label_dataset_generation.py`
research script. EM-5 will add one pure function,
`athena.calendar.remaining_session_minutes(as_of, session_close)`,
following `resolve_as_of.py`'s existing no-hidden-clock convention
(explicit inputs, no internal `datetime.now()`) — a calendar-module
addition, not new business logic.

---

## 5. ALREADY_OCCURRED

Reuses `event_labels.evaluate_touch_label`/`outcome_from_touch_time`
exactly, unchanged. If the target was already touched strictly before
checkpoint C (by the same `ts_open < C` boundary as research), the
symbol is **not** a forward candidate at C — it is not scored, not
ranked, and does not appear in the eligible-candidate list. It
transitions directly to `TARGET_REACHED` (from whatever state it was
in, or `INACTIVE` if never previously scanned today) with the real
`first_touch_time` persisted as evidence. This mirrors the exact
forward-prediction semantics EM-1b already froze — no new
interpretation of "already happened."

---

## 6. Ranking

One ranking per (session_date, checkpoint) — a single, internally
consistent evidence snapshot. The scan cycle reads all eligible
symbols' evidence at the *same* checkpoint instant before scoring any
of them (§10's bulk-read requirement makes this natural: one grouped
read, one snapshot, then per-symbol scoring against that one
snapshot) — never mixing symbols observed at different times or
different checkpoint model states within one ranked list.

Tie-break and ordering reuse `em4c_ranking.rank_observations`'s
already-frozen, already-tested rule verbatim: score descending,
ties broken by `instrument_id` ascending — the same rule used
throughout EM-4C/EM-4E, not a new one invented for live use.

**Persisted per ranked row**: `rank`, `calibrated_probability`
(nullable — only when the cell's calibration level is not
`UNCALIBRATED_INSUFFICIENT_SUPPORT`), `raw_logistic_estimate` (always
present), `family`, `threshold`, `checkpoint`, `session_date`,
`em4b_model_version` (the promoted-artifact ID derived from its own
source SHA256, §1), `em4d_calibration_version` (same, derived from the
EM-4D source file's own SHA256 — never a field written into the source
file itself), `evidence_timestamp`, `freshness`, `feasibility`, `state`.

---

## 7. Probability Language

Reuses EM-4D's exact, already-decided hierarchy — no new language
invented: `CHECKPOINT_SPECIFIC` or `POOLED_FAMILY_THRESHOLD` →
displayed as **calibrated probability**. `UNCALIBRATED_INSUFFICIENT_SUPPORT`
→ displayed as **raw estimate** (or, in research-facing contexts,
**uncalibrated research score**) — the sigmoid output is never
silently relabeled as a probability. In practice all 162 real
(family, threshold, checkpoint) cells cleared calibration in EM-4D (0
insufficient-support), so live traffic should see calibrated
probabilities everywhere today — but the code path must handle the
uncalibrated case correctly regardless, since a future re-promotion
could reintroduce one.

---

## 8. Flagship Product View

`top_touch_10_candidates(session_date, checkpoint, n)` — a read-only
query over the persisted ranking table, filtered to `TOUCH_10`,
ordered by `rank`, returning per candidate: rank, probability/estimate
(with the correct §7 label), current move (`return_from_open_c`/
`return_from_prev_close_c`), remaining target distance, evidence
completeness (count of known vs. UNKNOWN fields used), state,
top positive/negative evidence (§9), feasibility, and the model/
checkpoint/version stamps. The other 17 (family, threshold)
combinations are exposed through the identical mechanism
(`top_candidates(family, threshold, session_date, checkpoint, n)`), as
secondary research output — never merged into one cross-family
meta-score, per the explicit "do not merge" instruction.

---

## 9. Evidence Explanation — "logit contribution," not "probability contribution"

Persists a pointer to the actual EM-2 evidence row used for inference
(not a re-derivation). "Strongest positive/negative evidence" is
computed honestly as **this candidate's own per-term logit
contribution** — `coefficient x this_observation's_own_transformed_value`
— ranked by absolute contribution, for the top-K contributions in each
direction. This is deliberately *not* a global ranking by raw
coefficient magnitude (which would misrepresent a candidate that
doesn't actually exhibit a large-coefficient feature) — it is the
real, per-candidate decomposition of that candidate's own **raw
logit**, before calibration.

**Naming precision (per Owner clarification)**: every term here is a
**logit contribution**, never called a "probability contribution" —
Platt calibration is a single 2-parameter transform applied to the
*summed* logit, not something that distributes linearly back across
individual terms. The explanation includes **every** transformed term
that actually contributes to the raw logit, not just the "interesting"
ones:
- each standardized continuous field's own `coefficient x standardized_value`
- each one-hot categorical term (`regime_trend__BULL_TREND`, etc.)
  that is actually `1` for this observation
- the checkpoint one-hot term that is `1` for this observation
- each missing-indicator term (`__missing`) that is actually `1`,
  labelled explicitly as "value was UNKNOWN, imputed" rather than
  presented as if it were a real signal
- the intercept, listed separately, not folded into any feature's
  contribution

**Auditability requirement**: `sum(all listed contributions) + intercept`
must equal the persisted raw logit *exactly* (a direct equality
check, not an approximation) — this is testable and will be a unit
test (`test_em5_scoring.py`), not just documentation. The calibrated
probability is then computed from that raw logit via the frozen Platt
transform (§7) as one separate step, never implied to be a linear sum
of per-term "probability contributions."

Checkpoint, current price/volume/VWAP state, gap/regime context, and
model/calibration version are included verbatim from the evidence row.

---

## 10. Bulk Data Requirement

No `MarketDataProvider` call anywhere in EM-5's live path (confirmed:
today's `scanner/` module doesn't touch it either, and EM-5 must not
be the first). All live reads go through a new **read-only** port,
`EmrMarketDataPort`, mirroring `DarvaxMarketDataPort` exactly
(`src/athena/darvax/ports.py`) — a `Protocol` over already-ingested
`SqliteRepository` data, exposing only the bulk methods EM-5 needs
(e.g. `candles_for_checkpoint(instrument_ids, session_date, checkpoint)`),
implemented following `SqliteRepository.candle_coverage`'s existing
grouped-`IN(...)`-query, chunked-at-~500 pattern — one query (or a
handful of chunked queries) per scan cycle across the whole eligible
universe, never one query per symbol. Live ingestion of the actual
candle data (getting bars from Kite into `db/athena.db` in the first
place) is unchanged, out of scope, and already exists.

---

## 11. Replay Determinism

Each scan cycle gets a deterministic `run_id`:
`em5-scan-{sha256 of the deterministic content}`, following the exact
fingerprinting convention already used throughout EM-1 through EM-4E
(sorted-key JSON, wall-clock fields like `elapsed_seconds` excluded
from the hash, included only in the persisted record afterward).
Given identical canonical market data, checkpoint, and the same
promoted frozen-model version (§1), re-running produces byte-identical
evidence values, logits, calibrated probabilities, states, and rank
ordering — this is mechanically guaranteed by construction (every
computation in the live path is a pure function of its inputs; no
`datetime.now()`/`random` anywhere in `explosive_move/`'s existing
modules, and EM-5 must preserve that).

---

## 12. No Model Learning in EM-5 — enforced, not just promised

`.fit(`, `LogisticRegression(`, `Newton`, any `sklearn`/`numpy` import,
and any online-update method are all absent from the new live module
by construction (score_logit/apply_platt_scaling are pure application,
not fitting) and this is **tested**, not just documented (§18's
architecture test). Live observations get persisted as evidence for a
later EM-7 shadow-validation analysis — never fed back into
coefficients, calibration, feature normalization, or state-transition
thresholds during EM-5 itself.

---

## 13. Scanner Performance

Every scan cycle persists (own run-ledger row, mirroring the existing
`runs` table / `save_run` convention, §15): eligible-symbol count,
evidence-generation duration, inference duration, total scan duration,
DB read latency, provider/network request count (must be `0` by
construction — asserted, not just measured), and, where cheaply
measurable, process CPU/memory deltas. No per-symbol network calls
(§10). The scan must not run inside, or block, ATHENA's own
`SchedulingFramework`/`CycleWorker` cycle — following DarvaX's own
precedent of an entirely separate trigger (§14), so host-resource
contention is measured honestly as "EMR's own process taking X
seconds/Y MB," not hidden inside ATHENA's cycle timing.

---

## 14. Fail-Fast Operational Gate — mature-history TRAIN completeness floor (Blocker 5, remeasured)

This directly reuses CLAUDE.md's own already-adopted "Expensive
external-data runs" canary rule (adopted 2026-08-24, after the EM-1r3
production incident) — not a new policy invented for EM-5.

**Correction (Blocker 5, second pass): the all-TRAIN 88.36% baseline
was rejected as the wrong reference** — it's depressed by early-history
warm-up sessions that a live 2026 universe, with years of accumulated
history, should not experience. Remeasured on a **mature-history**
subset, defined *deterministically from the frozen evidence contract
itself*, never from observed completeness: the maximum
`minimum_lookback_sessions` across all 22 `CANDIDATE_FEATURE` fields is
exactly **50** (`SMA50_REL`) — so an (instrument, session) pair is
"mature" iff that instrument already has `>= 50` admitted daily bars
strictly before that session (i.e., it is at least the instrument's
51st admitted session). This uses only `artifacts/research/em1r3/checkpoint.json`'s
real ADMITTED-session records (session order/count) plus the frozen
`evidence_contract.ALL_FIELDS` lookback declarations — no labels, no
outcomes, no observed-completeness curve-fitting.

182,326 real (instrument, TRAIN-session) pairs qualify as mature.

| Checkpoint | n (mature rows) | all-22-fields-known |
|---|---|---|
| 09:20 | 182,326 | **99.9929%** |
| 09:30 | 182,326 | 100.0000% |
| 09:45 | 182,326 | 100.0000% |
| 10:00 | 182,326 | 100.0000% |
| 10:30 | 182,326 | 100.0000% |
| 11:00 | 182,326 | 100.0000% |
| 12:00 | 182,326 | 100.0000% |
| 13:00 | 182,326 | 100.0000% |
| 14:00 | 182,326 | 100.0000% |

**Per-field known %**: every one of the 13 session-invariant fields
and 9 checkpoint-dynamic fields is **100.0000%** known on the mature
subset at every checkpoint, with exactly one exception: `VWAP_REL_C`
at `09:20` is 99.9929% known (13 of 182,326 rows UNKNOWN).

**UNKNOWN reason distribution** (the only non-empty one in the entire
mature-history measurement): all 13 UNKNOWN `VWAP_REL_C` rows at 09:20
carry the reason `"VWAP_THROUGH_C is UNKNOWN"` — a genuine edge case
(zero cumulative traded volume in the handful of M5 candles before
09:20 on that specific session for that specific instrument, making
VWAP undefined), not a systemic gap. No other field, at any checkpoint,
has a single UNKNOWN row in the mature-history subset.

**Proposed numeric canary floor: 99% all-required-fields-known**, per
checkpoint, on the canary's real symbol slice (restricted to
mature-history instruments, matching how the canary should be
constructed) — roughly 1 percentage point below the measured
99.9929%–100% mature-history baseline, giving real headroom for the
genuine, tiny, already-understood edge case above (zero-volume VWAP)
while still failing closed by nearly two orders of magnitude of margin
on anything resembling the EM-1r3 incident's ~0% usable admission.
This is derived from the actual measured distribution, not picked
first and justified after.

**Hard invariants, checked independently of the numeric floor** (any
one of these failing fails the canary regardless of the completeness
percentage):
- every promoted frozen artifact (§1) loads and its SHA256 matches
  `FROZEN_MODEL_MANIFEST.json` exactly;
- the checkpoint-boundary regression tests (§2) pass against the
  canary's own real candle data, not just synthetic fixtures;
- zero provider/network calls occurred during the canary (asserted,
  not just logged);
- no systemic stale-data condition (every canary symbol's freshness
  check, §4, passes);
- every hard eligibility input (§4) is structurally well-formed (no
  malformed/impossible values slipping through unchecked);
- running the canary twice against the identical input produces byte-
  identical evidence, logits, calibrated probabilities, and rank
  ordering (§11's replay determinism, exercised for real here, not
  just unit-tested);
- no checkpoint's real completeness for this canary run falls more
  than 2 percentage points below that checkpoint's mature-history
  baseline above (a *relative* systemic-UNKNOWN-spike check,
  independent of the absolute 99% floor — appropriately tight given
  the baseline itself is 99.99–100%, so even a small relative
  regression is meaningful and should not be masked by the absolute
  floor's own small margin).

A canary miss on either the numeric floor or any hard invariant **fails
closed automatically** — refuses to proceed to full-universe scanning,
naming exactly which check failed — distinguishing a systemic defect
from an already-understood, bounded limitation, exactly as CLAUDE.md's
existing rule requires.

---

## 15. Persistence

New, EMR-owned SQLite database (`db/emr.db`), own independently
versioned schema (`EMR_SCHEMA_VERSION`, an `emr_schema_version` table
— mirroring `darvax/store/schema.py`'s exact precedent), living under
`src/athena/explosive_move/store/{schema.py, repository.py}`. Two core
tables:

- `emr_scan_runs` — one row per scan cycle: `run_id`, `session_date`,
  `checkpoint`, `frozen_model_version` (the `config/emr/frozen_models/`
  directory version from §1), started/finished timestamps, the
  performance fields from §13, status (RUNNING → terminal).
- `emr_candidates` — one row per (symbol, family, threshold,
  checkpoint) scored observation: FK to `run_id`, all the ranked
  fields from §6, the state-transition fields from §3, evidence
  completeness, and a pointer/reference to the underlying evidence
  values (not a duplicate copy of raw OHLC candles, which ATHENA
  already persists canonically — only the *derived* EM-2 feature
  values this observation actually used, so it stays explainable
  without re-deriving evidence at read time).

No canonical ATHENA table (`decisions`, `portfolio`, `runs`, etc.) is
touched, ever.

---

## 16. Experimental Isolation — DarvaX's exact pattern, reused

- **Own DB, own schema** (§15).
- **Read-only port, not a service call** — `EmrMarketDataPort` (§10),
  a `Protocol` with an explicit `EMR_MARKET_DATA_READ_METHODS`
  frozenset, asserted equal to the Protocol's actual members by a
  test (mirroring `DARVAX_MARKET_DATA_READ_METHODS`'s exact
  precedent) — so a write-shaped method added later fails a test
  rather than silently passing.
- **One-way import direction, enforced by test** — a new architecture
  test (mirroring `tests/darvax/test_dx1_isolation.py`'s `ast`-based
  import scan) asserting nothing outside `explosive_move/` imports
  `athena.explosive_move.{store,scanner}` except one guarded seam
  module, and that `athena.explosive_move` never imports
  `athena.decision`, `athena.risk`, `athena.portfolio`, `athena.orders`,
  `athena.execution`, or `athena.orchestration`. **This closes a real
  gap**: ADR-012's own "Required Controls" section already claims this
  test exists ("Architecture tests prevent EMR imports into canonical
  scoring, risk, decision, and TradePlan modules") — it does not yet;
  EM-5 will add it, matching what the ADR already committed to.
- **Single guarded mount seam** (only needed if/when EM-5 exposes any
  API surface at all — see §17: it should not need one yet, since
  there's no UI and no canonical-facing route in this milestone; if a
  minimal internal query function is exposed for EM-6 to later import,
  it stays a plain Python function call, not a mounted route, so no
  `emr_mount.py` seam is required until EM-6).
- **Its own trigger, never ATHENA's cycle** — confirmed via research
  that DarvaX never hooks into `due_triggers`/`CycleWorker`; EM-5
  follows the same precedent (§14/§13).

---

## 17. No UI

EM-5 stops at a clean, plain-Python service/domain output —
`top_candidates(...)`/`top_touch_10_candidates(...)` query functions
over `emr_candidates`, callable by a future EM-6 without any HTTP
route, dashboard change, or `index.html`/`DASHBOARD_JS_PARTS` touch in
this milestone.

---

## 18. Testing

Mapped to the Owner's 16 required categories, as new files under
`tests/explosive_move/`:

| Category | Test file (proposed) |
|---|---|
| Checkpoint cutoff/leakage | `test_em5_checkpoint_boundary.py` |
| Frozen-artifact inference | `test_em5_scoring.py` |
| Calibration application | `test_em5_scoring.py` (shared) |
| ALREADY_OCCURRED | `test_em5_already_occurred.py` |
| Eligibility/feasibility | `test_em5_eligibility.py` |
| Deterministic ranking + tie-break | `test_em5_ranking.py` |
| State transitions | `test_em5_state_machine.py` |
| UNKNOWN handling | `test_em5_eligibility.py` (shared) |
| Stale data | `test_em5_eligibility.py` (shared) |
| Replay determinism | `test_em5_replay.py` |
| Bulk/no-per-symbol-call enforcement | `test_em5_isolation.py` |
| Persistence/reload | `test_em5_repository.py` |
| Scanner performance instrumentation | `test_em5_performance.py` |
| Model-version mismatch | `test_em5_artifact_loading.py` |
| Malformed/missing artifact fail-closed | `test_em5_artifact_loading.py` (shared) |
| Import-graph isolation (§16) | `test_em5_isolation.py` (shared) |

Full ATHENA suite run + Ruff (pinned to the accepted 0.15.22) zero
net-new findings, exactly as every prior EM milestone in this
workstream has required.

---

## Revision history

**2026-08-28, revision 1** — five blocking corrections incorporated
(state thresholds, checkpoint-price direction, artifact immutability,
hard-vs-contextual eligibility, canary floor grounding). See git
history of this file for the original five-item list; superseded in
places by revision 2 below.

**2026-08-28, revision 2** — Owner decision: "four of the five
original blockers are resolved... two final corrections required":

- **Final Blocker A (§2) — NOT resolved, returned to Owner.** Revision
  1's `live_price_at_checkpoint` "fix" was itself audited and found
  wrong: it silently changes the feature the frozen model was trained
  and FINAL_TEST-validated on. Real EM-1r3 candle data shows
  `prev_candle.close != this_candle.open` in 29.6–35.2% of consecutive
  pairs (two independent samples: 20 instruments/758,722 pairs and 60
  instruments/3,142,558 pairs), with mismatches up to 3.92% — large
  enough to flip threshold decisions. This is Outcome C exactly as the
  Owner defined it: STOP, do not substitute, return for decision. The 7
  price-dependent `CANDIDATE_FEATURE` fields are listed in §2 with
  their exact formulas. Two real paths forward are described (a live
  LTP/quote snapshot via the already-existing batched `quotes()`
  provider method and canonical `quotes` table; or knowingly accepting
  the measured close-of-prior-candle discrepancy) — neither chosen; no
  scanner code for these 7 features until this is decided.
- **Final Blocker B (§14) — resolved.** Remeasured completeness on a
  *mature-history* TRAIN subset (>=50 prior admitted daily bars per
  instrument, derived from the frozen contract's own maximum
  lookback requirement — `SMA50_REL`'s 50 — never from observed
  completeness): 182,326 real mature (instrument, session) pairs,
  99.9929–100.0000% all-22-fields-known across all 9 checkpoints, one
  understood edge case (`VWAP_REL_C` zero-volume UNKNOWN, 13 rows at
  09:20 only). Canary floor revised from 80% to **99%**.
- **FADING recovery — completed (§3).** No special recovery rule
  needed: the same rank-tier evaluation applies every checkpoint
  regardless of current state, so `FADING` naturally re-enters
  `WATCH`/`DEVELOPING`/`CONFIRMED`/`HIGH_CONVICTION` whenever rank
  recovers, gated only by whether that tier was ever reached earlier
  this session (a plain fact from the persisted transition log) — no
  probability threshold anywhere in recovery.

## Open questions for Owner sign-off

1. **Final Blocker A (§2): live parity diagnostic complete, PARITY
   ACCEPTABLE recommended** (18/18 real observations, max 0.0685%
   price difference, negligible logit/probability impact on the frozen
   `TOUCH_10` model — full evidence in §2's RESOLVED subsection and
   `artifacts/research/em5_diagnostic/`). **This is a recommendation,
   not a decision** — the Owner's explicit PARITY ACCEPTABLE /
   PARITY NOT ACCEPTABLE call, and EM-5 contract `ACCEPTED` status,
   remain outstanding.
2. If PARITY ACCEPTABLE is confirmed: the production
   `allowed_observation_delay` for `checkpoint_reference_price(C)`
   still needs a number — this diagnostic's real 0-188s latency
   distribution (18 observations, today's session) is the evidence to
   set it from; the diagnostic's own 300s collection window was itself
   diagnostic-only, not a proposal.
3. The rank cutoffs (20/10/5) and the 99% canary floor are both now
   either Owner-approved or evidence-derived — flag only if you want
   either adjusted; otherwise treat as settled.
