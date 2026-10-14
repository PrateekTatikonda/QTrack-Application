"""Queue business logic: Redis queue state, Redis Streams events and Postgres logging."""

import asyncio
import json
import logging
import uuid
from datetime import datetime
from typing import AsyncIterator, Optional

import redis.asyncio as redis
from sqlalchemy.orm import Session

from app.models.queue_log import QueueLog
from app.schemas.queue import JoinQueueRequest

logger = logging.getLogger(__name__)

# How long a stream reader blocks waiting for events before sending a heartbeat.
STREAM_BLOCK_MS = 30000


class UserNotFoundError(Exception):
    pass


class MissingBranchError(Exception):
    pass


class QueueEntryNotFoundError(Exception):
    pass


class LogEntryNotFoundError(Exception):
    pass


def _now_iso() -> str:
    return datetime.utcnow().isoformat()


def _queue_key(name: str) -> str:
    return f"queue:{name}"


def _stream_key(name: str) -> str:
    return f"queue_stream:{name}"


def _user_key(user_id: str) -> str:
    return f"user:{user_id}"


async def get_queue_ids(r: redis.Redis, service_type: str) -> list[str]:
    """Return queued user IDs, merging the lowercase key with a legacy original-case key."""
    queue_original = (
        await r.lrange(_queue_key(service_type), 0, -1)
        if service_type != service_type.lower()
        else []
    )
    queue_lower = await r.lrange(_queue_key(service_type.lower()), 0, -1)
    return list(queue_lower) + [uid for uid in queue_original if uid not in queue_lower]


async def enrich_queue(r: redis.Redis, user_ids: list[str], service_type: str) -> list[dict]:
    enriched = []
    for user_id in user_ids:
        user_data = await r.hgetall(_user_key(user_id))
        if user_data:
            enriched.append({
                "user_id": user_id,
                "name": user_data.get("name", "Unknown"),
                "service_type": user_data.get("service_type", service_type.lower()),
                "branch_id": user_data.get("branch_id", "main"),
                "joined_at": user_data.get("joined_at", "Unknown"),
                "status": user_data.get("status", "waiting"),
            })
    return enriched


async def get_queue_snapshot(r: redis.Redis, service_type: str) -> dict:
    return {
        "service_type": service_type,
        "queue": await enrich_queue(r, await get_queue_ids(r, service_type), service_type),
        "timestamp": _now_iso(),
    }


async def join_queue(r: redis.Redis, db: Session, request: JoinQueueRequest) -> str:
    user_id = f"user_{uuid.uuid4().hex[:8]}"
    requested_service = (request.service_type or "").strip().lower()
    if not requested_service or requested_service == "general":
        requested_service = (request.branch_id or "general").strip().lower()

    await r.rpush(_queue_key(requested_service), user_id)
    await r.hset(_user_key(user_id), mapping={
        "name": request.name,
        "phone": request.phone,
        "branch_id": request.branch_id,
        "service_type": requested_service,
        "status": "waiting",
        "joined_at": _now_iso(),
    })

    await r.xadd(_stream_key(requested_service), {
        "event": "join_queue",
        "user_id": user_id,
        "name": request.name,
        "action": "added",
        "timestamp": _now_iso(),
    })

    db.add(QueueLog(user_id=user_id, branch_id=request.branch_id, status="waiting"))
    db.commit()

    return user_id


async def update_status(r: redis.Redis, user_id: str, new_status: str) -> None:
    user_key = _user_key(user_id)
    if not await r.exists(user_key):
        raise UserNotFoundError(user_id)

    user_data = await r.hgetall(user_key)
    branch_id = user_data.get("branch_id")
    service_type = (user_data.get("service_type") or "").strip().lower()

    if not branch_id:
        raise MissingBranchError(user_id)

    await r.hset(user_key, "status", new_status)

    # Publish to every compatible stream key so all connected SSE clients update.
    stream_keys = {_stream_key(branch_id), _stream_key(branch_id.lower())}
    if service_type:
        stream_keys.add(_stream_key(service_type))

    event_payload = {
        "event": "status_update",
        "user_id": user_id,
        "new_status": new_status,
        "name": user_data.get("name", "Unknown"),
        "timestamp": _now_iso(),
    }
    for stream_key in stream_keys:
        await r.xadd(stream_key, event_payload)


async def remove_from_queue(r: redis.Redis, branch_id: str, user_id: str) -> int:
    user_key = _user_key(user_id)
    user_data = await r.hgetall(user_key)
    if not user_data:
        raise QueueEntryNotFoundError(user_id)

    user_name = user_data.get("name", "Unknown")
    service_type = (user_data.get("service_type") or "").strip().lower()

    queue_keys = {_queue_key(branch_id), _queue_key(branch_id.lower())}
    if service_type:
        queue_keys.add(_queue_key(service_type))

    removed_count = 0
    for queue_key in queue_keys:
        removed_count += await r.lrem(queue_key, 0, user_id)

    if removed_count == 0:
        raise QueueEntryNotFoundError(user_id)

    await r.delete(user_key)

    stream_keys = {_stream_key(branch_id), _stream_key(branch_id.lower())}
    if service_type:
        stream_keys.add(_stream_key(service_type))

    event_payload = {
        "event": "remove_from_queue",
        "user_id": user_id,
        "name": user_name,
        "action": "removed",
        "timestamp": _now_iso(),
    }
    for stream_key in stream_keys:
        await r.xadd(stream_key, event_payload)

    return removed_count


def remove_log(db: Session, user_id: str, name: Optional[str] = None) -> None:
    # `name` is accepted for API compatibility but not used for filtering yet (docs/PLAN.md F9).
    entry = db.query(QueueLog).filter(QueueLog.user_id == user_id).first()
    if not entry:
        raise LogEntryNotFoundError(user_id)

    db.delete(entry)
    db.commit()


async def queue_event_stream(r: redis.Redis, service_type: str) -> AsyncIterator[str]:
    """Yield SSE payloads: an initial snapshot, then a fresh snapshot per stream event."""
    stream_key_lower = _stream_key(service_type.lower())
    stream_key_original = _stream_key(service_type)

    try:
        yield f"data: {json.dumps(await get_queue_snapshot(r, service_type))}\n\n"

        last_id_lower = "$"
        last_id_original = "$"

        while True:
            try:
                streams_to_check = {}
                if service_type != service_type.lower():
                    streams_to_check[stream_key_original] = last_id_original
                streams_to_check[stream_key_lower] = last_id_lower

                response = await r.xread(streams_to_check, block=STREAM_BLOCK_MS, count=1)

                if response:
                    for stream_name, messages in response:
                        for msg_id, _msg_data in messages:
                            if stream_name == stream_key_lower:
                                last_id_lower = msg_id
                            else:
                                last_id_original = msg_id

                            yield f"data: {json.dumps(await get_queue_snapshot(r, service_type))}\n\n"
                else:
                    yield ": heartbeat\n\n"

            except Exception as e:
                logger.error("SSE Error: %s", e)
                await asyncio.sleep(5)

    except asyncio.CancelledError:
        return
    except Exception:
        yield f"data: {json.dumps({'error': 'Connection lost'})}\n\n"
