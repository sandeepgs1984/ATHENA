# ATHENA — SI-P2D deterministic written research summary discovery

Date: 2026-09-14
Status: **DISCOVERY COMPLETE — IMPLEMENTATION AUTHORIZED**
Frozen baseline: SI-P1/P2A/P2B/P2C complete and frozen; SI-P2C asset `9.250.0`

## 1. Discovery verdict

The existing Written summary is a frontend-only, deterministic renderer in
`08c-symbol-intelligence.js`. It is currently a verbose card-by-card restatement
with eleven headings, explicit one-line absence notices, DarvaX navigation copy,
and methodology-placeholder prose. It adds little synthesis and is the exact
surface deferred by SI-P2B to SI-P2D.

The frozen `SymbolIntelligenceBundleDTO` already contains sufficient approved
evidence for a concise research narrative. No API, DTO, persistence, provider,
DecisionEngine, Portfolio, DarvaX, chart, or methodology change is required.
All requested sentence families can be supported by owned fields or the already
approved arithmetic relationships used by the Price Map.

No stop condition is met: provenance is explicit, D1 coherence flags exist,
session boundaries are carried by `latest_session` and source freshness, and the
summary can omit unsupported statements instead of inventing content.

## 2. Current implementation trace

- Builder/rendering: `siCompleteReview(bundle)` in
  `src/athena/api/static/js/08c-symbol-intelligence.js`.
- Host: collapsed `<details class="si-written-summary">` on Stock 360, rendered
  only when `identity.resolved` is true.
- Current output: Market Snapshot, Trend, Momentum Evidence, Structure, Key
  Levels, Entry Evidence, ATHENA Decision, DarvaX, Portfolio Context, and Data
  Availability headings.
- Existing formatters: `siMoney`, `siInteger`, `siRsi`, `siScore`, `siPct`,
  `siEnumLabel`, `siZoneShort`, `siChartLongDate`.
- Existing presentation arithmetic: `siCloseVsBoundary`, `siLevelVsClose`, and
  their sentence helpers. These use completed-D1 close only; live quote is never
  mixed with D1 structural levels.
- Existing tests: SI-P2A/P2B presentation contracts and real JavaScript helper
  execution in `tests/symbol_intelligence/`; no exact summary-composer test yet.

## 3. Available evidence and boundaries

| Concern | Frozen bundle fields | Admission rule | Source |
|---|---|---|---|
| Identity | `identity.resolved`, `symbol`, `instrument_id` | summary only for resolved identity | Symbol master |
| D1 boundary | `d1.present`, `latest_session`, `expected_session` | completed D1 only | D1 candles |
| SMA structure | `symbol_trend`, `symbol_trend_is_coherent`, `fast_sma`, `slow_sma` | coherent flag true; approved enum only | Portfolio trend adapter |
| SuperTrend | `supertrend_direction`, `supertrend_is_coherent`, `supertrend_value` | coherent flag true; BULLISH/BEARISH only | Portfolio D1 evidence |
| RSI | `rsi14`, `rsi_is_coherent` | coherent and finite | Portfolio D1 evidence |
| Participation | `volume`, `volume_ma20`, `volume_is_coherent` | coherent and both finite | Portfolio D1 evidence |
| Structure | S1/MS/RT/T1/T2/T3, `structural_is_coherent` | coherent, finite exact zone | Portfolio structural review |
| Prior high | `available_history_high`, `ath_is_coherent` | coherent and finite; never call 52-week/ATH | Portfolio D1 evidence |
| Decision | `present`, type, `ts`, confidence, depth score, gates, plan | persisted only; never rerun or reinterpret | ATHENA Decision |
| Portfolio | status, quantity, average, P&L and snapshot fields | Portfolio-owned facts only | Portfolio |
| Freshness | `sources`, `overall_freshness` | report stale D1 materially; no new status | SI composer |
| Capabilities | fundamentals/news status | combine two NOT_INGESTED facts | Frozen placeholders |
| Chart/session | chart uses same `d1.latest_session` cutoff | no chart data enters summary | SI-P2C presentation |

DarvaX is deliberately excluded from the narrative. Live quote is excluded from
all level arithmetic. Available-history high and T2/T3 remain on their existing
surfaces and are not needed for the concise summary.

## 4. Composer ownership decision

Keep ownership in the frontend, but replace ad-hoc HTML prose with a named pure
composer: `siComposeResearchSummary(bundle)`. Reasons:

1. the current summary is already dashboard presentation;
2. all inputs are present in the frozen coherent bundle;
3. the permitted relationships are existing P2B presentation arithmetic;
4. no other consumer currently needs summary text; and
5. backend ownership would require a new frozen DTO field and unnecessary SI-P1
   contract reopening.

The composer returns traceable statement objects rather than opaque HTML:
`{kind, text, source_refs, as_of}`. Rendering escapes their text. Tests execute
the actual JavaScript composer with deterministic real-shaped fixtures.

## 5. Deterministic sentence taxonomy

### STRUCTURE

- Required: `d1.present`; admit SMA only when `symbol_trend_is_coherent === true`
  and enum is UPTREND/DOWNTREND/SIDEWAYS/MIXED; admit SuperTrend only when
  `supertrend_is_coherent === true` and enum is BULLISH/BEARISH.
- Both same mapped direction: “Daily SMA structure and SuperTrend both indicate
  Up/Down.”
- Both different: “Daily SMA structure is Up, while SuperTrend is Down; the two
  measurements disagree.”
- One present: state that measurement and say the other is unavailable.
- Neither: omit.
- Prohibited: blended trend, winner, strength, probability, confirmation, bias.

### MOMENTUM

- RSI admitted only when coherent and finite; format one decimal.
- Volume relationship admitted only when coherent and both volume values are
  finite; `volume >= volume_ma20` is “above”, otherwise “below”.
- Both: one combined sentence. One: one factual sentence. Neither: omit.
- Prohibited: overbought/oversold, weak/strong, Momentum Quality, causality.

### LEVEL_POSITION

- Requires coherent structural evidence, finite non-zero D1 close, and valid
  finite zone boundary.
- First observation: Support 1 upper boundary; if absent, Major Support upper
  boundary.
- Second observation: Review Trigger lower boundary; if absent, Target 1 lower
  boundary.
- Maximum two observations in one sentence. Existing P2B arithmetic and one
  decimal formatting are reused. T2/T3 and prior-history high stay in Price Map.
- Prohibited: importance ranking, good/bad buffer, entry/exit/action semantics.

### ATHENA_DECISION

- Present: persisted human-readable decision type, owner-formatted date when
  available, and confidence when available.
- Optional second clause: persisted score and/or gate pass count, stated only as
  facts. Absence of a Trade Plan is not interpreted.
- Missing: “ATHENA has no persisted Decision for this symbol; Stock 360
  technical research remains available.”
- Prohibited: new Decision, advice, bearish/bullish translation, wait/avoid/safe.

### PORTFOLIO

- HELD: state held status; include quantity and average price when both exist;
  include current Portfolio P&L percentage when finite.
- NOT_HELD: “This symbol is not held in My Portfolio.”
- No context: omit.
- Prohibited: SI-owned HOLD/SELL/REDUCE or interpretation of Portfolio status.

### DATA_AVAILABILITY

- D1 source STALE: explicitly say completed-D1 evidence is stale through its
  date. Otherwise provide a compact “Data through …” footer when date exists.
- Combine fundamentals and news when both are NOT_INGESTED: “Fundamentals and
  news/catalysts are not yet ingested.”
- Missing optional D1 measurements are combined into at most one note. If up to
  three of SMA structure, SuperTrend, RSI, or volume are missing, name them; if
  more are missing, use “Some optional D1 measurements are unavailable.”
- Coverage PARTIAL is not repeated when the no-Decision sentence already proves
  its relevant cause.
- Prohibited: raw NOT_INGESTED codes, one absence sentence per field, causal or
  quality inference.

## 6. Inclusion, ordering, and length guard

Fixed order: STRUCTURE → MOMENTUM → LEVEL_POSITION → ATHENA_DECISION →
PORTFOLIO → DATA_AVAILABILITY.

Presentation model:

- one primary paragraph containing at most four statement families: structure,
  momentum, levels, Decision;
- at most one Portfolio supporting row; and
- at most one compact availability/footer row.

No arbitrary text truncation occurs. Length is controlled solely through fixed
family count and deterministic level/availability inclusion rules.

## 7. Responsive and accessibility decision

Retain the secondary collapsed disclosure. Inside it, use one semantic heading,
one readable primary paragraph, and compact supporting/footer rows. At 390px the
content remains in normal flow, wraps at local card width, uses existing body
type sizing, and has no horizontal scrolling. Meaning is entirely textual and
does not depend on color.

## 8. Planned deterministic validation

Create `tests/symbol_intelligence/test_si_p2d_written_summary.py` that executes
the actual JavaScript composer for WIPRO-like, TI-like, ACMESOLAR-like,
minimal-data, stale, and invalid cases. Cover agreement Up/Down, disagreement,
unavailable SuperTrend/RSI, volume, support/MS, RT/T1, Decision/no Decision,
held/not-held, READY/PARTIAL/stale, capability absence, optional evidence,
human enum formatting, provenance, sentence/order/length limits, and forbidden
prediction/recommendation/MQ/EQ language.

Live validation will use real persisted data without mutation: WIPRO, TI,
ACMESOLAR, one naturally sparse symbol if available, a 390px case, and invalid
symbol. Evidence capture is planned only after implementation tests pass.

## 9. Architecture and scope conclusion

This is a bounded report/presentation change aligned with ATHENA-002's rule that
the report layer renders stored objects and does not compute business decisions.
The only calculations are already-approved display relationships. No ADR is
required. SI-P1/P2A/P2B/P2C remain frozen; SI-P2E and all later work remain
deferred.

## 10. Presentation refinement note

Owner / Chief Architect review of the initial `9.251.0` implementation accepted
this discovery's deterministic composer, evidence taxonomy, provenance, and
sentence rules, but rejected the one-primary-paragraph presentation as too dense
at 390px. Asset `9.252.0` therefore maps the same six families to five structured
Research Brief rows plus a Data footer. This note supersedes sections 6 and 7
only as presentation guidance; it does not reopen or alter any evidence rule,
methodology, API, DTO, backend ownership, or semantic statement contract above.
Owner approval of that structured direction subsequently authorized only a
final `9.253.0` responsive hierarchy polish for ATHENA and Data display groups;
the same limitation applies.
The final `9.254.0` micro-correction changes only rendered Portfolio-row
admission: NOT_HELD evidence remains composed but is omitted from Research Brief.
