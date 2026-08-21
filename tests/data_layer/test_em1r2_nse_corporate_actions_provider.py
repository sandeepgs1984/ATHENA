"""EM-1r2 official NSE corporate-action retrieval boundary tests."""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, date, datetime
from pathlib import Path

import pytest

from athena.data.providers.nse_corporate_actions_provider import (
    CapturedNseCorporateActionsProvider,
    NseCorporateActionsProvider,
)
from athena.errors import ProviderError


class _Response:
    def __init__(self, body: bytes, content_type: str) -> None:
        self._body = body
        self.headers = {"Content-Type": content_type}

    def __enter__(self):
        return self

    def __exit__(self, *_args) -> None:
        return None

    def read(self) -> bytes:
        return self._body


def test_provider_requests_exact_interval_and_records_official_provenance() -> None:
    requests = []
    payload = json.dumps(
        [
            {
                "symbol": "AAA",
                "series": "EQ",
                "isin": "INE000A01001",
                "exDate": "03-Jun-2024",
                "subject": "Bonus 1:1",
            }
        ]
    ).encode()

    def fake_urlopen(request, *, timeout):
        requests.append((request, timeout))
        if request.full_url == NseCorporateActionsProvider.FILINGS_URL:
            return _Response(b"ok", "text/html")
        return _Response(payload, "application/json; charset=utf-8")

    retrieved = NseCorporateActionsProvider(
        urlopen_fn=fake_urlopen,
        clock=lambda: datetime(2026, 8, 21, 6, tzinfo=UTC),
    ).retrieve(date(2024, 6, 1), date(2024, 6, 30))

    assert len(requests) == 2
    assert "from_date=01-06-2024" in requests[1][0].full_url
    assert "to_date=30-06-2024" in requests[1][0].full_url
    assert "index=equities" in requests[1][0].full_url
    assert requests[1][0].headers["Accept"] == "application/json"
    assert requests[1][0].headers["Referer"] == NseCorporateActionsProvider.FILINGS_URL
    assert retrieved.complete is True
    assert retrieved.parsed.rows[0].source_url == retrieved.source_url
    assert retrieved.parsed.rows[0].payload_sha256 == retrieved.parsed.payload_sha256


@pytest.mark.parametrize(
    ("body", "content_type", "message"),
    [
        (b"<html>blocked</html>", "text/html", "not JSON"),
        (b'{"data": []}', "application/json", "must be a JSON array"),
        (b"not-json", "application/json", "invalid official NSE"),
    ],
)
def test_provider_fails_loudly_on_non_authoritative_response_shapes(
    body: bytes, content_type: str, message: str
) -> None:
    calls = 0

    def fake_urlopen(_request, *, timeout):
        nonlocal calls
        calls += 1
        if calls == 1:
            return _Response(b"ok", "text/html")
        return _Response(body, content_type)

    provider = NseCorporateActionsProvider(urlopen_fn=fake_urlopen)
    with pytest.raises(ProviderError, match=message):
        provider.retrieve(date(2024, 6, 1), date(2024, 6, 30))


def test_provider_marks_out_of_interval_rows_incomplete() -> None:
    payload = json.dumps(
        [
            {
                "symbol": "AAA",
                "series": "EQ",
                "exDate": "01-Jul-2024",
                "subject": "Bonus 1:1",
            }
        ]
    ).encode()
    calls = 0

    def fake_urlopen(_request, *, timeout):
        nonlocal calls
        calls += 1
        return _Response(
            b"ok" if calls == 1 else payload,
            "text/html" if calls == 1 else "application/json",
        )

    retrieved = NseCorporateActionsProvider(urlopen_fn=fake_urlopen).retrieve(
        date(2024, 6, 1), date(2024, 6, 30)
    )

    assert retrieved.complete is False
    assert "outside" in retrieved.completeness_basis


def test_captured_provider_replays_exact_checksum_verified_interval(tmp_path: Path) -> None:
    body = json.dumps(
        [
            {
                "symbol": "AAA",
                "series": "EQ",
                "exDate": "03-Jun-2024",
                "subject": "Bonus 1:1",
            }
        ]
    ).encode()
    digest = hashlib.sha256(body).hexdigest()
    raw = tmp_path / "raw" / f"{digest}.json"
    raw.parent.mkdir()
    raw.write_bytes(body)
    manifest = tmp_path / "manifest.json"
    manifest.write_text(
        json.dumps(
            {
                "retrieval_slices": [
                    {
                        "requested_start": "2024-06-01",
                        "requested_end": "2024-06-30",
                        "retrieved_at": "2026-08-21T06:00:00+00:00",
                        "source_url": NseCorporateActionsProvider.API_URL,
                        "payload_sha256": digest,
                        "raw_artifact": f"raw/{digest}.json",
                        "complete": True,
                        "completeness_basis": "captured exact interval",
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    retrieved = CapturedNseCorporateActionsProvider(
        source_manifest=manifest,
        evidence_root=tmp_path,
    ).retrieve(date(2024, 6, 1), date(2024, 6, 30))

    assert retrieved.body == body
    assert retrieved.parsed.payload_sha256 == digest
    assert retrieved.complete is True


def test_captured_provider_rejects_checksum_mismatch(tmp_path: Path) -> None:
    raw = tmp_path / "raw" / "payload.json"
    raw.parent.mkdir()
    raw.write_bytes(b"[]")
    manifest = tmp_path / "manifest.json"
    manifest.write_text(
        json.dumps(
            {
                "retrieval_slices": [
                    {
                        "requested_start": "2024-06-01",
                        "requested_end": "2024-06-30",
                        "retrieved_at": "2026-08-21T06:00:00+00:00",
                        "source_url": NseCorporateActionsProvider.API_URL,
                        "payload_sha256": "0" * 64,
                        "raw_artifact": "raw/payload.json",
                        "complete": True,
                        "completeness_basis": "captured exact interval",
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    provider = CapturedNseCorporateActionsProvider(
        source_manifest=manifest,
        evidence_root=tmp_path,
    )
    with pytest.raises(ProviderError, match="checksum mismatch"):
        provider.retrieve(date(2024, 6, 1), date(2024, 6, 30))
