# MP-RV7: Browser Validation and Hardening

Owner authorized 2026-09-13. Status: implemented; Owner review required.

## Scope

Close the browser-validation gaps recorded by MP-RV6 using the real HTML,
stylesheet imports and assembled dashboard JavaScript. Exercise populated
holdings, sticky navigation, filter scroll behavior, privacy, detail reopening,
upload preview and sync blocking. Use isolated synthetic API responses only;
never read credentials, contact Kite or mutate the owner's portfolio.

Per ATHENA-002 report boundaries and ADR-004, changes remain presentation-only.
No analysis, schema, interpretation, persisted financial data or API changes.

## Acceptance

- Chromium runs at 390, 768, 1280 and 1920 CSS pixels; also a 640-pixel layout
  with doubled text size as a text-zoom stress test (not browser zoom parity).
- Zero uncaught JavaScript errors and zero unmocked API requests.
- No document horizontal overflow; wide holdings stay in their table scroller.
- Initial summary is unobscured; sticky chrome remains inside its scrollport.
- Filters do not jump (maximum 16 CSS pixels for native layout/scroll anchoring);
  explicit View Holdings navigates.
- Private values are masked in summary, holdings and detail.
- Detail opens at scroll position zero, including after closing/reopening.
- Preview opens automatically; sync blocker covers the viewport, including
  while scrolled, and is removed on completion or a reported terminal failure.
- Run full pytest and scoped lint; disclose any existing failures separately.

## Review Gate

Record reproducible findings, fixes, screenshots, test totals and residual
limitations here and in IMPLEMENTATION_SUMMARY.md. Stop for Owner review;
do not start another milestone or perform git operations.

## Findings and Corrections

- Expanded desktop sidebar left almost no content width at 390px. A
  Portfolio-only responsive rail now takes 64px below 920px without changing
  the saved desktop collapse preference or other tabs.
- Stacked sticky toolbars intercepted table clicks with enlarged text. Below
  920px the toolbars flow with content; the column-heading dock remains sticky
  at top zero. Desktop sticky geometry is untouched.
- Export extended beyond the viewport when anchored to its small trigger,
  including at 1280px. It is now viewport-positioned, height-limited and
  scrollable, with an explicit close button restoring focus to the trigger.
- Actual detail reset behavior passed after the scheduled animation frame;
  no detail-scroll code change was necessary.

## Verification and Reproduction

`tests/browser/portfolio-validation.cjs` loads the production HTML, CSS and
the exact JS part list from app.py. Forty-eight synthetic holdings contain
positive/negative values, mixed status and a long symbol. Every HTTP request
is intercepted; unexpected API requests fail the run. No local service,
credentials, financial data or live broker is used.

Install Playwright in your test environment and have Chrome available. Run
`rtk proxy node tests/browser/portfolio-validation.cjs`; NODE_PATH can point
to an existing Playwright installation. PLAYWRIGHT_CHANNEL selects another
installed Chromium channel. PORTFOLIO_UI_ARTIFACTS selects screenshot output
(default `/tmp/athena-rv7`). The pytest wrapper is opt-in with
ATHENA_BROWSER_TESTS=1 and fails loudly if dependencies are absent.

Browser gate: **5/5 configurations passed**, zero uncaught JS errors and zero
unexpected API requests. Configurations: 390, 768, 1280, 1920 pixels plus 640 pixels with
200% root text size. Assertions cover initial summary hit testing, populated
filters without scroll jumps, profiles, desktop sticky position, risk/heatmap
disclosure, privacy, detail reopen, reset confirmation lock, export bounds
and dismissal, automatic upload preview, viewport-sized sync blocking and
terminal success/failure dismissal. Screenshot artifacts are synthetic only.

Full pytest: **4022 passed, 1 skipped, 1 pre-existing failure**, 126.22s.
The skipped opt-in browser wrapper is executed separately as the Node gate.
Existing failure: `tests/ops/test_macos_launcher.py::test_installer_builds_configured_app_bundle`
at installer line 63. Scoped Ruff and Node syntax checks pass. No claim of
an all-green full suite; Owner review must retain this exception.

## Boundaries and Remaining Validation

External font/icon requests are deliberately blocked, so screenshots use
fallback fonts and do not prove CDN availability or exact reference typography.
This is Chromium layout and interaction evidence, not authenticated live
browser, Safari, physical-device, native browser-zoom or screen-reader parity.
No real export download, destructive reset or import confirmation is performed.
Synthetic review evidence does not validate analytical correctness. No new
APIs, methodology, schemas, financial calculations, dependencies or ADRs.
Remaining work: Owner review and optional cross-browser/live visual sign-off.
