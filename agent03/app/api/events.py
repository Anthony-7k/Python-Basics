from __future__ import annotations

import asyncio
import json

from fastapi import APIRouter, Depends, Header, Request
from fastapi.responses import StreamingResponse

from app.api.dependencies import get_principal
from app.domain import JobStatus
from app.repositories import TenantRepository
from app.security.tokens import Principal

router = APIRouter(tags=["jobs"])


@router.get("/jobs/{job_id}/events")
def job_events(
    job_id: str,
    request: Request,
    last_event_id: str | None = Header(default=None, alias="Last-Event-ID"),
    principal: Principal = Depends(get_principal),
):
    with request.app.state.database.session_factory() as session:
        TenantRepository(session, principal.tenant_id).get_job(job_id)
    try:
        start_sequence = max(0, int(last_event_id or 0))
    except ValueError:
        start_sequence = 0

    async def stream():
        sequence = start_sequence
        while True:
            if await request.is_disconnected():
                break
            with request.app.state.database.session_factory() as session:
                repo = TenantRepository(session, principal.tenant_id)
                job = repo.get_job(job_id)
                events = repo.list_events(job_id, sequence)
                for event in events:
                    sequence = event.sequence
                    envelope = {
                        "event_id": event.id,
                        "event_type": event.event_type,
                        "tenant_id": event.tenant_id,
                        "case_id": event.case_id,
                        "job_id": event.job_id,
                        "trace_id": event.trace_id,
                        "occurred_at": event.occurred_at.isoformat(),
                        "schema_version": event.schema_version,
                        "payload": event.payload,
                    }
                    yield f"id: {event.sequence}\nevent: {event.event_type}\ndata: {json.dumps(envelope)}\n\n"
                if JobStatus(job.status) in {JobStatus.SUCCEEDED, JobStatus.FAILED} and not events:
                    break
            await asyncio.sleep(0.25)

    return StreamingResponse(
        stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )

