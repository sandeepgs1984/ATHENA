# ATHENA — Kite Connect runbook (live market data)

**Purpose:** Step-by-step reference for using Zerodha Kite as ATHENA’s live `MarketDataProvider` (R4 / DD-1).

**Non-goals:** Order placement · websockets (DD-2) · deep multi-year 5m history (DD-10).

**Default mode:** Keep `config/ingestion.json` → `"provider": "file"` unless you intentionally run live Kite.

---

## 0. One-time setup (do once)

### 0.1 Zerodha + Kite Connect app

1. You need an active **Zerodha trading account** (Client ID = your Kite login id, e.g. `AB1234`).
2. Open [developers.kite.trade](https://developers.kite.trade) → **Create app**.
3. Choose type **Connect** (paid; Personal has **no** historical/quotes).
4. Fill:
   - **App name:** e.g. `ATHENA`
   - **Zerodha Client ID:** your login id exactly, **no spaces**
   - **Redirect URL:** `http://127.0.0.1`
   - **Postback URL:** leave empty (ATHENA does not place orders)
   - **Description:** e.g. `Personal read-only market data for ATHENA`
5. After create, copy **API key** and **API secret**.

If login later says *“The user is not enabled for the app”*: Client ID mismatch or browser logged into a different Zerodha account. Fix Client ID / use the matching login (incognito helps).

### 0.2 Secrets file

From the **repo root**:

```bash
cp .env.example .env
```

Edit `.env` (never commit this file):

```bash
KITE_API_KEY=your_api_key
KITE_API_SECRET=your_api_secret
KITE_ACCESS_TOKEN=   # filled every trading day — see §1
```

Confirm git ignores it:

```bash
git check-ignore -v .env
```

### 0.3 How to run the ATHENA CLI

On some machines `athena` is a **shell alias** that only `cd`s into the repo — that is **not** the CLI.

**Preferred (always works):**

```bash
cd "/path/to/ATHENA"
PYTHONPATH=src python3 -m athena.cli version
```

You should see `athena 0.1.0 (...)`.

Optional later: `unalias athena` and `pip3 install -e .` so bare `athena` works.

---

## 1. Daily: get a fresh access token

Kite **access tokens expire ~06:00 IST** next day. Do this before live ingest each trading day.

### 1.0 Recommended — root helper script

From the **repo root**:

```bash
./kite-auth
```

Same thing via module CLI:

```bash
PYTHONPATH=src python3 -m athena.cli kite-auth
```

What it does:

1. Asks for `KITE_API_KEY` / `KITE_API_SECRET` (Enter keeps values already in `.env`)
2. Opens the Kite login URL (or print-only with `--no-browser`)
3. You Authorize in the browser
4. You paste the redirect URL (or `request_token`) when prompted  
   — **or** use auto-capture: `./kite-auth --listen 8765` after setting Kite Redirect URL to `http://127.0.0.1:8765`
5. Exchanges the token (form POST) and writes `KITE_ACCESS_TOKEN` into `.env`
6. **Re-injects** those values into the process from `.env` (overwrites any stale env)
7. **Verifies** with an authenticated Kite `GET /user/profile` — prints `VERIFY OK` or fails loudly

Optional: refresh token **and** ingest in one go (requires `ingestion.provider` = `kite`):

```bash
./kite-auth --ingest
./kite-auth --ingest --as-of 2026-07-23T15:30:00+05:30   # after hours
./kite-auth --skip-verify   # only if you must skip the profile check
```

### 1.1 Manual login (browser) — if you prefer not to use the script

1. Open (replace with your real API key):

   ```text
   https://kite.zerodha.com/connect/login?v=3&api_key=YOUR_API_KEY
   ```

2. Log in with the **same** Zerodha Client ID as the app → tap **Authorize**.

3. Browser goes to `127.0.0.1` and may show **“This site can’t be reached”**.  
   **That is OK.** Nothing needs to run on localhost.

4. Look at the **address bar**. You want:

   ```text
   http://127.0.0.1/?action=login&type=login&status=success&request_token=XXXXXXXX
   ```

5. Copy the `request_token` value only (expires in a few minutes; one-time use).

### 1.2 Manual exchange (only if not using `./kite-auth`)

Use **form-urlencoded** POST (not JSON). Replace the three placeholders, then run immediately:

```bash
python3 <<'PY'
import hashlib, json, urllib.error, urllib.parse, urllib.request

api_key = "YOUR_API_KEY"
api_secret = "YOUR_API_SECRET"
request_token = "PASTE_NEW_REQUEST_TOKEN"

checksum = hashlib.sha256(f"{api_key}{request_token}{api_secret}".encode()).hexdigest()
body = urllib.parse.urlencode({
    "api_key": api_key,
    "request_token": request_token,
    "checksum": checksum,
}).encode()

req = urllib.request.Request(
    "https://api.kite.trade/session/token",
    data=body,
    headers={
        "X-Kite-Version": "3",
        "Content-Type": "application/x-www-form-urlencoded",
    },
    method="POST",
)
try:
    with urllib.request.urlopen(req) as resp:
        data = json.load(resp)
    print(data["data"]["access_token"])
except urllib.error.HTTPError as e:
    print(e.read().decode())
PY
```

Success = a long token string printed (no error JSON).

### 1.3 Save token (manual path only)

Put it in `.env`:

```bash
KITE_ACCESS_TOKEN=paste_access_token_here
```

Rules:

- No spaces around `=`
- Do **not** store `request_token` as the access token
- Token must belong to **this** `KITE_API_KEY`

---

## 2. Configure ATHENA for a live ingest

### 2.1 Universe — `config/providers/kite.json`

Keep the list small for smoke / early use:

```json
"symbols": ["INFY"]
```

Empty `symbols: []` means “all NSE EQ” — heavy; avoid until you mean it.

Instrument ids everywhere else are **`NSE:SYMBOL`** (e.g. `NSE:INFY`).

### 2.2 Ingest switch — `config/ingestion.json`

For live:

```json
"provider": "kite",
"timeframes": ["5m"],
"lookback_minutes": 30,
"lookback_days": 5,
"include_daily": true,
"include_quotes": true,
"instrument_ids": ["NSE:INFY"]
```

For normal / file-backed / CI default:

```json
"provider": "file",
"instrument_ids": []
```

---

## 3. Run live ingest

From repo root, with `.env` filled:

### During market hours

```bash
PYTHONPATH=src python3 -m athena.cli ingest
```

### After market hours (or freshness errors)

Quotes are stamped near the last trade. If you run at night, “now” looks stale vs the 20‑minute freshness budget.

Pin `as_of` near the session close (IST):

```bash
PYTHONPATH=src python3 -m athena.cli ingest --as-of 2026-07-23T15:30:00+05:30
```

(Use the actual calendar trading day you care about.)

### Success looks like

```text
ingest complete @ 2026-07-23T15:30:00+05:30
instruments     : 1
candles fetched : 10  written: 10
quotes fetched  : 1  written: 1
datasets ok     : 3  empty skipped: 0
```

### After you’re done

Set `"provider": "file"` again in `config/ingestion.json` unless you intend to stay on Kite.

---

## 4. Quick checklist (print / bookmark)

| # | Step | Done? |
|---|---|---|
| 1 | Fresh `KITE_ACCESS_TOKEN` via `./kite-auth` (or §1 manual) | ☐ |
| 2 | `kite.json` → `symbols` set | ☐ |
| 3 | `ingestion.json` → `"provider": "kite"` + `instrument_ids` | ☐ |
| 4 | `PYTHONPATH=src python3 -m athena.cli ingest` (+ `--as-of` if after hours) | ☐ |
| 5 | Flip `"provider": "file"` when finished | ☐ |

---

## 5. Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| `athena ingest` prints nothing | Shell alias `athena` = `cd` only | Use `./kite-auth` / `PYTHONPATH=src python3 -m athena.cli …` |
| `KITE_ACCESS_TOKEN is missing` | Not in `.env` / empty | Add token (§1) |
| `Incorrect api_key or access_token` (403) | Expired/wrong token, or token for another app | New login + exchange; match API key |
| `The user is not enabled for the app` | Client ID / wrong Zerodha login | Fix app Client ID; same account; incognito |
| Chrome “127.0.0.1 refused to connect” after Authorize | Expected with redirect `http://127.0.0.1` | Copy `request_token` from URL bar |
| Token exchange HTTP 400 | Posted JSON, or reused/expired `request_token` | Use form POST script (§1.2); new Authorize |
| `quotes are N min behind as_of` | After-hours with `as_of=now` | Pass `--as-of …T15:30:00+05:30` |
| `kite symbols not found` | Bad tradingsymbol | Fix `symbols` / try another NSE EQ |

---

## 6. Security reminders

- Secrets only in `.env` — never in JSON config, never in git, never in chat/screenshots when avoidable.
- ATHENA’s Kite HTTP client is **GET-only** on `/instruments*` and `/quote*` — no order APIs.
- If a key/secret was pasted into chat or a ticket, regenerate API secret in the developer console and update `.env`.

---

## 7. Related docs

| Doc | Role |
|---|---|
| [DD-1 decision](../decisions/DD-1-broker-live-data-vendor.md) | Why Kite |
| [ADR-002](../adr/ADR-002-broker-abstraction.md) | Provider abstraction |
| [File-backed daily ops](FILE_BACKED_DAILY_OPS.md) | Non-Kite daily path |
| [Production readiness](../PRODUCTION_READINESS_ROADMAP.md) | R4 / R5 context |
