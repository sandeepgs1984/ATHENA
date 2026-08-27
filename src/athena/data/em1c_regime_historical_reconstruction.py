"""EM-1c regime-evidence prerequisite: chronologically replay the
canonical, unmodified RegimeEngine across the full EMR study window,
using the accepted NIFTY 50 / INDIA VIX acquisition evidence and the
point-in-time-safe rule in ``athena.explosive_move.regime_replay``.

Read-only against the accepted acquisition manifest/payloads and
EM-1b's real study-session dates
(``artifacts/research/em1b/partition_measurement.json``); write-only
against ``artifacts/research/em1c-regime/`` (git-ignored). Never mutates
canonical tables, matching every EMR script in this workstream.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path

from athena.config.loader import load_config
from athena.domain.enums import Timeframe
from athena.domain.market import Candle
from athena.explosive_move.regime_replay import (
    REGIME_REPLAY_CONTRACT_VERSION,
    reconstruct_session_regime,
)


def _load_candles(acquisition_dir: Path, manifest: dict, instrument_id: str) -> tuple[Candle, ...]:
    entry = manifest["instruments"][instrument_id]
    payload = json.loads((acquisition_dir / entry["payload_file"]).read_text(encoding="utf-8"))
    out = []
    for row in payload:
        ts_open = datetime.fromisoformat(row["ts_open"])
        out.append(Candle(
            instrument_id=instrument_id, timeframe=Timeframe.D1, ts_open=ts_open,
            open=Decimal(row["open"]), high=Decimal(row["high"]), low=Decimal(row["low"]),
            close=Decimal(row["close"]), volume=row["volume"], source="kite", adjusted=False,
        ))
    return tuple(out)


def main() -> None:
    parser = argparse.ArgumentParser(description="EM-1c historical regime reconstruction.")
    parser.add_argument("--config-dir", type=Path, default=Path("config"))
    parser.add_argument(
        "--acquisition-dir", type=Path, default=Path("artifacts/research/em1c-regime/acquisition"),
    )
    parser.add_argument(
        "--em1b-measurement", type=Path,
        default=Path("artifacts/research/em1b/partition_measurement.json"),
    )
    parser.add_argument("--out", type=Path, default=Path("artifacts/research/em1c-regime/regime_by_session.json"))
    args = parser.parse_args()

    config = load_config(args.config_dir)
    manifest = json.loads((args.acquisition_dir / "manifest.json").read_text(encoding="utf-8"))
    if not manifest["overall_validation_passed"]:
        raise SystemExit(
            f"acquisition manifest {manifest['manifest_id']} did not pass validation -- "
            "refusing to reconstruct from unaccepted evidence"
        )

    nifty_candles = _load_candles(args.acquisition_dir, manifest, "NSE:NIFTY 50")
    vix_candles = _load_candles(args.acquisition_dir, manifest, "NSE:INDIA VIX")

    em1b_measurement = json.loads(args.em1b_measurement.read_text(encoding="utf-8"))
    session_dates = tuple(sorted(date.fromisoformat(d) for d in em1b_measurement["per_date_counters"]))

    records = []
    for session_date in session_dates:
        result = reconstruct_session_regime(
            session_date=session_date, index_symbol="NSE:NIFTY 50",
            nifty_candles=nifty_candles, vix_candles=vix_candles, config=config.regime,
        )
        records.append({
            "session_date": result.session_date.isoformat(),
            "index_symbol": result.index_symbol,
            "index_data_cutoff": result.index_data_cutoff.isoformat() if result.index_data_cutoff else None,
            "vix_data_cutoff": result.vix_data_cutoff.isoformat() if result.vix_data_cutoff else None,
            "trend": result.trend.value,
            "volatility": result.volatility.value,
            "gap": result.gap.value,
            "trend_explanation": result.trend_explanation,
            "volatility_explanation": result.volatility_explanation,
            "gap_explanation": result.gap_explanation,
        })

    output = {
        "contract_version": REGIME_REPLAY_CONTRACT_VERSION,
        "regime_config": {
            "trend_ma_fast": config.regime.trend_ma_fast,
            "trend_ma_slow": config.regime.trend_ma_slow,
            "high_volatility_vix": config.regime.high_volatility_vix,
            "low_volatility_vix": config.regime.low_volatility_vix,
            "gap_pct_threshold": config.regime.gap_pct_threshold,
        },
        "source_acquisition_manifest_id": manifest["manifest_id"],
        "session_count": len(records),
        "sessions": records,
    }
    fingerprint = hashlib.sha256(
        json.dumps(
            {k: v for k, v in output.items() if k != "run_id"},
            sort_keys=True, separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()
    output["run_id"] = f"em1c-regime-replay-{fingerprint}"

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(output, indent=2), encoding="utf-8")
    print(f"wrote {args.out} -- {len(records)} sessions, run_id={output['run_id']}")


if __name__ == "__main__":
    main()
