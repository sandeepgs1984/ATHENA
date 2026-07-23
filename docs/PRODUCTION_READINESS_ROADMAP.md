# ATHENA — Production Readiness Roadmap (Daily Advisory Use)

**Purpose:** Bridge from “Phases 0–10 mostly complete” to **reliable daily decision support** for NSE/BSE swing trading — without order placement (constitutionally forbidden).

**Owner goal (2026-07-23):** Use ATHENA every trading day as advisory intelligence — real (or faithfully maintained) market data, premarket/intraday cycles, briefings you can act on at the broker yourself.

**Governing docs:** ATHENA-000 · ATHENA-002 · `docs/MILESTONES.md` · ADR-002 (broker abstraction).

**Rule:** One milestone in flight; owner authorizes each gate. This roadmap does **not** auto-start work.

---

## Current state (honest baseline)

| Capability | Today |
|---|---|
| Phases 0–9 | Complete — intelligence, paper path, API, dashboard/ops |
| M10.1–M10.3 | Approved — file ingest, dry-run cadence + run ledger, briefings |
| M10.4 | Approved — closes Phase 10 |
| Market data | **FileProvider only** (`config/ingestion.json` → `provider: file`). DD-1 open |
| Broker | Paper translation only — no network, no placement |
| Default daily cycle | Ingest + run ledger (`ingest_only`); full paper pipeline optional/injectable |
| Briefings | Strong on **runs**; often **DEGRADED** without injected decisions (journal not in SQLite) |
| Unattended ops | No embedded cron — CLI + external launcher (launchd/cron) |

**Verdict:** Excellent **lab / paper / review** workstation. **Not** yet “wake up and trust live NSE feeds unattended.”

---

## Target outcome (Definition of Ready — Daily Advisory)

ATHENA is **daily-advisory-ready** when all of the following are true:

1. **Data path:** Either (A) a maintained FileProvider tree refreshed before each cycle, or (B) a DD-1 live `MarketDataProvider` bound and passing the contract suite.
2. **Daily loop:** Premarket + intraday refresh cycles run on a schedule you trust; failures fail loudly (quarantine / run status / briefing DEGRADED|FAILED).
3. **Decisions durable:** Cycle outcomes include persisted decisions + traces (or equivalent) so briefings are OK, not chronically DEGRADED.
4. **Human action surface:** Dashboard + `athena brief` (file and/or webhook) give you a clear premarket plan and refresh deltas — **you** place orders at the broker.
5. **Ops hygiene:** DB backup cadence, health check, and at least one outbound alert path for hard failures.
6. **Non-goals remain true:** No order-placement code; secrets only in `.env`; architecture frozen unless ADR approved.

---

## Roadmap tracks (ordered)

Work proceeds **left to right**. Tracks B–D can be partially parallelized only after owner splits milestones; default is still one milestone at a time.

```text
Finish Phase 10          Interim daily use           Live data              Hardened daily ops
─────────────────        ─────────────────           ─────────              ──────────────────
M10.4 Playbook    →    R1 File-backed SOP    →    R3 DD-1 Provider  →   R5 Launchd + alerts
                       R2 Decision journal         R4 Live ingest bind     R6 Closing cycle
                       persistence + briefings                             (optional polish)
```

### Track 0 — Finish Phase 10 (required before claiming Phase 10 complete)

| ID | Milestone | Objective | Exit criteria |
|---|---|---|---|
| **M10.4** | AI Playbook Diagnostics | Propose config/weight tuning from journal-like outcomes; **human approves** any change | **✅ APPROVED 2026-07-23** — closes Phase 10 |

*Note:* M10.4 quality depends on having outcomes to analyze. If journal persistence (R2) is thin, M10.4 may be **propose-only over run ledger + injected outcomes**, or R2 may be authorized first — owner chooses at authorization time.

---

### Track A — Interim daily use on FileProvider (usable now, with discipline)

| ID | Milestone | Objective | Exit criteria |
|---|---|---|---|
| **R1** | File-backed Daily Ops SOP | Document + script the day: refresh CSVs → `athena due` → `athena cycle` → dashboard → `athena brief --dry-run` | **✅ APPROVED 2026-07-23** — `docs/ops/FILE_BACKED_DAILY_OPS.md` + `scripts/smoke_file_backed_day.sh` |
| **R2** | Decision Journal Persistence | Persist decisions/traces (or cycle decision summaries) to SQLite; wire into briefing `DecisionSummarySource` | **✅ APPROVED 2026-07-23** |

**After R1+R2:** You can use ATHENA **daily** if you keep `data/` fresh (manual export or your own downloader). Still not live broker feed.

---

### Track B — Live market data (unlocks “real market” daily use)

| ID | Milestone | Objective | Exit criteria |
|---|---|---|---|
| **R3** | DD-1 Decision Record | Owner picks vendor against ATHENA-002 §15 criteria (depth, rate limits, cost, auth burden, stability) | Written choice + acceptance notes; no code until R4 authorized |
| **R4** | Live Provider Adapter | Implement `MarketDataProvider` for chosen vendor; pass `tests/contract/provider_contract.py`; bind via config (not hardcoded) | Contract suite green; secrets in `.env`; FileProvider remains default/fallback; ingest config can select live provider |

**After R4:** Ingest/cycles can poll **real** quotes/candles (within vendor limits). Still advisory-only.

---

### Track C — Unattended daily operations

| ID | Milestone | Objective | Exit criteria |
|---|---|---|---|
| **R5** | Host Schedule + Failure Alerts | launchd/cron (or equivalent) invokes `athena cycle` / `brief`; hard failures notify (webhook and/or email — advances DD-9) | Documented plist/cron; failure notification tested; localhost/secrets policy preserved |
| **R6** | Closing / Day-Summary Cycle | Optional post-15:30 cycle: day roll-up + journal prompts (Blueprint §8) | Trigger + briefing section; owner approval |

---

### Track D — Explicitly out of scope (do not schedule)

- Order placement, OMS, broker execute APIs  
- Multi-user / cloud SaaS  
- Silent auto-tuning of strategy weights (M10.4 proposes only)  
- Streaming websockets (DD-2) until polling is proven insufficient  

---

## Suggested authorization sequence (when you resume)

1. **`authorize M10.4`** — close Phase 10 (or authorize **R2 before M10.4** if you want richer diagnostics).  
2. **`authorize R1`** — SOP so you can practice daily use on files immediately.  
3. **`authorize R2`** — make briefings decision-complete.  
4. Owner workshop → **`authorize R3`** (DD-1 choice only).  
5. **`authorize R4`** — live provider.  
6. **`authorize R5`** (then optional **R6**) — unattended + alerts.

**Daily-advisory-ready** ≈ R1 + R2 + (R3+R4 **or** disciplined file refresh) + R5.

---

## How this relates to `docs/MILESTONES.md`

- **Phases 0–10** remain the engineering milestone authority.  
- **R1–R6** are the **production-readiness** appendices for your daily-use goal; they are authorized the same way (owner gate, one at a time).  
- Do not start R* work until the corresponding authorize message; finishing M10.4 first is the default unless you say otherwise.

---

## Resume checklist

When ready to continue, reply with one of:

- `authorize M10.4` — finish Phase 10  
- `authorize R1` — file-backed daily SOP first  
- `authorize R2` — decision journal persistence first  
- `authorize R3` — start DD-1 vendor decision only  

Until then: no further Phase 10 / R* implementation.
