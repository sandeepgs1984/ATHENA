"""EM-6B: the isolated, read-only Explosive Move Radar (EMR) presentation
route.

The only ATHENA API surface that knows EMR exists. It depends on
`EmrPresentationService` alone (which itself depends only on
`athena.explosive_move.live.presentation`, EM-6A) -- never on
`athena.decision`/`athena.risk`/`athena.portfolio`/`athena.scoring`/
`athena.intraday`/`athena.darvax`, and never on ATHENA's own
`SqliteRepository`/`db/athena.db`. Read-only: no mutation endpoint of any
kind lives here or ever should (ADR-012).

EM-6B.1: captures exactly one `datetime.now(tz=timezone.utc)` per
request, reused for both the service call (scan-age computation) and
`ResponseMeta.as_of` -- never two independent clock reads for one
response, in the populated case or the empty-scan case alike.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime

from fastapi import APIRouter, Depends, Request, status

from athena.api.dependencies import get_emr_presentation_service, get_emr_request_clock
from athena.api.security import Permission, RequirePermission
from athena.api.security.models import AuthenticatedPrincipal
from athena.api.v1.dtos import AthenaResponse, ResponseMeta
from athena.api.v1.dtos.emr import EmrTouch10RadarDTO
from athena.api.v1.services.emr_presentation_service import EmrPresentationService

router = APIRouter(prefix="/emr", tags=["Explosive Move Radar (Experimental)"])


@router.get(
    "/experimental/touch-10-radar",
    response_model=AthenaResponse[EmrTouch10RadarDTO],
    summary="Get the latest persisted EMR TOUCH-10 research radar (Experimental, read-only)",
    status_code=status.HTTP_200_OK,
    operation_id="getEmrTouch10Radar",
)
def get_emr_touch_10_radar(
    request: Request,
    session_date: str | None = None,
    service: EmrPresentationService = Depends(get_emr_presentation_service),  # noqa: B008
    clock: Callable[[], datetime] = Depends(get_emr_request_clock),  # noqa: B008
    principal: AuthenticatedPrincipal = Depends(RequirePermission(Permission.READ)),  # noqa: B008
) -> AthenaResponse[EmrTouch10RadarDTO]:
    """Read-only. Returns the latest persisted, `COMPLETE` EMR scan's
    TOUCH-10 candidates, coverage, and scan-age -- or a well-defined
    empty state if no completed scan exists. Never runs the scanner,
    never mutates `db/emr.db`, never calls a provider.

    Exactly one clock read for this whole request: `request_as_of` below
    drives both the service's scan-age computation and
    `ResponseMeta.as_of` -- applies in the empty-scan branch too, since
    the service always receives it regardless of whether a scan exists."""
    request_as_of = clock()
    data = service.get_touch_10_radar(session_date=session_date, request_as_of=request_as_of)
    request_id = getattr(request.state, "request_id", "unknown")

    meta = ResponseMeta(
        request_id=request_id,
        api_version="v1",
        as_of=request_as_of,
    )

    return AthenaResponse(status="success", data=data, meta=meta)
