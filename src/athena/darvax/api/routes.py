"""DarvaX's own data API (DX-4), served under ``/darvax``.

**Authentication is delegated to ATHENA, not reimplemented.** DarvaX reuses
ATHENA's existing ``RequirePermission`` guard so the owner's single dashboard
session covers both lanes: one login, one credential store, one place where auth
correctness lives. Standing up a second authentication system inside the
satellite would be worse engineering and materially worse security than reusing
the audited one. This is a deliberate, narrow widening of the DarvaX → ATHENA
import surface beyond ``domain``/``errors``, and it is recorded as such in the
DX-4 review summary.

ATHENA's auth dependency resolves ``request.app.state.token_signer`` — and a
mounted sub-application has its own ``state`` — so the mount seam copies exactly
those two attributes across. See ``athena.api.darvax_mount``.

Every response carries the experimental label. Nothing here is validated: the
source deck ships no backtest evidence, and DX-5 is what changes that.
"""

from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal, InvalidOperation
from typing import Annotated, Any
from uuid import uuid4

from fastapi import APIRouter, Body, Depends, HTTPException, Request, status

from athena.api.security import Permission, RequirePermission
from athena.darvax import __version__ as darvax_version
from athena.darvax.config import methodology_digest
from athena.darvax.digest import read_latest_digest, resolve_output_dir
from athena.darvax.positions.models import DarvaxPosition
from athena.darvax.scan import scan_instruments
from athena.darvax.screening.engine import screen_signal
from athena.darvax.screening.models import (
    RISK_BEARING_ACTIONS,
    DarvaxTier,
    ScreenResult,
    SweepRecord,
)
from athena.darvax.screening.sweep import SweepBusyError
from athena.darvax.signals import DarvaxSignal
from athena.darvax.signals.models import DarvaxSignalType
from athena.darvax.signals.stops import compute_stop
from athena.domain.enums import Timeframe
from athena.errors import AthenaError, RepositoryError

router = APIRouter(prefix="/api", tags=["DarvaX (experimental)"])

#: Stamped on every payload so a response can never be mistaken for validated
#: ATHENA output, whatever context it is read in.
EXPERIMENTAL_STATUS = "EXPERIMENTAL_UNVALIDATED"

_DISCLAIMER = (
    "DarvaX is an experimental, unvalidated satellite lane. It never contributes "
    "to ATHENA's scoring, confidence, risk, Decision, or TradePlan. The source "
    "methodology ships no backtest evidence; validation is ADR-010 DX-5."
)


def _signal_payload(signal: DarvaxSignal) -> dict[str, Any]:
    """Serialise a signal, including its persisted explanation and evidence.

    The explanation and evidence are read out as stored — this endpoint never
    recomputes or re-words them, per ADR-005's explainability-as-data principle.
    """
    return {
        "signal_id": signal.signal_id,
        "instrument_id": signal.instrument_id,
        "symbol": signal.instrument_id.split(":")[-1],
        "as_of": signal.as_of.isoformat(),
        "signal_type": signal.signal_type.value,
        "darvas_rule": signal.darvas_rule.value if signal.darvas_rule else None,
        "close": str(signal.close),
        "box_top": str(signal.box_top) if signal.box_top is not None else None,
        "box_bottom": str(signal.box_bottom) if signal.box_bottom is not None else None,
        "box_is_topmost": signal.box_is_topmost,
        "trigger_price": (
            str(signal.trigger_price) if signal.trigger_price is not None else None
        ),
        "stop": (
            {
                "basis": signal.stop.basis.value,
                "price": str(signal.stop.price),
                "reference_price": str(signal.stop.reference_price),
                "detail": signal.stop.detail,
                "ema_period": signal.stop.ema_period,
                "pct": str(signal.stop.pct) if signal.stop.pct is not None else None,
            }
            if signal.stop is not None
            else None
        ),
        "explanation": signal.explanation,
        "evidence": [
            {"name": e.name, "value": e.value, "detail": e.detail}
            for e in signal.evidence
        ],
        "methodology_digest": signal.methodology_digest,
        "darvax_version": signal.darvax_version,
        "status": signal.status,
    }


def _optional(value: Decimal | None) -> str | None:
    """Decimals cross the wire as strings — a JSON float would quietly corrupt a
    price the rest of the system keeps exact."""
    return str(value) if value is not None else None


def _envelope(data: Any, **extra: Any) -> dict[str, Any]:
    return {
        "status": "success",
        "darvax_status": EXPERIMENTAL_STATUS,
        "disclaimer": _DISCLAIMER,
        "darvax_version": darvax_version,
        "data": data,
        **extra,
    }


def _screen_payload(result: ScreenResult) -> dict[str, Any]:
    """Serialise a screen result.

    Tier, rank and both measurements are read out exactly as the screening
    engine persisted them — nothing here classifies or re-measures anything
    (ADR-005). Decimals are serialised as strings so a percentage survives the
    round trip that a JSON float would quietly corrupt.
    """
    return {
        "instrument_id": result.instrument_id,
        "symbol": result.instrument_id.split(":")[-1],
        "signal_id": result.signal_id,
        "tier": result.tier.value,
        "signal_type": result.signal_type.value,
        "darvas_rule": result.darvas_rule.value if result.darvas_rule else None,
        "rank": result.rank,
        "close": str(result.close),
        "box_top": str(result.box_top) if result.box_top is not None else None,
        "box_bottom": (
            str(result.box_bottom) if result.box_bottom is not None else None
        ),
        "trigger_price": (
            str(result.trigger_price) if result.trigger_price is not None else None
        ),
        "distance_to_trigger_pct": (
            str(result.distance_to_trigger_pct)
            if result.distance_to_trigger_pct is not None
            else None
        ),
        # The ranking key, plus the level it was measured to, so the UI can show
        # what drove the order instead of leaving the reader to infer it.
        "distance_to_breakout_pct": (
            str(result.distance_to_breakout_pct)
            if result.distance_to_breakout_pct is not None
            else None
        ),
        "breakout_reference": result.breakout_reference,
        "box_height_pct": (
            str(result.box_height_pct) if result.box_height_pct is not None else None
        ),
        "explanation": result.explanation,
        # DX-7a. The action and its justification are read from the record, not
        # derived from `tier` or `signal_type` here — an API that recomputed them
        # could disagree with what the sweep actually persisted (ADR-005).
        "action": result.action.value,
        "action_reason": result.action_reason,
        # DX-8a: the plain sentence leads in the UI, the technical one sits
        # behind a disclosure. Both persisted by the engine (ADR-005).
        "action_reason_plain": result.action_reason_plain,
        # Rule B mandates a stop; a screen that recommends an entry without one
        # is recommending half a trade.
        "stop_price": _optional(result.stop_price),
        "stop_basis": result.stop_basis,
        # DX-9c: the same 10% stop lands above the breakout level for one
        # instrument and below it for another. Compared and worded by the
        # engine, so the browser renders a fact rather than deriving one.
        "stop_vs_ceiling": _optional(result.stop_vs_ceiling),
        "stop_vs_ceiling_note": result.stop_vs_ceiling_note,
        # DX-10a. Rupees; the UI converts to crore. Null means unmeasured, which
        # a filter must not treat as illiquid.
        "liquidity_value": _optional(result.liquidity_value),
        # DX-12a. Trend context, not a DAR-CARD rule. Independently nullable —
        # a symbol may have enough history for one EMA period and not the other.
        "ema_50": _optional(result.ema_50),
        "ema_100": _optional(result.ema_100),
        # Which chips must carry the unvalidated badge is a domain fact, not a
        # styling choice, so the client is told rather than left to hardcode a
        # list that would drift when an action is added (design §4, decision 3b).
        "risk_bearing": result.action in RISK_BEARING_ACTIONS,
        "status": EXPERIMENTAL_STATUS,
    }


def _sweep_payload(sweep: SweepRecord) -> dict[str, Any]:
    return {
        "sweep_id": sweep.sweep_id,
        "started_at": sweep.started_at.isoformat(),
        "finished_at": sweep.finished_at.isoformat() if sweep.finished_at else None,
        "state": sweep.state,
        "as_of": sweep.as_of.isoformat() if sweep.as_of else None,
        "methodology_digest": sweep.methodology_digest,
        "darvax_version": sweep.darvax_version,
        "requested": sweep.requested,
        "evaluated": sweep.evaluated,
        "partial": sweep.partial,
        "tier_counts": {t.value: c for t, c in sweep.tier_counts.items()},
        "skipped": [
            {"instrument_id": i, "reason": r} for i, r in sweep.skipped
        ],
    }


@router.get("/signals", summary="List persisted DarvaX signals (experimental)")
def list_signals(
    request: Request,
    limit: int = 200,
    signal_type: str | None = None,
    _principal: Annotated[
        object, Depends(RequirePermission(Permission.READ))
    ] = None,
) -> dict[str, Any]:
    """Newest-first signals, optionally filtered to one structural state."""
    if not 1 <= limit <= 1000:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="limit must be between 1 and 1000",
        )
    store = request.app.state.darvax_store
    if signal_type is None:
        signals = store.list_signals(limit=limit)
    else:
        try:
            parsed = DarvaxSignalType(signal_type)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail=(
                    f"unknown signal_type {signal_type!r}; valid values: "
                    + ", ".join(s.value for s in DarvaxSignalType)
                ),
            ) from None
        signals = store.list_signals_by_type(parsed, limit=limit)
    return _envelope([_signal_payload(s) for s in signals], count=len(signals))


# --------------------------------------------------------------------------- #
# Universe screening (DX-6b, ADR-010 Amendment 2)
# --------------------------------------------------------------------------- #


@router.post("/screen", summary="Start a universe sweep (experimental)")
def start_screen(
    request: Request,
    _principal: Annotated[
        object, Depends(RequirePermission(Permission.EXECUTE))
    ] = None,
) -> dict[str, Any]:
    """Begin an owner-triggered sweep of the whole ledger.

    Single-flight: a second request while one runs is **refused with 409**,
    never queued (ADR-010 Amendment 2). Sweeps are never scheduled — that is
    what keeps the DX-4a no-contention finding true.
    """
    runner = request.app.state.darvax_sweep_runner
    try:
        sweep_id = runner.start()
    except SweepBusyError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail=str(exc)
        ) from exc
    return _envelope({"sweep_id": sweep_id}, state="running")


@router.get("/screen/progress", summary="Sweep progress (experimental)")
def screen_progress(
    request: Request,
    _principal: Annotated[
        object, Depends(RequirePermission(Permission.READ))
    ] = None,
) -> dict[str, Any]:
    """Transient progress for the running (or last) sweep."""
    progress = request.app.state.darvax_sweep_runner.progress()
    return _envelope(
        {
            "state": progress.state,
            "stage": progress.stage,
            "sweep_id": progress.sweep_id,
            "total": progress.total,
            "evaluated": progress.evaluated,
            "skipped": progress.skipped,
            "elapsed_seconds": round(progress.elapsed_seconds, 2),
            "error": progress.error,
        }
    )


@router.delete("/screen", summary="Cancel the running sweep (experimental)")
def cancel_screen(
    request: Request,
    _principal: Annotated[
        object, Depends(RequirePermission(Permission.EXECUTE))
    ] = None,
) -> dict[str, Any]:
    """Stop the running sweep. Work already done is kept and marked partial."""
    cancelled = request.app.state.darvax_sweep_runner.cancel()
    return _envelope({"cancelled": cancelled})


@router.get("/screen/latest", summary="Latest screen results (experimental)")
def latest_screen(
    request: Request,
    tier: str | None = None,
    limit: int = 1000,
    _principal: Annotated[
        object, Depends(RequirePermission(Permission.READ))
    ] = None,
) -> dict[str, Any]:
    """The most recent sweep's results, in rank order, optionally one tier."""
    if not 1 <= limit <= 5000:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="limit must be between 1 and 5000",
        )
    parsed_tier: DarvaxTier | None = None
    if tier is not None:
        try:
            parsed_tier = DarvaxTier(tier)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail=(
                    f"unknown tier {tier!r}; valid values: "
                    + ", ".join(t.value for t in DarvaxTier)
                ),
            ) from None

    store = request.app.state.darvax_store
    # The digest DarvaX is configured with *now*. Served alongside the sweep's
    # own digest so the reader can be told when a screen was produced under
    # different methodology settings than are currently in force — a 10% stop
    # screen read as though it were a 1% stop screen is misleading, and the
    # mismatch is invisible without both values.
    current_digest = methodology_digest(request.app.state.darvax_config.methodology)

    latest_attempt = store.latest_sweep()
    sweep = store.latest_authoritative_sweep()
    attempt_warning = None
    if latest_attempt is not None and (
        sweep is None or latest_attempt.sweep_id != sweep.sweep_id
    ):
        attempt_warning = (
            f"Latest sweep {latest_attempt.state}; showing the most recent "
            "stable sweep."
            if sweep is not None
            else f"Latest sweep {latest_attempt.state}; no stable sweep is available."
        )
    if sweep is None:
        freshness = request.app.state.darvax_freshness_classifier.classify(
            sweep=None,
            current_methodology_digest=current_digest,
            reference_time=request.app.state.darvax_freshness_clock(),
        )
        # An honest empty state, not an error: no sweep has ever run.
        return _envelope(
            [],
            sweep=None,
            freshness=freshness.to_payload(),
            count=0,
            current_methodology_digest=current_digest,
            latest_attempt=(
                _sweep_payload(latest_attempt) if latest_attempt is not None else None
            ),
            latest_attempt_warning=attempt_warning,
        )

    results = store.list_screen_results(
        sweep.sweep_id, tier=parsed_tier, limit=limit
    )
    freshness = request.app.state.darvax_freshness_classifier.classify(
        sweep=sweep,
        current_methodology_digest=current_digest,
        reference_time=request.app.state.darvax_freshness_clock(),
    )
    return _envelope(
        [_screen_payload(r) for r in results],
        sweep=_sweep_payload(sweep),
        freshness=freshness.to_payload(),
        count=len(results),
        current_methodology_digest=current_digest,
        latest_attempt=(
            _sweep_payload(latest_attempt) if latest_attempt is not None else None
        ),
        latest_attempt_warning=attempt_warning,
    )


@router.get("/screen/sweeps", summary="Sweep history (experimental)")
def list_sweeps(
    request: Request,
    limit: int = 50,
    _principal: Annotated[
        object, Depends(RequirePermission(Permission.READ))
    ] = None,
) -> dict[str, Any]:
    """Past sweeps, newest first, for replay and comparison."""
    if not 1 <= limit <= 500:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="limit must be between 1 and 500",
        )
    sweeps = request.app.state.darvax_store.list_sweeps(limit=limit)
    return _envelope([_sweep_payload(s) for s in sweeps], count=len(sweeps))


@router.get("/screen/near-misses", summary="Latest near-miss digest (experimental)")
def get_near_misses(
    request: Request,
    _principal: Annotated[
        object, Depends(RequirePermission(Permission.READ))
    ] = None,
) -> dict[str, Any]:
    """AUX-4c: a read of AUX-4b's already-persisted digest file (written
    once per completed sweep) -- never a recomputation."""
    output_dir = resolve_output_dir(request.app.state.darvax_config.near_miss.output_dir)
    digest = read_latest_digest(output_dir)
    return _envelope(digest)


@router.get(
    "/signals/{instrument_id:path}",
    summary="Latest persisted DarvaX signal for one instrument (experimental)",
)
def latest_signal(
    request: Request,
    instrument_id: str,
    _principal: Annotated[
        object, Depends(RequirePermission(Permission.READ))
    ] = None,
) -> dict[str, Any]:
    store = request.app.state.darvax_store
    signal = store.latest_signal(instrument_id)
    if signal is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"DarvaX has no signal for {instrument_id}",
        )
    return _envelope(_signal_payload(signal))


@router.post("/scan", summary="Evaluate DarvaX signals for instruments (experimental)")
def scan(
    request: Request,
    payload: Annotated[dict[str, Any], Body(...)],
    _principal: Annotated[
        object, Depends(RequirePermission(Permission.EXECUTE))
    ] = None,
) -> dict[str, Any]:
    """Run a bounded scan and persist one signal per instrument.

    Advisory only: this computes and stores observations. Nothing here places an
    order, and nothing here writes to ATHENA.
    """
    raw = payload.get("instrument_ids")
    if not isinstance(raw, list) or not raw:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="instrument_ids must be a non-empty list of instrument ids",
        )
    instrument_ids = [str(item) for item in raw]

    timeframe_raw = str(payload.get("timeframe") or Timeframe.D1.value)
    try:
        timeframe = Timeframe(timeframe_raw)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=f"unknown timeframe {timeframe_raw!r}",
        ) from None

    try:
        result = scan_instruments(
            market_data=request.app.state.darvax_market_data,
            store=request.app.state.darvax_store,
            config=request.app.state.darvax_config,
            instrument_ids=instrument_ids,
            timeframe=timeframe,
        )
    except AthenaError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc)
        ) from exc

    # AUX-8: classify each signal with the same pure function a real sweep
    # uses (screen_signal), so an on-demand scan's result carries the same
    # tier/action/buy-above/stop-loss shape as a sweep's ScreenResult -- not
    # a second, thinner reading a caller has to know to interpret differently.
    # Never persisted: "adhoc-scan" is not a real sweep id, and this classifies
    # without the owner's held-position context or sweep-wide liquidity/trend
    # (screen_signal's own documented, purely-additive optional inputs) -- a
    # deliberately smaller scope than a full sweep, not a second methodology.
    screened = [screen_signal(s, sweep_id="adhoc-scan") for s in result.signals]

    return _envelope(
        [_signal_payload(s) for s in result.signals],
        screened=[_screen_payload(r) for r in screened],
        requested=result.requested,
        evaluated=result.evaluated,
        timeframe=result.timeframe.value,
        skipped=[
            {"instrument_id": s.instrument_id, "reason": s.reason}
            for s in result.skipped
        ],
    )


# --------------------------------------------------------------------------- #
# Positions (DX-7b) — DarvaX's own record of what is held.
#
# Advisory only, and emphatically not a broker: recording a position here tells
# DarvaX what the owner already bought elsewhere. Nothing in this module places,
# routes, or simulates an order, and no order API exists in this repository.
# --------------------------------------------------------------------------- #


def _position_payload(position: DarvaxPosition) -> dict[str, Any]:
    return {
        "position_id": position.position_id,
        "instrument_id": position.instrument_id,
        "quantity": position.quantity,
        "entry_price": str(position.entry_price),
        "entry_date": position.entry_date.isoformat(),
        "opened_at": position.opened_at.isoformat(),
        "stop_price": _optional(position.stop_price),
        "stop_basis": position.stop_basis.value if position.stop_basis else None,
        "methodology_digest": position.methodology_digest,
        "closed_at": position.closed_at.isoformat() if position.closed_at else None,
        "note": position.note,
        "is_open": position.is_open,
        "status": EXPERIMENTAL_STATUS,
    }


@router.get("/positions", summary="DarvaX-lane positions (experimental)")
def list_positions(
    request: Request,
    open_only: bool = True,
    _principal: Annotated[
        object, Depends(RequirePermission(Permission.READ))
    ] = None,
) -> dict[str, Any]:
    """What DarvaX believes is held.

    **Not reconciled with ATHENA's `owner_positions`** — the owner chose
    separate lists (advisor design decision 1a), so a position closed in ATHENA
    stays open here until closed here too.
    """
    store = request.app.state.darvax_store
    positions = store.list_positions(open_only=open_only)
    return _envelope(
        [_position_payload(p) for p in positions],
        open_only=open_only,
        count=len(positions),
    )


@router.post("/positions", summary="Record a held position (experimental)")
def open_position(
    request: Request,
    payload: Annotated[dict[str, Any], Body()],
    _principal: Annotated[
        object, Depends(RequirePermission(Permission.EXECUTE))
    ] = None,
) -> dict[str, Any]:
    """Record that the owner holds an instrument, so DarvaX can say HOLD/EXIT.

    The stop is **derived here and frozen** from the stop policy in force now
    (deck p.67's 10% on first breakout, unless configured otherwise), rather
    than recomputed on every read: changing the policy later must not silently
    move the level an open position was actually protected by.
    """
    config = request.app.state.darvax_config
    store = request.app.state.darvax_store

    try:
        instrument_id = str(payload["instrument_id"]).strip()
        quantity = int(payload["quantity"])
        entry_price = Decimal(str(payload["entry_price"]))
        entry_date = date.fromisoformat(str(payload["entry_date"]))
    except (KeyError, TypeError, ValueError, InvalidOperation) as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=(
                "instrument_id, quantity, entry_price and entry_date (ISO) are "
                f"required and must be well-formed: {exc}"
            ),
        ) from exc

    if not instrument_id:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="instrument_id must not be empty",
        )
    if quantity < 1:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=f"quantity must be at least 1, got {quantity}",
        )
    if entry_price <= 0:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=f"entry_price must be positive, got {entry_price}",
        )

    now = datetime.now(tz=timezone.utc)
    stop_price: Decimal | None = None
    stop_basis = None
    raw_stop = payload.get("stop_price")
    if raw_stop not in (None, ""):
        # An owner-supplied stop wins over the derived one, but its basis is
        # recorded as such so a reader is never told Darvas chose a level the
        # owner did.
        try:
            stop_price = Decimal(str(raw_stop))
        except InvalidOperation as exc:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail=f"stop_price is not a number: {raw_stop!r}",
            ) from exc
    else:
        derived = compute_stop(
            [], config.methodology, reference_price=entry_price
        )
        if derived is not None:
            stop_price, stop_basis = derived.price, derived.basis

    position = DarvaxPosition(
        position_id=f"pos-{uuid4().hex[:12]}",
        instrument_id=instrument_id,
        quantity=quantity,
        entry_price=entry_price,
        entry_date=entry_date,
        opened_at=now,
        stop_price=stop_price,
        stop_basis=stop_basis,
        methodology_digest=methodology_digest(config.methodology),
        note=str(payload.get("note") or ""),
    )
    try:
        store.upsert_position(position)
    except RepositoryError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail=str(exc)
        ) from exc
    return _envelope(_position_payload(position))


@router.post(
    "/positions/{position_id}/close", summary="Close a position (experimental)"
)
def close_position(
    request: Request,
    position_id: str,
    _principal: Annotated[
        object, Depends(RequirePermission(Permission.EXECUTE))
    ] = None,
) -> dict[str, Any]:
    """Mark a position closed. The row is kept, not deleted — a closed position
    is the record of a completed round trip."""
    store = request.app.state.darvax_store
    closed = store.close_position(position_id, closed_at=datetime.now(tz=timezone.utc))
    if not closed:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"no open DarvaX position {position_id!r}",
        )
    return _envelope({"position_id": position_id, "closed": True})


@router.delete("/positions/{position_id}", summary="Delete a position (experimental)")
def delete_position(
    request: Request,
    position_id: str,
    _principal: Annotated[
        object, Depends(RequirePermission(Permission.EXECUTE))
    ] = None,
) -> dict[str, Any]:
    """Remove a mis-recorded position outright.

    Distinct from closing on purpose: **close** preserves a real trade's
    history, **delete** erases a typo. Conflating them would quietly destroy
    round trips.
    """
    store = request.app.state.darvax_store
    if not store.delete_position(position_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"no DarvaX position {position_id!r}",
        )
    return _envelope({"position_id": position_id, "deleted": True})
