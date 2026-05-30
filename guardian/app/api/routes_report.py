"""Guardian report API: build the status report on demand (optionally send it)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request

from guardian.app.auth import require_api
from guardian.app.reporting import GuardianReportResult

router = APIRouter(tags=["report"])


@router.get("/report", response_model=GuardianReportResult)
async def report(request: Request, send: bool = False, _: None = Depends(require_api)) -> GuardianReportResult:
    service = request.app.state.report_service
    return await service.generate_and_send(send=send)
