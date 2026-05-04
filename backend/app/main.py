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
# Force reload for updated medical services and fixed schema with service_type
import signal
import sys
import os
from dotenv import load_dotenv
import pathlib

# Load environment variables from the correct path
env_path = pathlib.Path(__file__).parent.parent / '.env'
load_dotenv(env_path)

# Debug: Print if key is loaded
print(f"GROQ_API_KEY loaded: {'Yes' if os.getenv('GROQ_API_KEY') else 'No'}")
if os.getenv('GROQ_API_KEY'):
    print(f"Key starts with: {os.getenv('GROQ_API_KEY')[:10]}...")

# Import AI agent routes
from app.ai_routes import router as ai_router

app = FastAPI(
    title="QTrack API",
    description="AI-Powered Hospital Queue Management System",
    version="2.0.0"
)

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
    requested_service = (request.service_type or "").strip().lower()
    if not requested_service or requested_service == "general":
        requested_service = (request.branch_id or "general").strip().lower()

    # Store in service-specific queue instead of branch-specific
    queue_key = f"queue:{requested_service}"
    user_key = f"user:{user_id}"

    # 1. Push to Redis
    await r.rpush(queue_key, user_id)
    await r.hset(user_key, mapping={
        "name": request.name,
        "phone": request.phone,
        "branch_id": request.branch_id,
        "service_type": requested_service,
        "status": "waiting",
        "joined_at": datetime.utcnow().isoformat()
    })

    # 2. Publish update to Redis Stream (use service-specific stream)
    stream_key = f"queue_stream:{requested_service}"
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

@app.get("/live-queue/{service_type}")
async def live_queue(service_type: str):
    # Check both original case and lowercase for backward compatibility
    queue_key_original = f"queue:{service_type}"
    queue_key_lower = f"queue:{service_type.lower()}"
    
    # Get queue from both possible locations
    queue_original = await r.lrange(queue_key_original, 0, -1) if service_type != service_type.lower() else []
    queue_lower = await r.lrange(queue_key_lower, 0, -1)
    
    # Combine queues (prioritize lowercase as it's our new standard)
    all_queue_ids = list(queue_lower) + [uid for uid in queue_original if uid not in queue_lower]
    
    if not all_queue_ids:
        return {
            "service_type": service_type,
            "message": "No tokens in queue"
        }

    enriched_queue = []

    for user_id in all_queue_ids:
        user_key = f"user:{user_id}"
        user_data = await r.hgetall(user_key)
        if user_data:  # Only add if user data exists
            enriched_queue.append({
                "user_id": user_id,
                "name": user_data.get("name", "Unknown"),
                "service_type": user_data.get("service_type", service_type.lower()),
                "branch_id": user_data.get("branch_id", "main"),
                "joined_at": user_data.get("joined_at", "Unknown"),
                "status": user_data.get("status", "waiting")
            })

    return {
        "service_type": service_type,  # Return original case for frontend compatibility
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
    service_type = (user_data.get("service_type") or "").strip().lower()
    
    if not branch_id:
        raise HTTPException(status_code=400, detail="Branch ID not found for user")

    # Update status
    await r.hset(user_key, "status", new_status)

    # Publish update to all compatible stream keys so connected SSE clients receive updates.
    stream_keys = set()
    if branch_id:
        stream_keys.add(f"queue_stream:{branch_id}")
        stream_keys.add(f"queue_stream:{branch_id.lower()}")
    if service_type:
        stream_keys.add(f"queue_stream:{service_type}")

    event_payload = {
        "event": "status_update",
        "user_id": user_id,
        "new_status": new_status,
        "name": user_data.get("name", "Unknown"),
        "timestamp": datetime.utcnow().isoformat()
    }
    for stream_key in stream_keys:
        await r.xadd(stream_key, event_payload)

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
    user_key = f"user:{user_id}"

    # Get user data before removal for the stream event
    user_data = await r.hgetall(user_key)
    if not user_data:
        raise HTTPException(status_code=404, detail=f"{user_id} not found in queue")

    user_name = user_data.get("name", "Unknown")
    service_type = (user_data.get("service_type") or "").strip().lower()

    queue_keys = {f"queue:{branch_id}", f"queue:{branch_id.lower()}"}
    if service_type:
        queue_keys.add(f"queue:{service_type}")

    removed_count = 0
    for queue_key in queue_keys:
        removed_count += await r.lrem(queue_key, 0, user_id)  # Remove all occurrences of user_id

    if removed_count == 0:
        raise HTTPException(status_code=404, detail=f"{user_id} not found in queue")

    # Clean up user data hash from Redis
    await r.delete(user_key)

    # Publish update to all compatible stream keys so subscribed clients update immediately.
    stream_keys = {f"queue_stream:{branch_id}", f"queue_stream:{branch_id.lower()}"}
    if service_type:
        stream_keys.add(f"queue_stream:{service_type}")

    event_payload = {
        "event": "remove_from_queue",
        "user_id": user_id,
        "name": user_name,
        "action": "removed",
        "timestamp": datetime.utcnow().isoformat()
    }
    for stream_key in stream_keys:
        await r.xadd(stream_key, event_payload)

    return {
        "message": f"{user_id} removed from queue",
        "removed_count": removed_count
    }

@app.get("/live-queue-stream/{service_type}")
async def live_queue_stream(service_type: str):
    # Use lowercase for consistent storage, support both cases like the main endpoint
    service_type_lower = service_type.lower()
    queue_key_lower = f"queue:{service_type_lower}"
    stream_key_lower = f"queue_stream:{service_type_lower}"
    
    # Also check for uppercase streams for backward compatibility
    queue_key_original = f"queue:{service_type}" 
    stream_key_original = f"queue_stream:{service_type}"

    async def event_generator():
        try:
            # Send initial payload using the same logic as live_queue endpoint
            # Check both original case and lowercase for backward compatibility
            queue_key_original = f"queue:{service_type}"
            queue_key_lower = f"queue:{service_type.lower()}"
            
            # Get queue from both possible locations
            queue_original = await r.lrange(queue_key_original, 0, -1) if service_type != service_type.lower() else []
            queue_lower = await r.lrange(queue_key_lower, 0, -1)
            
            # Combine queues (prioritize lowercase as it's our new standard)
            all_queue_ids = list(queue_lower) + [uid for uid in queue_original if uid not in queue_lower]
            
            enriched_queue = []
            for user_id in all_queue_ids:
                user_key = f"user:{user_id}"
                user_data = await r.hgetall(user_key)
                if user_data:  # Only add if user data exists
                    enriched_queue.append({
                        "user_id": user_id,
                        "name": user_data.get("name", "Unknown"),
                        "service_type": user_data.get("service_type", service_type.lower()),
                        "branch_id": user_data.get("branch_id", "main"),
                        "joined_at": user_data.get("joined_at", "Unknown"),
                        "status": user_data.get("status", "waiting")
                    })
            
            initial_queue_data = {
                "service_type": service_type,
                "queue": enriched_queue,
                "timestamp": datetime.utcnow().isoformat()
            }
            yield f"data: {json.dumps(initial_queue_data)}\n\n"

            # Listen to both stream keys for updates
            last_id_lower = '$'
            last_id_original = '$'

            while True:
                try:
                    # Read from both streams (prioritize lowercase as new standard)
                    streams_to_check = {}
                    if service_type != service_type.lower():
                        streams_to_check[stream_key_original] = last_id_original
                    streams_to_check[stream_key_lower] = last_id_lower
                    
                    response = await r.xread(streams_to_check, block=30000, count=1)  # 30 sec timeout
                    
                    if response:
                        # Process real updates
                        for stream_name, messages in response:
                            for msg_id, msg_data in messages:
                                # Update appropriate last_id
                                if stream_name == stream_key_lower:
                                    last_id_lower = msg_id
                                else:
                                    last_id_original = msg_id
                                
                                # Send updated queue data immediately - reuse same logic
                                queue_original_update = await r.lrange(queue_key_original, 0, -1) if service_type != service_type.lower() else []
                                queue_lower_update = await r.lrange(queue_key_lower, 0, -1)
                                all_queue_ids_update = list(queue_lower_update) + [uid for uid in queue_original_update if uid not in queue_lower_update]
                                
                                enriched_queue_update = []
                                for user_id in all_queue_ids_update:
                                    user_key = f"user:{user_id}"
                                    user_data = await r.hgetall(user_key)
                                    if user_data:
                                        enriched_queue_update.append({
                                            "user_id": user_id,
                                            "name": user_data.get("name", "Unknown"),
                                            "service_type": user_data.get("service_type", service_type.lower()),
                                            "branch_id": user_data.get("branch_id", "main"),
                                            "joined_at": user_data.get("joined_at", "Unknown"),
                                            "status": user_data.get("status", "waiting")
                                        })
                                
                                updated_queue_data = {
                                    "service_type": service_type,
                                    "queue": enriched_queue_update,
                                    "timestamp": datetime.utcnow().isoformat()
                                }
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
                "service_type": user_data.get("service_type", "general"),
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

# Include AI agent routes
app.include_router(ai_router, prefix="/ai", tags=["AI Agent"])

@app.get("/")
async def root():
    return {
        "message": "QTrack API v2.0 - AI-Powered Hospital Queue Management", 
        "features": [
            "Queue Management",
            "Real-time Updates", 
            "AI Conversational Agent",
            "WhatsApp Integration"
        ],
        "endpoints": {
            "queue": "/join-queue, /live-queue/{branch_id}",
            "ai_agent": "/ai/chat, /ai/whatsapp/webhook",
            "health": "/health-check, /ai/health"
        }
    }