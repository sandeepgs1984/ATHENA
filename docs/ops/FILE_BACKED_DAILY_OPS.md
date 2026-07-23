# File-backed Daily Ops SOP (R1)

**Audience:** Owner running ATHENA as **daily advisory** support while market data still comes from **FileProvider** (DD-1 live vendor not bound).

**Non-negotiables**
- ATHENA never places orders — you execute at the broker.
- Secrets stay in `.env` only.
- Bad/stale files must fail loudly (quarantine / cycle FAILED) — do not “force through.”

**Related:** `docs/PRODUCTION_READINESS_ROADMAP.md` · Phase 10 CLIs · `config/providers/file.json`

---

## 0. Prerequisites (once)

1. Install the package so `athena` is on `PATH` (`pip install -e .` from repo root).
2. Confirm calendar/config load: `athena today` and `athena health`.
3. Know your paths:
   - Config: `ATHENA_CONFIG_DIR` (default `config/`)
   - DB: `ATHENA_DB_PATH` or `config/base.json` → `paths.db` (default `db/athena.db`)
   - Market files: `config/providers/file.json` → `data_root` (default `data/` under repo root)
4. Optional dashboard: start the API host per README/ops notes; open the workstation console for review after cycles.

---

## 1. Refresh FileProvider data (every session)

Update files under `data_root` **before** ingest/cycle. Expected layout (see FileProvider docstring):

| Artifact | Path pattern |
|---|---|
| Instruments | `{data_root}/{instruments_file}` CSV |
| Daily candles | `{data_root}/{daily_dir}/{instrument_id}.csv` |
| Intraday | `{data_root}/{intraday_dir}/{1m\|5m\|15m}/{instrument_id}.csv` |
| Quotes | `{data_root}/{quotes_file}` CSV |
| Snapshot | `{data_root}/{snapshot_file}` JSON |

**Freshness tips (IST)**
- Premarket (~08:15): overnight **daily** bars should include the prior session; quotes may still be EOD — expect freshness failures if you force a quote-heavy cycle too early unless files match `as_of`.
- Intraday refresh: quotes + latest 5m bars must be within `config/validation.json` intraday freshness (default 20 minutes behind `as_of`).

Until DD-1, refreshing these files is **your** job (broker export, vendor dump, or a personal downloader **outside** this repo’s placement ban).

---

## 2. Trading-day command sequence

Use timezone-aware ISO times (`+05:30`). Omit `--as-of` only when wall clock matches the market session you intend.

### Premarket (~08:15–09:00 IST)

```bash
athena health --date YYYY-MM-DD
athena due --as-of "YYYY-MM-DDT08:20:00+05:30"
athena cycle --trigger premarket --as-of "YYYY-MM-DDT08:20:00+05:30"
```

### Intraday refresh (every N minutes while session open)

`N` = `config/base.json` → `refresh_interval_minutes` (default 15), unless overridden in `config/scheduling.json`.

```bash
athena due --as-of "YYYY-MM-DDTHH:MM:00+05:30"
athena cycle --trigger refresh --as-of "YYYY-MM-DDTHH:MM:00+05:30"
```

### After a successful cycle

```bash
athena brief --as-of "YYYY-MM-DDTHH:MM:00+05:30" --dry-run
athena diagnose --as-of "YYYY-MM-DDTHH:MM:00+05:30" --dry-run
```

- Briefings write under `artifacts/briefings/`. With R2, persisted decisions make status **OK**; without decisions the briefing is **DEGRADED** (`no_decision_summaries`).
- Diagnostics write under `artifacts/diagnostics/` (propose-only; never auto-applies config).

### Human action

1. Read briefing text/JSON and/or dashboard Overview / Decisions / Operations.
2. Decide at the broker yourself.
3. Optional: record journal notes offline until R2 persists them.

### Ops hygiene (recommended daily/weekly)

- Operations tab: create SQLite backup before risky restores.
- After failures: check quarantine / `runs` status; fix data; re-run cycle — do not delete evidence blindly.

---

## 3. Smoke checklist (fixture mock day)

Run from **repo root** (uses `tests/data/fileprovider` + temp DB/config — does not touch production `db/`):

```bash
./scripts/smoke_file_backed_day.sh
```

Or via pytest:

```bash
python -m pytest tests/ops/test_file_backed_daily_smoke.py -q
```

**Pass criteria**
- [ ] `athena health` exits 0 for fixture date
- [ ] `athena due` reports PREMARKET in the 08:20 window
- [ ] `athena due` reports REFRESH in the session window
- [ ] `athena cycle --trigger refresh` completes with fixture-aligned `--as-of`
- [ ] Seeded/persisted decision present (R2) so briefing is not chronically DEGRADED
- [ ] `athena brief --dry-run` writes a briefing artifact with **status OK** when decisions exist
- [ ] `athena diagnose --dry-run` writes a diagnostics artifact
- [ ] Script exits 0

---

## 4. Failure playbook (loud failures are correct)

| Symptom | Likely cause | Action |
|---|---|---|
| `DataStaleError` / cycle FAILED | Files older than freshness budget vs `--as-of` | Refresh CSVs/quotes; align `as_of`; re-run |
| `DataValidationError` / quarantine | Bad OHLC, duplicates | Fix source file; inspect quarantine; re-run |
| Briefing `no runs found` | No cycle yet that day | Run `athena cycle` first |
| Briefing DEGRADED `no_decision_summaries` | Expected until R2 | Use runs section; do not ignore data failures |
| `due: (none)` | Outside premarket/refresh windows or already ran | Check IST time + last run in DB |

---

## 5. Explicit non-goals (R1)

- Live broker/API ingest (R3/R4)
- launchd/cron packaging (R5)
- Decision journal SQLite persistence (R2)
- Order placement (never)
