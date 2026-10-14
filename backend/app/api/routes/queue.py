from typing import Optional

import redis.asyncio as redis
from fastapi import APIRouter, Body, Depends, HTTPException
from sqlalchemy.orm import Session
from sse_starlette.sse import EventSourceResponse

from app.api.deps import get_db, get_redis
from app.schemas.queue import JoinQueueRequest
from app.services import queue_service
from app.services.queue_service import (
    LogEntryNotFoundError,
    MissingBranchError,
    QueueEntryNotFoundError,
    UserNotFoundError,
)

router = APIRouter(tags=["Queue"])


@router.post("/join-queue")
async def join_queue(
    request: JoinQueueRequest,
    db: Session = Depends(get_db),
    r: redis.Redis = Depends(get_redis),
):
    user_id = await queue_service.join_queue(r, db, request)
    return {"message": "Joined queue successfully", "user_id": user_id}


@router.get("/live-queue/{service_type}")
async def live_queue(service_type: str, r: redis.Redis = Depends(get_redis)):
    user_ids = await queue_service.get_queue_ids(r, service_type)
    if not user_ids:
        return {"service_type": service_type, "message": "No tokens in queue"}

    return {
        "service_type": service_type,
        "queue": await queue_service.enrich_queue(r, user_ids, service_type),
    }


@router.put("/update-status")
async def update_status(
    user_id: str = Body(...),
    new_status: str = Body(...),
    r: redis.Redis = Depends(get_redis),
):
    try:
        await queue_service.update_status(r, user_id, new_status)
    except UserNotFoundError:
        raise HTTPException(status_code=404, detail="User not found in queue")
    except MissingBranchError:
        raise HTTPException(status_code=400, detail="Branch ID not found for user")

    return {"message": f"Status for {user_id} updated to {new_status}"}


@router.delete("/remove-log")
async def remove_log(user_id: str, name: Optional[str] = None, db: Session = Depends(get_db)):
    try:
        queue_service.remove_log(db, user_id, name)
    except LogEntryNotFoundError:
        raise HTTPException(status_code=404, detail="Entry not found")

    return {"message": f"Log for {user_id} removed"}


@router.delete("/remove-from-queue")
async def remove_from_queue(branch_id: str, user_id: str, r: redis.Redis = Depends(get_redis)):
    try:
        removed_count = await queue_service.remove_from_queue(r, branch_id, user_id)
    except QueueEntryNotFoundError:
        raise HTTPException(status_code=404, detail=f"{user_id} not found in queue")

    return {"message": f"{user_id} removed from queue", "removed_count": removed_count}


@router.get("/live-queue-stream/{service_type}")
async def live_queue_stream(service_type: str, r: redis.Redis = Depends(get_redis)):
    return EventSourceResponse(
        queue_service.queue_event_stream(r, service_type),
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "Content-Type": "text/event-stream",
            "Access-Control-Allow-Origin": "*"
        }
    )
