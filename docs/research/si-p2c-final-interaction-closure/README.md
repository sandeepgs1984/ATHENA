# SI-P2C final interaction / collision / mobile closure evidence

Captured 2026-09-14 from a temporary localhost-only ATHENA process against the
owner's unmodified persisted WIPRO data. The process used the existing
single-user read-only dashboard path. It triggered no hydration, provider call,
Decision, Portfolio Sync, or database mutation.

Asset under review: `9.250.0`.

## Captures

- `desktop-01-idle.png` — calm default 6M state with tighter plot reserve.
- `desktop-02-t1-hover.png` — transient Target 1 preview and full inspector.
- `desktop-03-t1-pinned.png` — persistent Target 1 selection.
- `desktop-04-t1-pinned-t2-hover.png` — transient Target 2 over pinned T1.
- `desktop-05-t1-restored.png` — T1 restored after leaving T2.
- `desktop-06-d1-level-separation.png` — real WIPRO Major Support/D1 close
  proximity with displaced MS tag, immutable true anchor, and leader.
- `desktop-07-levels-selected.png` — persistent selected row, synchronized
  chart geometry, and non-overlapping desktop inspector.
- `desktop-08-candle-inspection.png` — structured OHLC/volume/SMA inspector.
- `390-01-idle.png` — narrow 6M state with recovered plot width.
- `390-02-levels-list.png` — in-flow, local-card-width touch list.
- `390-03-major-support-selected.png` — collapsed list, persistent MS geometry,
  and stable in-flow human-readable inspector.
- `390-04-candle-inspection.png` — stable in-flow keyboard candle inspection.

## Browser assertions

- zero page errors and zero document-width overflow at 1579px and 390px;
- exactly one selected 3M/6M/All control with 63/126/180 sessions;
- mouse-clicked T1 persists after pointer exit;
- transient T2 preview restores persistent T1 on leave;
- menu and chart agree on transient and persistent identities;
- the real close/MS tag intervals do not overlap while the connector retains
  distinct natural and displaced Y coordinates;
- desktop inspector, menu, and axis tags do not overlap;
- mobile Levels list spans the local control/card width and collapses on select;
- mobile selection retains one geometry and exposes the exact full inspector;
- mobile plot width is 176 of 220 SVG units (80%), up from 138 of 208 (66%) on
  asset `9.249.0` — 27.5% more plot width with no global-rail redesign; and
- desktop plot width is 1011 of 1181 SVG units with a stable 112px right reserve.

This evidence supplements the earlier SI-P2C discovery, functional, and visual
closure folders; it does not change their historical asset attribution.
