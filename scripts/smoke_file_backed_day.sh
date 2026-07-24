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
# This smoke is explicitly file-backed; do not inherit the owner's live provider.
ingestion = Path("$TMP/config/ingestion.json")
i = json.loads(ingestion.read_text(encoding="utf-8"))
i["provider"] = "file"
ingestion.write_text(json.dumps(i, indent=2) + "\n", encoding="utf-8")
# Fixture catalog is SYN-AAA/SYN-BBB only — never pull live Nifty 500 into smoke.
seed = Path("$TMP/config/candidate_seed.json")
s = json.loads(seed.read_text(encoding="utf-8"))
s["source"] = "none"
seed.write_text(json.dumps(s, indent=2) + "\n", encoding="utf-8")
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

echo "==> [3b] seed fixture owner candidates (AAA / BBB)"
PYTHONPATH="${ROOT}/src" python3 - <<PY
from athena.data.store import SqliteRepository
from athena.ops.owner_candidates import SqliteCandidateStore

with SqliteRepository("$ATHENA_DB_PATH") as repo:
    repo.initialize()
    store = SqliteCandidateStore(repo)
    for sym in ("AAA", "BBB"):
        store.upsert_candidate(symbol=sym, notes="r1-smoke-fixture", active=True)
print("seeded owner candidates: AAA BBB")
PY

echo "==> [4/6] athena cycle --trigger refresh (fixture-aligned as_of)"
run_athena cycle --trigger refresh --as-of "$REFRESH_AS_OF"

echo "==> [4b] seed advisory decision into SQLite (R2 — until live cycle emits decisions)"
PYTHONPATH="${ROOT}/src" python3 - <<PY
from datetime import datetime
from zoneinfo import ZoneInfo
from athena.data.store import SqliteRepository
from athena.domain.decision import Decision, DecisionTrace, TraceStage
from athena.domain.enums import DecisionType, Direction

IST = ZoneInfo("Asia/Kolkata")
as_of = datetime.fromisoformat("$REFRESH_AS_OF")
decision = Decision(
    decision_id="smoke-watch-1",
    ts=as_of,
    run_id="smoke",
    cycle_id="smoke",
    decision_type=DecisionType.WATCH,
    explanation="R2 smoke advisory WATCH on SYN-AAA",
    instrument_id="SYN-AAA",
    direction=Direction.NONE,
)
trace = DecisionTrace(
    decision_ref="smoke-watch-1",
    stages=(TraceStage("decision", ("smoke-watch-1",), "fixture watch"),),
)
with SqliteRepository("$ATHENA_DB_PATH") as repo:
    repo.initialize()
    repo.save_decision(decision, trace=trace)
print("seeded decision smoke-watch-1")
PY

echo "==> [5/6] athena brief --dry-run"
run_athena brief --as-of "$REFRESH_AS_OF" --dry-run
test -f "$TMP/artifacts/briefings/brief-2026-02-13.json"
test -f "$TMP/artifacts/briefings/brief-2026-02-13.txt"
grep -q '"status": "OK"' "$TMP/artifacts/briefings/brief-2026-02-13.json"

echo "==> [6/6] athena diagnose --dry-run"
run_athena diagnose --as-of "$REFRESH_AS_OF" --dry-run
test -f "$TMP/artifacts/diagnostics/diag-2026-02-13.json"
test -f "$TMP/artifacts/diagnostics/diag-2026-02-13.txt"
echo
echo "R1 smoke checklist: PASS"
echo "  SOP: docs/ops/FILE_BACKED_DAILY_OPS.md"
