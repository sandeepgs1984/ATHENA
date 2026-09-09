# EM-7D — Evidence Readiness, Settled-M5 Repair, and Statistical Readiness

**Status (2026-09-09): READ-ONLY EVIDENCE-READINESS WORK COMPLETE. EM-7D
STATISTICAL VALIDATION NOT AUTHORIZED. NO CODE/METHODOLOGY/STATE-MACHINE
CHANGE. NATURAL EMR ACCUMULATION UNCHANGED AND ACTIVE.**

This document consolidates a continuous sequence of Owner-authorized,
read-first (one exception: an explicitly authorized, backed-up settled-
history repair) EM-7D readiness investigations conducted 2026-09-08/09,
following on from EM-7D0's own accepted classification
(`OPERATIONALLY_SOUND_BUT_NOT_YET_STATISTICALLY_READY`,
`docs/research/EM-7D0-EVIDENCE-READINESS-FIRST-PRODUCTION-SHADOW-AUDIT.md`).
No new EM-7D.x milestone was created at any point — this is the same
EM-7D evidence-readiness question, revisited as natural evidence and
repair evidence accumulated.

---

## 1. Evidence-readiness re-audit (natural accumulation since EM-7D0)

By 2026-09-08, natural EMR production accumulation had grown from
EM-7D0's single session (`2026-09-04`) to three sessions: `2026-09-04`,
`2026-09-07`, `2026-09-08` (`2026-09-05`/`06` are the weekend — no gap).
A fresh read-only audit against `db/emr.db` found:

- 27 scan-run attempts (9 checkpoints × 3 sessions): 22 `COMPLETE`, 5
  orphaned `RUNNING` (never terminated — atomicity held, zero partial
  candidate/transition rows for any of them; root cause not provable
  from retained evidence, compounded by a genuine, separate, whole-
  application logging-configuration gap — `athena.*` loggers have no
  configured handler, so `logging.lastResort`'s `WARNING`+ threshold
  silently drops INFO-level lifecycle logs application-wide, not EMR-
  specific; recorded as `APPLICATION_INFO_LOGGING_NOT_CONFIGURED`
  operational debt, deliberately not fixed here).
- **`INVALIDATED`/`STALE_DATA` dominance root-caused**: the frozen EM-5
  state machine's `TERMINAL_STATES = {INVALIDATED, TARGET_REACHED}`
  makes a single transient `STALE_DATA` blip *permanent* for the rest of
  a session even after the underlying M5 data genuinely recovers (proven
  directly: `NSE:360ONE`/`TOUCH`/`5%`/`09-04` triggered `STALE_DATA` at
  12:00, then showed `freshness=FRESH` with live-updating real quotes at
  13:00/14:00, yet stayed `INVALIDATED`). This is a frozen
  methodology/data-contract limitation, not an implementation defect —
  the code correctly implements EM-5's own frozen contract, which does
  not distinguish "temporarily unavailable evidence" from "genuinely
  invalidated." **Live `INVALIDATED` must never be used as a statistical
  negative label.**
- A partial-universe anomaly on `2026-09-08` (only 37/517 instruments
  scored at several mid-morning checkpoints) was traced to a real,
  independently-confirmed canonical-ATHENA ingestion outage that
  morning (a stuck/failed REFRESH cycle), not an EMR-specific defect.

## 2. Retrospective-label reconstruction feasibility

Confirmed the frozen EM-1b forward-label functions
(`athena.explosive_move.event_labels.evaluate_touch_label` /
`evaluate_close_label`) can retrospectively reconstruct genuine
`POSITIVE`/`NEGATIVE`/`ALREADY_OCCURRED` outcomes from already-persisted
checkpoint evidence and canonical candle history, entirely independent
of the live EM-5 state machine's own `INVALIDATED` label — this is the
correct way to obtain a genuine negative class, not a live-state
substitute.

**Exact frozen reference-price semantics** (`em1b_label_dataset_generation.py`,
never changed):

| Family | Reference price |
|---|---|
| `TOUCH` | prior trading session's own close (`prev_close`) |
| `OPEN_TO_HIGH` | current session's own open |
| `CLOSE` | prior session's own close (`prev_close`); `session_close = session_candles[-1].close`, unchanged, never switched to D1 |

A forward-path completeness audit found the canonical M5 series for all
three sessions was 95–99.7% **off-grid** (drifted timestamps from
`LiveIngestionEngine`'s known, already-authorized-and-once-repaired
settlement-drift defect, `src/athena/data/live_m5_settlement_repair.py`,
2026-08-28 authorization) — meaning a naive completeness check on the
*raw* data would have wrongly rejected almost everything. `run_settlement_repair()`
had never been re-run for these three (more recent) dates.

## 3. Settled-M5 repair — executed for all three sessions

Owner-authorized, backed-up (`db/backups/athena-pre-em7d-m5-repair-*.db`,
each independently integrity-verified), using the existing, unmodified
`run_settlement_repair()` path (real Kite historical fetch,
`SqliteRepository.replace_candles` atomic per-session-date replace) —
no interpolation, no synthetic candles, no quote substitution, no code
change.

| Session | Requests | Failures | Off-grid before → after |
|---|---|---|---|
| 2026-09-04 | 517 | 1 (`NSE:HEG`) | ~majority of 62,629 rows → 113 (all `NSE:HEG`) |
| 2026-09-07 | 517 | 1 (`NSE:HEG`) | ~majority of 46,741 rows → 0 |
| 2026-09-08 | 517 | 1 (`NSE:HEG`) | 21,672 → 0 |

**Canonical 75-slot completeness** (exact `expected_intraday_opens`
grid, `09:15→15:25`, no tolerance): identical on all three sessions —
**306/517 (59.19%) instruments fully complete, 211/517 incomplete**
(210 + `NSE:HEG`). The exact same 211-instrument set is missing the
exact same 3 slots — `15:15`/`15:20`/`15:25`, the session's own final 15
minutes — on all three independently repaired sessions.

## 4. Systematic final-3-slot investigation

Exhaustive comparison of the 306-complete vs. 211-incomplete cohorts
across every classification available to ATHENA (own `instruments`/
`symbol_master` tables, Kite's own raw `/instruments/NSE` CSV fields,
D1/M5 volume) found **no distinguishing property** — both cohorts are
100% `NSE`/`EQ`/`MAINBOARD`/`ACTIVE`; volume is actually *higher* in the
incomplete cohort (ruling out an illiquidity explanation).

Direct, repeated, live queries against the real Kite historical
endpoint (the same call `run_settlement_repair` itself makes) proved:

- The raw Kite JSON response itself never contains the final 3 candles
  for the 211-cohort tokens, on any of the three dates — confirmed via
  an exact row-count match between the raw provider response and the
  persisted result (nothing is dropped by ATHENA's own provider
  normalization, repair logic, or repository write path).
- Re-querying `2026-09-04` **five calendar days later** returns the
  identical 72-candle result, providing strong evidence against
  ordinary short settlement lag; the gap is persistent across the
  observed re-query window and originates in the Kite historical
  response itself.
- NSE's regular `09:15–15:30` session (uniform across all mainboard
  equities, `config/market.nse.json`) confirms the canonical 75-slot
  expectation is correct — not an ATHENA session/calendar error.

**Frozen finding (Owner-corrected wording, 2026-09-09):**

    FINAL3_GAP_PRESENT_IN_KITE_HISTORICAL_PROVIDER_RESPONSE

No observable instrument classification explains which 211 instruments
are affected — the gap is proven provider-side and proven stable, but
its underlying mechanism inside Kite's own data-serving infrastructure
is outside what ATHENA can directly observe or diagnose further.

**`NSE:HEG`** (separate, unrelated instrument-master operational debt,
not fixed here): Kite's own current tradingsymbol for this security is
`HEG-BE` (NSE's real Book-Entry/trade-to-trade series designation);
ATHENA's instrument master still registers it under the stale plain
`NSE:HEG` identity, so `KiteProvider`'s strict symbol-filter lookup
fails with `"unknown instrument id"`. A real, narrow, single-row
instrument-master staleness — flagged for a future Owner-authorized
correction, not addressed in this investigation.

## 5. Retrospective-label reconstruction cohort (frozen)

**`RETROSPECTIVE_LABEL_RECONSTRUCTION_READY_WITH_EXPLICIT_INCOMPLETE_COHORT`**
— unchanged, now more precisely grounded: the 306-instrument cohort is
the correct, currently trustworthy `COMPLETE_FORWARD_PATH` population
for `TOUCH`/`OPEN_TO_HIGH` `NEGATIVE`/`POSITIVE`/`ALREADY_OCCURRED`
labels and for fully-reliable `CLOSE` labels; the 211-instrument cohort
(plus `NSE:HEG`) is treated as **explicitly incomplete under currently
observed provider behavior**, excluded unless/until future provider
evidence demonstrates otherwise — it must not be converted to
`NEGATIVE`, interpolated, or worked around.

## 6. Episode-level statistical-readiness assessment

Critical correctness step: the 9 frozen checkpoints per session are
**not independent observations** of a `TOUCH`/`OPEN_TO_HIGH` outcome —
they are repeated views of one underlying session-level fact (did price
cross the threshold at all, and when). Collapsing to one row per
(instrument, session, family, threshold) using the full session's
candles gives the correct, non-inflated unit: **918 independent
instrument-session episodes** (306 instruments × 3 sessions) per
family/threshold — not 918×9 checkpoint-rows, and not the much larger
raw per-checkpoint counts cited in earlier drafts of this work.

At the 918-episode level:

- **5% threshold**: the only tier with meaningful two-class support —
  `TOUCH` 47 positive/871 negative, `OPEN_TO_HIGH` 44/874, `CLOSE`
  25/893 — spread across 23–41 distinct instruments, low single-
  instrument concentration (≤4.5% share).
- **8% threshold**: sparse (3–12 positives) — borderline.
- **10–15% thresholds**: near-zero support (2–4 positives total), high
  single-instrument concentration risk (up to 50% from one instrument).
- **20% threshold**: **zero positive support**, all three families, all
  three sessions.
- Session concentration: `2026-09-04` alone contributes ~49% of the 5%-
  tier `TOUCH` positives — a real, moderate concentration.
- Regime representativeness (from ATHENA's own already-persisted
  `regime_assessment`/`market_health_score`, no new classifier
  invented): `09-04` = `SIDEWAYS`/`STRONG_BREADTH`; `09-07`/`09-08` both
  = `BEAR_TREND`/`WEAK_BREADTH`. **All three sessions share
  `VOLATILITY_CALM`** — zero elevated-volatility evidence exists yet,
  plausibly explaining the near-total absence of positive support above
  5–8%.

With only 3 independent sessions, the frozen chronological/session-
grouped methodology cannot yet form a credible discovery/validation
structure. ID-7B.2's own materially deeper 14-discovery/6-validation,
20-session split is cited only as historical context showing that
prior ATHENA validation used materially deeper session separation — it
is not an EM-7D minimum-session rule.

## 7. Frozen classifications (Owner decision, 2026-09-09)

    FINAL3_GAP_PRESENT_IN_KITE_HISTORICAL_PROVIDER_RESPONSE
    RETROSPECTIVE_LABEL_RECONSTRUCTION_READY_WITH_EXPLICIT_INCOMPLETE_COHORT
    OPERATIONALLY_SOUND_BUT_NOT_YET_STATISTICALLY_READY
    AUTHORIZE_EM7D_STATISTICAL_VALIDATION = NO

**Decisive reason:** label reconstruction is now proven methodologically
trustworthy, but evidence depth has not changed in kind — only 3
independent sessions exist, the frozen chronological/session-grouped
validation shape cannot be formed at this scale, 8%+ thresholds have
extremely sparse-to-zero positive support, `CLOSE` is sparser still, and
all observed sessions share one (calm) volatility regime. Repeated
checkpoint rows were correctly collapsed to instrument-session episodes
throughout and must never be treated as independent samples in any
future EM-7D work.

**No new minimum-session-count rule was introduced** — the historical
14/6-session precedent is cited only as an existing shape comparison,
not converted into a new frozen threshold for EM-7D.

## 8. What would change this

Continued **natural** EMR accumulation only (no forced scans, no
backfill, no synthetic evidence) — specifically more independent
sessions, and/or a session under different (elevated) volatility
conditions. When materially new natural evidence has accumulated, the
identical sequence — settled-M5 repair (§3) → episode-level
reconstruction (§6) → readiness reassessment — should be repeated
against the enlarged evidence base, still without starting statistical
validation until this same readiness question is asked and answered
again.

---

**EM-7D STATISTICAL VALIDATION REMAINS NOT AUTHORIZED — CLASSIFICATIONS ABOVE FROZEN BY OWNER / CHIEF ARCHITECT DECISION, 2026-09-09**
