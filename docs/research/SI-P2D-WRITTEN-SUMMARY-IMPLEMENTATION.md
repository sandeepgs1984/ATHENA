# ATHENA — SI-P2D deterministic written research summary implementation

Date: 2026-09-14
Status: **COMPLETE AND FROZEN**
Asset: `9.254.0`

## 1. Objective and result

SI-P2D replaces the mechanically assembled Written summary with a concise,
deterministic research note over evidence already present in the frozen Symbol
Intelligence bundle. The note answers structure, evidence agreement, momentum
and participation, selected price relationships, persisted ATHENA Decision,
Portfolio membership, freshness, and capability limitations without creating a
prediction, recommendation, causal claim, score, target, or methodology.

SI-P1, SI-P2A, SI-P2B, and SI-P2C remain complete and frozen. SI-P2E has not
started. No API, DTO, persistence, provider, Decision, Portfolio, DarvaX,
hydration, candle-request, chart, or domain implementation changed.

## 2. Ownership

The composer remains frontend-owned because the prior summary was already a
dashboard presentation, every admitted input is present in the frozen coherent
bundle, and no other consumer needs a summary-text contract. Moving it to the
backend would reopen the SI-P1 DTO solely for presentation convenience.

`siComposeResearchSummary(bundle)` is pure and testable. It returns immutable
statement objects whose original semantic contract remains intact, with
presentation-only compact parts retained beside it:

```text
{ kind, text, source_refs, as_of, display_parts, display_meta }
```

`kind`, `text`, `source_refs`, and `as_of` are unchanged. `display_parts` and
`display_meta` are deterministically derived from the same admitted evidence.
The renderer escapes text and aggregates source references into a debug/audit
data attribute. It does not generate or persist evidence.

## 3. Before and after

Before, `siCompleteReview()` emitted ten repeated subheadings, one absence line
per missing capability, DarvaX navigation prose, raw technical enums, and MQ/EQ
placeholder text. It repeated Stock 360 rather than synthesizing it.

After the initial implementation, Owner / Chief Architect review found that its
single primary paragraph was still too dense for a research cockpit, especially
at 390px. Asset `9.252.0` replaces that presentation with one semantic Research
Brief containing five ordered rows—Structure, Momentum, Key Levels, ATHENA, and
Portfolio—and one subordinate Data footer.

On desktop, each row uses an aligned label/evidence grid with restrained
separators. At 390px, each label stacks above its evidence at the same readable
body size; content remains in normal flow with no horizontal overflow. Missing
families leave no empty row. This is presentation compression only: the fixed
taxonomy, admission rules, semantic statement text, provenance, and collapsed-
by-default disclosure behavior remain unchanged.

Owner / Chief Architect then approved the structured direction and requested
one final bounded hierarchy polish. Asset `9.253.0` groups persisted ATHENA
Decision display parts into primary type/confidence evidence, secondary
score/gates evidence, and as-of metadata. On narrow layouts the groups stack;
on desktop they remain compact inline evidence. Atomic Decision facts use
non-breaking internal spaces so wrapping occurs between facts rather than
orphaning words such as “confidence.” The Data footer similarly renders
freshness and capability availability as separate traceable spans: inline with
a restrained separator on desktop and stacked on narrow screens. Stale
freshness alone retains warning prominence rather than coloring or burying the
ordinary capability note.

The final Owner-authorized micro-correction on asset `9.254.0` changes only
Portfolio row admission. A composed `PORTFOLIO` statement remains present and
traceable for HELD and NOT_HELD states, but the Research Brief renderer admits
the row only when `portfolio.status === "HELD"`. This removes repetitive “Not
held” visual noise without changing Portfolio facts or provenance.

## 4. Deterministic sentence families

Fixed order is STRUCTURE → MOMENTUM → LEVEL_POSITION → ATHENA_DECISION →
PORTFOLIO → DATA_AVAILABILITY. Exact field/coherence/variant rules are frozen in
`SI-P2D-WRITTEN-SUMMARY-DISCOVERY.md`.

- **STRUCTURE:** coherent approved SMA and SuperTrend enums only. Same mapped
  direction is stated as agreement; different directions are stated as
  disagreement without resolving it. A single available measurement is stated
  with the other marked unavailable.
- **MOMENTUM:** coherent numeric RSI to one decimal and coherent completed-D1
  volume compared with its owned MA20. No RSI threshold semantics.
- **LEVEL_POSITION:** maximum two observations. Support 1 upper boundary falls
  back to Major Support; Review Trigger lower boundary falls back to Target 1.
  Existing P2B completed-D1 arithmetic and one-decimal display are reused.
- **ATHENA_DECISION:** persisted human-readable type, date, confidence, optional
  persisted score, and gate count. Missing Decision says technical research
  remains available. No explanation is reinterpreted and no Decision runs.
- **PORTFOLIO:** factual held/not-held state; held quantity/average and P&L only
  when present. Portfolio guidance fields are not admitted.
- **DATA_AVAILABILITY:** compact D1 date or stale warning, one bounded optional
  evidence note, and human-readable fundamentals/news non-ingestion.

## 5. Length and omission rules

The Research Brief admits at most five ordered rows. Availability admits at
most one footer. A level family contains no more than two observations. Empty
families are omitted; text is never arbitrarily truncated.

Up to three unreported missing optional D1 measurements are named in one note.
Four missing measurements collapse to one generic availability sentence.
SuperTrend absence already stated by STRUCTURE is not repeated in the footer.
PARTIAL is not repeated when the no-Decision sentence already communicates its
relevant cause.

## 6. Safety boundaries

- No LLM, OpenAI call, local model, external summarizer, or external service.
- No live quote is compared with completed-D1 levels.
- No blended trend, bullishness, probability, strength, confirmation, causal
  explanation, recommendation, or action language.
- No Momentum Quality, Entry Quality, new score, confidence, target, or plan.
- No DarvaX interpretation or narrative inclusion.
- Invalid identity produces no research summary.
- All output is derived from explicit bundle fields or frozen P2B arithmetic.

## 7. Tests

`tests/symbol_intelligence/test_si_p2d_written_summary.py` executes the actual
JavaScript composer with real-shaped fixtures and covers:

- Up/Up and Down/Down agreement;
- SMA/SuperTrend disagreement and unavailable SuperTrend;
- RSI/volume together, individually, and unavailable;
- Support 1/Major Support and Review Trigger/Target 1 fallbacks;
- persisted Decision and no-Decision cases;
- held ACMESOLAR-like and not-held Portfolio cases;
- READY, PARTIAL, and stale market evidence;
- fundamentals/news not ingested and sparse optional evidence;
- invalid identity omission;
- human-readable enums, statement provenance, fixed ordering and length bounds;
- no prediction, recommendation, causal, MQ, EQ, or invented trend language;
- compact semantic rendering, deterministic label/order mapping, absent-family
  omission, responsive desktop/mobile CSS, and asset pins.

Results:

- SI-P2D focused: **16 passed**;
- SI/P2A/P2B/P2C/P2D/API/hosting integration: **88 passed**;
- complete repository: **4094 passed, 0 failed, 2 skipped**;
- Ruff: passed;
- scoped mypy (`src/athena/symbol_intelligence`): passed, 4 source files;
- JavaScript syntax: passed;
- `git diff --check`: passed.

The complete-repository result preceded the final loading-overlay addition.
After that presentation-only change, the full impacted SI/API/hosting regression
was rerun and remained **88 passed**; the full suite was not repeated.

## 8. Live validation

Real-browser GET-only validation passed on WIPRO, TI, ACMESOLAR, 390px WIPRO,
390px TI, and an invalid symbol. Asset `9.253.0` loaded for CSS and JavaScript;
all pages had zero horizontal overflow. Desktop labels aligned in a two-column
grid; both mobile briefs stacked into one column without font-size reduction.
WIPRO's mobile ATHENA row measured 136.6px while showing all three evidence
tiers; its Data footer separated freshness from capability availability. TI's
no-Decision row remained a single concise evidence group. The affected WIPRO
desktop, WIPRO mobile, and TI mobile captures were replaced; unaffected TI and
ACMESOLAR desktop and invalid-state captures were not unnecessarily regenerated.
Per Owner direction, no browser screenshots were generated for the `9.254.0`
Portfolio-admission correction. Owner / Chief Architect subsequently reviewed
the final source and actual rendering and approved SI-P2D for freeze.

The final `9.254.0` presentation bundle also gives the existing symbol-result
GET and Analyze requests one accessible, blocking progress overlay consistent
with Portfolio Sync. Symbol selection truthfully says it is loading persisted
evidence; Analyze truthfully says it is refreshing completed-D1 evidence. The
overlay shows the active symbol, preserves prior evidence until completion,
respects reduced-motion preferences, and uses the existing in-flight lifecycle.
Request method, cancellation/generation protection, hydration, and response
handling are unchanged.

- WIPRO: READY, Down/Down, RSI 30.8, above-average volume, Major Support and
  Review Trigger relationships, persisted No Trade/High/35.0/6-of-6 Decision,
  not held.
- TI: PARTIAL, Up/Down disagreement, RSI 44.1, below-average volume, Support 1
  and Review Trigger relationships, no Decision, not held.
- ACMESOLAR: READY, Up/Up, RSI 54.8, persisted Watch/High/51.1/6-of-6 Decision,
  held 418 shares at ₹408.35 with Portfolio P&L -1.60%.
- Invalid: no Written summary rendered.

No naturally sparse case was found among seven read-only candidates; the report
does not claim one. Deterministic sparse behavior is covered by fixtures.

## 9. Files

Created:

- `docs/research/SI-P2D-WRITTEN-SUMMARY-DISCOVERY.md`
- `docs/research/SI-P2D-WRITTEN-SUMMARY-IMPLEMENTATION.md`
- `tests/symbol_intelligence/test_si_p2d_written_summary.py`

Modified:

- `src/athena/api/static/js/08c-symbol-intelligence.js`
- `src/athena/api/static/css/15-symbol-intelligence.css`
- dashboard asset pins and their existing release tests
- `docs/MILESTONES.md`, `ATHENA_BRIEFING.md`, `IMPLEMENTATION_SUMMARY.md`

## 10. Architecture review

ATHENA-002 report/presentation boundaries are preserved. Determinism,
replayability, PIT boundaries, one-request behavior, provider independence, and
all frozen contracts remain unchanged. No ADR is required. Technical debt
introduced: none known.

## 11. Known limitations and deferrals

The narrative can only report evidence already in the bundle. Fundamentals,
news/catalysts, Momentum Quality, Entry Quality, predictions, recommendations,
Decision generation, sentiment, corporate actions, DarvaX interpretation, and
Portfolio action methodology remain unavailable or explicitly deferred.
SI-P2E and every later milestone require separate authorization.

## 12. Suggested consolidated commit message

```text
feat(report): complete SI-P2D research brief

- Replace dense summary prose with a scannable evidence-backed Research Brief.
- Present structure, momentum, key levels, ATHENA, and held-portfolio context.
- Omit non-held Portfolio presentation while preserving traceable evidence.
- Add accessible Symbol Intelligence loading feedback without changing evidence.
- Preserve frozen SI methodology, API, Decision, Portfolio, and chart contracts.
- Freeze validated SI-P2D presentation on asset 9.254.0.
```

**Milestone stop:** SI-P2D — COMPLETE AND FROZEN on asset `9.254.0`. Do not
start SI-P2E.
