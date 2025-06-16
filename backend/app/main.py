# Qtrack-app/backend/app/main.py

from fastapi import FastAPI, Depends
from app.services.redis_client import r
from app.models.schemas import JoinQueueRequest
from app.services.db import SessionLocal
from app.models.db_models import QueueLog
from app.models import db_models
from app.services.db import engine
import uuid
from fastapi import Body
from fastapi import HTTPException
from typing import Optional
from fastapi import Request
from sse_starlette.sse import EventSourceResponse
import asyncio
import json

app = FastAPI()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@app.get("/health-check")
def root():
    return {"message": "QTrack backend is working!"}

@app.post("/join-queue")
async def join_queue(request: JoinQueueRequest, db=Depends(get_db)):
    user_id = f"user_{uuid.uuid4().hex[:8]}"
    queue_key = f"queue:{request.branch_id}"
    user_key = f"user:{user_id}"

    # 1. Push to Redis
    await r.rpush(queue_key, user_id)
    await r.hset(user_key, mapping={
        "name": request.name,
        "phone": request.phone,
        "branch_id": request.branch_id,
        "status": "waiting"
    })

    # ✅ Publish update to Redis stream channel
    await r.publish(f"queue_updates:{request.branch_id}", "update")

    # 2. Log to PostgreSQL
    log_entry = QueueLog(
        user_id=user_id,
        branch_id=request.branch_id,
        status="waiting"
    )
    db.add(log_entry)
    db.commit()

    return {
        "message": "Joined queue successfully",
        "user_id": user_id
    }



@app.get("/live-queue/{branch_id}")
async def live_queue(branch_id: str):
    queue_key = f"queue:{branch_id}"
    length = await r.llen(queue_key)

    if length == 0:
        return {
            "branch_id": branch_id,
            "message": "No tokens in queue"
        }

    queue = await r.lrange(queue_key, 0, -1)
    enriched_queue = []

    for user_id in queue:
        user_key = f"user:{user_id}"
        user_data = await r.hgetall(user_key)
        enriched_queue.append({
            "user_id": user_id,
            "name": user_data.get("name", "Unknown"),
            "joined_at": user_data.get("joined_at", "Unknown"),
            "status": user_data.get("status", "Unknown")
        })

    return {
        "branch_id": branch_id,
        "queue": enriched_queue
    }
@app.put("/update-status")
async def update_status(user_id: str = Body(...), new_status: str = Body(...)):
    user_key = f"user:{user_id}"

    exists = await r.exists(user_key)
    if not exists:
        raise HTTPException(status_code=404, detail="User not found in queue")

    await r.hset(user_key, "status", new_status)

    # ✅ Get branch_id to publish update
    user_data = await r.hgetall(user_key)
    branch_id = user_data.get("branch_id")
    if branch_id:
        # await r.publish(f"queue_updates:{branch_id}", "update")
        await r.xadd(f"queue_stream:{branch_id}", {
    "event": "status_update",
    "user_id": user_id,
    "new_status": new_status,
    
})


    return {"message": f"Status for {user_id} updated to {new_status}"}

@app.delete("/remove-log")
async def remove_log(user_id: str, name: Optional[str] = None, db=Depends(get_db)):
    query = db.query(QueueLog).filter(QueueLog.user_id == user_id)
    
    if name:
        query = query.filter(QueueLog.user_id == user_id)

    entry = query.first()

    if not entry:
        raise HTTPException(status_code=404, detail="Entry not found")

    db.delete(entry)
    db.commit()
    return {"message": f"Log for {user_id} removed"}

@app.delete("/remove-from-queue")
async def remove_from_queue(branch_id: str, user_id: str):
    queue_key = f"queue:{branch_id}"

    removed_count = await r.lrem(queue_key, 0, user_id)  # Remove all occurrences of user_id

    if removed_count == 0:
        raise HTTPException(status_code=404, detail=f"{user_id} not found in queue")

    # Optionally, clean up user data hash from Redis
    await r.delete(f"user:{user_id}")

    # ✅ Publish update to Redis stream channel
    await r.publish(f"queue_updates:{branch_id}", "update")

    

    return {
        "message": f"{user_id} removed from queue:{branch_id}",
        "removed_count": removed_count
    }
@app.get("/live-queue-stream/{branch_id}")
async def live_queue_stream(branch_id: str):
    queue_key = f"queue:{branch_id}"
    stream_key = f"queue_stream:{branch_id}"

    async def event_generator():
        # 1️⃣ Send initial payload once
        queue_ids = await r.lrange(queue_key, 0, -1)
        queue_data = []

        for user_id in queue_ids:
            user_data = await r.hgetall(f"user:{user_id}")
            if user_data:
                queue_data.append({
                    "user_id": user_id,
                    "name": user_data.get("name", "Unknown"),
                    "status": user_data.get("status", "waiting"),
                    "joined_at": user_data.get("joined_at", "Unknown")
                })

        yield f"data: {json.dumps({'branch_id': branch_id, 'queue': queue_data})}\n\n"

        # 2️⃣ Start listening to Redis Stream for new messages
        last_id = '$'  # '$' means: only new messages from now on

        try:
            while True:
                response = await r.xread({stream_key: last_id}, block=0)  # Wait indefinitely
                if response:
                    _, messages = response[0]
                    for msg_id, msg_data in messages:
                        last_id = msg_id  # Advance to next message ID

                        # 🔁 Refresh full queue and send
                        queue_ids = await r.lrange(queue_key, 0, -1)
                        queue_data = []
                        for user_id in queue_ids:
                            user_data = await r.hgetall(f"user:{user_id}")
                            if user_data:
                                queue_data.append({
                                    "user_id": user_id,
                                    "name": user_data.get("name", "Unknown"),
                                    "status": user_data.get("status", "waiting"),
                                    "joined_at": user_data.get("joined_at", "Unknown")
                                })

                        yield f"data: {json.dumps({'branch_id': branch_id, 'queue': queue_data})}\n\n"

        except asyncio.CancelledError:
            raise

    return EventSourceResponse(event_generator())

   
db_models.Base.metadata.create_all(bind=engine)