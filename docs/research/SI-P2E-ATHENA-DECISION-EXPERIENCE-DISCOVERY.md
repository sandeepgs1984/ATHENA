# SI-P2E — ATHENA Decision Experience Discovery

**Date:** 2026-09-14

**Baseline:** SI-P1/P2A/P2B/P2C/P2D COMPLETE AND FROZEN; dashboard asset `9.254.0`

**Status:** DISCOVERY COMPLETE — GO; implementation not started pending Owner / Chief Architect approval

## 1. Verdict

**GO without a contract change.** The frozen `SymbolIntelligenceBundleDTO`
already exposes enough authoritative Decision evidence to build the intended
evidence-first surface: persisted identity and timing, type/direction,
explanation, confidence, all individual gate results and their details, the
complete optional TradePlan, persisted analytical depth, and deterministic
Decision/plan freshness.

SI-P2E can therefore remain a presentation-only refinement of
`08c-symbol-intelligence.js` and `15-symbol-intelligence.css`. It must not call a
new endpoint, expand the SI DTO, read Decision tables directly, invoke the
`DecisionEngine`, or alter Analyze. Category-C material remains in the existing
Decision Brief and is reached through the existing link.

This is aligned with `ATHENA-002-System-Blueprint.md` §2 and §7: the report
layer renders stored objects and never computes a Decision or reconstructs an
explanation.

## 2. Current architecture trace

1. `DecisionEngine.decide()` creates the immutable domain `Decision` and
   `DecisionTrace`. A Decision owns its required explanation, optional source
   references, all `GateResult` objects, and an optional complete `TradePlan`.
2. `SqliteRepository.save_decision(..., trace=...)` persists the Decision and
   trace. Run detail/report persistence supplies the analytical depth used by
   the Decisions service.
3. `DecisionsService.get_decision()` maps the stored Decision to `DecisionDTO`.
   Confidence level is read from the persisted decision report. Gate detail and
   TradePlan values are copied without reinterpretation.
4. `DecisionsService.get_decision_depth()` maps persisted eligibility,
   score, confidence, and risk report blocks. `get_trade_plan_freshness()`
   performs read-time arithmetic over the persisted validity window; it never
   recomputes the plan.
5. `SymbolIntelligenceComposer._compose_decision()` selects the latest
   persisted Decision for the instrument, reads the DTO, depth, TradePlan
   freshness, and optional Decision-bound intraday view, and copies them into
   `SiDecisionSummaryDTO`. Exceptions fail closed to absent optional detail.
6. The composer independently classifies Decision freshness from the Decision
   timestamp's market date versus the calendar's expected session. It also
   retains D1 freshness as a separate source fact.
7. `GET /api/v1/symbol-intelligence/{query}` only re-reads these sources.
   `POST` Analyze may hydrate completed-D1 candles and then re-read; it does not
   run the Decision engine.
8. `siAthenaView()` / `siDecisionCard()` currently show a small field summary,
   the persisted explanation, a minimal entry-band line, a local Evidence jump,
   and `/dashboard/decisions?decision=<decision_id>`.
9. The Decision Brief independently loads the canonical Decision, depth,
   context, trace, plan freshness, history and other Decision-owned views. It
   remains the authoritative deep-inspection destination.

## 3. Field classification matrix

Classification: **A** persisted authoritative Decision evidence; **B** derived
presentation-safe; **C** available elsewhere but not exposed through SI;
**D** unavailable; **E** unsafe to infer.

| Candidate UI fact | Class | Existing source | SI-P2E admission |
|---|---:|---|---|
| Decision ID | A | `decision.decision_id` | Keep as link identity, not primary chrome |
| Decision type | A | `decision.decision_type` | Primary headline; human-label enum only |
| Direction | A | `decision.direction` | Show when meaningful; do not manufacture for `NONE` |
| Decision timestamp/date | A | `decision.ts` | Primary metadata with explicit “Decision as of” |
| Run and cycle IDs | A | `decision.run_id`, `cycle_id` | Evidence/provenance disclosure only |
| Persisted Decision explanation | A | `decision.explanation` | Primary “Why” text, escaped and not rewritten causally |
| Confidence level | A | persisted report via `confidence_level` | Show only when non-null |
| Persisted composite score | A | `decision.depth.score.value` | Show only when present; `/100` is existing display convention |
| Score status/explanation/dimensions | A | `decision.depth.score.*` | Available, but defer detail to Decision Brief to avoid duplication |
| Confidence/risk depth | A | `decision.depth.confidence/risk` | Available, but defer detail to Decision Brief |
| Eligibility result/rules | A | `decision.depth.eligibility` | Available, but not required in the compact SI surface |
| Individual gate name | A | `decision.gates[].gate` | Human-readable six-gate list |
| Individual gate outcome | A | `decision.gates[].passed` | Passed/failed state; authoritative |
| Individual gate detail/reason | A | `decision.gates[].detail` | Progressive disclosure; never regenerate |
| Passed/total gate count | B | count of authoritative `gates[]` | Summary only; preserve actual array length |
| Failed gate list/count | B | filter authoritative `gates[]` | Safe as “failed/blocked checks,” not universal causal prose |
| “All safety checks passed” | B | non-empty gates and zero failures | Safe factual summary; does not imply TRADE |
| Decision freshness | B | Decision date vs expected session | Prominent independent current/stale label |
| SI overall coverage | B | frozen `overall_freshness` | Context only; never substitute for Decision freshness |
| D1 market-data freshness | B | `sources.D1_CANDLES` | Warning context only; do not blend D1 indicators into Decision |
| TradePlan entry low/high | A | `decision.trade_plan` | Label Entry or Entry band; not “trigger” unless contract says so |
| TradePlan stop loss | A | `decision.trade_plan.stop_loss` | Label Stop loss; never relabel as Support |
| TradePlan target list | A | `decision.trade_plan.targets` | Render exact list length; invent no T2/T3 |
| Position size | A | `decision.trade_plan.position_size` | Optional secondary plan fact |
| Risk amount | A | `decision.trade_plan.risk_amount` | Optional secondary plan fact |
| Risk/reward | A | `decision.trade_plan.risk_reward` | Optional secondary plan fact |
| Plan valid-from/until | A | `decision.trade_plan.valid_*` | Show compactly when a plan exists |
| Plan freshness/status/summary | B | arithmetic over plan window at `read_as_of` | Show independently from Decision freshness |
| “No persisted trade plan” | B | `trade_plan === null` | Exact factual empty state |
| Decision trace stages/ref IDs | C | `/decisions/{id}/trace` | Do not expand SI; use Decision Brief |
| Analysis resource references | C | canonical `DecisionDTO.analysis.*_ref` | Keep in Decision Brief/Evidence |
| Regime, market health, sector context | C | `/decisions/{id}/context` | Do not fetch into SI-P2E |
| Journal response and realized outcome | C | Decision journal/outcome endpoints | Decision Brief/history only |
| Analogs, counterfactual and near misses | C | existing Decisions endpoints | Not part of compact persisted-conclusion surface |
| Full Decision history/timeline | C | Decisions list/history | Decision Brief only |
| A second generated rationale | D/E | no authoritative artifact | Prohibited |
| Inferred probability/strength/conviction | E | no approved SI semantics | Prohibited |
| Stock 360 SMA/SuperTrend/RSI/volume as Decision causes | E | current D1, not necessarily decision-time trace | Prohibited |
| Invented entry, support, exit, target or recommendation | E | absent | Prohibited |

## 4. Exact proposed information architecture

### 4.1 Persisted Decision present

1. **Decision hero:** human-readable Decision type, optional meaningful
   direction, Decision current/stale treatment, and “Decision as of” timestamp.
2. **Strength row:** persisted confidence and score where present, plus factual
   passed/total gate summary. Missing optional values disappear rather than
   becoming fake zeroes.
3. **Why ATHENA decided this:** display the persisted Decision explanation
   unchanged in meaning. Follow it with a compact six-gate checklist. Each row
   uses a human gate label, passed/failed state, and stored detail through
   progressive disclosure where space requires it.
4. **Persisted TradePlan:** if present, show Entry band, Stop loss, every stored
   target, risk/reward, size/risk amount, validity, and plan freshness in a
   disciplined grid. If absent, state “No persisted trade plan for this
   decision.”
5. **Actions:** `Open Decision Brief` as the primary deep-inspection route and
   `View Evidence` as the local audit route. Provenance IDs stay subordinate.

Desktop may use a two-column evidence/plan region after the hero. At about
390px all content must remain in normal flow, use one column, keep values
aligned within their rows, and avoid horizontal scrolling. Gate detail should
be progressively disclosed, not squeezed into tiny text.

### 4.2 No persisted Decision

Render a compact first-class empty state:

- `ATHENA Decision` / `No persisted decision`;
- “ATHENA has not produced a persisted Decision for this symbol. Stock 360
  research remains available.”;
- a direct `Back to Stock 360` action and `View Evidence` for the source status.

This is not an Analyze error, not proof that the symbol is unattractive, and
not permission to add Generate/Revalidate actions. No outbound decision-specific
link is possible without a `decision_id`; the existing Decisions workspace may
remain reachable through global navigation.

## 5. Freshness and staleness semantics

Decision freshness is computed independently: the Decision timestamp is
`CURRENT` only when its market-local date equals the calendar-resolved expected
session; otherwise it is `STALE` (or `UNAVAILABLE` when no Decision/calendar).
TradePlan freshness is a separate validity-window calculation with
`FRESH/AGING/STALE/EXPIRED/NO_PLAN` semantics.

A persisted Decision can coexist with stale D1 evidence because both are
independent stored sources. The UI must therefore cover these combinations:

| Market D1 | Decision | Required treatment |
|---|---|---|
| CURRENT | CURRENT | Normal hero; no stale warning |
| CURRENT | absent | No persisted decision; Stock 360 remains available |
| CURRENT | STALE | Mark the Decision stale beside its timestamp; do not let overall `READY` hide it |
| STALE | present | Mark market evidence stale and independently mark Decision current/stale; keep stored Decision visible as historical evidence |
| unavailable/invalid | unavailable | Clear prior content and render the existing invalid/unavailable state |

The frozen overall rollup deliberately treats current D1 plus any present
Decision as `READY`, even when that Decision source is stale. SI-P2E must read
the `ATHENA_DECISION` source row directly for Decision freshness rather than
using overall coverage as a proxy.

## 6. Gate explanation semantics

`gate_pass_count` is not stored as a new score. It is the presentation count of
`gates[]` entries whose persisted `passed` value is true, divided by the actual
number of persisted gate rows. The current engine normally emits the six
ATHENA-002 gates, but the UI must not hardcode six when evidence is absent or a
historical record has another count.

Individual outcomes and details are authoritative because `GateResult.detail`
is mandatory on the immutable domain object and is persisted with the
Decision. It is safe to say “2 of 6 checks failed” and list those failed checks.
It is not always safe to say those failures *caused* the Decision: TRADE also
requires the score threshold, a direction, and a valid plan; WATCH/NO_TRADE can
occur with all gates passed. Causality may be shown only where it is already in
the persisted `decision.explanation` or exact gate detail.

Missing gate rows mean “No gate results were persisted for this Decision,” not
“all gates passed.” A missing detail cannot occur in a valid current domain
object, but presentation still fails closed if legacy/malformed payloads omit
it.

## 7. TradePlan semantics

The authoritative plan is all-or-none in the typed contract: entry low/high,
stop loss, a non-empty target list, position size, risk amount, risk/reward,
valid from, and valid until. A “partial TradePlan” is not a valid
`TradePlanDTO`; the UI must tolerate missing individual payload values by
omitting/failing closed, but must never complete them.

Use `Entry`/`Entry band`, `Stop loss`, and `Target 1…n`. “Support” is a different
structural concept owned elsewhere and must not be substituted for stop loss.
An expired plan remains persisted historical evidence and must be visibly
non-current, not presented as an actionable current setup.

## 8. Stock 360 duplication audit

Do not repeat current SMA20/SMA50, SuperTrend, RSI, completed-D1 volume,
structural zones, chart, current price map, Research Brief Structure/Momentum/
Key Levels, Portfolio guidance, or DarvaX output. Those answer what the stock
looks like now, not what the persisted Decision concluded at its own timestamp.

SI-P2E should retain only the persisted Decision conclusion, explanation,
score/confidence, gates, plan, timestamps/freshness, and navigation. Detailed
score/confidence/risk dimensions already present in the SI bundle should remain
behind the Decision Brief unless a later owner review explicitly requests a
bounded progressive disclosure.

## 9. Evidence and Decision Brief navigation

- **Open Decision Brief:** existing safe route
  `/dashboard/decisions?decision=<encoded decision_id>`.
- **View Evidence:** existing `data-si-jump="audit"` navigation to the SI
  Evidence/Audit section for source status, as-of, lineage and reasons.
- Raw reference IDs, complete trace stages, analytical dimensions, context,
  history, journal/outcome, analogs and counterfactual material remain in the
  Decisions workspace. SI-P2E does not duplicate or fetch them.

## 10. Explicit answers to the discovery questions

1. **Persisted today:** immutable Decision identity/time/run/cycle/type/
   direction/explanation, refs, gate outcomes/details, optional complete
   TradePlan, separate DecisionTrace, and persisted run/report depth.
2. **Already through SI:** all summary fields, explanation, confidence, gates,
   TradePlan, plan freshness, depth, optional Decision-bound intraday view, and
   Decision source freshness.
3. **Decision Brief-only:** canonical refs, trace, context, journal/outcomes,
   analogs, counterfactual, history, track record, and near-miss views.
4. **Without DTO change:** yes.
5. **Gate pass count:** passed booleans divided by the actual persisted gate
   list length; a status summary, not a cause or score.
6. **Individual outcomes:** yes, exposed and authoritative.
7. **Failed-gate reasons:** yes; mandatory persisted `detail` strings.
8. **Causal wording:** only persisted explanation/detail is safe. Derived
   “because” prose is not.
9. **Authoritative plan fields:** entry range, stop loss, exact target list,
   position size, risk amount, risk/reward, valid-from and valid-until.
10. **Decision freshness:** Decision market date versus expected session.
11. **Decision with stale D1:** yes.
12. **UI response:** preserve the Decision as stored evidence and disclose D1
    and Decision staleness independently; never masquerade either as current.
13. **Outbound route:** `/dashboard/decisions?decision=<decision_id>`.
14. **Stock 360 duplication:** current D1 technicals, chart/levels, price map,
    Research Brief, Portfolio and DarvaX.
15. **Evidence-only:** source freshness/lineage and unavailable reasons locally;
    raw IDs, full trace/provenance and deep analytical/history artifacts in the
    Decision Brief.

## 11. Implementation boundary and validation plan

If the Owner approves implementation, the bounded working set is expected to
be the SI renderer/CSS, focused SI-P2E presentation tests, asset pins, and
milestone/status documentation. No production Python, API, DTO, schema,
repository, composer, Decision, Portfolio or DarvaX file is required.

Fixtures should cover current TRADE/WATCH/NO_TRADE, no Decision, stale Decision,
stale D1 plus Decision, held/non-held, invalid symbol, complete/missing plan,
variable gate counts, failed gate detail, absent optional score/confidence, and
desktop/~390px contracts. Natural screenshots must not require persisted-data
mutation. Analyze tests must continue proving POST is D1 hydration/re-read only.

## 12. Known limitations and deferrals

- SI exposes the latest persisted Decision only; it is not a Decision history
  browser.
- Gate detail can be technical because it is persisted engine evidence; labels
  may be humanized, but its meaning must not be paraphrased into new causality.
- A complete plan is optional and normally belongs to a TRADE Decision. No plan
  is an expected state for other decisions.
- Decision freshness is session-date freshness, while plan freshness is
  validity-window freshness. Neither asserts that current D1 evidence matches
  the evidence used during the originating run.
- Full trace, context, resource refs, counterfactual, analogs, journal/outcome,
  history, candidate workflows, Generate Decision and Revalidate Decision are
  explicitly deferred/out of SI-P2E.
- SI-F0 and SI-N0 remain not started.

## 13. Discovery validation

This discovery is based on direct source review of the frozen domain models,
Decision engine, repository/service mapping, SI DTO/composer, Decision Brief,
SI renderer, existing SI tests, milestone documentation, and ATHENA-002. No
runtime code, stylesheet, asset pin, API, DTO, schema or persisted data changed.

**Implementation gate:** GO. Stop here for Owner / Chief Architect review before
starting SI-P2E implementation.
