# F-5 — Market Health Score Contract

| | |
|---|---|
| Status | **ACCEPTED** — Owner approved 2026-07-28 (proceed MH-1) |
| Date | 2026-07-28 |
| Blueprint | ATHENA-002 §4 `MarketHealthScore`; ATHENA-002R **F-5** |
| ADR | ADR-005 (persist explanation); ADR-008 (institutional flow input) |
| Related | [DD-11](../decisions/DD-11-institutional-flow-fii-dii.md) |

---

## 1. Purpose

Define the **exact** numeric Market Health Score ATHENA will construct so the Market Summary mock ring (`84/100`) is honest: computed by the engine, persisted as data, rendered by the UI — never reconstructed in the dashboard.

This is the missing implementation of the already-frozen domain type:

```text
MarketHealthScore:
  ts, components{trend_quality, breadth, liquidity, volatility,
                 institutional_strength, gap_stability},
  total (0..100), explanation
```

---

## 2. Non-negotiable rules

1. **Six components only** — exact F-5 set. No substituting `momentum` for `liquidity`. Categorical `MarketHealthAssessment` may keep its existing four labels (incl. momentum) for compatibility; the **score** uses F-5 keys only.
2. **Each component is an integer 0..100** or **absent** (not scored). Absent ≠ 50.
3. **`total`** is the config-weighted round of scoreable components (see §5). If **any required component is absent**, `MarketHealthScore` is **not emitted** for gates/UI rings — callers see `null` / unavailable (ADR-005 honesty). Optional: still persist a diagnostic categorical assessment.
4. **Config over hardcoding** — all windows, bands, and weights live in `config/market_health.json` (extended in MH-1/MH-2).
5. **Single authoritative number** — decision/scoring/risk market-quality consumption must converge on this persisted `total` (or stay unknown). The current scoring path that averages categorical label points becomes a **compat shim** until MH-2 switches it to `MarketHealthScore.total` (owner-approved cutover in MH-2, not a permanent dual formula).
6. **Explainability** — `explanation` mandatory; each component contributes evidence (inputs, thresholds, points) persisted with the run (ADR-005).

---

## 3. Component definitions (inputs → points)

All comparisons use `Decimal` math; timestamps timezone-aware. “Index” defaults to configured Nifty benchmark already used by regime/health (typically `NSE:NIFTY 50`).

### 3.1 `trend_quality` (existing engine logic → points)

| Input | Canonical D1 index candles over `trend_quality.window` |
| Method | Same consistency ratio as today’s `MarketHealthEngine._trend_quality` |
| Map | `STRONG` → strong_points; `MIXED` → mid_points; `WEAK` → weak_points; `UNKNOWN` → absent |
| Config keys | existing window/consistency bands + new `points` map |

### 3.2 `breadth` (universe participation — owner choice)

| Input | Owner candidates / Nifty-500 seed universe with ≥2 D1 bars |
| Method | Latest close vs prior close: **advance** / **decline** / **neutral** (unchanged) |
| Ratio for bands | `advances / (advances + declines)` — neutrals excluded from ratio denominator (standard breadth practice) but **reported** in counts |
| Persist on snapshot | `breadth_advances`, `breadth_declines`, and reviewed additive field **`breadth_neutral`** (blueprint §4 field addition — docs-typed, no rename) |
| Coverage gate | If scored symbols &lt; `breadth.min_coverage` (config, e.g. 70% of universe with 2 bars) → absent |
| Map | Same strong/mixed/weak bands as today → points; zero adv+dec → absent |

**Not** exchange-wide NSE ADV/DEC (Kite cannot supply). UI must label “Universe breadth” (or equivalent), never imply all-NSE.

### 3.3 `liquidity` (new — market aggregate)

| Input | Universe members’ recent average daily rupee volume (close × volume) or volume MA already used by universe/scoring |
| Method | Median (or mean — pick one in MH-1 config, default **median**) of member liquidity vs `liquidity.healthy_median_turnover` / `liquidity.weak_median_turnover` |
| Map | healthy → high points; between → mid; below weak → low; insufficient members → absent |
| Note | Instrument-level scoring liquidity stays separate; this is **market-level** participation liquidity |

### 3.4 `volatility` (existing VIX logic → points)

| Input | `MarketSnapshot.india_vix` |
| Method | Same calm / normal / elevated bands as today’s health volatility |
| Map | CALM / NORMAL / ELEVATED → configured points; missing VIX → absent |

### 3.5 `institutional_strength` (new — DD-11)

| Input | Latest institutional flow row for the session (prefer non-provisional) |
| Method | Combine FII net + DII net (₹ Cr) over `institutional.lookback_sessions` (default 1 for v1; optional 5-day sum later) |
| Strength signal | Net combined flow vs config bands (`strong_buy_cr`, `weak_buy_cr`, `strong_sell_cr`, …) **or** percentile vs trailing `institutional.history_window` — **v1 recommendation:** absolute ₹ Cr bands in config (simple, explainable); history percentiles optional MH-2+ |
| Map | strong buy / mild buy / balanced / mild sell / strong sell → points; missing/stale beyond `max_age_sessions` → absent |
| Evidence must include | session date, FII net, DII net, provisional flag, source id |

### 3.6 `gap_stability` (new — rolling gaps)

| Input | Index D1 candles over `gap_stability.window` |
| Method | For each day: gap% = (open − prior close) / prior close. Count days with \|gap%\| ≥ `regime.gap_pct_threshold` (reuse regime threshold unless overridden) |
| Stability ratio | `1 − (gap_days / scored_days)` |
| Map | ratio ≥ strong → high points; ≤ weak → low; else mid; &lt; min bars → absent |

---

## 4. Unknown / unavailable policy

| Situation | Behavior |
|---|---|
| Component inputs insufficient | Component **absent** (not 0, not 50) |
| Any of the six absent | **Do not construct** a displayable `MarketHealthScore` for UI rings / decision market gate that requires a floor |
| Categorical engine | May still emit labels including `*_UNKNOWN` for the four legacy dimensions |
| UI | Show “Unavailable” / categorical fallbacks — **never** invent 84 or 72 |
| Downstream scoring | `market_quality` unknown when score absent (same as today’s “no scoreable dimensions”) |

---

## 5. Total calculation

```text
weights in config/market_health.json → must sum to 100
  trend_quality, breadth, liquidity, volatility,
  institutional_strength, gap_stability

total = round( Σ (component_points[c] * weight[c]) / Σ weight[c] for c in present )
```

**Only present components** enter the sum. Because §4 forbids emitting the object when any component is absent, v1 `total` always uses all six weights. (If a future amendment allows partial scores, the formula above already supports it — UI must then show coverage.)

`total` clamped/validated to 0..100 by the frozen type.

---

## 6. Persistence & provenance (ADR-005)

When constructed during validation / regime stage:

| Artifact | Storage |
|---|---|
| Full `MarketHealthScore` JSON | Run `detail_json` (and/or dedicated append-only table if MH-1 chooses schema clarity) |
| Per-component evidence | Evidence ids + explanations (mirror `HealthEvidence`) |
| Config snapshot id | Already on `RunRecord` |
| Institutional flow row used | Foreign key / payload ref to append-only flow store |
| Breadth counts | Enriched `MarketSnapshot` (adv/dec/neutral) written on ingest/validation |

Replay must reconstruct the same `total` from persisted inputs + config snapshot — not from live NSE.

---

## 7. Consumer alignment (MH-2 cutover)

| Consumer | Today | After MH-2 |
|---|---|---|
| Market Summary UI | 4 categorical dims | Ring from persisted `total` + component breakdown tooltips |
| `ScoringEngine._market_quality` | Average of categorical label points | Prefer `MarketHealthScore.total` when present |
| Decision `market_floor` gate | Uses scoring’s market_quality component | Same floor (`regime.json` / decision thresholds) applied to authoritative total |
| Ticker strip | Omits health | Optional chip only when score present (MH-3) |

No dual competing “health numbers” after cutover.

---

## 8. API / history contract (MH-3 consumes; MH-1/2 produce)

Proposed read model fields (names indicative):

```text
MarketSummaryDTO
  as_of
  regime { trend, volatility, gap, explanation, evidence[] }
  market_health {
    score: int | null          # MarketHealthScore.total
    components: {name: int} | null
    explanation: str | null
    dimensions: {…}            # categorical legacy, always honest
  }
  breadth {
    advances, declines, neutral, advance_pct, universe_size, coverage
  } | null
  gap_detail { points, pct } | null
  vix { level, change_pct } | null
  sparklines { nifty_closes[], vix_closes[] }  # from persisted candles
```

History endpoints:

- Reuse / extend candle history for NIFTY & VIX sparklines (no new sparkline table).
- `list_snapshots_recent(limit)` for Recent Activity index/VIX events (MI-5 partial gap).

---

## 9. Blueprint field addition (reviewed)

Add to `MarketSnapshot` (ATHENA-002 §4 — additive field, docs-typed commit in MH-1):

| Field | Type | Meaning |
|---|---|---|
| `breadth_neutral` | `int = 0` | Universe names with unchanged close vs prior |

No removals/renames.

---

## 10. Milestone mapping

| Milestone | Delivers |
|---|---|
| **MH-0** (this doc + DD-11 + ADR-008) | Contracts locked |
| **MH-1** | Flow ingest, breadth+neutral, liquidity & gap inputs, snapshot history reads |
| **MH-2** | Construct/persist `MarketHealthScore`; consumer cutover |
| **MH-3** | Summary API + mock-faithful UI (rings, sparklines, ADV/DEC/neutral) |

---

## 11. Acceptance checklist (owner)

- [ ] Accept six-component F-5 set and unknown policy (§2–§4)
- [ ] Accept universe breadth + neutral (not all-NSE) (§3.2)
- [ ] Accept DD-11 NSE+file institutional source
- [ ] Accept ADR-008 separate Protocol
- [ ] Accept single authoritative `total` cutover in MH-2 (§7)
- [ ] Authorize MH-1 implementation
