"""Provider-independent data Validation Layer (M1.3).

First line of data-quality assurance before any market intelligence consumes
market data. Consumes canonical domain objects, returns immutable validation
results. No provider/file/SQLite/broker awareness.
"""

from athena.data.validation.dataset_validator import DatasetValidator
from athena.data.validation.quarantine import QuarantineRecord, QuarantineRegistry
from athena.data.validation.reports import (
    Severity,
    ValidationReport,
    ValidationResult,
    ValidationSummary,
    ValidationType,
)
from athena.data.validation.validators import (
    validate_daily_gaps,
    validate_duplicates,
    validate_freshness,
    validate_intraday_gaps,
    validate_ohlc,
    validate_quotes,
)

__all__ = [
    "DatasetValidator",
    "QuarantineRecord",
    "QuarantineRegistry",
    "Severity",
    "ValidationReport",
    "ValidationResult",
    "ValidationSummary",
    "ValidationType",
    "validate_daily_gaps",
    "validate_duplicates",
    "validate_freshness",
    "validate_intraday_gaps",
    "validate_ohlc",
    "validate_quotes",
]
