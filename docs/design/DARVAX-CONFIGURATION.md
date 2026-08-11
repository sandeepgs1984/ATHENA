# DarvaX configuration reference (`config/darvax.json`)

Complete reference for the DarvaX satellite's configuration file: how to turn
DarvaX on and off, every key it accepts, what each value does, where the value
comes from, and how the module fails when configuration is wrong.

**Governing decision:** [ADR-010](../adr/ADR-010-darvax-satellite-module.md)
(Accepted 2026-08-10) and its **Amendment 1** (Accepted 2026-08-11, the
dashboard tab). **Contract source:** [`src/athena/darvax/config.py`](../../src/athena/darvax/config.py)
is authoritative — if this document and that file ever disagree, the file wins
and this document is the defect.

---

## 1. The ownership boundary (read this before editing anything)

`config/darvax.json` lives next to ATHENA's config files as a filesystem
convention only. It is **not** shared ownership:

| | Reads | Via |
|---|---|---|
| **ATHENA core** | the single top-level `enabled` boolean, nothing else | [`athena/api/darvax_mount.py`](../../src/athena/api/darvax_mount.py) |
| **DarvaX** | the entire file, including `enabled` | [`athena/darvax/config.py`](../../src/athena/darvax/config.py) |

ATHENA is deliberately **methodology-blind**. It does not parse stop policies,
EMA ladders, box settings, or scan bounds — it reads one boolean and decides
whether to mount a sub-application. This is why a malformed `methodology` block
cannot break ATHENA's startup unless DarvaX is actually enabled.

Consequences to respect:

- **Never** add a DarvaX field to any `athena.config` model.
- **Never** make ATHENA code read anything from this file except `enabled`.
- Changing DarvaX config requires **no** ATHENA change, and vice versa.

---

## 2. Turning DarvaX on and off

The flag is read **once, at application startup**. Editing the file while the
server is running changes nothing until you restart.

### Enable

1. Set `"enabled": true` in `config/darvax.json`.
2. Restart the server (`./athena-serve --with-cycles --open`).
3. Hard-reload the dashboard (`Cmd+Shift+R`). A plain reload may not be enough:
   while DarvaX was disabled the browser negatively cached the 404 for
   `/darvax/static/tab.js`.

You should then see a **DarvaX** item with an amber **Exp** badge at the bottom
of the sidebar, and `/darvax/` reachable directly.

### Disable

Set `"enabled": false` and restart. The tab vanishes, every `/darvax/*` route
404s, and `athena.darvax` is never imported — the mount seam's import is
function-local precisely so that "disabled means never imported" is literally
true rather than aspirational. ATHENA is byte-for-byte unaffected.

`db/darvax.db` is left on disk when you disable. It is DarvaX's own ledger and
touching it is never required to disable the module; delete it only if you want
to discard stored signals.

### How the dashboard tab is gated

There is exactly **one** DarvaX reference in ATHENA's `index.html` — a deferred
`<script src="/darvax/static/tab.js">` tag. That tag **is** the flag guard:
only the DarvaX sub-application serves that asset, so when DarvaX is disabled
the request 404s, the injector never runs, and the dashboard renders its
original five tabs. There is no ATHENA-side conditional to keep in sync.

The visible cost of that design: **while DarvaX is disabled, every dashboard
load logs one 404 for `tab.js` in the browser console.** That is expected, and
it is the whole mechanism — not a symptom of misconfiguration.

---

## 3. Key reference

Types and bounds below are enforced by pydantic at load time. `Decimal` fields
accept JSON numbers.

### Top level

| Key | Type | Default | Notes |
|---|---|---|---|
| `enabled` | bool | `false` | The **only** key ATHENA reads. Shipped default is off — DarvaX is opt-in (ADR-010 §7) |
| `database` | object | see below | DarvaX's own ledger |
| `methodology` | object | see below | Every methodology parameter |
| `scan` | object | see below | Bounds on one scan request |

### `database`

| Key | Type | Default | Notes |
|---|---|---|---|
| `path` | string (min length 1) | `db/darvax.db` | DarvaX's own SQLite file. **Must never be `db/athena.db`** (ADR-010 §2). DarvaX writes only here; it reads ATHENA's candle history read-only through `DarvaxMarketDataPort` and has its own independent schema version |

### `methodology`

| Key | Type | Default | Range | Source |
|---|---|---|---|---|
| `stop_policy` | enum | `canonical_darvas` | `canonical_darvas` \| `darvax_tight` \| `ema_ladder` | see the contradiction note below |
| `canonical_stop_pct` | Decimal | `10` | > 0, ≤ 50 | Darvas' canonical first-breakout stop, deck p.67 |
| `tight_stop_pct` | Decimal | `1` | > 0, ≤ 50 | DarvaX's own tighter variant, deck p.44 |
| `ema_stop_ladder` | map of string → int | `{very_short_term: 5, swing: 10, positional: 20, investor: 200}` | each period ≥ 1 | Close-below-EMA exit ladder by horizon, deck p.9 |

**The stop-sizing contradiction is deliberately unresolved in code.** The source
deck contradicts itself: Nicolas Darvas' canonical rule is a 10% stop on first
breakout (p.67), while DarvaX's own "How to Play" says 1% (p.44). Both are
selectable. The default is the **canonical, attributable** rule, and DX-5's
evidence — not a guess — decides which should be used.

#### `methodology.box`

| Key | Type | Default | Range | Source |
|---|---|---|---|---|
| `confirmation_bars` | int | `3` | 1–50 | Bars a ceiling/floor must survive unbeaten to be confirmed. **The deck states no number**; 3 is the value used by the classical Darvas implementations it links to |

#### `methodology.swing`

| Key | Type | Default | Range | Source |
|---|---|---|---|---|
| `threshold_pct` | Decimal | `5` | > 0, ≤ 100 | Reversal percentage that confirms a ZigZag pivot, deck p.32 |

#### `methodology.breakout`

| Key | Type | Default | Range | Source |
|---|---|---|---|---|
| `retest_tolerance_pct` | Decimal | `2` | > 0, ≤ 25 | How close price must return to the box ceiling to count as a retest, as a percentage of the ceiling. **The deck shows retests qualitatively (the #TRENT example) without naming a tolerance** |
| `stop_horizon` | enum | `swing` | `very_short_term` \| `swing` \| `positional` \| `investor` | Which rung of the EMA ladder applies (deck p.9). `swing` is the 10-EMA rung, matching ATHENA's own swing focus |

**Cross-field rule:** `ema_stop_ladder` must contain a rung named by
`breakout.stop_horizon`, and every rung period must be ≥ 1. Violating either is
a load-time `ConfigError`, not a silent fallback.

### `scan`

| Key | Type | Default | Range | Notes |
|---|---|---|---|---|
| `max_instruments` | int | `50` | 1–1000 | Most instruments one scan request may evaluate. An over-cap request is **refused, not truncated** — silently dropping symbols would misrepresent coverage |
| `lookback_bars` | int | `400` | 10–5000 | Candles per instrument fed to the signal engine |

Both bounds exist because ADR-010's performance guarantee is *architectural*
(no synchronous dependency on ATHENA), not a promise of zero host-level
contention — DarvaX shares a workstation with ATHENA. DX-4a measures that
contention; these caps keep it bounded meanwhile.

---

## 4. Omitted keys, and why the shipped file is short

Every block and key above has a default, so the shipped `config/darvax.json`
only spells out `enabled`, `database`, and `methodology`. The `box`, `swing`,
`breakout`, and `scan` blocks are absent from the file and therefore take the
defaults in the table above — they are live, not inert.

To change one, add just that block:

```json
{
  "enabled": true,
  "scan": { "max_instruments": 120 },
  "methodology": {
    "stop_policy": "ema_ladder",
    "breakout": { "stop_horizon": "positional" }
  }
}
```

**Keys beginning with `_` are documentation, not configuration.** They are
stripped at every nesting level before validation, which is why `_meta` and
`_note` can sit in the file without tripping the strict-schema check.

---

## 5. Changing methodology values changes the signal digest

Every stored `DarvaxSignal` carries a `methodology_digest`: a sha256 of the
canonicalised `methodology` block, first 16 characters. It is deterministic —
identical settings always produce an identical digest, and changing **any**
methodology value changes it.

This is the replayability requirement in ADR-010 §10: a signal can always be
traced back to the exact parameters that produced it. The practical implication
is that after you change a methodology value, **previously stored signals keep
their old digest** and were computed under the old rules. Signals are not
retroactively recomputed. Compare digests before comparing signals.

Note that only the `methodology` block feeds the digest — `enabled`,
`database`, and `scan` do not, because they change *what was scanned*, not
*how a signal was derived*.

---

## 6. Failure modes

DarvaX fails loudly. None of the below degrades silently.

| Situation | Result |
|---|---|
| File absent | Treated as **not requested**. DarvaX is opt-in, so its absence is a normal supported state, not an error |
| Invalid JSON | `ConfigError` at startup, naming the file and the parse error |
| Top-level JSON is not an object | `ConfigError` |
| `enabled: true` but `athena.darvax` is missing from disk | **Hard startup failure** with a `ConfigError` telling you to restore the module or set `enabled: false`. Leaving you believing DarvaX is running when it is not is a worse outcome than refusing to start |
| `enabled: true` but ATHENA's SQLite ledger is unavailable | **Hard startup failure** — DarvaX has nothing to read candles from |
| Unknown / misspelled key | `ConfigError` listing the offending key. The schema is strict (`extra="forbid"`) so a typo can never be silently ignored |
| Value out of range, or a cross-field rule broken | `ConfigError` from validation |
| `enabled: false` and the config is otherwise garbage | **ATHENA starts normally.** ATHENA reads only `enabled` and never calls DarvaX's loader, so DarvaX's methodology validation cannot affect ATHENA's startup |

### One gotcha worth knowing

The flag is read from the directory `ATHENA_CONFIG_DIR` selects (defaulting to
`config`), the same directory every other ATHENA config consumer uses. If you
run with a non-default `ATHENA_CONFIG_DIR`, DarvaX's flag must live in *that*
directory — putting it in the repo-root `config/` will have no effect.

---

## 7. Status

DarvaX output is labelled **EXPERIMENTAL / UNVALIDATED** on every API payload
and in the page banner, and that label is unconditional — it is a correctness
requirement, not decoration, and embedded mode does not hide it.

On record in ADR-010 and `docs/MILESTONES.md`: the source deck ships **no
backtest evidence of any kind** — only cherry-picked winners and testimonial
screenshots — and its author disclaims it in the deck itself. The label stays
until DX-5 produces real expectancy, win/loss, drawdown, and sample-size
evidence. No configuration change removes it.

DarvaX never contributes to ATHENA's scoring, confidence, risk, `Decision`,
`TradePlan`, universe, or decision pipeline, and there is no order-placement
code anywhere in this repository.
