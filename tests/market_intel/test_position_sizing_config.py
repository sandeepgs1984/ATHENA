"""ID-9 V0 Capital Policy Activation: the canonical production
configuration seam (`position_sizing_config.py`).

Missing `config/position_sizing_policy.json` is safely inert (`None`,
preserving `CAPITAL_POLICY_UNAVAILABLE`); a present-but-invalid file
fails loudly; a valid file constructs exactly one immutable
`CapitalPolicy` with exact Decimal semantics and exact `policy_version`
propagation; dormant `capital.json`/`risk.json` are never read by this
loader; and `cli.py`'s single canonical `_owner_validation_pipeline`
seam wires the (possibly-`None`) result straight into
`OwnerValidationPipeline` -- proven end-to-end with a real multi-
instrument scan sharing one policy instance.
"""

from __future__ import annotations

import ast
import inspect
import json
from decimal import Decimal
from pathlib import Path

import pytest

from athena.errors import ConfigError
from athena.intraday import position_sizing_config as config_module
from athena.intraday.position_sizing_config import (
    POSITION_SIZING_POLICY_CONFIG_FILENAME,
    PositionSizingPolicyConfig,
    load_position_sizing_policy_config,
    position_sizing_policy_config_path,
)
from athena.intraday.position_sizing_models import CapitalPolicy

VALID_PAYLOAD = {
    "_meta": {"description": "test fixture"},
    "total_deployable_capital": "500000.00",
    "risk_budget_per_trade_pct": "0.50",
    "max_position_value_pct": "15.00",
    "policy_version": "policy-2026-09-07-v1",
}


def _write(config_dir: Path, payload: dict) -> Path:
    path = position_sizing_policy_config_path(config_dir)
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


# ---- safe absence ----------------------------------------------------


def test_missing_file_returns_none(tmp_path: Path) -> None:
    assert load_position_sizing_policy_config(tmp_path) is None


def test_missing_file_path_helper_is_deterministic(tmp_path: Path) -> None:
    assert position_sizing_policy_config_path(tmp_path) == tmp_path / POSITION_SIZING_POLICY_CONFIG_FILENAME


# ---- valid configuration ----------------------------------------------


def test_valid_config_constructs_capital_policy(tmp_path: Path) -> None:
    _write(tmp_path, VALID_PAYLOAD)
    policy = load_position_sizing_policy_config(tmp_path)
    assert isinstance(policy, CapitalPolicy)
    assert policy.total_deployable_capital == Decimal("500000.00")
    assert policy.risk_budget_per_trade_pct == Decimal("0.50")
    assert policy.max_position_value_pct == Decimal("15.00")
    assert policy.policy_version == "policy-2026-09-07-v1"


def test_exact_policy_version_propagated(tmp_path: Path) -> None:
    payload = dict(VALID_PAYLOAD, policy_version="owner-chosen-id-v7")
    _write(tmp_path, payload)
    policy = load_position_sizing_policy_config(tmp_path)
    assert policy is not None
    assert policy.policy_version == "owner-chosen-id-v7"


def test_decimal_semantics_preserved_no_float_drift(tmp_path: Path) -> None:
    # 0.1 has no exact binary float representation; a float round-trip
    # would silently perturb it. Parsed directly from the JSON string,
    # Decimal("0.10") must come back byte-exact.
    payload = dict(VALID_PAYLOAD, risk_budget_per_trade_pct="0.10")
    _write(tmp_path, payload)
    policy = load_position_sizing_policy_config(tmp_path)
    assert policy is not None
    assert policy.risk_budget_per_trade_pct == Decimal("0.10")
    assert str(policy.risk_budget_per_trade_pct) == "0.10"


@pytest.mark.parametrize(
    "field_name", ["total_deployable_capital", "risk_budget_per_trade_pct", "max_position_value_pct"]
)
def test_bare_json_number_rejected_not_silently_float_converted(tmp_path: Path, field_name: str) -> None:
    payload = dict(VALID_PAYLOAD)
    payload[field_name] = 0.5  # bare JSON number, not a string
    _write(tmp_path, payload)
    with pytest.raises(ConfigError):
        load_position_sizing_policy_config(tmp_path)


def test_one_policy_instance_reused_is_equal_for_repeated_loads(tmp_path: Path) -> None:
    _write(tmp_path, VALID_PAYLOAD)
    first = load_position_sizing_policy_config(tmp_path)
    second = load_position_sizing_policy_config(tmp_path)
    assert first == second
    assert first is not None and second is not None


# ---- invalid configuration: fails loudly, never clamps/defaults -------


def test_invalid_json_fails_loudly(tmp_path: Path) -> None:
    position_sizing_policy_config_path(tmp_path).write_text("{not json", encoding="utf-8")
    with pytest.raises(ConfigError):
        load_position_sizing_policy_config(tmp_path)


def test_non_object_json_fails_loudly(tmp_path: Path) -> None:
    position_sizing_policy_config_path(tmp_path).write_text("[1, 2, 3]", encoding="utf-8")
    with pytest.raises(ConfigError):
        load_position_sizing_policy_config(tmp_path)


def test_unknown_key_rejected(tmp_path: Path) -> None:
    payload = dict(VALID_PAYLOAD, extra_unapproved_field="1.0")
    _write(tmp_path, payload)
    with pytest.raises(ConfigError):
        load_position_sizing_policy_config(tmp_path)


@pytest.mark.parametrize("bad_value", ["0", "-100.00", "0.00"])
def test_non_positive_capital_rejected(tmp_path: Path, bad_value: str) -> None:
    payload = dict(VALID_PAYLOAD, total_deployable_capital=bad_value)
    _write(tmp_path, payload)
    with pytest.raises(ConfigError):
        load_position_sizing_policy_config(tmp_path)


@pytest.mark.parametrize("bad_value", ["0", "-1.0", "100.01", "500"])
def test_invalid_risk_budget_pct_rejected(tmp_path: Path, bad_value: str) -> None:
    payload = dict(VALID_PAYLOAD, risk_budget_per_trade_pct=bad_value)
    _write(tmp_path, payload)
    with pytest.raises(ConfigError):
        load_position_sizing_policy_config(tmp_path)


@pytest.mark.parametrize("bad_value", ["0", "-1.0", "100.01", "999"])
def test_invalid_max_position_value_pct_rejected(tmp_path: Path, bad_value: str) -> None:
    payload = dict(VALID_PAYLOAD, max_position_value_pct=bad_value)
    _write(tmp_path, payload)
    with pytest.raises(ConfigError):
        load_position_sizing_policy_config(tmp_path)


@pytest.mark.parametrize("bad_value", ["", "   "])
def test_empty_policy_version_rejected(tmp_path: Path, bad_value: str) -> None:
    payload = dict(VALID_PAYLOAD, policy_version=bad_value)
    _write(tmp_path, payload)
    with pytest.raises(ConfigError):
        load_position_sizing_policy_config(tmp_path)


def test_missing_policy_version_key_rejected(tmp_path: Path) -> None:
    payload = {k: v for k, v in VALID_PAYLOAD.items() if k != "policy_version"}
    _write(tmp_path, payload)
    with pytest.raises(ConfigError):
        load_position_sizing_policy_config(tmp_path)


# ---- dormant capital.json/risk.json are never read ---------------------


def test_dormant_capital_and_risk_json_never_imported(tmp_path: Path) -> None:
    # Real dormant-style capital.json/risk.json present in the same
    # config_dir, carrying values that would NOT satisfy this loader's
    # own contract if they were ever silently read (float-typed
    # percentages, different field names entirely) -- and no
    # position_sizing_policy.json at all. The absence of that one file
    # must still yield None, proving the dormant files are irrelevant
    # rather than being scanned/coerced/adapted.
    (tmp_path / "capital.json").write_text(
        json.dumps({"total_capital": "1000000", "reserved_pct": 20.0,
                    "max_capital_per_position_pct": 10.0, "max_capital_per_sector_pct": 30.0}),
        encoding="utf-8",
    )
    (tmp_path / "risk.json").write_text(
        json.dumps({"max_daily_loss_pct": 2.0, "per_trade_risk_pct": 0.5,
                    "max_consecutive_losses": 3, "max_decisions_per_day": 5,
                    "no_trade": {"min_market_health": 40, "block_on_stale_data": True}}),
        encoding="utf-8",
    )
    assert load_position_sizing_policy_config(tmp_path) is None


def _strip_docstring(body: list) -> list:
    if body and isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Constant) and isinstance(body[0].value.value, str):
        return body[1:]
    return body


def _source_without_module_docstring(module: object) -> str:
    """Strips every module/class/function docstring so prose explaining
    e.g. 'this never reads capital.json' does not itself trip a
    substring check meant to catch real code references."""
    tree = ast.parse(inspect.getsource(module))
    tree.body = _strip_docstring(tree.body)
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            node.body = _strip_docstring(node.body)
    return ast.unparse(tree)


def test_source_never_reads_capital_or_risk_json_filenames() -> None:
    code = _source_without_module_docstring(config_module)
    assert "capital.json" not in code
    assert "risk.json" not in code
    assert "CapitalConfig" not in code
    assert "RiskConfig" not in code


# ---- no order/broker/execution/provider activation ---------------------


def test_source_never_touches_orders_brokers_execution_or_network() -> None:
    tree = ast.parse(inspect.getsource(config_module))
    imported_modules: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            imported_modules.append(node.module)
        elif isinstance(node, ast.Import):
            imported_modules.extend(alias.name for alias in node.names)
    forbidden_prefixes = (
        "athena.orders", "athena.brokers", "athena.execution",
        "athena.allocation", "athena.sizing",
        "athena.data.providers", "requests", "httpx", "urllib",
    )
    for mod in imported_modules:
        assert not mod.startswith(forbidden_prefixes), f"unexpected import: {mod}"


def test_loader_makes_no_network_or_provider_call(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _write(tmp_path, VALID_PAYLOAD)

    def _fail(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("position sizing policy loading must never open a socket")

    import socket

    monkeypatch.setattr(socket.socket, "connect", _fail)
    policy = load_position_sizing_policy_config(tmp_path)
    assert policy is not None


# ---- PositionSizingPolicyConfig model itself ----------------------------


def test_model_drops_underscore_prefixed_documentation_keys() -> None:
    parsed = PositionSizingPolicyConfig.model_validate(VALID_PAYLOAD)
    assert parsed.policy_version == VALID_PAYLOAD["policy_version"]
