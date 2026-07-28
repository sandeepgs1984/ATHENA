"""NSE live InstitutionalFlowProvider (ADR-008 / DD-11).

Fetches the official NSE FII/FPI & DII Capital Market JSON. Failure raises
ProviderError — callers must treat that as unknown institutional strength,
never abort the daily cycle.
"""

from __future__ import annotations

import json
import re
from datetime import date, datetime, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Callable
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from athena.config.models import InstitutionalNseProviderConfig
from athena.domain.enums import HealthStatus
from athena.domain.interfaces import ProviderHealth
from athena.domain.market import InstitutionalFlowSession
from athena.errors import ProviderError

_MONTHS = {
    "Jan": 1, "Feb": 2, "Mar": 3, "Apr": 4, "May": 5, "Jun": 6,
    "Jul": 7, "Aug": 8, "Sep": 9, "Oct": 10, "Nov": 11, "Dec": 12,
}
_DATE_RE = re.compile(r"^(\d{1,2})-([A-Za-z]{3})-(\d{4})$")


def parse_nse_flow_date(raw: str) -> date:
    text = raw.strip()
    match = _DATE_RE.match(text)
    if not match:
        raise ValueError(f"unrecognized NSE flow date: {raw!r}")
    day, mon, year = match.groups()
    month = _MONTHS.get(mon.title())
    if month is None:
        raise ValueError(f"unrecognized NSE flow month: {mon!r}")
    return date(int(year), month, int(day))


def _money(raw: object, field: str) -> Decimal:
    text = str(raw).replace(",", "").strip()
    try:
        return Decimal(text)
    except (InvalidOperation, AttributeError) as exc:
        raise ProviderError(f"invalid NSE {field}: {raw!r}") from exc


def parse_nse_fiidii_payload(
    payload: object,
    *,
    fetched_at: datetime,
    source_id: str = "nse",
) -> list[InstitutionalFlowSession]:
    """Parse NSE fiidiiTradeReact JSON into one session per unique date."""
    if not isinstance(payload, list):
        raise ProviderError("NSE FII/DII payload must be a JSON array")
    by_date: dict[date, dict[str, Decimal | bool]] = {}
    for row in payload:
        if not isinstance(row, dict):
            continue
        category = str(row.get("category") or row.get("Category") or "").upper()
        date_raw = row.get("date") or row.get("Date")
        if not date_raw:
            continue
        try:
            session_date = parse_nse_flow_date(str(date_raw))
        except ValueError as exc:
            raise ProviderError(str(exc)) from exc
        bucket = by_date.setdefault(
            session_date,
            {
                "fii_buy": Decimal("0"), "fii_sell": Decimal("0"), "fii_net": Decimal("0"),
                "dii_buy": Decimal("0"), "dii_sell": Decimal("0"), "dii_net": Decimal("0"),
                "seen_fii": False, "seen_dii": False,
            },
        )
        buy = _money(row.get("buyValue") or row.get("buyVal") or 0, "buyValue")
        sell = _money(row.get("sellValue") or row.get("sellVal") or 0, "sellValue")
        net = _money(row.get("netValue") or row.get("netVal") or (buy - sell), "netValue")
        if "FII" in category or "FPI" in category:
            bucket["fii_buy"] = buy
            bucket["fii_sell"] = sell
            bucket["fii_net"] = net
            bucket["seen_fii"] = True
        elif "DII" in category:
            bucket["dii_buy"] = buy
            bucket["dii_sell"] = sell
            bucket["dii_net"] = net
            bucket["seen_dii"] = True
    sessions: list[InstitutionalFlowSession] = []
    for session_date, vals in sorted(by_date.items()):
        if not vals["seen_fii"] and not vals["seen_dii"]:
            continue
        sessions.append(
            InstitutionalFlowSession(
                session_date=session_date,
                fii_buy=vals["fii_buy"],  # type: ignore[arg-type]
                fii_sell=vals["fii_sell"],  # type: ignore[arg-type]
                fii_net=vals["fii_net"],  # type: ignore[arg-type]
                dii_buy=vals["dii_buy"],  # type: ignore[arg-type]
                dii_sell=vals["dii_sell"],  # type: ignore[arg-type]
                dii_net=vals["dii_net"],  # type: ignore[arg-type]
                provisional=True,  # NSE same-day figures are provisional (DD-11)
                source_id=source_id,
                fetched_at=fetched_at,
            )
        )
    return sessions


class NseInstitutionalFlowProvider:
    """Live NSE Capital Market FII/DII report adapter."""

    name = "institutional_nse"

    def __init__(
        self,
        config: InstitutionalNseProviderConfig,
        *,
        urlopen_fn: Callable[..., object] | None = None,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._config = config
        self._urlopen = urlopen_fn or urlopen
        self._clock = clock or (lambda: datetime.now(timezone.utc))

    @classmethod
    def from_config_dir(cls, config_dir: Path) -> NseInstitutionalFlowProvider:
        from athena.config.loader import load_institutional_nse_provider_config

        return cls(load_institutional_nse_provider_config(config_dir))

    def latest_session(self) -> InstitutionalFlowSession:
        sessions = self._fetch_sessions()
        if not sessions:
            raise ProviderError("NSE FII/DII response contained no cash-market rows")
        return max(sessions, key=lambda s: s.session_date)

    def sessions(self, start: date, end: date) -> list[InstitutionalFlowSession]:
        if start > end:
            raise ProviderError(f"invalid institutional flow range: {start} > {end}")
        return [s for s in self._fetch_sessions() if start <= s.session_date <= end]

    def health(self) -> ProviderHealth:
        try:
            latest = self.latest_session()
        except ProviderError as exc:
            return ProviderHealth(status=HealthStatus.WARN, detail=str(exc))
        return ProviderHealth(
            status=HealthStatus.OK,
            detail=f"NSE institutional flow session {latest.session_date.isoformat()}",
            last_data_ts=latest.fetched_at,
        )

    def _fetch_sessions(self) -> list[InstitutionalFlowSession]:
        # Warm-up cookie jar: NSE often requires a homepage hit first.
        self._get(self._config.home_url, accept="text/html")
        body = self._get(self._config.api_url, accept="application/json")
        try:
            payload = json.loads(body)
        except json.JSONDecodeError as exc:
            raise ProviderError(f"NSE FII/DII response is not JSON: {exc}") from exc
        return parse_nse_fiidii_payload(
            payload, fetched_at=self._clock(), source_id=self._config.source_id
        )

    def _get(self, url: str, *, accept: str) -> str:
        headers = {
            "User-Agent": self._config.user_agent,
            "Accept": accept,
            "Referer": self._config.home_url,
        }
        request = Request(url, headers=headers, method="GET")
        try:
            with self._urlopen(request, timeout=self._config.timeout_seconds) as resp:
                raw = resp.read()
        except HTTPError as exc:
            raise ProviderError(f"NSE HTTP {exc.code} for {url}") from exc
        except URLError as exc:
            raise ProviderError(f"NSE network error for {url}: {exc.reason}") from exc
        if isinstance(raw, bytes):
            return raw.decode("utf-8", errors="replace")
        return str(raw)
