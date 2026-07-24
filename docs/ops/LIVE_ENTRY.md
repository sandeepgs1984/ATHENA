# ATHENA — Professional Live Entry

Operational runbook for the approved workstation path:

**Dock/URL → ATHENA unlock → Kite when needed → LIVE**

ATHENA remains localhost-only and advisory. It never places orders.

## Daily path

Preferred:

1. Click **ATHENA** in the macOS Dock.
2. Unlock with the owner username/password.
3. If shown, use the Kite panel to authorize the daily read-only session.
4. Confirm the header shows **KITE · connected** and **LIVE ENGINE ACTIVE**
   (or **API UP · MANUAL CYCLES** if the cycle worker was intentionally disabled).

Terminal fallback:

```bash
./athena-serve --with-cycles --open
```

No manual `PYTHONPATH`, `uvicorn`, or `DYLD_LIBRARY_PATH` command is required
for normal use.

## One-time setup

```bash
# Owner unlock hash (paste the printed values into .env)
./athena-daily set-owner-password --username owner

# Thin macOS app
./install-athena-app
```

Drag `~/Applications/ATHENA.app` to the Dock. Rerun the installer if the
repository moves.

## Security behavior

- Owner password is stored only as a bcrypt hash in `.env`.
- JWT signing uses `ATHENA_JWT_SECRET` when provided; otherwise a stable,
  non-default secret is derived from the owner bcrypt hash.
- Five failed unlocks within ten minutes lock that username/client for fifteen
  minutes. Defaults can be changed with the documented `ATHENA_LOGIN_*` values.
- Login success/failure and logout continue through the structured security
  audit sink.
- Kite API secret/access token never return to browser JavaScript.
- Broker website logout does not revoke a Kite Connect token. Use the header
  **KITE** button → **Clear Session** to force a fresh authorize.
- The API and Dock launcher bind/open `127.0.0.1`, not the LAN.

## Smoke checklist

After installation or an upgrade:

- [ ] Dock click opens `http://127.0.0.1:8000/dashboard/`.
- [ ] Unlock rejects an incorrect password and accepts the owner password.
- [ ] Profile footer shows the `/auth/me` username and role.
- [ ] Header KITE button shows the verified session state.
- [ ] **Clear Session** blocks LIVE and requires a fresh Kite authorize.
- [ ] After reconnect, KITE is connected and the gate closes.
- [ ] Header health is healthy; cycle status matches the chosen serve mode.
- [ ] Dashboard logout returns to Workstation Unlock.
- [ ] A second Dock click opens the existing server instead of starting another.
- [ ] `artifacts/logs/athena-serve.log` has no startup traceback.

Automated regression:

```bash
PYTHONPATH=src python3 -m pytest -q
```

## Optional localhost HTTPS

HTTP on `127.0.0.1` is the default and recommended low-friction single-user
mode. For an explicitly trusted local certificate:

```bash
brew install mkcert
mkcert -install
mkdir -p artifacts/tls
mkcert \
  -cert-file artifacts/tls/localhost.pem \
  -key-file artifacts/tls/localhost-key.pem \
  localhost 127.0.0.1 ::1

./athena-serve --with-cycles --open \
  --ssl-certfile artifacts/tls/localhost.pem \
  --ssl-keyfile artifacts/tls/localhost-key.pem
```

The Dock app intentionally retains the default HTTP localhost path. Optional
TLS is a power-user terminal mode.

## Troubleshooting

**Port 8000 already in use:** an older manual uvicorn process may still be
running. Stop that process once, then use only the Dock app or `./athena-serve`.

**App reports startup failure:** inspect
`artifacts/logs/athena-serve.log`, then run `./athena-serve --with-cycles`
once in Terminal for visible diagnostics.

**Kite gate does not appear after broker website logout:** that logout does not
invalidate the Connect token. Click the header KITE button and clear the
session.

**Repository moved:** rerun `./install-athena-app` so the app stores the new
absolute path.
