# ATHENA — Host schedule + failure alerts (R5)

**Purpose:** Run due premarket/refresh cycles unattended via **launchd** or **cron**, and notify on hard failures (DD-9: webhook + file).

**Non-goals:** Embedded production cron replacing launchd · SMTP email · order placement · auto Kite login (still use `./kite-auth` when `provider=kite`).

**Interactive complement (M-E2):** while you are at the desk, prefer:

```bash
./athena-serve --with-cycles --open
# or: PYTHONPATH=src python3 -m athena.cli serve --with-cycles --open
```

That starts the API + optional in-process due poller. launchd/`./athena-run-due` stays for unattended daytime ticks. Both paths share `artifacts/locks/cycle-runner.lock` so they do not overlap.

### macOS Dock launcher (M-E4)

Install the thin native wrapper once:

```bash
./install-athena-app
```

This creates `~/Applications/ATHENA.app` and reveals it in Finder. Drag it to
the Dock. Afterwards:

1. Click **ATHENA** in the Dock.
2. If the API is already healthy, the dashboard opens immediately.
3. Otherwise the app starts `./athena-serve --with-cycles`, waits for health,
   then opens `http://127.0.0.1:8000/dashboard/`.
4. Unlock ATHENA; connect Kite if the dashboard requests it.

The wrapper is intentionally only a macOS app bundle with a shell executable;
it does not introduce Tauri, Qt, Electron, or another UI runtime (ADR-004).
Secrets remain in the repository `.env`; the app stores only the absolute
repository path.

Logs: `artifacts/logs/athena-serve.log`. If the repository moves, rerun
`./install-athena-app`. Re-running the installer safely refreshes the app.

Optional system-wide destination (may require administrator permission):

```bash
./install-athena-app --destination "/Applications/ATHENA.app"
```

---

## 1. What `run-due` does

```bash
./athena-daily              # normal day: seed (if due) + run-due
./athena-daily smoke        # first-time proof on 10 symbols
./athena-daily status
```

Also: `./athena-run-due` (same run-due core; prefer `./athena-daily` for owner daily use).

1. Load `.env` (wrapper script sources it for launchd’s bare environment).
2. Evaluate cadence (`athena due` logic): which of PREMARKET / REFRESH / **CLOSING** are due *now*.
3. If none due → exit 0 (`idle`) — safe to poll every 15 minutes.
4. If due → run those cycles (ingest + run ledger).
5. If `host_ops.brief_after_cycles` → run briefing dispatch (includes **day summary** + **journal prompts**).
6. On hard failure → write `artifacts/alerts/…` and POST webhook (if configured), then exit non-zero.

Config: `config/host_ops.json` · cadence: `config/scheduling.json` (`closing.run_at`, default 15:45 IST).

### Closing cycle (R6)

Once per day after session close and `closing.run_at`:

```bash
PYTHONPATH=src python3 -m athena.cli due --as-of 2026-07-23T15:50:00+05:30
# expect: CLOSING when not yet run today

PYTHONPATH=src python3 -m athena.cli cycle --trigger closing --as-of 2026-07-23T15:50:00+05:30
PYTHONPATH=src python3 -m athena.cli brief --as-of 2026-07-23T15:50:00+05:30 --dry-run
```

Briefing text includes **Day summary** (run/decision roll-up) and **Journal prompts** for decisions still missing a journal action.
---

## 2. Failure alerts (DD-9 for R5)

| Channel | How |
|---|---|
| **File** (default on) | `artifacts/alerts/alert-*.json` + `.txt` |
| **Webhook** (default on) | `ATHENA_ALERT_WEBHOOK_URL` if set, else `ATHENA_WEBHOOK_URL` |

Email SMTP remains deferred (same as M10.3). Webhook + file advances DD-9 for single-user workstation ops.

Test a fake failure alert path by pointing webhook at [https://webhook.site](https://webhook.site) (or similar) in `.env`, then temporarily break ingest and run `./athena-run-due` during market hours — or call the dispatcher in tests (CI covers file + webhook mock).

---

## 3. macOS launchd (recommended)

### 3.1 Copy and edit the plist

Example template: [`docs/ops/launchd/com.athena.run-due.plist.example`](launchd/com.athena.run-due.plist.example)

1. Copy to `~/Library/LaunchAgents/com.athena.run-due.plist`
2. Replace `REPO_ROOT` with your absolute ATHENA path (spaces OK if XML-escaped carefully; prefer a path without spaces if possible).
3. Ensure `python3` path matches `which python3` on your Mac.

### 3.2 Load

```bash
launchctl unload ~/Library/LaunchAgents/com.athena.run-due.plist 2>/dev/null || true
launchctl load ~/Library/LaunchAgents/com.athena.run-due.plist
launchctl start com.athena.run-due
```

Logs (if configured in plist): `artifacts/logs/run-due.stdout.log` / `.stderr.log`.

### 3.3 Cadence note

The example uses **StartInterval = 900** (15 minutes). ATHENA itself decides whether a cycle is due; most ticks will be `idle`.

---

## 4. cron alternative

```cron
*/15 8-15 * * 1-5 cd /path/to/ATHENA && ./athena-run-due >> artifacts/logs/run-due.cron.log 2>&1
```

(Adjust hours to IST / your shell’s timezone.)

---

## 5. Live Kite vs file

| Provider | Unattended note |
|---|---|
| `file` | Refresh CSVs before the day (R1 SOP); launchd can run all day |
| `kite` | Access token dies ~06:00 IST — run `./kite-auth` each morning **before** trusting live `run-due` |

Keep `"provider": "file"` as default unless you intentionally run live.

---

## 6. Checklist

| Step | Done? |
|---|---|
| `config/host_ops.json` reviewed | ☐ |
| `.env` has alert webhook (optional but recommended) | ☐ |
| `./athena-run-due` works manually once | ☐ |
| launchd plist installed **or** cron line added | ☐ |
| Forced failure produces a file under `artifacts/alerts/` | ☐ |

---

## 7. Related

- Cadence: `config/scheduling.json` + `athena due`
- Kite daily auth: `docs/ops/KITE_LIVE_DATA.md` + `./kite-auth`
- File-backed day: `docs/ops/FILE_BACKED_DAILY_OPS.md`
- Roadmap: `docs/PRODUCTION_READINESS_ROADMAP.md` R5
