from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
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
from fastapi import APIRouter, BackgroundTasks
from fastapi.responses import StreamingResponse
from app.services.redis_client import redis
import asyncio
import json
from datetime import datetime
import signal
import sys

app = FastAPI()

# Add signal handlers for graceful shutdown
def signal_handler(signum, frame):
    print(f"\nReceived signal {signum}. Shutting down gracefully...")
    sys.exit(0)

signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173", "http://localhost:3000", "*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

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
        "status": "waiting",
        "joined_at": datetime.utcnow().isoformat()
    })

    # 2. Publish update to Redis Stream (consistent approach)
    stream_key = f"queue_stream:{request.branch_id}"
    await r.xadd(stream_key, {
        "event": "join_queue",
        "user_id": user_id,
        "name": request.name,
        "action": "added",
        "timestamp": datetime.utcnow().isoformat()
    })

    # 3. Log to PostgreSQL
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

    # Get user data before updating
    user_data = await r.hgetall(user_key)
    branch_id = user_data.get("branch_id")
    
    if not branch_id:
        raise HTTPException(status_code=400, detail="Branch ID not found for user")

    # Update status
    await r.hset(user_key, "status", new_status)

    # Publish update to Redis Stream
    stream_key = f"queue_stream:{branch_id}"
    await r.xadd(stream_key, {
        "event": "status_update",
        "user_id": user_id,
        "new_status": new_status,
        "name": user_data.get("name", "Unknown"),
        "timestamp": datetime.utcnow().isoformat()
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
    user_key = f"user:{user_id}"

    # Get user data before removal for the stream event
    user_data = await r.hgetall(user_key)
    user_name = user_data.get("name", "Unknown")

    removed_count = await r.lrem(queue_key, 0, user_id)  # Remove all occurrences of user_id

    if removed_count == 0:
        raise HTTPException(status_code=404, detail=f"{user_id} not found in queue")

    # Clean up user data hash from Redis
    await r.delete(user_key)

    # Publish update to Redis Stream
    stream_key = f"queue_stream:{branch_id}"
    await r.xadd(stream_key, {
        "event": "remove_from_queue",
        "user_id": user_id,
        "name": user_name,
        "action": "removed",
        "timestamp": datetime.utcnow().isoformat()
    })

    return {
        "message": f"{user_id} removed from queue:{branch_id}",
        "removed_count": removed_count
    }

@app.get("/live-queue-stream/{branch_id}")
async def live_queue_stream(branch_id: str):
    queue_key = f"queue:{branch_id}"
    stream_key = f"queue_stream:{branch_id}"

    async def event_generator():
        try:
            # Send initial payload once
            initial_queue_data = await get_current_queue_data(branch_id, queue_key)
            yield f"data: {json.dumps(initial_queue_data)}\n\n"

            # Start listening to Redis Stream
            last_id = '$'  # Only new messages from now on

            while True:
                try:
                    # Read from stream with longer timeout to reduce pings
                    response = await r.xread({stream_key: last_id}, block=30000, count=1)  # 30 sec timeout
                    
                    if response:
                        # Process real updates
                        for stream_name, messages in response:
                            for msg_id, msg_data in messages:
                                last_id = msg_id
                                
                                # Send updated queue data immediately
                                updated_queue_data = await get_current_queue_data(branch_id, queue_key)
                                yield f"data: {json.dumps(updated_queue_data)}\n\n"
                    else:
                        # Send single keepalive ping only when no updates (every 30 seconds)
                        yield f": heartbeat\n\n"
                        
                except Exception as e:
                    # Only log errors, don't send them to client
                    print(f"SSE Error: {e}")
                    await asyncio.sleep(5)  # Wait before retrying

        except asyncio.CancelledError:
            # Client disconnected cleanly
            return
        except Exception as e:
            # Send final error and close
            yield f"data: {json.dumps({'error': 'Connection lost'})}\n\n"

    return EventSourceResponse(
        event_generator(),
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "Content-Type": "text/event-stream",
            "Access-Control-Allow-Origin": "*"
        }
    )

async def get_current_queue_data(branch_id: str, queue_key: str):
    """Helper function to get current queue data"""
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

    return {
        "branch_id": branch_id,
        "queue": queue_data,
        "timestamp": datetime.utcnow().isoformat()
    }

# Create database tables
db_models.Base.metadata.create_all(bind=engine)