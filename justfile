# ATHENA task runner. Requires: just, python3 (>=3.10), pip/uv.

# Run all tests
test:
    python3 -m pytest -q

# Lint + type check (dev extras required)
check:
    python3 -m ruff check src tests
    python3 -m mypy

# Show today's calendar context
today:
    PYTHONPATH=src python3 -m athena.cli today

# Run system health pre-flight
health:
    PYTHONPATH=src python3 -m athena.cli health

# Back up the SQLite database (Phase 1 populates it)
backup:
    mkdir -p db/backups
    test -f db/athena.db && sqlite3 db/athena.db ".backup db/backups/athena-$(date +%Y%m%d).db" || echo "no db yet"
