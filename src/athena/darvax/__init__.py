"""DarvaX — an isolated, opt-in satellite module (ADR-010).

DarvaX is a *parallel advisory lane*, never an input to ATHENA's scoring,
confidence, risk, Decision, TradePlan, universe, or decision pipeline. It
reads ATHENA's market data through a narrow read-only port, keeps its own
database file, and exposes its own sub-application.

Dependency direction is one-way and enforced by tests:

    ATHENA read contracts -> DarvaxMarketDataPort -> DarvaX

No module under ``src/athena/`` outside this package imports ``athena.darvax``,
except the single guarded mount seam in ``athena.api.darvax_mount``.

DX-1 scope: isolation foundation only. This package deliberately contains
**zero** trading/methodology logic — no Darvas boxes, EMAs, Fibonacci, swing
detection, ATH detection, volume expansion, range contraction, signal
generation, stop policies, or backtesting. Those arrive in DX-2 onwards, each
behind its own owner approval gate.
"""

from __future__ import annotations

#: DarvaX module version, independent of ATHENA's own version.
__version__ = "0.1.0"

__all__ = ["__version__"]
