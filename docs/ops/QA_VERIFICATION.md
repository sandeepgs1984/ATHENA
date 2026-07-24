# ATHENA — QA Verification Runbook

Repeatable verification procedure for changes to ATHENA. Run commands from the
repository root.

## 1. Prepare the test environment

ATHENA supports Python 3.10 or newer. Install the project and development
dependencies once:

```bash
python3 -m pip install -e '.[dev]'
```

Record the runtime used for the evidence:

```bash
python3 --version
```

Do not place production credentials or database files in test fixtures. Tests
must use temporary databases, fixture providers, and isolated configuration.

## 2. Run the full regression suite

Canonical command:

```bash
PYTHONPATH=src python3 -m pytest -q
```

Acceptance criteria:

- Pytest exits with code `0`.
- Every collected test passes.
- There are no failures, errors, hangs, or unexpected skips.
- The pass count matches the current baseline, unless the change deliberately
  adds or removes tests and the implementation summary explains why.

Verified baseline on 2026-07-24:

```text
976 passed, 127 warnings in 9.53s
```

Environment: macOS Darwin 25.2.0, Python 3.14.6.

Warnings do not fail the current suite. The 127-warning baseline consists of
known dependency/test-configuration warnings:

- Starlette deprecation warning for the current TestClient/httpx integration.
- PyJWT warning for the short development-only signing key used by API tests.
- Starlette rename warning for HTTP 422 constants.

Treat any new warning category or increased warning count as a regression to
investigate; do not automatically accept it because the suite exits successfully.

## 3. Run high-risk targeted suites

### File-backed daily operations

```bash
PYTHONPATH=src python3 -m pytest \
  tests/ops/test_file_backed_daily_smoke.py -q --tb=short
```

Expected result: `3 passed`.

The R1 smoke test:

- creates a temporary config/database workspace;
- forces the FileProvider fixture;
- disables live Nifty 500 candidate seeding;
- seeds only fixture candidates `AAA` and `BBB`;
- runs health, due checks, refresh cycle, briefing, and diagnostics;
- removes its temporary workspace on exit.

This isolation is mandatory. A smoke run must never depend on internet
availability or mutate the owner's live candidate list/database.

### Authentication and workstation hosting

```bash
PYTHONPATH=src python3 -m pytest \
  tests/api/v1/test_login_limiter.py \
  tests/api/v1/test_auth_routes.py \
  tests/api/v1/test_security.py \
  tests/ops/test_serve_runtime.py \
  -q --tb=short
```

Expected result: `33 passed`.

This verifies owner unlock, token rotation/logout, login lockout, JWT secret
resolution, serve runtime state, due-cycle worker behavior, and runner locking.

## 4. Validate changed runtime files

Run Ruff against every Python file touched by the change:

```bash
PYTHONPATH=src python3 -m ruff check <changed-python-files>
```

Acceptance criterion: `All checks passed!`

Repository-wide Ruff currently has pre-existing findings recorded in
`IMPLEMENTATION_SUMMARY.md`. Until that debt is addressed in its own approved
change set, changed files must remain clean and must not increase the baseline.

For launcher or shell changes:

```bash
bash -n \
  athena-daily athena-run-due athena-serve install-athena-app \
  scripts/bash_load_dotenv.sh \
  scripts/macos/install-athena-app.sh \
  packaging/macos/ATHENA.app/Contents/MacOS/ATHENA

plutil -lint packaging/macos/ATHENA.app/Contents/Info.plist
```

Acceptance criteria: shell syntax exits successfully and plist output is `OK`.

## 5. Complete workstation acceptance checks

After automated QA passes, complete the manual smoke checklist in
[`LIVE_ENTRY.md`](LIVE_ENTRY.md):

- Dock launch and existing-server reuse;
- owner unlock, profile, and logout;
- Kite clear/reconnect gate;
- LIVE/cycle health state;
- startup log inspection.

Automated tests do not replace these browser and broker-session checks.

## 6. Investigate a failure

Rerun only the failed test with full diagnostics:

```bash
PYTHONPATH=src python3 -m pytest \
  path/to/test_file.py::test_name -vv --tb=long -s
```

Useful follow-ups:

```bash
# Rerun the failures from the previous pytest session
PYTHONPATH=src python3 -m pytest --lf -vv --tb=long

# Execute the R1 smoke directly for complete step output
./scripts/smoke_file_backed_day.sh
```

Classify the failure before changing code:

- Product regression: implementation violates an approved contract.
- Test-isolation defect: test inherits live config, network, credentials, time,
  or owner data.
- Environment/dependency issue: interpreter or dependency behavior differs.
- Expected contract change: update implementation, tests, and governing
  documentation together after approval.

Never weaken assertions merely to make a failing suite green.

## 7. Record QA evidence

Add the following evidence to `IMPLEMENTATION_SUMMARY.md` for each milestone:

- verification date and environment;
- exact commands executed;
- pass/fail counts and duration;
- warning count and whether categories changed;
- targeted suite results;
- lint/type/shell/plist results as applicable;
- manual acceptance checks performed;
- failures found, root cause, and corrective action;
- coverage summary;
- final ready-for-review status.

Do not mark a milestone complete while any required check is failing.
