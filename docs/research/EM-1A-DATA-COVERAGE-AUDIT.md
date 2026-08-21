# EM-1a Data Coverage Audit and Frozen Research Contract

**Status:** Approved 2026-08-21
**Observed:** 21 Aug 2026 IST  
**Ledger:** `db/athena.db`, schema version 15  
**Governing boundary:** ADR-012  

## Milestone conclusion

ATHENA has enough raw daily history to describe a present-day survivor cohort, but it does not yet have the evidence required to create trustworthy Explosive Move Radar labels. EM research therefore remains **blocked**. No event labels, checkpoint labels, model inputs, rankings, or production claims are authorized by EM-1a.

The block is deliberate. A missing corporate-action row cannot be interpreted as proof that no corporate action occurred, current membership cannot be projected backward, and duplicated intraday slots cannot be treated as separate observations.

## Measured source inventory

| Source | Measured production coverage | Research decision |
|---|---:|---|
| Instrument registry | 2,204 instruments; no populated listing or delisting dates | Current identity only; not point-in-time eligible |
| Symbol master | 10,197 rows; `first_seen_at = last_seen_at = 16 Aug 2026`; no official series rows | Current snapshot only |
| Universe membership | 4,574 memberships; official index snapshots exist only for 31 Jul 2026; board snapshots only for 16 Aug 2026 | Historical membership unavailable |
| Daily candles | 1,395,749 raw Kite bars across 2,204 instruments, 11 Aug 2023 to 21 Aug 2026 | Descriptive coverage only until corporate actions are authoritative |
| Daily depth | 1,915 instruments have at least 252 bars; 1,844 have at least 400; maximum 751 | Coverage is uneven and survivor-biased |
| 5-minute candles | 844,914 rows across 533 instruments, 23 Jul to 21 Aug 2026 | Blocked: non-canonical timestamp grid |
| 15-minute candles | 124,085 rows across 533 instruments, 29 Jul to 21 Aug 2026 | Blocked: partial sessions and insufficient span |
| Quotes | 194,441 rows; 512 instruments contain a 1 Jan 1970 default timestamp | Invalid epoch rows must be excluded |
| Corporate actions | 0 rows; 0 adjusted candles | Coverage unavailable, not "no actions" |
| Sectors | 500 instruments across 20 sectors | Current narrow mapping; historical mapping unavailable |
| Price bands | No authoritative source persisted | Preserve as `UNKNOWN` |
| Trading halts | No authoritative source persisted | Preserve as `UNKNOWN` |
| Catalysts/news | No authoritative source persisted | Preserve as `UNKNOWN` |

## Intraday integrity finding

The 5-minute store has 844,914 rows but only 671,851 canonical instrument/session/minute slots. That is 173,063 surplus rows across 150,740 duplicated slots, with as many as four records in one logical slot. Per-session counts reach 251 rows where a regular NSE session has 75 five-minute intervals. Timestamp-second drift creates overlapping candle sequences.

The 15-minute store has 16 duplicate rows and commonly covers only 10 to 23 of the expected 25 regular-session intervals. It is also only about 18 sessions deep.

Consequently, all nine proposed checkpoints remain candidates and **zero checkpoints are accepted**. EM-1b must not create checkpoint records until timestamp normalization/re-ingestion and complete-session checks pass.

## Survivorship and point-in-time limits

- Listing and delisting dates are absent, so the ledger cannot prove that an instrument was tradable on an older study date.
- Index membership is a single recent snapshot, not a dated membership history.
- The board universe is a current snapshot. Using it for older dates would exclude delisted names and include later entrants.
- Sector mappings are current and incomplete. Historical sector attribution is unavailable.
- The current data can describe today's surviving cohort only. It cannot support an "all NSE stocks at that time" claim.

Every future manifest must identify the universe and membership snapshot used. A symbol-day without point-in-time membership evidence is excluded, not silently assigned current membership.

## False corporate-action prevention

The codebase already has typed corporate-action models and adjustment strategies, but production coverage is zero and all candles are raw. Engine capability is not data coverage.

EM applies these fail-closed rules:

1. Corporate-action coverage requires an explicit authoritative start and end date. A row count of zero alone is never authoritative.
2. If the authority does not cover the full study interval, the symbol-day is excluded.
3. A raw reference window containing a known split, bonus, dividend, or rename is excluded.
4. Fully adjusted candles are preferred. Authoritatively action-free raw windows may be admitted later, with provenance recorded.
5. Missing price-band, halt, and catalyst evidence remains `UNKNOWN`; it is never converted to `false`.

These rules are implemented as immutable pure contracts in `src/athena/explosive_move/contracts.py` and regression-tested without generating labels.

## Frozen event contract

- Families: `TOUCH`, `CLOSE`, `OPEN_TO_HIGH`.
- Thresholds: 5%, 8%, 10%, 12%, 15%, 20%.
- Regular session: 09:15 to 15:30 IST; pre-open excluded.
- References: previous-session adjusted close for `TOUCH` and `CLOSE`; regular-session open for `OPEN_TO_HIGH`.
- Horizon: the same regular trading session.
- Special sessions: included only when an authoritative calendar identifies their bounds.
- Candidate checkpoints: 09:20, 09:30, 09:45, 10:00, 10:30, 11:00, 12:00, 13:00, 14:00 IST.
- Accepted checkpoints: none in EM-1a.
- Dataset partitions: `TRAIN`, `VALIDATION`, `CALIBRATION`, `FINAL_TEST`. Final-test data remains untouched until the final locked evaluation.
- Every checkpoint record must include `remaining_session_minutes` so unequal time-to-close is explicit.

The machine-readable contract is `config/explosive_move.json`. Later milestones may version it through review; they must not reinterpret it in place.

## Dataset manifest contract

Every generated dataset must persist:

- immutable manifest ID and contract version;
- creation time, study bounds, universe name, and membership snapshot IDs;
- source provenance and corporate-action coverage bounds;
- accepted checkpoint set and partition role;
- included and excluded row counts;
- exclusion counts by explicit reason.

The symbol-day and checkpoint field lists are frozen in the machine-readable contract. No downstream model may infer omitted evidence.

## Required remediation before EM-1b

1. Acquire and persist authoritative corporate-action coverage with bounded provenance.
2. Normalize or re-ingest intraday candles onto canonical exchange-session slots, then prove duplicate-free complete sessions.
3. Acquire dated index/board membership and listing lifecycle evidence, or formally narrow the research claim to a named survivor cohort.
4. Exclude the 512 epoch-default quote rows from any derived dataset.
5. Re-run this audit and obtain owner approval for a non-empty accepted checkpoint set before label generation.

## Owner review outcome

The owner approved EM-1a on 21 Aug 2026 as a coverage audit and frozen
contract. The approval accepts the fail-closed conclusion; it does not waive
the remediation gate or authorize labels. EM-1b remains blocked until the
EM-1r remediation sequence admits a non-empty checkpoint set.
