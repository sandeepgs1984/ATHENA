#!/usr/bin/env bash
# R1 smoke: mock file-backed trading day on tests/data/fileprovider fixtures.
# Does not touch production db/ or data/. Safe to run from CI/local.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
export PYTHONPATH="${ROOT}/src${PYTHONPATH:+:$PYTHONPATH}"

if command -v athena >/dev/null 2>&1; then
  run_athena() { athena "$@"; }
else
  run_athena() {
    python3 -c "import sys; from athena.cli import main; raise SystemExit(main(sys.argv[1:]))" "$@"
  }
fi

TMP="$(mktemp -d "${TMPDIR:-/tmp}/athena-r1-smoke.XXXXXX")"
cleanup() { rm -rf "$TMP"; }
trap cleanup EXIT

echo "==> R1 smoke workspace: $TMP"

cp -R "$ROOT/config" "$TMP/config"
python3 - <<PY
import json
from pathlib import Path
root = Path("$ROOT")
cfg_path = Path("$TMP/config/providers/file.json")
data = json.loads(cfg_path.read_text(encoding="utf-8"))
data["data_root"] = str(root / "tests/data/fileprovider")
cfg_path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
# Keep briefings/diagnostics inside the temp tree.
notify = Path("$TMP/config/notifications.json")
n = json.loads(notify.read_text(encoding="utf-8"))
n["channels"]["file"]["output_dir"] = str(Path("$TMP") / "artifacts/briefings")
notify.write_text(json.dumps(n, indent=2) + "\n", encoding="utf-8")
diag = Path("$TMP/config/diagnostics.json")
d = json.loads(diag.read_text(encoding="utf-8"))
d["output_dir"] = str(Path("$TMP") / "artifacts/diagnostics")
diag.write_text(json.dumps(d, indent=2) + "\n", encoding="utf-8")
PY

export ATHENA_CONFIG_DIR="$TMP/config"
export ATHENA_DB_PATH="$TMP/athena.db"

PREMARKET_AS_OF="2026-02-13T08:20:00+05:30"
# Session close is 15:30 exclusive for refresh due-ness; keep inside the open interval.
REFRESH_AS_OF="2026-02-13T15:25:00+05:30"
FIXTURE_DATE="2026-02-13"

echo "==> [1/6] athena health"
run_athena health --date "$FIXTURE_DATE"

echo "==> [2/6] athena due (premarket window)"
DUE_PRE="$(run_athena due --as-of "$PREMARKET_AS_OF")"
echo "$DUE_PRE"
echo "$DUE_PRE" | grep -q "PREMARKET"

echo "==> [3/6] athena due (refresh window)"
DUE_REF="$(run_athena due --as-of "$REFRESH_AS_OF")"
echo "$DUE_REF"
echo "$DUE_REF" | grep -q "REFRESH"

echo "==> [4/6] athena cycle --trigger refresh (fixture-aligned as_of)"
run_athena cycle --trigger refresh --as-of "$REFRESH_AS_OF"

echo "==> [5/6] athena brief --dry-run"
run_athena brief --as-of "$REFRESH_AS_OF" --dry-run
test -f "$TMP/artifacts/briefings/brief-2026-02-13.json"
test -f "$TMP/artifacts/briefings/brief-2026-02-13.txt"

echo "==> [6/6] athena diagnose --dry-run"
run_athena diagnose --as-of "$REFRESH_AS_OF" --dry-run
test -f "$TMP/artifacts/diagnostics/diag-2026-02-13.json"
test -f "$TMP/artifacts/diagnostics/diag-2026-02-13.txt"
echo
echo "R1 smoke checklist: PASS"
echo "  SOP: docs/ops/FILE_BACKED_DAILY_OPS.md"
